from modules import ai_description
from modules import google_drive
from modules import utils
import pandas as pd
import yaml
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os, json

# ✅ Load environment variables
load_dotenv()

# ✅ Load configuration from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Retrieve folder IDs from config
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_keywords_from_drive():
    """Fetches keywords from the latest document in Google Drive."""
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "text/plain")
    if doc_file:
        doc_path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(doc_path) if doc_path else []
    return []

def upload_to_google_sheets(df, pdf_filename, pdf_folder_id):
    """Uploads DataFrame to Google Sheet named after the PDF file."""
    sheet_name = pdf_filename.replace(".pdf", "")
    
    # ====== AUTHENTICATION ======
    try:
        service_account_json = os.environ["GOOGLE_CREDENTIALS"]
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        print("✅ Credentials validated")
    except Exception as e:
        print(f"❌ FATAL: Credential failure: {e}")
        return

    # ====== CLIENT INITIALIZATION ======
    try:
        client = gspread.authorize(creds)
        print("✅ Sheets client initialized")
    except Exception as e:
        print(f"❌ FATAL: Client authorization failed: {e}")
        return

    # ====== SHEET OPERATIONS ======
    try:
        sheet = client.open(sheet_name)
        print(f"✅ Found existing sheet: {sheet_name}")
    except gspread.SpreadsheetNotFound:
        print(f"🛑 Creating new sheet: {sheet_name}")
        sheet = client.create(sheet_name)

    # ====== MOVE TO FOLDER ======
    try:
        drive_service = build("drive", "v3", credentials=creds)
        drive_service.files().update(
            fileId=sheet.id,
            addParents=pdf_folder_id,
            removeParents="root",
            fields="id, parents"
        ).execute()
        print(f"✅ Sheet moved to folder: {pdf_folder_id}")
    except Exception as e:
        print(f"❌ Failed to move sheet: {e}")

    # ====== UPDATE WORKSHEET ======
    try:
        worksheet = sheet.get_worksheet(0) or sheet.add_worksheet(title="Sheet1", rows="1000", cols="10")
        data = [df.columns.tolist()] + df.values.tolist()
        worksheet.clear()
        worksheet.update(values=data, range_name="A1")
        print(f"✅ Data uploaded to: {sheet.url}")
    except Exception as e:
        print(f"❌ Failed to update worksheet: {e}")

def process_pdf():
    """Extracts data from the latest PDFs, generates descriptions, and uploads to Google Sheets."""
    pdf_files = google_drive.list_all_files_in_drive(PDF_FOLDER_ID, "application/pdf")
    if not pdf_files:
        print("❌ No PDFs found in Google Drive folder")
        return

    for pdf_file in pdf_files:
        pdf_filename = pdf_file["name"]
        pdf_path = google_drive.download_file_from_drive(pdf_file["id"], pdf_filename)

        if not pdf_path:
            print(f"❌ Failed to download {pdf_filename}")
            continue

        extracted_data = google_drive.extract_text_and_images_from_pdf(pdf_path)
        keywords = get_keywords_from_drive()

        processed_data = [
            ai_description.generate_description(entry["style_number"], entry["images"], keywords)
            for entry in extracted_data
        ]

        if not processed_data:
            print(f"❌ No processed data for {pdf_filename}")
            continue

        df = pd.DataFrame(processed_data)

        # Validate required columns
        expected_columns = [
            "Style Number", "Product Title", "Product Description", "Tags", 
            "Product Category", "Product Type", "Option2 Value", "Keywords"
        ]
        missing_columns = [col for col in expected_columns if col not in df.columns]
        if missing_columns:
            print(f"❌ Missing columns in DataFrame from {pdf_filename}: {missing_columns}")
            continue

        # Add character count columns
        df["Product Name Character Count"] = df["Product Title"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Description Character Count"] = df["Product Description"].apply(lambda x: len(x) if pd.notnull(x) else 0)

        # Reorder columns
        column_order = [
            "Style Number", 
            "Product Name Character Count", 
            "Product Title", 
            "Description Character Count", 
            "Product Description", 
            "Tags", 
            "Product Category", 
            "Product Type", 
            "Option2 Value", 
            "Keywords"
        ]
        df = df[column_order]

        upload_to_google_sheets(df, pdf_filename, PDF_FOLDER_ID)
        print(f"✅ Finished processing {pdf_filename}")

if __name__ == "__main__":
    process_pdf()

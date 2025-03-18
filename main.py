from modules import ai_description
from modules import google_drive
from modules import utils
import pandas as pd
import yaml
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
import googleapiclient
# ✅ Load environment variables FIRST
from dotenv import load_dotenv
import os, json

load_dotenv()  # Loads .env before any other imports

# ✅ Load Configuration from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Retrieve Folder IDs from Config
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

print(f"DEBUG: Creds type: {type(creds)}")  # Should show <class 'google.oauth2.service_account.Credentials'>
print(f"DEBUG: Client type: {type(client)}")  # Should show <class 'gspread.client.Client'>

def get_keywords_from_drive():
    """Fetches keywords from the latest document in Google Drive."""
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "text/plain")
    
    if doc_file:
        doc_path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(doc_path) if doc_path else []
    
    return []

def upload_to_google_sheets(df, pdf_filename, pdf_folder_id):
    sheet_name = pdf_filename.replace(".pdf", "")
    
    # ====== AUTHENTICATION ======
    try:
        # Validate credentials FIRST
        service_account_json = os.environ["GOOGLE_CREDENTIALS"]
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        print("✅ Credentials validated")
    except Exception as e:
        print(f"❌ FATAL: Credential failure: {e}")
        return

    # ====== CLIENT INITIALIZATION ======
    try:
        client = gspread.authorize(creds)  # <-- THIS MUST SUCCEED
        print("✅ Sheets client initialized")
    except Exception as e:
        print(f"❌ FATAL: Client authorization failed: {e}")
        return

    # ====== SHEET OPERATIONS ======
    try:
        sheet = client.open(sheet_name)  # <-- NOW SAFE TO USE CLIENT
        print(f"✅ Found existing sheet: {sheet_name}")
    except gspread.SpreadsheetNotFound:
        print(f"🛑 Creating new sheet: {sheet_name}")
        sheet = client.create(sheet_name)
    
    # Rest of your folder moving and data upload code...

def process_pdf():
    """Extracts data from the latest PDF, generates descriptions, and uploads both files to Google Sheets."""
    # Initialize variables first
    extracted_data = []
    processed_data = []
    
    pdf_file = google_drive.list_files_in_drive(PDF_FOLDER_ID, "application/pdf")

    if pdf_file:
        pdf_filename = pdf_file["name"]  # Get the actual name of the PDF
        pdf_path = google_drive.download_file_from_drive(pdf_file["id"], pdf_filename)
        
        if pdf_path:  # Check if download succeeded
            extracted_data = google_drive.extract_text_and_images_from_pdf(pdf_path)
        else:
            print("❌ Failed to download PDF file")
            return

        # ✅ Fetch Keywords from Drive
        keywords = get_keywords_from_drive()

        # ✅ Generate descriptions (AFTER extracted_data is populated)
        processed_data = [
            ai_description.generate_description(entry["style_number"], entry["images"], keywords) 
            for entry in extracted_data
        ]

        # ✅ Debug: Print the structure of the first item
        if processed_data:
            print("Sample processed entry:", processed_data[0])

        # ✅ Convert to DataFrame
        df = pd.DataFrame(processed_data)

        # ✅ Ensure proper column order
        expected_columns = [
            "Style Number", "Product Title", "Product Description", "Tags", 
            "Product Category", "Product Type", "Option2 Value", "Keywords"
        ]
        
        # Add column validation
        missing_columns = [col for col in expected_columns if col not in df.columns]
        if missing_columns:
            print(f"❌ Missing columns in DataFrame: {missing_columns}")
            return

        df = df[expected_columns]

        # ✅ Upload the data to a Google Sheet
        upload_to_google_sheets(df, pdf_filename, PDF_FOLDER_ID)
        print(f"✅ Process completed. Files in folder: {PDF_FOLDER_ID}")
    else:
        print("❌ No PDF found in Google Drive folder")

if __name__ == "__main__":
    process_pdf()

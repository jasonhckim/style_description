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
TEMPLATE_SHEET_ID = config["template_sheet_id"]  # <-- New line

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_keywords_from_drive():
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "text/plain")
    if doc_file:
        doc_path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(doc_path) if doc_path else []
    return []

def upload_to_google_sheets(df, pdf_filename, pdf_folder_id):
    sheet_name = pdf_filename.replace(".pdf", "")

    try:
        service_account_json = os.environ["GOOGLE_CREDENTIALS"]
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES,
            subject="jason@hyfve.com"
        )
        print("✅ Credentials validated")
    except Exception as e:
        print(f"❌ FATAL: Credential failure: {e}")
        return

    try:
        drive_service = build("drive", "v3", credentials=creds)
        copied_file = drive_service.files().copy(
            fileId=TEMPLATE_SHEET_ID,
            body={"name": sheet_name, "parents": [pdf_folder_id]}
        ).execute()
        print("✅ Sheet copied from template")
    except Exception as e:
        print(f"❌ Failed to copy template: {e}")
        return

    try:
        client = gspread.authorize(creds)
        sheet = client.open_by_key(copied_file["id"])
        print(f"✅ Sheet opened: {sheet_name}")
    except Exception as e:
        print(f"❌ Failed to open new sheet: {e}")
        return

    try:
        worksheet = sheet.get_worksheet(0)
        worksheet.clear()
        worksheet.update(values=[df.columns.tolist()] + df.values.tolist())
        print(f"✅ Data uploaded to: {sheet.url}")
    except Exception as e:
        print(f"❌ Failed to update worksheet: {e}")

    designer_cols = [
        "Style Number",
        "Product Name Character Count",
        "Product Title",
        "Description Character Count",
        "Product Description"
    ]
    designer_df = df[designer_cols]
    try:
        d_ws = sheet.worksheet("Designer")
    except:
        d_ws = sheet.add_worksheet(title="Designer", rows="1000", cols="10")

    d_ws.clear()
    d_ws.update(values=[designer_df.columns.tolist()] + designer_df.values.tolist())
    print("✅ Designer sheet synced")

def process_pdf():
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
        drive_service = google_drive.get_drive_service()

        processed_data = []

        for entry in extracted_data:
            if not entry["images"]:
                print(f"⚠️ Skipping page {entry['page']} — no images found")
                continue

            try:
                image_url = entry["images"][0]["image_url"]
                result = ai_description.generate_description(entry["style_number"], [image_url], keywords, entry["text"])
                processed_data.append(result)
            except Exception as e:
                print(f"❌ Error processing style {entry['style_number']}: {e}")
                continue

        if not processed_data:
            print(f"❌ No processed data for {pdf_filename}")
            continue

        df = pd.DataFrame(processed_data)

        expected_columns = [
            "Style Number", "Product Title", "Product Description", "Tags", 
            "Product Category", "Product Type", "Option2 Value", "Keywords"
        ]
        missing_columns = [col for col in expected_columns if col not in df.columns]
        if missing_columns:
            print(f"❌ Missing columns in DataFrame from {pdf_filename}: {missing_columns}")
            continue

        df["Product Name Character Count"] = df["Product Title"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Description Character Count"] = df["Product Description"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Edit Product Title"] = ""
        df["Edit Product Description"] = ""

        column_order = [
            "Style Number", 
            "Product Name Character Count", 
            "Product Title",
            "Edit Product Title",
            "Description Character Count", 
            "Product Description",
            "Edit Product Description",
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

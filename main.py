# main.py
from modules import ai_description
from modules import google_drive
from modules import utils
import pandas as pd
import yaml
import gspread
from google.oauth2 import service_account
import os
import json
from dotenv import load_dotenv
from modules.attribute_writer import write_marketplace_attribute_sheet

# ✅ Load environment variables
load_dotenv()

# ✅ Load configuration
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

PDF_FOLDER_ID  = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID  = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID  = config["drive_folder_ids"]["csv"]
TEMPLATE_ID    = config["template_sheet_id"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_keywords_from_drive():
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "text/plain")
    if doc_file:
        path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(path) if path else []
    return []

def upload_to_google_sheets(df, pdf_filename, folder_id):
    # (auth + copy template + write sheets — unchanged)
    ...

def process_pdf():
    pdf_files = google_drive.list_all_files_in_drive(PDF_FOLDER_ID, "application/pdf")
    if not pdf_files:
        print("❌ No PDFs found")
        return

    for pdf in pdf_files:
        name = pdf["name"]
        path = google_drive.download_file_from_drive(pdf["id"], name)
        if not path:
            print(f"❌ Failed to download {name}")
            continue

        data = google_drive.extract_text_and_images_from_pdf(path)
        keywords = get_keywords_from_drive()
        processed = []

        for entry in data:
            if not entry["images"]:
                print(f"⚠️ Skipping page {entry['page']}: no images")
                continue
            try:
                url    = entry["images"][0]["image_url"]
                result = ai_description.generate_description(
                    entry["style_number"], [url], keywords, entry["text"]
                )
                if result["Product Title"] == "N/A":
                    print(f"⚠️ Skipping {entry['style_number']}: AI failed")
                    continue
                processed.append(result)
                print(f"✅ Processed style {entry['style_number']}")
            except Exception as e:
                print(f"❌ Error on {entry['style_number']}: {e}")
                continue

        if not processed:
            print(f"❌ No processed data for {name}")
            continue

        df = pd.DataFrame(processed)

        expected_columns = [
            "Style Number","Product Title","Product Description","Tags",
            "Product Category","Product Type","Option2 Value","Keywords",
            "Fabric","Silhouette","Length","Neckline","Sleeve"
        ]
        # ✅ Guarantee missing columns are filled with "N/A"
        for col in expected_columns:
            if col not in df.columns:
                df[col] = "N/A"

        df["Product Name Character Count"]    = df["Product Title"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Description Character Count"]     = df["Product Description"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Edit Product Title"]              = ""
        df["Edit Product Description"]        = ""

        column_order = [
            "Style Number","Product Name Character Count","Product Title",
            "Edit Product Title","Description Character Count",
            "Product Description","Edit Product Description","Tags",
            "Product Category","Product Type","Option2 Value","Keywords",
            "Fabric","Silhouette","Length","Neckline","Sleeve"
        ]
        df = df[column_order]

        # (upload + marketplace sheet write)
        upload_to_google_sheets(df, name, PDF_FOLDER_ID)
        write_marketplace_attribute_sheet(df, name, service_account.Credentials.from_service_account_file(os.environ["GOOGLE_CREDENTIALS"]), PDF_FOLDER_ID)

        print(f"✅ Finished processing {name}")

if __name__ == "__main__":
    process_pdf()

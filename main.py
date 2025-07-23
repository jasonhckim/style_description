# main.py
from modules import ai_description, google_drive, utils
import pandas as pd
import yaml
import gspread
from google.oauth2 import service_account
import os
import json
from dotenv import load_dotenv
from modules.attribute_writer import write_marketplace_attribute_sheet

# ─── Load env + config ────────────────────────────────────────────────────────
load_dotenv()
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]
TEMPLATE_ID   = config["template_sheet_id"]
SOURCE_APPS_SCRIPT_ID = config.get("apps_script_id")  # ✅ Add this key to config.yaml

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects"
]

def get_service_credentials():
    """
    Build a delegated service-account credential for Drive & Sheets
    from JSON stored in environment variable (GitHub Secret).
    """
    return service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDENTIALS"]),
        scopes=SCOPES,
        subject="jason@hyfve.com"
    )

def get_keywords_from_drive():
    """
    Download keywords.txt from your 'doc' folder and extract keywords.
    """
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "text/plain")
    if doc_file:
        path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(path) if path else []
    return []

def upload_to_google_sheets(df: pd.DataFrame, pdf_filename: str, folder_id: str):
    """
    1) Copy your template sheet into `folder_id`
    2) Write the main DataFrame into the first tab
    3) Write the designer-specific columns into a 'Designer' tab
    4) Attach Apps Script to the newly created Sheet
    """
    creds = get_service_credentials()
    client = gspread.authorize(creds)

    # ✅ Clean DataFrame to avoid gspread APIError (flatten lists, handle None)
    df = df.applymap(lambda x: ", ".join(x) if isinstance(x, list) else ("" if x is None else str(x)))

    sheet_title = pdf_filename.replace(".pdf", "")
    print(f"🛠️ Copying sheet from template as '{sheet_title}'…")

    # ✅ Create the new Sheet from template
    sheet_id = google_drive.copy_sheet_from_template(TEMPLATE_ID, sheet_title, folder_id)
    sheet = client.open_by_key(sheet_id)
    print(f"✅ Created new sheet: {sheet.url}")

    # — Main tab —
    ws_main = sheet.get_worksheet(0)
    ws_main.clear()
    ws_main.update(values=[df.columns.tolist()] + df.values.tolist())
    print("✅ Main sheet updated")

    # — Designer tab —
    designer_cols = [
        "Style Number",
        "Product Name Character Count",
        "Product Title",
        "Description Character Count",
        "Product Description"
    ]
    designer_df = df[designer_cols]
    try:
        ws_designer = sheet.worksheet("Designer")
    except gspread.WorksheetNotFound:
        ws_designer = sheet.add_worksheet(
            title="Designer",
            rows=str(len(designer_df) + 5),
            cols=str(len(designer_cols))
        )
    ws_designer.clear()
    ws_designer.update(values=[designer_df.columns.tolist()] + designer_df.values.tolist())
    print("✅ Designer sheet synced")

    # ✅ Attach Apps Script to the new Sheet
    if SOURCE_APPS_SCRIPT_ID:
        try:
            google_drive.attach_apps_script_to_sheet(sheet_id, SOURCE_APPS_SCRIPT_ID)
            print(f"✅ Apps Script successfully attached to: {sheet.url}")
        except Exception as e:
            print(f"❌ Failed to attach Apps Script: {e}")

    return sheet_id

def process_pdf():
    """
    1) List all PDFs in your input folder
    2) Download each, extract text+images
    3) Call AI to generate title/description/tags
    4) Build final DataFrame, fill missing columns with "N/A"
    5) Push to Sheets, attach Apps Script & marketplace-attribute writer
    """
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

        extracted = google_drive.extract_text_and_images_from_pdf(path)
        keywords  = get_keywords_from_drive()
        processed = []

        for entry in extracted:
            if not entry["images"]:
                print(f"⚠️ Skipping page {entry['page']}: no images")
                continue
            try:
                url = entry["images"][0]["image_url"]
                res = ai_description.generate_description(
                    style_number=entry["style_number"],
                    images=[url],
                    keywords=keywords,
                    text=entry["text"],
                    product_title=entry.get("title", "")  # ✅ Pass title if extracted, else ""
                )

                if res["Product Title"] == "N/A":
                    print(f"⚠️ Skipping {entry['style_number']}: AI returned N/A")
                    continue
                processed.append(res)
                print(f"✅ Processed style {entry['style_number']}")
            except Exception as e:
                print(f"❌ Error on {entry['style_number']}: {e}")
                continue

        if not processed:
            print(f"❌ No processed data for {name}")
            continue

        df = pd.DataFrame(processed)

        # Ensure all expected columns exist
        expected = [
            "Style Number","Product Title","Product Description","Tags",
            "Product Category","Product Type","Option2 Value","Keywords",
            "Fabric","Silhouette","Length","Neckline","Sleeve"
        ]
        for col in expected:
            if col not in df.columns:
                df[col] = "N/A"

        # Add character‐count & edit columns
        df["Product Name Character Count"] = df["Product Title"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Description Character Count"]  = df["Product Description"].apply(lambda x: len(x) if pd.notnull(x) else 0)
        df["Edit Product Title"]           = ""
        df["Edit Product Description"]     = ""

        # Reorder
        column_order = [
            "Style Number","Product Name Character Count","Product Title",
            "Edit Product Title","Description Character Count",
            "Product Description","Edit Product Description","Tags",
            "Product Category","Product Type","Option2 Value","Keywords",
            "Fabric","Silhouette","Length","Neckline","Sleeve"
        ]
        df = df[column_order]

        # ✅ Upload to Sheets + attach Apps Script
        sheet_id = upload_to_google_sheets(df, name, PDF_FOLDER_ID)

        # ✅ Write marketplace attributes
        creds = get_service_credentials()
        write_marketplace_attribute_sheet(df, name, creds, PDF_FOLDER_ID)

        print(f"✅ Finished processing {name} → {sheet_id}")

if __name__ == "__main__":
    process_pdf()

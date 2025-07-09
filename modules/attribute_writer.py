import pandas as pd
import re
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

def download_marketplace_attributes(creds, file_name="Marketplace_attributes.xlsx"):
    # Find file in Drive folder
    drive = build("drive", "v3", credentials=creds)
    folder_id = "1YrYWjpWUmGN-ISJK0TrO66SirBsLeMcH"
    query = f"'{folder_id}' in parents and name='{file_name}' and trashed = false"
    results = drive.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if not files:
        raise FileNotFoundError("Marketplace_attributes.xlsx not found in Drive folder")

    file_id = files[0]["id"]
    request = drive.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    return pd.read_excel(fh, sheet_name=None)

def extract_allowed_columns(row):
    allowed = {}
    for col, val in row.items():
        if pd.isna(val):
            continue
        match = re.search(r"\\((\\d)\\)", str(val))
        allowed_count = int(match.group(1)) if match else 1
        allowed[col] = allowed_count
    return allowed

def select_values_for_category(df, category, allowed_columns):
    values = {}
    for col, max_count in allowed_columns.items():
        if col not in df.columns:
            continue
        candidates = df[col].dropna().unique().tolist()
        selected = candidates[:max_count]  # TODO: Improve selection logic
        values[col] = ", ".join(selected)
    return values

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    from gspread import authorize
    from google.auth.transport.requests import Request
    import gspread

    marketplace_data = download_marketplace_attributes(creds)

    client = authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_title = pdf_filename.replace(".pdf", " marketplace attribute")

    # Create new blank spreadsheet
    spreadsheet = client.create(sheet_title)
    spreadsheet_id = spreadsheet.id
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

    for tab_name in ["faire", "fgo"]:
        tab_df = marketplace_data[tab_name]
        header_row = tab_df.iloc[0]
        allowed_columns = extract_allowed_columns(header_row)
        data_start_row = 1

        output_rows = []
        for _, row in df.iterrows():
            product_type = row.get("Product Type", "N/A")
            product_category = row.get("Product Category", product_type)
            selected = select_values_for_category(tab_df.iloc[data_start_row:], product_category, allowed_columns)
            selected["Style Number"] = row.get("Style Number")
            output_rows.append(selected)

        # Ensure all columns are present for consistency
        all_columns = ["Style Number"] + list(allowed_columns.keys())
        final_df = pd.DataFrame(output_rows)[all_columns]

        try:
            sheet = spreadsheet.worksheet(tab_name)
        except:
            sheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="20")

        sheet.clear()
        sheet.update([final_df.columns.tolist()] + final_df.values.tolist())

    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

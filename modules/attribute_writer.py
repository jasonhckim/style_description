import pandas as pd
import numpy as np
import re
import gspread
from gspread_dataframe import get_as_dataframe
from googleapiclient.discovery import build

def download_marketplace_attributes(creds):
    sheet_id = "12lJYw9TL97djaPKjF3qKp-Bio-5sQmPbsprEvD4mERA"
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)

    data = {}
    for tab in ["faire", "fgo"]:
        worksheet = sheet.worksheet(tab)
        df = get_as_dataframe(worksheet, evaluate_formulas=True, header=0)
        df.columns = df.columns.map(lambda c: "" if pd.isna(c) else str(c).strip())
        df = df.dropna(how="all")
        data[tab] = df.reset_index(drop=True)

    return data

def parse_selection_limit(header):
    match = re.search(r"\((\d+)\)", header)
    return int(match.group(1)) if match else 1

def normalize_text(text):
    return re.sub(r"[^\w\s]", "", text).lower()

def select_matching_values(text_blob, attr_values, limit):
    matches = []
    text_blob = normalize_text(text_blob)
    for val in attr_values:
        val_norm = normalize_text(str(val))
        if val_norm in text_blob:
            matches.append(val.strip())
        if len(matches) >= limit:
            break
    return matches

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    drive = build("drive", "v3", credentials=creds)
    client = gspread.authorize(creds)

    marketplace_data = download_marketplace_attributes(creds)
    sheet_title = pdf_filename.replace(".pdf", " marketplace attribute")
    spreadsheet = client.create(sheet_title)
    drive.files().update(fileId=spreadsheet.id, addParents=folder_id, removeParents="root").execute()

    for tab_name, tab_df in marketplace_data.items():
        headers = tab_df.columns.tolist()
        output_rows = []

        for _, row in df.iterrows():
            style_number = row.get("Style Number", "")
            product_type = (row.get("Product Type") or row.get("Product Category") or "").lower()
            blob = " ".join([str(row.get(k, "")) for k in ["product_title", "description", "hashtags", "key_attribute"]])

            attr_row = {"Style Number": style_number}
            for col in headers:
                col_clean = col.strip()
                if not col_clean:
                    continue

                # Detect scoped attribute like 'TOP: Sleeve Length (1)'
                scoped = col_clean.split(":")
                if len(scoped) == 2:
                    scope, attr_name = scoped[0].strip().lower(), scoped[1].strip()
                    if scope not in product_type:
                        continue
                else:
                    attr_name = col_clean

                values = tab_df[col].dropna().tolist()[1:]  # Skip row 1
                limit = parse_selection_limit(attr_name)
                matched = select_matching_values(blob, values, limit)
                attr_row[col_clean] = ", ".join(matched)

            output_rows.append(attr_row)

        final_df = pd.DataFrame(output_rows)

        all_columns = ["Style Number"] + [col for col in headers if col.strip()]
        for col in all_columns:
            if col not in final_df.columns:
                final_df[col] = ""

        final_df = final_df[all_columns]
        final_df = final_df.replace([np.nan, float("inf"), float("-inf")], "").fillna("").astype(str)

        try:
            sheet = spreadsheet.worksheet(tab_name)
        except:
            sheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="30")

        sheet.clear()
        sheet.update([final_df.columns.tolist()] + final_df.values.tolist())

    print(f"✅ Marketplace sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")
    return spreadsheet.id

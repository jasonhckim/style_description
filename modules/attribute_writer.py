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
        data[tab] = df

    return data


def parse_selection_limit(col_name):
    match = re.search(r"\\((\\d+)\\)", col_name)
    return int(match.group(1)) if match else 1


def extract_relevant_columns(df, product_type):
    matched_columns = []
    for col in df.columns:
        if pd.isna(col):
            continue
        if ":" in col:
            prefix, attr_name = map(str.strip, col.split(":", 1))
            if prefix.lower() == product_type.lower() or prefix.lower() == "_global":
                matched_columns.append((col, attr_name.strip()))
    return matched_columns


def select_attributes_from_sheet(df, relevant_columns):
    result = {}
    for full_col, attr_name in relevant_columns:
        try:
            col_series = df[full_col].dropna()
            limit = parse_selection_limit(attr_name)
            values = col_series.unique().tolist()
            selected = values[:limit]
            result[attr_name] = ", ".join(map(str, selected))
        except Exception as e:
            print(f"⚠️ Error processing column '{full_col}': {e}")
            result[attr_name] = ""
    return result


def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    marketplace_data = download_marketplace_attributes(creds)
    client = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_title = pdf_filename.replace(".pdf", " marketplace attribute")
    spreadsheet = client.create(sheet_title)
    spreadsheet_id = spreadsheet.id
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

    for tab_name, tab_df in marketplace_data.items():
        output_rows = []

        for _, row in df.iterrows():
            style_number = row.get("Style Number", "")
            product_type = row.get("Product Type", "") or row.get("Product Category", "")
            if not product_type:
                print(f"⚠️ Missing product_type for style {style_number}")
                continue

            relevant_columns = extract_relevant_columns(tab_df, product_type)
            attributes = select_attributes_from_sheet(tab_df, relevant_columns)
            attributes["Style Number"] = style_number
            output_rows.append(attributes)

        # Assemble DataFrame
        all_keys = ["Style Number"] + sorted(
            {attr for col in tab_df.columns if isinstance(col, str) and ":" in col
             for prefix, attr in [col.split(":", 1)] if prefix.strip().lower() in [product_type.lower(), "_global"]}
        )

        final_df = pd.DataFrame(output_rows)
        for key in all_keys:
            if key not in final_df.columns:
                final_df[key] = ""

        final_df = final_df[all_keys].replace([np.nan, float("inf"), float("-inf")], "").fillna("").astype(str)

        try:
            sheet = spreadsheet.worksheet(tab_name)
        except:
            sheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="50")

        sheet.clear()
        sheet.update([final_df.columns.tolist()] + final_df.values.tolist())

    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

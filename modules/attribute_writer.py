import pandas as pd
import re
import os
import numpy as np
from googleapiclient.discovery import build
from gspread_dataframe import get_as_dataframe
import gspread

def download_marketplace_attributes(creds):
    sheet_id = "12lJYw9TL97djaPKjF3qKp-Bio-5sQmPbsprEvD4mERA"
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    return {tab: get_as_dataframe(sheet.worksheet(tab), evaluate_formulas=True, header=1).fillna("") for tab in ["faire", "fgo"]}

def parse_selection_limit(attribute_name):
    match = re.search(r"\((\d)\)", attribute_name)
    return int(match.group(1)) if match else 1

def extract_category_attributes(df):
    # Recognize columns with prefixes like "DRESS:", "TOP:", etc.
    col_metadata = {}
    for col in df.columns:
        col_str = str(col).strip()
        if ':' in col_str:
            prefix, attr = col_str.split(':', 1)
            col_metadata[col] = {"prefix": prefix.strip().lower(), "attr": attr.strip()}
        else:
            col_metadata[col] = {"prefix": None, "attr": col_str.strip()}
    return col_metadata

def select_applicable_attributes(df, product_category, col_metadata):
    values = {}
    for col in df.columns:
        meta = col_metadata[col]
        if not meta["attr"]:
            continue

        # Include global columns or those with matching category prefix
        if meta["prefix"] is None or meta["prefix"] in product_category.lower():
            limit = parse_selection_limit(meta["attr"])
            col_series = df[col].dropna().astype(str).str.strip()
            unique_vals = col_series[col_series != ""].unique().tolist()
            selected = unique_vals[:limit]
            if selected:
                values[meta["attr"]] = ", ".join(selected)
    return values

def write_marketplace_attribute_sheet(description_df, pdf_filename, creds, folder_id):
    marketplace_data = download_marketplace_attributes(creds)
    drive = build("drive", "v3", credentials=creds)
    client = gspread.authorize(creds)

    sheet_title = pdf_filename.replace(".pdf", " marketplace attribute")
    spreadsheet = client.create(sheet_title)
    spreadsheet_id = spreadsheet.id
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

    for tab_name, tab_df in marketplace_data.items():
        col_metadata = extract_category_attributes(tab_df)
        output_rows = []

        for _, row in description_df.iterrows():
            style_number = row.get("Style Number", "")
            category = row.get("Product Category", "").strip().lower()
            selected_attrs = select_applicable_attributes(tab_df, category, col_metadata)
            selected_attrs["Style Number"] = style_number
            output_rows.append(selected_attrs)

        all_columns = ["Style Number"] + sorted({meta["attr"] for meta in col_metadata.values() if meta["attr"]})
        final_df = pd.DataFrame(output_rows)

        for col in all_columns:
            if col not in final_df.columns:
                final_df[col] = ""

        final_df = final_df[all_columns].replace([np.nan, float("inf"), float("-inf")], "").fillna("").astype(str)

        try:
            sheet = spreadsheet.worksheet(tab_name)
        except:
            sheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="30")

        sheet.clear()
        sheet.update([final_df.columns.tolist()] + final_df.values.tolist())

    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

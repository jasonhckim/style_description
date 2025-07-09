import pandas as pd
import re
import os
import numpy as np
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

def download_marketplace_attributes(creds):
    import gspread
    from gspread_dataframe import get_as_dataframe

    sheet_id = "12lJYw9TL97djaPKjF3qKp-Bio-5sQmPbsprEvD4mERA"
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)

    data = {}
    for tab in ["faire", "fgo"]:
        worksheet = sheet.worksheet(tab)
        df = get_as_dataframe(worksheet, evaluate_formulas=True, header=None)
        data[tab] = df

    return data

def extract_allowed_columns(product_row, attribute_row):
    category_to_columns = {}
    for col_idx, category in enumerate(product_row):
        if pd.isna(category):
            continue
        category = str(category).strip().title()
        attr = str(attribute_row[col_idx]).strip()
        if not category or not attr:
            continue
        if category not in category_to_columns:
            category_to_columns[category] = []
        category_to_columns[category].append((col_idx, attr))
    return category_to_columns

def parse_selection_limit(attribute_name):
    match = re.search(r"\((\d)\)", attribute_name)
    return int(match.group(1)) if match else 1

def select_values_for_category(df, col_indices):
    output_row = {}
    for col_idx, attr_name in col_indices:
        try:
            col_series = df.iloc[2:, col_idx]  # From row 3 onward
            if not isinstance(col_series, pd.Series):
                print(f"⚠️ Skipping non-Series column {col_idx}")
                continue
            col_series = col_series.dropna()
            limit = parse_selection_limit(attr_name)
            values = col_series.unique().tolist()
            selected = values[:limit]
            output_row[attr_name] = ", ".join(selected)
        except Exception as e:
            print(f"⚠️ Error processing column {col_idx} ({attr_name}): {e}")
            output_row[attr_name] = ""
    return output_row

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    from gspread import authorize
    import gspread

    marketplace_data = download_marketplace_attributes(creds)
    client = authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_title = pdf_filename.replace(".pdf", " marketplace attribute")
    spreadsheet = client.create(sheet_title)
    spreadsheet_id = spreadsheet.id
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

    for tab_name in ["faire", "fgo"]:
        tab_df = marketplace_data[tab_name]

        product_row = tab_df.iloc[0]  # Row 1
        attribute_row = tab_df.iloc[1]  # Row 2
        value_df = tab_df.iloc[2:].reset_index(drop=True)

        category_to_columns = extract_allowed_columns(product_row, attribute_row)

        output_rows = []
        for _, row in df.iterrows():
            style_number = row.get("Style Number", "")
            product_type = row.get("Product Type", "") or row.get("Product Category", "")
            product_type = str(product_type).strip().title()
            col_indices = category_to_columns.get(product_type, [])

            if not col_indices:
                print(f"⚠️ No attribute columns mapped for product_type='{product_type}' (Style: {style_number})")

            selected_attrs = select_values_for_category(value_df, col_indices)
            selected_attrs["Style Number"] = style_number
            output_rows.append(selected_attrs)

        # Reconstruct full header list
        all_headers = ["Style Number"] + sorted(set(attr for pairs in category_to_columns.values() for _, attr in pairs))
        final_df = pd.DataFrame(output_rows)

        # Ensure all expected columns exist
        for col in all_headers:
            if col not in final_df.columns:
                final_df[col] = ""

        final_df = final_df[all_headers]
        final_df.columns = final_df.columns.map(lambda c: "" if pd.isna(c) else str(c))
        final_df = final_df.replace([np.nan, np.inf, -np.inf], "").fillna("").astype(str)

        try:
            sheet = spreadsheet.worksheet(tab_name)
        except:
            sheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="20")

        sheet.clear()
        sheet.update([final_df.columns.tolist()] + final_df.values.tolist())


    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

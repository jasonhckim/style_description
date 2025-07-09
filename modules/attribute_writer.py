import pandas as pd
import re
import os
import numpy as np
from googleapiclient.discovery import build
from gspread_dataframe import get_as_dataframe
import gspread

CATEGORY_ALIASES = {
    "shorts": ["bottom", "shorts"],
    "top": ["top", "shirt", "blouse", "cami"],
    "dress": ["dress", "dresses"],
    "skirt": ["skirt", "bottom", "skirt"],
    "hoodie": ["outerwear", "hoodie", "jacket", "sweatshirt"],
    "pants": ["bottom", "pants", "trousers"],
}

def download_marketplace_attributes(creds):
    sheet_id = "12lJYw9TL97djaPKjF3qKp-Bio-5sQmPbsprEvD4mERA"
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)

    tabs = {}
    for tab in ["faire", "fgo"]:
        worksheet = sheet.worksheet(tab)
        df = get_as_dataframe(worksheet, evaluate_formulas=True, header=0).fillna("")
        header_row = df.iloc[0]  # Row 1: Attribute names (e.g., "Color (1)", "TOP: Sleeve Length (1)")
        df = df[1:].reset_index(drop=True)  # Rows 2+ contain values
        tabs[tab] = (header_row, df)
    return tabs

def parse_selection_limit(attr_name):
    match = re.search(r"\((\d+)\)", attr_name)
    return int(match.group(1)) if match else 1

def extract_column_info(header_row):
    col_info = []
    for idx, col in enumerate(header_row):
        if pd.isna(col) or col == "":
            col_info.append({"index": idx, "prefix": None, "name": "", "limit": 1})
            continue
        col = str(col)
        limit = parse_selection_limit(col)  # ✅ Add this
        if ":" in col:
            prefix, name = col.split(":", 1)
            col_info.append({
                "index": idx,
                "prefix": prefix.strip().lower(),
                "name": name.strip(),
                "limit": limit
            })
        else:
            col_info.append({
                "index": idx,
                "prefix": None,
                "name": col.strip(),
                "limit": limit
            })
    return col_info


def category_matches(prefix, product_category):
    if not prefix:
        return True
    product_category = product_category.lower()
    for alias_list in CATEGORY_ALIASES.values():
        if prefix in alias_list and any(cat in product_category for cat in alias_list):
            return True
    return False

def select_attributes(product_description, category, col_info, df_values, style_number):
    selected = {"Style Number": style_number}
    for col in col_info:
        attr_name = col["name"]
        prefix = col["prefix"]
        max_select = col["limit"]
        values = df_values[attr_name].dropna().unique().tolist()

        # Only use this column if prefix is None or matches category
        if prefix and prefix.lower() not in category.lower():
            continue
        if not values or not attr_name:
            continue

        # Call OpenAI to pick matching values
        prompt = f"""
You are a fashion data assistant helping map a clothing item's attributes to a structured marketplace.

Style Number: {style_number}
Category: {category}
Description: {product_description}

From the following attribute list for **{attr_name}**, choose up to {max_select} values that apply:
{values}

Return only a comma-separated string of the selected values (or empty if none match).
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            answer = response.choices[0].message.content.strip()
            selected[attr_name] = answer
        except Exception as e:
            print(f"⚠️ Error selecting for {attr_name}: {e}")
            selected[attr_name] = ""
    return selected


def write_marketplace_attribute_sheet(description_df, pdf_filename, creds, folder_id):
    drive = build("drive", "v3", credentials=creds)
    client = gspread.authorize(creds)

    spreadsheet = client.create(pdf_filename.replace(".pdf", " marketplace attribute"))
    spreadsheet_id = spreadsheet.id

    # Move into destination folder
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

    marketplace_data = download_marketplace_attributes(creds)

    for tab_name, (header_row, df_values) in marketplace_data.items():
        col_info = extract_column_info(header_row)

        output_rows = []
        for _, row in description_df.iterrows():
            selected = select_attributes(
                product_description=row.get("Product Description", ""),
                category=row.get("Product Category", ""),
                col_info=col_info,
                df_values=df_values,
                style_number=row.get("Style Number", "")
            )
            output_rows.append(selected)


        # Prepare columns from row 1, inserting 'Style Number' first
        ordered_columns = ["Style Number"] + [c["name"] for c in col_info if c["name"]]

        final_df = pd.DataFrame(output_rows)
        for col in ordered_columns:
            if col not in final_df.columns:
                final_df[col] = ""
        final_df = final_df[ordered_columns].replace([np.nan, float("inf"), float("-inf")], "").fillna("").astype(str)

        # Create new tab and upload data
        try:
            sheet = spreadsheet.worksheet(tab_name)
        except:
            sheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="50")

        sheet.clear()
        sheet.update([final_df.columns.tolist()] + final_df.values.tolist())

    # ✅ Now delete "Sheet1" AFTER creating faire/fgo
    try:
        sheet1 = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(sheet1)
    except:
        pass

    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

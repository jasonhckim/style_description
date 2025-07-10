import pandas as pd
import re
import os
import json
import openai
import numpy as np
from googleapiclient.discovery import build
import gspread

# Load attributes from JSON
def load_flat_attributes(path="config/marketplace_attributes.json"):
    with open(path, "r") as f:
        return json.load(f)

# Extract attribute metadata (limit, prefix/category) from column name
def parse_column_metadata(attr_name):
    prefix = None
    limit = 1
    original = attr_name

    # Extract selection limit
    match = re.search(r"\((\d+)\)", attr_name)
    if match:
        limit = int(match.group(1))

    # Extract prefix like "TOP:", "DRESS:"
    if ":" in attr_name:
        parts = attr_name.split(":", 1)
        prefix = parts[0].strip().lower()
        attr_name = parts[1].strip()

    return {
        "name": attr_name.strip(),
        "original": original.strip(),
        "prefix": prefix,
        "limit": limit
    }

# Map which columns apply based on product category
def is_column_applicable(col_meta, category):
    if not col_meta["prefix"]:
        return True
    if not category:
        return False
    category = category.lower()
    prefix = col_meta["prefix"]
    CATEGORY_ALIASES = {
        "shorts": ["bottom", "shorts"],
        "top": ["top", "shirt", "blouse", "cami"],
        "dress": ["dress", "dresses"],
        "skirt": ["skirt", "bottom"],
        "hoodie": ["outerwear", "hoodie", "jacket", "sweatshirt"],
        "pants": ["bottom", "pants", "trousers"]
    }
    for aliases in CATEGORY_ALIASES.values():
        if prefix in aliases and any(a in category for a in aliases):
            return True
    return False

# Use GPT to select appropriate values for each attribute field
def select_attributes_from_ai(product_description, category, style_number, flat_attributes):
    output = {"Style Number": style_number}
    for attr_key, values in flat_attributes.items():
        col_meta = parse_column_metadata(attr_key)
        if not is_column_applicable(col_meta, category):
            continue
        if not values:
            continue

        prompt = f"""
You are a fashion merchandising assistant. Based on the clothing item below, select up to {col_meta["limit"]} attributes from the provided list.

Style Number: {style_number}
Category: {category}
Description: {product_description}

Select from: {values}

Respond with a comma-separated string of the best matching values, or empty if none apply.
"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.choices[0].message.content.strip()
            output[col_meta["original"]] = result
        except Exception as e:
            print(f"⚠️ OpenAI error for {col_meta['original']}: {e}")
            output[col_meta["original"]] = ""
    return output

def write_marketplace_attribute_sheet(description_df, pdf_filename, creds, folder_id):
    # Load from JSON
    flat_attributes = load_flat_attributes()

    drive = build("drive", "v3", credentials=creds)
    client = gspread.authorize(creds)

    # Create spreadsheet
    spreadsheet = client.create(pdf_filename.replace(".pdf", " marketplace attribute"))
    spreadsheet_id = spreadsheet.id
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

    # Create both faire and fgo tabs
    for tab_name in ["faire", "fgo"]:
        output_rows = []
        for _, row in description_df.iterrows():
            selected = select_attributes_from_ai(
                product_description=row.get("Product Description", ""),
                category=row.get("Product Category", ""),
                style_number=row.get("Style Number", ""),
                flat_attributes=flat_attributes
            )
            output_rows.append(selected)

        # Build column list from JSON keys
        all_columns = ["Style Number"] + list(flat_attributes.keys())

        final_df = pd.DataFrame(output_rows)
        for col in all_columns:
            if col not in final_df.columns:
                final_df[col] = ""
        final_df = final_df[all_columns].replace([np.nan, float("inf"), float("-inf")], "").fillna("").astype(str)

        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="50")

        worksheet.clear()
        worksheet.update([final_df.columns.tolist()] + final_df.values.tolist())

    # Remove default Sheet1
    try:
        sheet1 = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(sheet1)
    except:
        pass

    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

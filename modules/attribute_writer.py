import pandas as pd
import re
import os
import json
import numpy as np
import gspread
from googleapiclient.discovery import build

# ✅ Load attribute data from JSON file
def load_flat_attributes(path="config/marketplace_attributes.json"):
    with open(path, "r") as f:
        return json.load(f)

# ✅ Parse column name to get prefix and limit
def parse_column_metadata(attr_name):
    prefix = None
    limit = 1
    original = attr_name

    match = re.search(r"\((\d+)\)", attr_name)
    if match:
        limit = int(match.group(1))

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

# ✅ Determine if this attribute applies to the product category
def is_column_applicable(col_meta, category):
    if not col_meta["prefix"]:
        return True  # No prefix = always applicable
    category = category.lower()
    prefix = col_meta["prefix"].lower()

    category_keywords = {
        "top": ["top", "tops", "blouse", "cami", "shirt", "sweater"],
        "pants": ["pants", "bottom", "trousers"],
        "shorts": ["shorts", "bottom"],
        "dress": ["dress", "dresses"],
        "skirt": ["skirt", "skirts"],
        "hoodie": ["hoodie", "sweatshirt", "jacket", "outerwear"]
    }

    for key, aliases in category_keywords.items():
        if prefix.startswith(key) and any(word in category for word in aliases):
            return True

    return False

# ✅ AI attribute selector
# ✅ AI attribute selector
def select_attributes_from_ai(product_description, category, style_number, flat_attributes):
    output = {"Style Number": style_number}

    from openai import OpenAI
    client = OpenAI()

    for attr_key, values in flat_attributes.items():
        col_meta = parse_column_metadata(attr_key)

        if not is_column_applicable(col_meta, category):
            continue
        if not values:
            continue

        select_from = ", ".join(values[:10]) + ("..." if len(values) > 10 else "")
        prompt = f"""
You are a fashion merchandising assistant. Based on the clothing item below, select up to {col_meta["limit"]} attributes from the provided list.

Style Number: {style_number}
Category: {category}
Description: {product_description}

Select from: {select_from}
"""

        if col_meta["original"] == "Color (1)":
            prompt += """
NOTE: You may infer color from the image or product context — but DO NOT mention or invent it in title or description.
Only return the most likely dominant color. Leave blank if uncertain.
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            answer = response.choices[0].message.content.strip()
            cleaned = answer.replace("None", "").replace("Empty", "")
            output[col_meta["original"]] = cleaned

        except Exception as e:
            print(f"⚠️ OpenAI error for {col_meta['original']}: {e}")
            output[col_meta["original"]] = ""

    return output

# ✅ Write marketplace sheet (faire + fgo)
def write_marketplace_attribute_sheet(description_df, pdf_filename, creds, folder_id):
    flat_attributes = load_flat_attributes()
    drive = build("drive", "v3", credentials=creds)
    client = gspread.authorize(creds)

    spreadsheet = client.create(pdf_filename.replace(".pdf", " marketplace attribute"))
    spreadsheet_id = spreadsheet.id
    drive.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents="root").execute()

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

    # ✅ Clean up default Sheet1
    try:
        sheet1 = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(sheet1)
    except:
        pass

    print(f"✅ Marketplace attribute sheet created: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    return spreadsheet_id

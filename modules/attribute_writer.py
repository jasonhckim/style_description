import gspread
import openai
import json
import os
from modules.utils import get_env_variable

# ✅ Unified attribute map from config/marketplace_attributes.json
ATTRIBUTE_MAPPING = {
    # core_attributes
    "color": "Color (1)",
    "aesthetic": "Aesthetic (2)",
    "embellishment": "Embellishment",
    "neckline": "Neckline (1)",
    "occasion": "Occasion (2)",
    "occasion_theme": "Occasion Theme (3)",
    "pattern": "Pattern (1)",
    "product_language": "Product Language",color
    "season": "Season",
    "sleeve_length": "TOP: Sleeve Length (1)",
    "theme": "Theme",

    # product_specific
    "pants_length": "Pants Length",
    "shorts_length": "Shorts Length",
    "shorts_style": "Shorts Style",
    "shorts_rise_style": "Shorts: *Rise Style",
    "dress_style": "Dress Style",
    "dress_length": "Dress: Skirt & Dress Length",
    "skirt_style": "Skirt Style",
    "hoodie_application_type": "Hoodie: Application Type"
}

HEADERS = ["Style Number"] + list(ATTRIBUTE_MAPPING.values())

MANDATORY_KEYS = {
    "color": 1,
    "aesthetic": 2,
    "embellishment": 1,
    "neckline": 1,
    "occasion": 2,
    "occasion_theme": 3,
    "pattern": 1,
    "product_language": 1,
    "season": 1,
    "theme": 1
}

def format_attribute_row(style_number, selected_attrs):
    row = ["" for _ in HEADERS]
    row[0] = style_number

    for key, value in selected_attrs.items():
        column_name = ATTRIBUTE_MAPPING.get(key.lower())
        if column_name and column_name in HEADERS:
            index = HEADERS.index(column_name)
            val = ", ".join(value) if isinstance(value, list) else value
            row[index] = val

    return row

def select_attributes_from_ai(product_title, description):
    attr_constraints = {
        "color": 1,
        "aesthetic": 2,
        "embellishment": 1,
        "neckline": 1,
        "occasion": 2,
        "occasion_theme": 3,
        "pattern": 1,
        "product_language": 1,
        "season": 1,
        "theme": 1
    }

    attr_instructions = "\n".join([
        f"- {key}: return exactly {count} value(s)" for key, count in attr_constraints.items()
    ])

    prompt = f"""
You're selecting marketplace attributes for the product below.

Product Title: {product_title}
Description: {description}

MANDATORY — Provide values for all of the following attributes:
{attr_instructions}

Use exact keys (e.g. "color", "pattern", etc). Return each value as a string or list of strings.

Respond ONLY with a JSON object using this format:
{{
  "color": ["..."],
  "aesthetic": ["...", "..."],
  ...
}}
"""

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    gc = gspread.authorize(creds)
    title = pdf_filename.replace(".pdf", "").strip()
    sh = gc.create(f"Marketplace - {title}", folder_id)
    ws = sh.sheet1
    ws.update_title("faire")

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    print("📊 Normalized columns:", df.columns.tolist())

    ws.update("A1", [HEADERS])

    all_rows = []

    for _, row in df.iterrows():
        try:
            style_number = row["style_number"]
            title = row["product_title"]
            desc = row["product_description"]
            selected_attrs = select_attributes_from_ai(title, desc)
            row_data = format_attribute_row(style_number, selected_attrs)
            all_rows.append(row_data)
        except KeyError as e:
            print(f"⚠️ Skipping row due to missing field: {e}")
            continue

    if all_rows:
        ws.append_rows(all_rows, value_input_option="USER_ENTERED")

    print(f"✅ Sheet created and updated: https://docs.google.com/spreadsheets/d/{sh.id}")

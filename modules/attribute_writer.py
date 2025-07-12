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
    "product_language": "Product Language",
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

from openai import OpenAI
client = OpenAI()

def select_attributes_from_ai(product_title, description):
    attr_keys = list(ATTRIBUTE_MAPPING.keys())
    attr_preview = "\n".join([f"- {k}" for k in attr_keys])

    prompt = f"""
You're assigning marketplace attributes to a fashion product.

Product Title: {product_title}
Description: {description}

Choose values for only applicable attributes below:
{attr_preview}

Return a JSON object using only these keys. Each value must be a string or a list of strings.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a fashion assistant helping map products to their attributes."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ Error parsing AI response: {e}")
        return {}

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

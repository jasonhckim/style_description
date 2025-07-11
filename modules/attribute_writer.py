import gspread
import openai
import json
import os
from config.marketplace_attributes_data import marketplace_attributes
from modules.utils import get_env_variable
from modules.normalize_headers import normalize_column_name

def flatten_attribute_data(attr_data):
    flat = {}
    for section in attr_data.values():
        for key, label in section.items():
            flat[key] = label
    return flat

flat_attribute_data = flatten_attribute_data(marketplace_attributes)

# ✅ Maps normalized header names back to friendly column names for the sheet
def get_all_column_headers():
    return ["Style Number"] + list(flat_attribute_data.values())

def select_attributes_from_ai(product_title, description, category):
    """Send all attributes and values to GPT and ask it to return the applicable ones."""
    from config.marketplace_attribute_values import ATTRIBUTE_VALUES_BY_KEY

    attribute_text = ""
    for key, display_name in flat_attribute_data.items():
        options = ATTRIBUTE_VALUES_BY_KEY.get(key, [])
        if options:
            option_str = ", ".join(options[:30])  # limit length
            attribute_text += f"{display_name} ({key}): [{option_str}]\n"

    prompt = f"""
You're a fashion product tagging assistant for HYFVE wholesale.

Product Title: {product_title}
Product Description: {description}
Product Category: {category}

Pick the best matching values for each attribute below.
Only return a JSON object with the keys matching the attribute codes (e.g., "color", "pattern", etc.)
Do NOT include attributes that don't apply.

{attribute_text}

Return JSON only:
{{
  "color": "Beige",
  "neckline": "Crew neck",
  ...
}}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        json_start = content.find("{")
        json_data = content[json_start:]
        return json.loads(json_data)
    except Exception as e:
        print("⚠️ AI Error:", e)
        return {}

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    gc = gspread.authorize(creds)
    sh = gc.create(f"Marketplace - {pdf_filename}", folder_id)
    ws = sh.sheet1
    ws.update_title("faire")

    headers = get_all_column_headers()
    ws.update("A1", [headers])

    from config.marketplace_attribute_values import ATTRIBUTE_VALUES_BY_KEY  # For normalization

    rows_to_add = []
    for _, row in df.iterrows():
        style_number = row.get("Style Number", row.get("style_number", "N/A"))
        product_title = row.get("Product Title", row.get("product_title", ""))
        description = row.get("Product Description", row.get("description", ""))
        category = row.get("product_category", row.get("product_type", "Unknown"))

        selected = select_attributes_from_ai(product_title, description, category)

        # Build row using flat_attribute_data
        row_data = [style_number]
        for key in flat_attribute_data:
            val = selected.get(key, "")
            if isinstance(val, list):
                row_data.append(", ".join(val))
            else:
                row_data.append(val)

        rows_to_add.append(row_data)

    if rows_to_add:
        ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")

    print(f"✅ Sheet created and updated: https://docs.google.com/spreadsheets/d/{sh.id}")

import gspread
import openai
import json
import os
from config.marketplace_attributes_data import flat_attribute_data
from modules.utils import get_env_variable

def get_headers_for_category(category, flat_data):
    """Return headers filtered by category-specific relevance"""
    category = category.lower()

    relevant_keys = []
    for key, label in flat_data.items():
        key_lower = key.lower()
        label_lower = label.lower()

        if category in label_lower or category in key_lower:
            relevant_keys.append((key, label))

    # Always include some core attributes regardless of category
    always_include = ["color", "aesthetic", "season", "occasion", "theme"]
    for k in always_include:
        if k in flat_data and (k, flat_data[k]) not in relevant_keys:
            relevant_keys.append((k, flat_data[k]))

    headers = ["Style Number"] + [label for _, label in relevant_keys]
    return headers, [key for key, _ in relevant_keys]

def format_attribute_row(style_number, selected_attrs, attribute_keys, flat_data):
    row = [style_number]
    for key in attribute_keys:
        val = selected_attrs.get(key, "")
        if isinstance(val, list):
            row.append(", ".join(val))
        else:
            row.append(val)
    return row

def select_attributes_from_ai(product_title, description, category, attribute_keys, flat_data):
    preview_dict = {k: flat_data[k] for k in attribute_keys if k in flat_data}

    preview_text = "\n".join([f"{k}: {v}" for k, v in preview_dict.items()])

    prompt = f"""
You're selecting marketplace attributes for a product.

Product Title: {product_title}
Description: {description}
Category: {category}

Choose the most relevant values for the following attributes (limit selection to what's meaningful):

{preview_text}

Return a JSON object with keys exactly matching the attribute codes (e.g., "color", "style", "pattern").
Values should be either a string or list of strings.
Only include attributes that apply.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that selects product attributes for marketplace listings."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print("⚠️ Error parsing OpenAI response:", e)
        return {}

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    gc = gspread.authorize(creds)
    sh = gc.create(f"Marketplace - {pdf_filename}", folder_id)
    ws = sh.sheet1
    ws.update_title("faire")

    # ✅ Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    print("📊 Normalized columns:", df.columns.tolist())

    all_rows = []
    first_row_headers = None

    for _, row in df.iterrows():
        try:
            style_number = row["style_number"]
            title = row["product_title"]
            desc = row["product_description"]
            category = row.get("product_category", row.get("product_type", "unknown"))

            headers, attribute_keys = get_headers_for_category(category, flat_attribute_data)

            if first_row_headers is None:
                first_row_headers = headers
                ws.update("A1", [headers])  # Set headers once

            selected_attrs = select_attributes_from_ai(title, desc, category, attribute_keys, flat_attribute_data)
            row_data = format_attribute_row(style_number, selected_attrs, attribute_keys, flat_attribute_data)
            all_rows.append(row_data)

        except KeyError as e:
            print(f"⚠️ Skipping row due to missing key: {e}")
            continue

    if all_rows:
        ws.append_rows(all_rows, value_input_option="USER_ENTERED")

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sh.id}"
    print(f"✅ Sheet created and updated: {sheet_url}")

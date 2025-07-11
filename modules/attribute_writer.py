import gspread
import openai
import json
import os
from modules.utils import get_env_variable

# ✅ Key-to-column label mapping based on your original JSON structure
ATTRIBUTE_MAPPING = {
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
    """Map selected AI attributes to fixed column layout"""
    row = [""] * len(HEADERS)
    row[0] = style_number  # "Style Number" is always first

    for attr_key, value in selected_attrs.items():
        column_name = ATTRIBUTE_MAPPING.get(attr_key.lower())
        if column_name and column_name in HEADERS:
            index = HEADERS.index(column_name)
            val = ", ".join(value) if isinstance(value, list) else value
            row[index] = val

    return row

def select_attributes_from_ai(product_title, description):
    # Show attribute keys to AI (not full column names)
    preview = "\n".join([f"- {key}" for key in ATTRIBUTE_MAPPING.keys()])

    prompt = f"""
You're assigning marketplace attributes to the product below.

Product Title: {product_title}
Description: {description}

Here is the list of all possible attributes:
{preview}

Return a JSON object using these attribute keys (e.g., "color", "pattern") as keys.
Values should be a string or list of strings.
Only include attributes that apply.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant selecting product attributes for fashion listings."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ Error from OpenAI or JSON parsing: {e}")
        return {}

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    gc = gspread.authorize(creds)
    sh = gc.create(f"Marketplace - {pdf_filename}", folder_id)
    ws = sh.sheet1
    ws.update_title("faire")

    # ✅ Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    print("📊 Normalized columns:", df.columns.tolist())

    # ✅ Write headers
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
            print(f"⚠️ Skipping row due to missing key: {e}")
            continue

    if all_rows:
        ws.append_rows(all_rows, value_input_option="USER_ENTERED")

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sh.id}"
    print(f"✅ Sheet created and updated: {sheet_url}")

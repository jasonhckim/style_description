import gspread
import openai
import json
import os
from modules.utils import get_env_variable

# ✅ All supported marketplace attributes (manually defined once)
ALL_ATTRIBUTE_COLUMNS = [
    "Color (1)", "Aesthetic (2)", "Embellishment", "Neckline (1)", "Occasion (2)",
    "Occasion Theme (3)", "Pattern (1)", "Product Language", "Season",
    "TOP: Sleeve Length (1)", "Pants Length", "Shorts Length", "Shorts Style",
    "Shorts: *Rise Style", "Dress Style", "Dress: Skirt & Dress Length",
    "Skirt Style", "Hoodie: Application Type", "Theme"
]

HEADERS = ["Style Number"] + ALL_ATTRIBUTE_COLUMNS

def format_attribute_row(style_number, selected_attrs):
    """Map selected AI attributes to fixed columns"""
    row = [style_number]
    for col in ALL_ATTRIBUTE_COLUMNS:
        value = selected_attrs.get(col.lower(), "")  # match lowercase keys
        if isinstance(value, list):
            row.append(", ".join(value))
        else:
            row.append(value)
    return row

def select_attributes_from_ai(product_title, description):
    # Provide all possible attributes to the AI
    preview = "\n".join([f"- {col}" for col in ALL_ATTRIBUTE_COLUMNS])

    prompt = f"""
You're assigning marketplace attributes to the product below.

Product Title: {product_title}
Description: {description}

Here is the list of all possible attributes:
{preview}

Return a JSON where keys exactly match the lowercase version of the attribute labels (e.g., "color (1)", "pattern (1)"), and values are strings or lists of strings.
Only include relevant keys.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant selecting product attributes."},
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

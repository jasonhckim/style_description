from modules.marketplace_attributes_data import flat_attribute_data  # step 1
from openai import OpenAI
import gspread

def get_sheet_headers(attribute_dict):
    return ["Style Number"] + list(attribute_dict.keys())

def format_attribute_row(style_number, selected_attrs, attribute_dict):
    row = [style_number]
    for header in attribute_dict.keys():
        val = selected_attrs.get(header, "")
        if isinstance(val, list):
            row.append(", ".join(val))
        else:
            row.append(val)
    return row

def select_attributes_from_ai(product_title, description, category):
    import openai

    # Debug: Show top 10 options (fix TypeError here)
    preview_dict = {
        k: ", ".join(v[:10]) + ("..." if len(v) > 10 else "")
        for k, v in flat_attribute_data.items()
    }

    prompt = f"""
You're selecting attributes for a product to match marketplace listing requirements.

Product Title: {product_title}
Description: {description}
Category: {category}

You must choose the most relevant attributes from the following options (limit counts if noted):

{preview_dict}

Return a JSON with keys exactly matching those above, values can be strings or lists.
Only return fields where a value should be selected.
"""

    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant selecting product attributes."},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        content = response.choices[0].message.content
        return eval(content.strip())  # you may replace this with json.loads() if the output is strict JSON
    except Exception as e:
        print("⚠️ Error parsing OpenAI response:", e)
        return {}

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    import os
    from modules.utils import copy_template_sheet

    gc = gspread.authorize(creds)
    new_sheet_url = copy_template_sheet(pdf_filename, folder_id)
    sh = gc.open_by_url(new_sheet_url)
    main_ws = sh.worksheet("faire")  # or “fgo” based on use

    headers = get_sheet_headers(flat_attribute_data)
    rows = []

    for _, row in df.iterrows():
        style_number = row["Style Number"]
        title = row["product_title"]
        desc = row["description"]
        category = row.get("product_category", row.get("product_type", "Unknown"))

        selected_attrs = select_attributes_from_ai(title, desc, category)
        row_data = format_attribute_row(style_number, selected_attrs, flat_attribute_data)
        rows.append(row_data)

    main_ws.update("A1", [headers])
    main_ws.append_rows(rows, value_input_option="USER_ENTERED")

    print(f"✅ Updated sheet with attributes: {new_sheet_url}")

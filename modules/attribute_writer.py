import gspread
import json
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
    "theme": "Theme",

    # product_specific
    "sleeve_length": "TOP: Sleeve Length (1)",
    "pants_length": "Pants Length",
    "shorts_length": "Shorts Length",
    "shorts_style": "Shorts Style",
    "shorts_rise_style": "Shorts: *Rise Style",
    "dress_style": "Dress Style",
    "dress_length": "Dress: Skirt & Dress Length",
    "skirt_style": "Skirt Style",
    "hoodie_application_type": "Hoodie: Application Type"
}

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

HEADERS = ["Style Number"] + list(ATTRIBUTE_MAPPING.values())

def enforce_required_attributes(selected_attrs):
    """Ensure all mandatory attributes exist and have correct length."""
    for key, count in MANDATORY_KEYS.items():
        val = selected_attrs.get(key)
        if not val:
            selected_attrs[key] = ["N/A"] * count
        elif isinstance(val, list):
            while len(val) < count:
                val.append("N/A")
        elif isinstance(val, str):
            selected_attrs[key] = [val] * count
    return selected_attrs

def format_attribute_row(style_number, selected_attrs):
    """Formats selected attributes into a Google Sheets row."""
    row = ["" for _ in HEADERS]
    row[0] = style_number

    for key, value in selected_attrs.items():
        column_name = ATTRIBUTE_MAPPING.get(key.lower())
        if column_name and column_name in HEADERS:
            index = HEADERS.index(column_name)
            val = ", ".join(value) if isinstance(value, list) else value
            row[index] = val

    return row

def map_ai_attributes_to_marketplace(ai_attributes):
    """
    Converts ai_description.py attributes (fabric, silhouette, length, neckline, sleeve)
    to the marketplace ATTRIBUTE_MAPPING keys where relevant.
    """
    mapped = {}

    if not ai_attributes:
        return mapped

    # ✅ Example mapping logic (customize as needed)
    if ai_attributes.get("neckline"):
        mapped["neckline"] = [ai_attributes["neckline"]]

    if ai_attributes.get("sleeve"):
        mapped["sleeve_length"] = [ai_attributes["sleeve"]]  # maps to "TOP: Sleeve Length (1)"

    if ai_attributes.get("length"):
        mapped["dress_length"] = [ai_attributes["length"]]  # maps to "Dress: Skirt & Dress Length"

    if ai_attributes.get("silhouette"):
        mapped["dress_style"] = [ai_attributes["silhouette"]]

    if ai_attributes.get("fabric"):
        mapped["aesthetic"] = [ai_attributes["fabric"]]  # temporary mapping; can refine later

    return mapped

def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    """Writes product + attributes to Google Sheets."""
    gc = gspread.authorize(creds)
    title = pdf_filename.replace(".pdf", "").strip()
    sh = gc.create(f"Marketplace - {title}", folder_id)
    ws = sh.sheet1
    ws.update_title("faire")

    df.columns = [c.lower() for c in df.columns]

    print("📊 Normalized columns:", df.columns.tolist())

    ws.update("A1", [HEADERS])
    all_rows = []

    for _, row in df.iterrows():
        try:
            style_number = row["style_number"]
            ai_attributes = {
                "fabric": row.get("fabric", ""),
                "silhouette": row.get("silhouette", ""),
                "length": row.get("length", ""),
                "neckline": row.get("neckline", ""),
                "sleeve": row.get("sleeve", "")
            }


            # ✅ Map AI attributes to marketplace format
            selected_attrs = map_ai_attributes_to_marketplace(ai_attributes)

            # ✅ Ensure mandatory attributes
            selected_attrs = enforce_required_attributes(selected_attrs)

            row_data = format_attribute_row(style_number, selected_attrs)
            all_rows.append(row_data)

        except KeyError as e:
            print(f"⚠️ Skipping row due to missing field: {e}")
            continue

    if all_rows:
        ws.append_rows(all_rows, value_input_option="USER_ENTERED")

    print(f"✅ Sheet created and updated: https://docs.google.com/spreadsheets/d/{sh.id}")

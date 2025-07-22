import gspread
import json
from modules.utils import get_env_variable

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
    "theme": "Theme",
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

# ✅ Generate a usable column index map from HEADERS
ATTRIBUTE_COLUMN_MAP = {"style_number": 0}
ATTRIBUTE_COLUMN_MAP.update({k: i + 1 for i, k in enumerate(ATTRIBUTE_MAPPING.keys())})


def enforce_required_attributes(selected_attrs):
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


def format_attribute_row(style_no, attributes):
    # ✅ Automatically size the row based on HEADERS
    row = [""] * len(HEADERS)

    for key, value in attributes.items():
        idx = ATTRIBUTE_COLUMN_MAP.get(key)
        if idx is None:
            continue

        # ✅ Flatten nested lists before joining
        if isinstance(value, list):
            flat = []
            for v in value:
                if isinstance(v, list):
                    flat.extend(v)
                else:
                    flat.append(v)
            row[idx] = ", ".join(map(str, flat))
        else:
            row[idx] = str(value) if value is not None else ""

    # ✅ Ensure style number is always set
    row[0] = style_no
    return row


def map_ai_attributes_to_marketplace(ai_attributes):
    mapped = {}
    if ai_attributes.get("neckline"):
        mapped["neckline"] = [ai_attributes["neckline"]]
    if ai_attributes.get("sleeve"):
        mapped["sleeve_length"] = [ai_attributes["sleeve"]]
    if ai_attributes.get("length"):
        mapped["dress_length"] = [ai_attributes["length"]]
    if ai_attributes.get("silhouette"):
        mapped["dress_style"] = [ai_attributes["silhouette"]]
    if ai_attributes.get("fabric"):
        mapped["aesthetic"] = [ai_attributes["fabric"]]
    return mapped


def write_marketplace_attribute_sheet(df, pdf_filename, creds, folder_id):
    gc = gspread.authorize(creds)
    title = pdf_filename.replace(".pdf", "").strip()
    sh = gc.create(f"Marketplace - {title}", folder_id)
    ws = sh.sheet1
    ws.update_title("faire")

    # ✅ Normalize column names for consistency
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    ws.update("A1", [HEADERS])

    rows = []
    for _, row in df.iterrows():
        style_no = row.get("style_number") or row.get("Style Number")
        ai_attrs = {
            "fabric": row.get("fabric", ""),
            "silhouette": row.get("silhouette", ""),
            "length": row.get("length", ""),
            "neckline": row.get("neckline", ""),
            "sleeve": row.get("sleeve", "")
        }
        sel = enforce_required_attributes(map_ai_attributes_to_marketplace(ai_attrs))
        rows.append(format_attribute_row(style_no, sel))

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"✅ Sheet created: https://docs.google.com/spreadsheets/d/{sh.id}")

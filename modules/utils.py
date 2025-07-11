import logging
import time
import json
import re
from PIL import Image
import uuid
import os
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

def copy_template_sheet(creds, template_id, new_title):
    service = build("drive", "v3", credentials=creds)
    copied_file = {
        "name": new_title
    }
    new_sheet = service.files().copy(
        fileId=template_id,
        body=copied_file
    ).execute()
    return new_sheet["id"]
    
def save_image_temp(image_obj):
    """Save a PIL Image to a temporary file and return the path."""
    temp_dir = "/tmp" if os.name != "nt" else os.environ.get("TEMP", ".")
    filename = os.path.join(temp_dir, f"{uuid.uuid4().hex}.png")
    image_obj.save(filename, format="PNG")
    return filename


def setup_logging(log_file="script.log"):
    """Sets up logging configuration."""
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

def wait(seconds):
    """Pauses execution for a given number of seconds."""
    print(f"⏳ Waiting {seconds} seconds...")
    time.sleep(seconds)

def get_env_variable(var_name, default=None):
    """Gets an environment variable or returns a default value."""
    value = os.getenv(var_name, default)
    if value is None:
        print(f"⚠️ WARNING: {var_name} is not set!")
    return value

def load_json(file_path):
    """Loads a JSON file and returns the data."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        print(f"❌ ERROR: Could not read {file_path}. {e}")
        return None

def save_json(file_path, data):
    """Saves data to a JSON file."""
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        print(f"✅ Saved data to {file_path}")
    except Exception as e:
        print(f"❌ ERROR: Could not save {file_path}. {e}")

# ✅ Add This at the Bottom
def extract_keywords_from_doc(file_path):
    """Extracts keywords from a TXT file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            keywords = f.read().splitlines()
        return [kw.strip() for kw in keywords if kw.strip()]
    except Exception as e:
        print(f"❌ ERROR: Could not extract keywords from {file_path}. Debug: {e}")
        return []

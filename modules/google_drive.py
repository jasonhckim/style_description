import os
import json
import yaml
import io
import base64
import re
from PIL import Image
import fitz  # PyMuPDF

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# ✅ Load config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Folder IDs
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]

# ✅ Google Drive API Scopes
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ✅ Get Google Drive service using credentials
def get_drive_service():
    service_account_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not service_account_json:
        raise Exception("Missing GOOGLE_CREDENTIALS environment variable")

    info = json.loads(service_account_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

# ✅ Get the first matching file from a Drive folder
def list_files_in_drive(folder_id, mime_type):
    service = get_drive_service()
    query = f"'{folder_id}' in parents and mimeType='{mime_type}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    files = results.get("files", [])
    return files[0] if files else None

# ✅ Get all matching files from a Drive folder
def list_all_files_in_drive(folder_id, mime_type):
    service = get_drive_service()
    query = f"'{folder_id}' in parents and mimeType='{mime_type}' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])

# ✅ Download file from Google Drive
def download_file_from_drive(file_id, filename):
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, filename)

    try:
        service = get_drive_service()
        request = service.files().get_media(fileId=file_id)
        with open(file_path, "wb") as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        print(f"✅ Downloaded {filename} to: {file_path}")
        return file_path
    except Exception as e:
        print(f"❌ ERROR: Failed to download {filename}. Debug: {e}")
        return None

# ✅ Upload file to Google Drive
def upload_file_to_drive(file_path, folder_id):
    service = get_drive_service()
    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    print(f"✅ Uploaded CSV to Google Drive: https://drive.google.com/file/d/{uploaded_file['id']}")
    return uploaded_file["id"]

# ✅ Extract text and images from PDF
def extract_text_and_images_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    extracted_data = []
    style_regex = r"\b(DZ\d{2}[A-Z]\d{3,5}(-SET|-D)?|HF\d{2}[A-Z]\d{3,5}(-SET|-D)?)\b"

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        images = []

        for _, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            img_io = io.BytesIO()
            image.save(img_io, format="JPEG")
            img_base64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
            images.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}})

        style_number = re.findall(style_regex, text)
        style_number = style_number[0][0] if style_number else "Unknown"

        extracted_data.append({
            "page": page_num + 1,
            "style_number": style_number,
            "text": text.strip(),
            "images": images
        })

    return extracted_data

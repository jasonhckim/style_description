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
from googleapiclient.http import MediaInMemoryUpload
from googleapiclient.discovery import build as build_api



# ✅ Load config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Folder IDs
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]
TEMPLATE_SHEET_ID = config.get("google_sheet_template_id")

# ✅ Google Drive API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive", 
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.projects"
]

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
    drive_service = get_drive_service()
    extracted_data = []
    style_regex = r"\b(DZ\d{2}[A-Z]\d{3,5}(-SET|-D)?|HF\d{2}[A-Z]\d{3,5}(-SET|-D)?)\b"

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        public_image_urls = []

        for idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            pil_image = Image.open(io.BytesIO(image_bytes))

            # Save to temp file
            temp_path = f"/tmp/page{page_num+1}_img{idx}.png"
            pil_image.save(temp_path, format="PNG")

            # Upload to Drive
            public_url = upload_image_to_public_url(temp_path, drive_service)
            public_image_urls.append({"type": "image_url", "image_url": public_url})

        # Extract style number
        style_number = re.findall(style_regex, text)
        style_number = style_number[0][0] if style_number else "Unknown"

        extracted_data.append({
            "page": page_num + 1,
            "style_number": style_number,
            "text": text.strip(),
            "images": public_image_urls
        })

    return extracted_data
    
#Upload Image Publicly
def upload_image_to_public_url(local_image_path, drive_service, folder_id=None):
    """Uploads an image to Google Drive and returns a public URL."""
    file_metadata = {
        "name": os.path.basename(local_image_path),
        "mimeType": "image/png"
    }

    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(local_image_path, mimetype="image/png")
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    # Make file public
    drive_service.permissions().create(
        fileId=uploaded_file["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://drive.google.com/uc?id={uploaded_file['id']}"

#Copy a template Sheet
def copy_sheet_from_template(new_title, destination_folder_id, creds):
    drive = build("drive", "v3", credentials=creds)
    template_id = config["google_sheet_template_id"]  # 👈 Match your config

    copied_file = drive.files().copy(
        fileId=template_id,
        body={"name": new_title, "parents": [destination_folder_id]}
    ).execute()

    print(f"✅ Copied template to new sheet: https://docs.google.com/spreadsheets/d/{copied_file['id']}")
    return copied_file["id"]


    # ✅ Create Apps Script project bound to the Sheet
    script_project = script_service.projects().create(
        body={
            "title": "SyncEdits",
            "parentId": sheet_id
        }
    ).execute()

    project_id = script_project["scriptId"]
    print("✅ Apps Script project created and bound:", project_id)

    # ✅ Push script files
    timezone = config.get("apps_script", {}).get("timezone", "America/Los_Angeles")
    script_service.projects().updateContent(
        scriptId=project_id,
        body={
            "files": [
                {"name": "Code", "type": "SERVER_JS", "source": on_edit_code},
                {"name": "appsscript", "type": "JSON", "source": json.dumps({
                    "timeZone": timezone,
                    "exceptionLogging": "STACKDRIVER"
                })}
            ]
        }
    ).execute()

    print("✅ Apps Script code injected")

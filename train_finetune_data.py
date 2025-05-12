import os
import json
import pandas as pd
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# CONFIG
FOLDER_ID = "17fVHKtTVpv6QBpnGlf4_AV-6bPOGrHen"
MIN_TRAINING_ROWS = 10
JSONL_FILENAME = "training.jsonl"

# Setup Google Drive & Sheets credentials
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets.readonly"]
)
drive_service = build("drive", "v3", credentials=creds)
sheets_service = build("sheets", "v4", credentials=creds)

# List CSV and Sheets in folder
results = drive_service.files().list(
    q=f"'{FOLDER_ID}' in parents and (mimeType='text/csv' or mimeType='application/vnd.google-apps.spreadsheet')",
    fields="files(id, name, mimeType)"
).execute()

files = results.get("files", [])
if not files:
    print("No CSV or Google Sheets files found in the folder.")
    exit()

training_rows = []
file_ids_to_delete = []

for file in files:
    file_id = file["id"]
    file_name = file["name"]
    mime_type = file["mimeType"]

    print(f"📄 Processing file: {file_name} ({mime_type})")

    # Load into DataFrame
    if mime_type == "text/csv":
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        df = pd.read_csv(fh)

    elif mime_type == "application/vnd.google-apps.spreadsheet":
        sheet = sheets_service.spreadsheets().values().get(
            spreadsheetId=file_id,
            range="A1:Z1000"
        ).execute()
        values = sheet.get("values", [])
        if not values:
            print(f"⚠️ Google Sheet '{file_name}' is empty. Skipping.")
            continue
        df = pd.DataFrame(values[1:], columns=values[0])
    else:
        print(f"⚠️ Unsupported file type: {file_name}")
        continue

    for _, row in df.iterrows():
        title_changed = str(row["Product Title"]).strip() != str(row["Edit Product Title"]).strip()
        desc_changed = str(row["Product Description"]).strip() != str(row["Edit Product Description"]).strip()

        if title_changed or desc_changed:
            input_text = f"Style Number: {row['Style Number']}\nTitle: {row['Product Title']}\nDescription: {row['Product Description']}"
            output_text = f"Title: {row['Edit Product Title']}\nDescription: {row['Edit Product Description']}"
            training_rows.append({
                "messages": [
                    {"role": "system", "content": "You are a fashion copywriter. Write a product title and description."},
                    {"role": "user", "content": input_text},
                    {"role": "assistant", "content": output_text}
                ]
            })

    if len(training_rows) > 0:
        file_ids_to_delete.append(file_id)

# Submit to OpenAI if enough data
if len(training_rows) >= MIN_TRAINING_ROWS:
    with open(JSONL_FILENAME, "w") as f:
        for row in training_rows:
            f.write(json.dumps(row) + "\n")

    openai.api_key = os.environ["OPENAI_API_KEY"]

    with open(JSONL_FILENAME, "rb") as f:
        uploaded_file = openai.files.create(file=f, purpose="fine-tune")

    job = openai.fine_tuning.jobs.create(training_file=uploaded_file.id, model="gpt-3.5-turbo")

    print(f"✅ Fine-tune job submitted: {job.id}")
    print(f"Training rows: {len(training_rows)}")

    from googleapiclient.errors import HttpError

for file_id in file_ids_to_delete:
        try:
            drive_service.files().delete(fileId=file_id).execute()
            print(f"🗑️ Deleted file from Drive: {file_id}")
        except HttpError as e:
            if e.resp.status == 403:
                print(f"⚠️ Skipped deletion — insufficient permissions for file: {file_id}")
            else:
                raise
else:
    print(f"❌ Not enough rows to fine-tune (found {len(training_rows)}). Skipping upload.")

from datetime import datetime

with open("finetune_log.csv", "a", newline="") as log_file:
    log_writer = csv.writer(log_file)
    log_writer.writerow([
        datetime.utcnow().isoformat(),
        len(training_rows),
        uploaded_file.id,
        job.id,
        job.fine_tuned_model
    ])

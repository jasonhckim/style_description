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

# Setup Google Drive credentials
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/drive"]
)
drive = build("drive", "v3", credentials=creds)

# List all CSVs in target folder
results = drive.files().list(
    q=f"'{FOLDER_ID}' in parents and mimeType='text/csv'",
    fields="files(id, name)"
).execute()

files = results.get("files", [])
if not files:
    print("No CSV files found in the folder.")
    exit()

training_rows = []
file_ids_to_delete = []

for file in files:
    file_id = file["id"]
    file_name = file["name"]

    # Download CSV from Drive
    request = drive.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)

    df = pd.read_csv(fh)

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

    upload = openai.File.create(file=open(JSONL_FILENAME, "rb"), purpose="fine-tune")
    job = openai.FineTuningJob.create(training_file=upload["id"], model="gpt-3.5-turbo")

    print(f"✅ Fine-tune job submitted: {job['id']}")
    print(f"Training rows: {len(training_rows)}")

    # Delete processed files
    for file_id in file_ids_to_delete:
        drive.files().delete(fileId=file_id).execute()
        print(f"Deleted CSV: {file_id}")
else:
    print(f"❌ Not enough rows to fine-tune (found {len(training_rows)}). Skipping upload.")

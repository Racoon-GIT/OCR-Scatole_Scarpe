import os
import datetime
from utils import drive_list_files, drive_move_file, drive_download_file
from parsing import parse_label
from googleapiclient.discovery import build
from google.oauth2 import service_account

def append_to_sheet(row):
    creds = service_account.Credentials.from_service_account_info(
        eval(os.environ["GOOGLE_CREDENTIALS_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    body = {"values": [row]}
    sheet.spreadsheets().values().append(
        spreadsheetId=os.environ["SHEET_ID"],
        range="Sheet1!A1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

def process_inbox():
    inbox = os.environ["DRIVE_INBOX_FOLDER_ID"]
    processed = os.environ["DRIVE_PROCESSED_FOLDER_ID"]

    files = drive_list_files(inbox)
    results = []

    for f in files:
        img_path = drive_download_file(f["id"], f["name"])
        parsed = parse_label(img_path)

        row = [
            datetime.datetime.utcnow().isoformat(),
            f["name"],
            parsed.get("modello", ""),
            parsed.get("articolo", ""),
            parsed.get("colore", ""),
            parsed.get("taglia_fr", ""),
            parsed.get("barcode", ""),
            parsed.get("confidenza", ""),
            "OK" if parsed else "EMPTY"
        ]
        append_to_sheet(row)
        drive_move_file(f["id"], processed)
        results.append(row)

    return results

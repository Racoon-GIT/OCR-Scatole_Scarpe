import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        eval(os.environ["GOOGLE_CREDENTIALS_JSON"]),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def drive_list_files(folder_id):
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=q, fields="files(id,name,mimeType)").execute()
    return results.get("files", [])

def drive_download_file(file_id, filename):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(filename, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return filename

def drive_move_file(file_id, folder_id):
    service = get_drive_service()
    file = service.files().get(fileId=file_id, fields="parents").execute()
    prev_parents = ",".join(file.get("parents"))
    service.files().update(fileId=file_id, addParents=folder_id, removeParents=prev_parents).execute()

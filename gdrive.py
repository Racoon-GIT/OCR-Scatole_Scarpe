import io, os, json, logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2 import service_account

logger = logging.getLogger("gdrive")

SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/spreadsheets"]

def _creds():
    data = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    return service_account.Credentials.from_service_account_info(data, scopes=SCOPES)

def drive():
    return build("drive","v3",credentials=_creds(), cache_discovery=False)

def list_images(folder_id, page_size=50):
    svc = drive()
    q = f"'{folder_id}' in parents and trashed=false and mimeType contains 'image/'"
    res = svc.files().list(q=q, pageSize=page_size, fields="files(id,name,mimeType)",
                           includeItemsFromAllDrives=True, supportsAllDrives=True, corpora="allDrives").execute()
    files = res.get("files", [])
    logger.info("list_images | folder=%s count=%d", folder_id, len(files))
    return files

def download_file(file_id, out_path):
    svc = drive()
    logger.info("download_file | id=%s -> %s", file_id, out_path)
    req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(out_path,"wb") as fh:
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return out_path

def upload_image(folder_id, local_path, name=None, mime="image/jpeg"):
    svc = drive()
    name = name or os.path.basename(local_path)
    file_metadata = {"name": name, "parents":[folder_id]}
    logger.info("upload_image | %s -> folder=%s", name, folder_id)
    media = MediaIoBaseUpload(open(local_path,"rb"), mimetype=mime, resumable=False)
    f = svc.files().create(body=file_metadata, media_body=media, fields="id,name", supportsAllDrives=True).execute()
    return f

def move_file(file_id, to_folder_id):
    svc = drive()
    file = svc.files().get(fileId=file_id, fields="parents", supportsAllDrives=True).execute()
    prev = ",".join(file.get("parents", []))
    logger.info("move_file | id=%s to=%s from=%s", file_id, to_folder_id, prev)
    svc.files().update(fileId=file_id, addParents=to_folder_id, removeParents=prev,
                       fields="id,parents", supportsAllDrives=True).execute()


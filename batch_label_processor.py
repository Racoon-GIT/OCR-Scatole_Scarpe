import os
import json
import datetime
from typing import List, Dict

import gspread
from google.oauth2.service_account import Credentials

from utils import drive_list_files, drive_move_file, drive_download_file
from parsing import parse_label


# ---- Google Sheets (gspread) --------------------------------------------------

def _gs_client() -> gspread.Client:
    """
    Crea un client gspread usando il JSON del Service Account preso dalle ENV.
    Richiede che lo Sheet sia condiviso con l'email del SA (Editor).
    """
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


def append_to_sheet(row: List[str]) -> None:
    """
    Aggiunge UNA riga in coda al primo foglio dello Spreadsheet indicato da SHEET_ID.
    """
    gc = _gs_client()
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    ws = sh.sheet1
    ws.append_row(row, value_input_option="RAW")


# ---- Batch processor ----------------------------------------------------------

def _now_iso_utc() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def process_inbox() -> List[List[str]]:
    """
    Legge i file immagine dalla cartella INBOX (Drive), per ciascuno:
      - scarica il file
      - esegue il parsing (parse_label) per ottenere i campi
      - scrive una riga su Google Sheets
      - sposta l'originale nella cartella PROCESSED

    Ritorna la lista delle righe scritte.
    """
    inbox_id = os.environ["DRIVE_INBOX_FOLDER_ID"]
    processed_id = os.environ["DRIVE_PROCESSED_FOLDER_ID"]

    files = drive_list_files(inbox_id)  # [{id,name,mimeType}, ...]
    results: List[List[str]] = []

    for f in files:
        file_id = f["id"]
        file_name = f["name"]

        # 1) scarica localmente
        local_path = drive_download_file(file_id, file_name)

        # 2) parsing etichetta (testo/immagine → dict campi)
        parsed: Dict[str, str] = parse_label(local_path)

        # 3) prepara riga da scrivere
        row = [
            _now_iso_utc(),              # Timestamp UTC
            file_name,                   # Image_File
            parsed.get("modello", ""),   # Modello
            parsed.get("articolo", ""),  # Articolo
            parsed.get("colore", ""),    # Colore
            parsed.get("taglia_fr", ""), # Taglia_FR
            parsed.get("barcode", ""),   # Barcode
            parsed.get("confidenza", ""),# Confidenza
            "OK" if any(parsed.values()) else "EMPTY",
        ]

        # 4) append su Sheets
        append_to_sheet(row)

        # 5) sposta originale in PROCESSED
        drive_move_file(file_id, processed_id)

        results.append(row)

    return results

import os, time, tempfile, logging, cv2, pathlib
from datetime import datetime
from gdrive import list_images, download_file, upload_image, move_file
from sheets import append_rows
from ai_client import parse_with_ai
from label_detector import BatchLabelProcessor

logger = logging.getLogger("pipeline")

INBOX  = os.environ.get("DRIVE_INBOX_FOLDER_ID")
PRE    = os.environ.get("DRIVE_PREPROCESSED_FOLDER_ID")  # opzionale
PROC   = os.environ.get("DRIVE_PROCESSED_FOLDER_ID")

def _ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def run_full_batch(limit=5):
    files = list_images(INBOX, page_size=limit)
    processed = []
    rows = []

    with tempfile.TemporaryDirectory() as td:
        crops_dir = os.path.join(td, "crops")
        pathlib.Path(crops_dir).mkdir(parents=True, exist_ok=True)
        detector = BatchLabelProcessor(output_dir=crops_dir)

        for f in files:
            fid, name = f["id"], f["name"]
            logger.info("start file | id=%s name=%s", fid, name)
            local = os.path.join(td, name)
            download_file(fid, local)

            # Detect + crop
            base_stem = pathlib.Path(name).stem
            crop_paths = detector.process_single_image(local, base_stem)
            logger.info("detected crops | file=%s count=%d", name, len(crop_paths))

            # Upload to PRE (optional)
            if PRE:
                for c in crop_paths:
                    upload_image(PRE, c, name=os.path.basename(c), mime="image/jpeg")

            # Parse each crop via AI
            for c in (crop_paths or [local]):  # fallback: usa immagine intera se 0 crop
                parsed = parse_with_ai(c)
                modello    = (parsed.get("modello") or "").strip()
                articolo   = (parsed.get("articolo") or "").strip()
                colore     = (parsed.get("colore") or "").strip()
                taglia_fr  = (parsed.get("taglia_fr") or "").strip()
                barcode    = (parsed.get("barcode") or "").strip()
                conf       = int(parsed.get("confidenza") or 0)
                stato = "OK" if barcode else ("REVIEW" if any([modello, articolo, colore, taglia_fr]) else "EMPTY")

                rows.append([_ts(), os.path.basename(c), modello, articolo, colore, taglia_fr, barcode, conf, stato])

            # Move original
            try:
                move_file(fid, PROC)
            except Exception:
                logger.exception("move_file failed | file=%s", name)

            processed.append({"file": name, "crops": len(crop_paths)})

    if rows:
        append_rows(rows)

    return {"processed": len(processed), "results": processed, "rows_written": len(rows)}

import os, json, logging, sys
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---- Logging ----
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("app")

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/")
def index():
    routes = sorted([str(r) for r in app.url_map.iter_rules()])
    return jsonify(routes), 200

@app.get("/debug/env")
def debug_env():
    present = {k: (k in os.environ and bool(os.environ.get(k))) for k in [
        "GOOGLE_CREDENTIALS_JSON",
        "DRIVE_INBOX_FOLDER_ID",
        "DRIVE_PREPROCESSED_FOLDER_ID",
        "DRIVE_PROCESSED_FOLDER_ID",
        "SHEET_ID",
        "LLM_API_KEY",
        "OPENAI_VISION_MODEL",
    ]}
    sa_email = ""
    try:
        info = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON","{}"))
        sa_email = info.get("client_email","")
    except Exception as e:
        logger.warning("Failed to read service account email: %s", e)
    return {"env_present": present, "service_account_email": sa_email}, 200

@app.get("/debug/drive-inbox")
def debug_drive_inbox():
    try:
        from gdrive import list_images
        fid = os.environ.get("DRIVE_INBOX_FOLDER_ID","")
        if not fid:
            return {"error":"MISSING_ENV","detail":"DRIVE_INBOX_FOLDER_ID not set"}, 400
        files = list_images(fid, page_size=100)
        return {"folder": fid, "count": len(files),
                "files":[{"id":x["id"],"name":x["name"],"mimeType":x["mimeType"]} for x in files]}, 200
    except Exception as e:
        logger.exception("debug_drive_inbox error")
        return {"error":"DRIVE_LIST_FAILED","detail": str(e)}, 500

@app.post("/process")
def process():
    from pipeline import run_full_batch
    limit = _env_int("BATCH_LIMIT", 5)
    if request.args.get("limit"):
        try: limit = int(request.args.get("limit"))
        except Exception: pass
    logger.info("Process start | limit=%s", limit)
    try:
        result = run_full_batch(limit=limit)
        logger.info("Process end | processed=%s rows_written=%s",
                    result.get("processed"), result.get("rows_written"))
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Process failed")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","10000")), debug=False)


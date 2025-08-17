# app.py
from flask import Flask, request, jsonify
import os, json

app = Flask(__name__)

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default

# ---- ROUTES ----

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/debug/env")
def debug_env():
    present = {k: (k in os.environ) for k in [
        "GOOGLE_CREDENTIALS_JSON",
        "DRIVE_INBOX_FOLDER_ID",
        "DRIVE_PREPROCESSED_FOLDER_ID",
        "DRIVE_PROCESSED_FOLDER_ID",
        "SHEET_ID",
        "LLM_API_KEY",
        "LLM_ENDPOINT",
    ]}
    sa_email = ""
    try:
        info = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON","{}"))
        sa_email = info.get("client_email","")
    except Exception:
        pass
    return {"env_present": present, "service_account_email": sa_email}, 200

@app.get("/debug/drive-inbox")
def debug_drive_inbox():
    try:
        from utils import drive_list_files
        fid = os.environ.get("DRIVE_INBOX_FOLDER_ID","")
        if not fid:
            return {"error":"MISSING_ENV","detail":"DRIVE_INBOX_FOLDER_ID not set"}, 400
        files = drive_list_files(fid)
        return {"folder": fid, "count": len(files),
                "files":[{"id":x["id"],"name":x["name"],"mimeType":x["mimeType"]} for x in files]}, 200
    except Exception as e:
        return {"error":"DRIVE_LIST_FAILED","detail": str(e)}, 500

@app.route("/process", methods=["POST"])
def process():
    try:
        from batch_label_processor import process_inbox
        limit_qs = request.args.get("limit")
        # Se hai una versione di pipeline con limit, usala; altrimenti ignoralo
        results = process_inbox()  # la tua funzione corrente non prende limit
        return jsonify({"processed": len(results), "results": results}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# opzionale: vedere le rotte disponibili
@app.get("/")
def index():
    return jsonify(sorted([str(r) for r in app.url_map.iter_rules()])), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","10000")), debug=False)

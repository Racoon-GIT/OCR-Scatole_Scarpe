from flask import Flask, request, jsonify
import os
from batch_label_processor import process_inbox

app = Flask(__name__)

@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200

@app.route("/process", methods=["POST"])
def process():
    try:
        results = process_inbox()
        return jsonify({"processed": len(results), "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

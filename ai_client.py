# ai_client.py
import os
import base64
import json
import re
from typing import Dict, Any
import requests

# Modello vision consigliato (puoi sovrascriverlo via ENV)
DEFAULT_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")

# Endpoint e chiave: imposta su Render
# - LLM_API_KEY = <la tua chiave OpenAI>
# - (opz.) LLM_ENDPOINT = https://api.openai.com/v1/chat/completions
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

def _b64_data_url(image_path: str) -> str:
    """Converte un file immagine in data URL base64 (JPEG di default)."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def _safe_json_parse(text: str) -> Dict[str, Any]:
    """
    Tenta di leggere JSON puro. Se non è valido, prova ad estrarre il primo blocco {...}.
    Ritorna dict (o {}).
    """
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}

def _normalize_value(s: Any) -> str:
    if s is None:
        return ""
    if isinstance(s, (int, float)):
        return str(s)
    return str(s).strip()

def parse_with_ai(image_path: str) -> Dict[str, Any]:
    """
    Chiama OpenAI Vision (GPT-4o family) per estrarre i campi dall'etichetta.
    Ritorna un dict con:
      - modello, articolo, colore, taglia_fr, barcode
      - confidenza (0..100), stato (OK/REVIEW)
    Se la chiave non è configurata, ritorna una risposta 'REVIEW' con campi vuoti.
    """
    if not LLM_API_KEY:
        return {
            "modello": "", "articolo": "", "colore": "",
            "taglia_fr": "", "barcode": "",
            "confidenza": 0, "stato": "REVIEW"
        }

    data_url = _b64_data_url(image_path)

    # Prompt “a prova di output”: chiediamo JSON *puro* con chiavi esatte.
    system_msg = (
        "Sei un parser di etichette Adidas. "
        "Leggi esclusivamente il testo stampato sull'etichetta e restituisci JSON PULITO con queste chiavi: "
        "modello, articolo, colore, taglia_fr, barcode. "
        "Non inventare: se un campo non è visibile, lascia stringa vuota."
    )
    user_msg = (
        "Estrai i campi dall'immagine:\n"
        "- modello (es. 'SAMBA OG J', 'GAZELLE INDOOR W', 'CAMPUS 00s W', 'SUPERSTAR II J')\n"
        "- articolo (es. IE3675, HQ8708; 1–2 lettere + 4–6 cifre)\n"
        "- colore (forma AAA/BBBBB/CCC; numeri ammessi es. GUM5)\n"
        "- taglia_fr (es. '37 1/3', '38 2/3', '40', ammessi ½ ⅓ ⅔)\n"
        "- barcode (EAN-13 sotto il codice a barre)\n\n"
        "Rispondi SOLO con JSON, senza testo extra. Esempio:\n"
        "{"
        "\"modello\":\"SAMBA OG J\","
        "\"articolo\":\"IE3675\","
        "\"colore\":\"FTWWHT/CBLACK/GUM5\","
        "\"taglia_fr\":\"37 1/3\","
        "\"barcode\":\"4067886691568\""
        "}"
    )

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_msg},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.0,
    }

    try:
        resp = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        # Chat Completions: risposta nel primo choice → message.content[0].text (o content string)
        content = ""
        try:
            msg = data["choices"][0]["message"]
            # Se multimodale, "content" può essere list of parts; prendiamo testo
            if isinstance(msg.get("content"), list):
                # nuove API a volte usano parti; cerchiamo il primo blocco text
                for part in msg["content"]:
                    if isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                        content = part.get("text", "") or part.get("output_text", "")
                        if content:
                            break
            else:
                content = msg.get("content", "")
        except Exception:
            content = ""

        parsed = _safe_json_parse(content)

        modello   = _normalize_value(parsed.get("modello"))
        articolo  = _normalize_value(parsed.get("articolo"))
        colore    = _normalize_value(parsed.get("colore"))
        taglia_fr = _normalize_value(parsed.get("taglia_fr"))
        barcode   = _normalize_value(parsed.get("barcode"))

        # Confidenza: +20 per campo presente
        conf = sum(20 for v in [modello, articolo, colore, taglia_fr, barcode] if v)
        stato = "OK" if barcode else "REVIEW"

        return {
            "modello": modello,
            "articolo": articolo,
            "colore": colore,
            "taglia_fr": taglia_fr,
            "barcode": barcode,
            "confidenza": conf,
            "stato": stato,
        }

    except requests.HTTPError as e:
        # Errore HTTP dell’API
        return {
            "modello": "", "articolo": "", "colore": "",
            "taglia_fr": "", "barcode": "",
            "confidenza": 0, "stato": f"REVIEW_HTTP_{e.response.status_code}"
        }
    except Exception as e:
        # Qualunque altra eccezione (timeout, parsing, ecc.)
        return {
            "modello": "", "articolo": "", "colore": "",
            "taglia_fr": "", "barcode": "",
            "confidenza": 0, "stato": "REVIEW_ERROR"
        }

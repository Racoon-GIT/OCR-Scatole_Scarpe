# ai_client.py
import os, base64, json
from typing import Dict

# SDK ufficiale OpenAI
from openai import OpenAI

# Modello consigliato (vision, costo basso, ottimo per OCR+parsing)
OPENAI_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")

def _b64_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def parse_with_ai(image_path: str) -> Dict:
    """
    Passa il crop dell'etichetta al modello vision e ottiene:
      modello, articolo, colore, taglia_fr, barcode
    Ritorna anche confidenza (stima) e stato (OK/REVIEW).
    Richiede OPENAI_API_KEY come env su Render.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # fallback per non bloccare la pipeline
        return {
            "modello": "", "articolo": "", "colore": "",
            "taglia_fr": "", "barcode": "",
            "confidenza": 0, "stato": "REVIEW"
        }

    client = OpenAI(api_key=api_key)

    data_url = _b64_data_url(image_path)

    # Prompt molto “guidato” per campi Adidas
    system_msg = (
        "Sei un parser di etichette scarpe adidas. "
        "Estrai SOLO i campi richiesti dal testo dell'etichetta: "
        "modello (es. 'SAMBA OG J' / 'CAMPUS 00s W' / 'SUPERSTAR II'), "
        "articolo (es. 'IE3675'), "
        "colore (formato AAA/BBBBB/CCC con numeri ammessi es. 'FTWWHT/CBLACK/GUM5'), "
        "taglia_fr (formato es. '37 1/3', '36 2/3', ammesse ½ ⅓ ⅔), "
        "barcode (EAN-13). "
        "Rispondi JSON puro, con chiavi: modello, articolo, colore, taglia_fr, barcode."
    )

    user_instructions = (
        "Analizza l'immagine e restituisci un JSON con i campi richiesti. "
        "Se un campo non è visibile, metti stringa vuota."
    )

    # Responses API: input multimodale con image_url (data URL)
    resp = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": [{"type": "text", "text": system_msg}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_instructions},
                    {"type": "input_image", "image_url": {"url": data_url}},
                ],
            },
        ],
        # opzionale: temperature bassa per massima fedeltà
        temperature=0.0,
    )

    # Estrai il testo della risposta (dovrebbe essere JSON)
    text = resp.output_text  # SDK nuovo espone output_text
    try:
        data = json.loads(text)
    except Exception:
        # se non è JSON perfetto, prova una ripulita banale
        import re
        json_candidate = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(json_candidate.group(0)) if json_candidate else {}

    modello   = (data.get("modello") or "").strip()
    articolo  = (data.get("articolo") or "").strip()
    colore    = (data.get("colore") or "").strip()
    taglia_fr = (data.get("taglia_fr") or "").strip()
    barcode   = (data.get("barcode") or "").strip()

    # Stima confidenza semplice: +20 per ogni campo presente
    conf = 0
    for v in [modello, articolo, colore, taglia_fr, barcode]:
        if v: conf += 20

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

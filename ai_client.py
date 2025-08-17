# ai_client.py
import os
import base64
import json
import re
from typing import Dict, Any
import requests

# ===== Config =====
DEFAULT_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")
LLM_ENDPOINT  = os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")
LLM_API_KEY   = os.environ.get("LLM_API_KEY", "")

# ===== Helpers base =====
def _b64_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    # assume jpeg (i crop li salviamo in jpg)
    return f"data:image/jpeg;base64,{b64}"

def _safe_json_parse(text: str) -> Dict[str, Any]:
    """Prova a parse-are JSON; se fallisce, estrae il primo {...}."""
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

def _nz(x: Any) -> str:
    return "" if x is None else str(x).strip()

# ===== Regex “tolleranti” =====
RE_ARTICOLO = re.compile(r"\b([A-Z]|[I1][A-Z])\s?([0-9]{4,6})\b")   # IE3675, I E 3675, 1E3675
RE_COLORE   = re.compile(r"\b[A-Z0-9]{3,}(?:/[A-Z0-9]{3,}){1,3}\b")  # FTWWHT/CBLACK/GUM5
RE_SIZE_FR  = re.compile(r"\b(3[0-9]|4[0-6])(?: ?(?:1/2|1/3|2/3)|[½⅓⅔])?\b")
RE_BARCODE13= re.compile(r"\b\d{13}\b")
RE_BARCODE_S= re.compile(r"(?:\d\D*){13,18}")  # EAN-13 con spazi/punti

def _normalize_article(s: str) -> str:
    s = (s or "").strip().upper().replace(" ", "")
    # 1E3675 -> IE3675
    s = re.sub(r"^1([A-Z])", r"I\1", s)
    # IE 3675 -> IE3675 già rimosso spazio
    return s

def _normalize_color(s: str) -> str:
    s = (s or "").upper().strip()
    s = s.replace("GUMS", "GUM5")  # S↔5
    # riduci duplici slash/spazi
    s = re.sub(r"\s+", "", s)
    return s

def _normalize_model(s: str) -> str:
    s = (s or "").upper()
    s = re.sub(r"\s+", " ", s).strip()
    # 00S stilistico
    s = s.replace(" 00S", " 00s").replace("00S", "00s")
    return s

def _normalize_size(s: str) -> str:
    # normalizza frazioni unicode
    s = (s or "").replace("½", " 1/2").replace("⅓", " 1/3").replace("⅔", " 2/3")
    return s.strip()

def _extract_size_with_header(text: str) -> str:
    """
    Trucchetto per tabella: trova riga header con F/FR e prende la "colonna"
    corrispondente dalla riga successiva.
    """
    lines = [re.sub(r"\s+", " ", L).strip() for L in text.splitlines() if L.strip()]
    hdr_i = -1; fpos = -1
    for i, L in enumerate(lines):
        U = L.upper()
        if (" F " in f" {U} " or " FR " in f" {U} ") and any(k in U for k in ["UK","US","D","J","E","FR"]):
            hdr_i = i
            fpos = U.find(" FR ") if " FR " in U else U.find(" F ")
            if fpos == -1: fpos = U.find("F")
            break
    if hdr_i != -1 and fpos != -1:
        for j in range(hdr_i+1, min(hdr_i+4, len(lines))):
            row = lines[j]
            if not re.search(r"\d", row):  # deve avere numeri
                continue
            win = row[max(0, fpos-6): min(len(row), fpos+10)]
            m = RE_SIZE_FR.search(win)
            if m:
                return _normalize_size(m.group(0))
    return ""

def _fallback_from_text(raw_text: str) -> Dict[str,str]:
    """
    Estrai i campi direttamente dal testo grezzo (se la risposta AI è lacunosa).
    """
    t = raw_text or ""
    out = {"modello": "", "articolo": "", "colore": "", "taglia_fr": "", "barcode": ""}

    # Articolo
    m = RE_ARTICOLO.search(t)
    if m:
        out["articolo"] = _normalize_article(m.group(0))

    # Colore
    m = RE_COLORE.search(t.upper())
    if m:
        out["colore"] = _normalize_color(m.group(0))

    # Taglia FR: prova tabella, poi regex generica
    size = _extract_size_with_header(t)
    if not size:
        m = RE_SIZE_FR.search(t)
        if m:
            size = _normalize_size(m.group(0))
    out["taglia_fr"] = size

    # Barcode
    m = RE_BARCODE13.search(t)
    if m:
        out["barcode"] = m.group(0)
    else:
        m = RE_BARCODE_S.search(t)
        if m:
            digits = re.sub(r"\D", "", m.group(0))
            if len(digits) >= 13:
                out["barcode"] = digits[:13]

    return out

# ===== Chiamata principale =====
def parse_with_ai(image_path: str) -> Dict[str, Any]:
    """
    Invia il crop etichetta al modello vision e restituisce:
      modello, articolo, colore, taglia_fr, barcode, confidenza, stato
    Robusto a JSON non perfetto e integra fallback regex.
    """
    # Se non c'è chiave, non blocchiamo la pipeline
    if not LLM_API_KEY:
        return {
            "modello": "", "articolo": "", "colore": "",
            "taglia_fr": "", "barcode": "",
            "confidenza": 0, "stato": "REVIEW"
        }

    data_url = _b64_data_url(image_path)

    system_msg = (
        "Sei un parser di etichette Adidas. "
        "Leggi solo ciò che è stampato. "
        "Rispondi esclusivamente con JSON PULITO con le chiavi: "
        "modello, articolo, colore, taglia_fr, barcode. "
        "Non inventare: se un campo non è visibile, lascia stringa vuota."
    )
    user_msg = (
        "Estrai i campi dall'immagine:\n"
        "- modello (es. 'SAMBA OG J', 'GAZELLE INDOOR W', 'CAMPUS 00s W', 'SUPERSTAR II J')\n"
        "- articolo (1–2 lettere + 4–6 cifre; es. IE3675, HQ8708; accetta spazi interni tipo 'IE 3675')\n"
        "- colore (AAA/BBBBB/CCC; numeri ammessi, es. 'FTWWHT/CBLACK/GUM5')\n"
        "- taglia_fr (es. '37 1/3', '38 2/3', '40', ammessi ½ ⅓ ⅔)\n"
        "- barcode (EAN-13 sotto il codice a barre)\n\n"
        "Rispondi SOLO con JSON, senza testo extra. Esempio:\n"
        "{\"modello\":\"SAMBA OG J\",\"articolo\":\"IE3675\",\"colore\":\"FTWWHT/CBLACK/GUM5\",\"taglia_fr\":\"37 1/3\",\"barcode\":\"4067886691568\"}"
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

    # ==== Chiamata API ====
    raw_text = ""
    try:
        resp = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        # Estrai testo dalla risposta Chat Completions
        content = ""
        try:
            msg = data["choices"][0]["message"]
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                        content = part.get("text", "") or part.get("output_text", "")
                        if content:
                            break
            else:
                content = msg.get("content", "")
        except Exception:
            content = ""
        raw_text = content

        parsed = _safe_json_parse(content)

        # ===== Post-processing tollerante =====
        modello   = _normalize_model(_nz(parsed.get("modello")))
        articolo  = _normalize_article(_nz(parsed.get("articolo")))
        colore    = _normalize_color(_nz(parsed.get("colore")))
        taglia_fr = _normalize_size(_nz(parsed.get("taglia_fr")))
        barcode   = _nz(parsed.get("barcode"))

        # Fix barcode se manca o non è 13 cifre
        if not re.fullmatch(r"\d{13}", barcode or ""):
            # prova a ripescare dal testo grezzo
            fb = _fallback_from_text(raw_text or "")
            barcode = fb.get("barcode", "") or barcode

        # Se mancano altri campi, usa fallback dal testo grezzo
        need_fb = any(not v for v in [modello, articolo, colore, taglia_fr])
        if need_fb:
            fb = _fallback_from_text(raw_text or "")
            modello   = modello or _normalize_model(fb.get("modello", ""))
            articolo  = articolo or _normalize_article(fb.get("articolo", ""))
            colore    = colore or _normalize_color(fb.get("colore", ""))
            taglia_fr = taglia_fr or _normalize_size(fb.get("taglia_fr", ""))

        # Confidenza: +20 per ciascun campo presente
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
        return {
            "modello": "", "articolo": "", "colore": "",
            "taglia_fr": "", "barcode": "",
            "confidenza": 0, "stato": f"REVIEW_HTTP_{getattr(e.response, 'status_code', 'ERR')}"
        }
    except Exception:
        # Ultimissimo fallback: nessuna risposta utile
        fb = _fallback_from_text(raw_text or "")
        conf = sum(20 for v in [fb.get("modello"), fb.get("articolo"), fb.get("colore"),
                                fb.get("taglia_fr"), fb.get("barcode")] if v)
        return {
            "modello": _normalize_model(fb.get("modello","")),
            "articolo": _normalize_article(fb.get("articolo","")),
            "colore": _normalize_color(fb.get("colore","")),
            "taglia_fr": _normalize_size(fb.get("taglia_fr","")),
            "barcode": fb.get("barcode",""),
            "confidenza": conf,
            "stato": "REVIEW" if not fb.get("barcode") else "OK",
        }

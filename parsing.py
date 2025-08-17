import re

RE_BARCODE = re.compile(r"\b(\d{12,14})\b")
RE_MODEL = re.compile(r"\b(STAN SMITH|CAMPUS\s*(?:00S|0OS|OOS|J|W)?|GAZELLE(?:\s*INDOOR)?(?:\s*W|J)?|SAMBA(?:\s*OG)?(?:\s*W|J)?|FORUM|SUPERSTAR(?:\s*II)?(?:\s*W|J)?)\b", re.IGNORECASE)
RE_ARTICOLO = re.compile(r"\b([A-Z0-9]{5,})\b")
RE_COLORE = re.compile(r"\b([A-Z]{3,5}/[A-Z]{3,5}/[A-Z0-9]{3,5})\b")
RE_TAGLIA = re.compile(r"\b([2-4][0-9])\b")

def parse_label(text_or_path):
    text = ""
    if isinstance(text_or_path, str) and text_or_path.lower().endswith((".jpg",".png")):
        with open(text_or_path, "rb") as f:
            text = f.read().decode("latin-1", errors="ignore")
    else:
        text = text_or_path

    return {
        "modello": match_or_none(RE_MODEL, text),
        "articolo": match_or_none(RE_ARTICOLO, text),
        "colore": match_or_none(RE_COLORE, text),
        "taglia_fr": match_or_none(RE_TAGLIA, text),
        "barcode": match_or_none(RE_BARCODE, text),
        "confidenza": 75
    }

def match_or_none(regex, text):
    m = regex.search(text)
    return m.group(0) if m else None

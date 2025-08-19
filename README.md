# OCR Etichette — Pipeline Completa (Render)

## Flusso
1. **INBOX (Drive)**: immagini con più scatole/etichette
2. **Detector (Sobel + componenti connesse)**: ritaglia le etichette (label_detector.py)
3. **PRE-PROCESSED (Drive)**: upload dei crop (opzionale ma consigliato)
4. **AI (OpenAI Vision)**: parsing campi (modello, articolo, colore, taglia_fr, barcode)
5. **Google Sheets**: append delle righe
6. **PROCESSED (Drive)**: sposta gli originali

## Endpoint
- `GET  /healthz`
- `GET  /debug/env`
- `GET  /debug/drive-inbox`
- `POST /process?limit=5`

## Variabili d'ambiente (Render)
- `GOOGLE_CREDENTIALS_JSON`
- `DRIVE_INBOX_FOLDER_ID`
- `DRIVE_PREPROCESSED_FOLDER_ID`  (opzionale)
- `DRIVE_PROCESSED_FOLDER_ID`
- `SHEET_ID`
- `LLM_API_KEY`
- (opz) `OPENAI_VISION_MODEL` (default `gpt-4o-mini`)
- (opz) `BATCH_LIMIT` (default 5)
- (opz) `LOG_LEVEL` (`INFO`/`DEBUG`)

## Start (senza Dockerfile)
Build: `pip install -r requirements.txt`  
Start: `sh -c "gunicorn -w 1 -k gthread --threads 8 --timeout 120 -b 0.0.0.0:$PORT app:app"`

## Log
Logging strutturato su stdout (moduli: app/gdrive/sheets/ai_client/pipeline).  
Ogni file processato logga: download, #crop, esito AI, append su Sheet, move in PROCESSED.


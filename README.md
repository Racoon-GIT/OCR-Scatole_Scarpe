# OCR Pipeline su Render

## Setup
1. Configura variabili d’ambiente su Render:
   - `GOOGLE_CREDENTIALS_JSON`
   - `DRIVE_INBOX_FOLDER_ID`
   - `DRIVE_PROCESSED_FOLDER_ID`
   - `SHEET_ID`

2. Deploy su Render come **Web Service**.

3. Test endpoint:
   - `GET /healthz`
   - `POST /process`

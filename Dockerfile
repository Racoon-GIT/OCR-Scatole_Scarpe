FROM python:3.10-slim

# Dipendenze runtime minime per OpenCV/PIL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
CMD ["sh","-c","gunicorn -w 1 -k gthread --threads 8 --timeout 120 -b 0.0.0.0:$PORT app:app"]


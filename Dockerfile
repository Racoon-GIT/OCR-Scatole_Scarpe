# Usa un'immagine Python leggera
FROM python:3.10-slim

# Imposta la working directory
WORKDIR /app

# Copia requirements e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice
COPY . .

# Porta usata da Render
ENV PORT=10000

# Comando di avvio
CMD ["sh", "-c", "gunicorn -w 1 -k gthread --threads 8 --timeout 120 -b 0.0.0.0:$PORT app:app"]

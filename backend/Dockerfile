# Backend-Image mit Tesseract (fuer echtes OCR). Auf Render als Docker-Web-Service.
FROM python:3.11-slim

# Tesseract + deutsche Sprachdaten fuer die Foto-Aufgaben-Erkennung
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render setzt $PORT
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

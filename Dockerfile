FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-eng \
        fonts-noto-core \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Fail the image build early if code is not compatible with Railway's Python 3.11 runtime.
RUN python scripts/preflight.py

CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 300 --graceful-timeout 30 --access-logfile - --error-logfile - app:app"]

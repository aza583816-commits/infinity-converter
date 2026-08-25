FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2

# =========================================================
# System engines
# - LibreOffice: Word / Excel / PowerPoint conversions
# - Tesseract: OCR Arabic + English
# - Ghostscript: advanced PDF compression
# - Java: required by Tabula
# - Fonts: Arabic + Latin document rendering
# =========================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        ghostscript \
        default-jre-headless \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-eng \
        fonts-noto-core \
        fonts-noto-extra \
        fonts-dejavu-core \
        fontconfig \
        ca-certificates \
        curl \
        tini \
        procps \
        nice && \
    fc-cache -f -v && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Install Python dependencies first for Docker layer caching
COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

# Application
COPY . .

# Make sure LibreOffice has a writable HOME
ENV HOME=/tmp

# Railway / Render health endpoint
EXPOSE 5000

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "4", \
     "--worker-class", "gthread", \
     "--timeout", "300", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    ghostscript \
    tesseract-ocr \
    tesseract-ocr-ara \
    fonts-noto-core \
    fonts-noto-extra \
    fontconfig \
    ca-certificates \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.v2.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY app.py ./app.py
COPY templates ./templates
COPY static ./static
COPY manifest.json ./manifest.json

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/infinity-converter \
    && chown -R appuser:appuser /app /tmp/infinity-converter
USER appuser

ENV TMPDIR=/tmp/infinity-converter
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "--keep-alive", "5", "app:app"]

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/appuser

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-eng \
        fonts-noto-core \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
USER appuser

# Fail the image build early if architecture, routes, security gates, AdSense/SEO,
# and representative real conversions do not match the shipped application.
RUN python scripts/preflight.py

# Run the complete regression suite in the same Python/system-library image that
# Railway will execute. Test persistence stays in /tmp and is never shipped as
# application data.
RUN DATABASE_URL=sqlite:////tmp/infinity-tests.db \
    PUBLIC_AUTH_ENABLED=0 \
    PUBLIC_BILLING_ENABLED=0 \
    pytest -q && rm -f /tmp/infinity-tests.db*

CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 240 --graceful-timeout 30 --access-logfile - --error-logfile - app:app"]

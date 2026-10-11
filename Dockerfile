FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/appuser \
    MALLOC_ARENA_MAX=2

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-eng \
        fonts-noto-core \
        fonts-dejavu-core \
        fonts-liberation \
        ca-certificates \
        util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/instance && chown appuser:appuser /app/instance
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
    python -m pytest -q -p no:cacheprovider && rm -f /tmp/infinity-tests.db*

# Verify actual source-to-output semantics before the new image can go live.
# These reports stay in /tmp and do not contain customer files.
RUN for profile in baseline mixed dense; do \
      IC_TEST_FIXTURE_PROFILE=$profile \
      IC_SEMANTIC_REPORT=/tmp/semantic-$profile.json \
      python scripts/semantic_output_audit.py || exit 1; \
    done && \
    for language in english arabic mixed; do \
      IC_STRESS_INCLUDE_NATIVE=1 \
      IC_STRESS_TOOLS=word-to-pdf,excel-to-pdf,ppt-to-pdf,txt-to-pdf,html-to-pdf,markdown-to-pdf,csv-to-pdf \
      IC_STRESS_LANGUAGE=$language \
      IC_SEMANTIC_REPORT=/tmp/native-$language.json \
      python scripts/stress_semantic_audit.py || exit 1; \
    done && rm -f /tmp/semantic-*.json /tmp/native-*.json

# Two web workers keep health/navigation responsive if one process is busy or a
# native library crashes. Expensive conversion capacity is still bounded across
# workers by the process-shared admission slots in core/admission.py. Both values
# remain environment-overridable for future Railway sizing changes.
CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-2} --threads ${WEB_THREADS:-2} --worker-tmp-dir /dev/shm --timeout 240 --graceful-timeout 30 --keep-alive 5 --max-requests 250 --max-requests-jitter 50 --access-logfile - --error-logfile - app:app"]

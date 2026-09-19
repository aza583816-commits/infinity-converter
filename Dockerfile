FROM python:3.11-slim-bookworm AS base

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
        ca-certificates \
        util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt constraints.txt ./

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -c constraints.txt -r requirements.txt && \
    python -m pip check

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/instance && chown appuser:appuser /app/instance
USER appuser

# Build/test stage: production code and native libraries are verified in the same
# base image, while pytest itself does not ship in the final runtime stage.
FROM base AS verification
USER root
RUN pip install --no-cache-dir -c constraints.txt -r requirements-test.txt
USER appuser
RUN python scripts/verify_constraints.py constraints.txt
RUN python scripts/preflight.py
RUN DATABASE_URL=sqlite:////tmp/infinity-tests.db \
    PUBLIC_AUTH_ENABLED=0 \
    PUBLIC_BILLING_ENABLED=0 \
    python -m pytest -q -p no:cacheprovider && rm -f /tmp/infinity-tests.db* \
    && touch /tmp/infinity-production-verified

# The runtime starts from the dependency-minimal base, but copying the marker
# forces Docker to build the verification stage first. No pytest/test runner is
# installed in this final image.
FROM base AS runtime
COPY --from=verification --chown=appuser:appuser /tmp/infinity-production-verified /tmp/infinity-production-verified
RUN python scripts/verify_constraints.py constraints.txt
USER appuser

# Two web workers keep health/navigation responsive if one process is busy or a
# native library crashes. Expensive conversion capacity is still bounded across
# workers by the process-shared admission slots in core/admission.py. Both values
# remain environment-overridable for future Railway sizing changes.
CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-2} --threads ${WEB_THREADS:-2} --worker-tmp-dir /dev/shm --timeout 240 --graceful-timeout 30 --keep-alive 5 --max-requests 250 --max-requests-jitter 50 --access-logfile - --error-logfile - app:app"]

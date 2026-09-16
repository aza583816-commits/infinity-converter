import logging
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

# A shared backend (normally Redis in production) makes limits consistent across
# Gunicorn workers and future replicas. memory:// remains a safe local fallback
# for development and single-process tests, but we make the production fallback
# visible in logs instead of silently assuming it is globally shared.
RATE_LIMIT_STORAGE_URI = (os.getenv("RATE_LIMIT_STORAGE_URI") or "memory://").strip() or "memory://"

if RATE_LIMIT_STORAGE_URI == "memory://" and os.getenv("RAILWAY_ENVIRONMENT"):
    logger.warning(
        "RATE_LIMIT_STORAGE_URI is memory://; limits are process-local. "
        "Configure a shared Redis backend before scaling web workers/replicas or enabling paid AI traffic."
    )

# Shared instance: created here (not in app_factory) so route modules can
# import and decorate endpoints without triggering circular imports.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri=RATE_LIMIT_STORAGE_URI,
    strategy="fixed-window",
)


def limiter_storage_uri() -> str:
    """Return the configured backend for diagnostics/tests without exposing secrets."""
    if RATE_LIMIT_STORAGE_URI.startswith("redis://") or RATE_LIMIT_STORAGE_URI.startswith("rediss://"):
        return "redis://"
    return RATE_LIMIT_STORAGE_URI

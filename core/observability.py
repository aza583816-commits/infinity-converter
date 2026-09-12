import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("infinity.converter")

@contextmanager
def timed_operation(name: str, **fields):
    started = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000)
        safe = " ".join(f"{k}={v}" for k, v in fields.items())
        logger.info("operation=%s duration_ms=%s %s", name, duration_ms, safe)

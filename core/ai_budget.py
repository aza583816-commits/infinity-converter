from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
_BUDGET_PATH = Path(os.getenv("AI_BUDGET_STATE_FILE", Path(tempfile.gettempdir()) / "infinity-ai-budget.json"))


def _daily_limit() -> int:
    try:
        return max(0, int(os.getenv("AI_MAX_ENHANCED_CALLS_PER_DAY", "250")))
    except ValueError:
        return 250


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def consume_enhanced_ai_budget() -> tuple[bool, int, int]:
    """Reserve one enhanced-provider call using a process-shared file lock.

    This is a hard cost fuse for the current Railway replica. It is deliberately
    independent of per-IP rate limiting. A future Redis-backed implementation can
    replace this transparently when replicas are scaled horizontally.
    """
    limit = _daily_limit()
    if limit == 0:
        return False, 0, 0

    _BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        handle = _BUDGET_PATH.open("a+", encoding="utf-8")
        try:
            try:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass

            handle.seek(0)
            try:
                state = json.load(handle)
            except (json.JSONDecodeError, ValueError):
                state = {}
            day = _today()
            count = int(state.get("count", 0)) if state.get("date") == day else 0
            if count >= limit:
                return False, count, limit
            count += 1
            handle.seek(0)
            handle.truncate()
            json.dump({"date": day, "count": count}, handle, separators=(",", ":"))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
            return True, count, limit
        finally:
            try:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            handle.close()

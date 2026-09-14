"""Process-shared admission control for expensive conversion work.

Gunicorn can run more than one worker so a slow native conversion cannot make the
whole web service unresponsive.  Plain ``threading.Semaphore`` objects do not
coordinate across worker processes, though, so this module uses small ``flock``
slot files on Linux.  Locks are held by an open file descriptor and the kernel
releases them automatically if a worker crashes, which gives us a simple
process-shared capacity gate without a queue server or stale lock cleanup.

On platforms without ``fcntl`` (mainly local Windows development) the module
falls back to in-process bounded semaphores.  Production runs on Linux, where the
file-backed gate is active.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

try:  # pragma: no cover - exercised on Linux in production/CI
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows development fallback
    fcntl = None


_ADMISSION_DIR = Path(os.getenv("ADMISSION_DIR", "/tmp/infinity-admission"))
_FALLBACK_LOCK = threading.Lock()
_FALLBACK_POOLS: dict[tuple[str, int], threading.BoundedSemaphore] = {}


class AdmissionToken:
    """A held admission slot. ``release`` is idempotent."""

    __slots__ = ("_fd", "_semaphore", "_released")

    def __init__(self, *, fd: int | None = None, semaphore: threading.BoundedSemaphore | None = None):
        self._fd = fd
        self._semaphore = semaphore
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._fd is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
        if self._semaphore is not None:
            self._semaphore.release()
            self._semaphore = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def _fallback_pool(name: str, slots: int) -> threading.BoundedSemaphore:
    key = (name, slots)
    with _FALLBACK_LOCK:
        pool = _FALLBACK_POOLS.get(key)
        if pool is None:
            pool = threading.BoundedSemaphore(slots)
            _FALLBACK_POOLS[key] = pool
        return pool


def acquire_slot(name: str, slots: int, timeout: float) -> AdmissionToken | None:
    """Acquire one named capacity slot within ``timeout`` seconds.

    A named pool consists of ``slots`` files.  Every Gunicorn worker in the same
    container sees the same files, so total expensive-work concurrency remains
    bounded even when web workers are multiplied for responsiveness.
    """
    slots = max(1, int(slots))
    timeout = max(0.0, float(timeout))

    if fcntl is None:
        semaphore = _fallback_pool(name, slots)
        if not semaphore.acquire(timeout=timeout):
            return None
        return AdmissionToken(semaphore=semaphore)

    _ADMISSION_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + timeout
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name)[:48] or "work"

    while True:
        for index in range(slots):
            path = _ADMISSION_DIR / f"{safe_name}-{index}.lock"
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                continue
            except Exception:
                os.close(fd)
                raise
            else:
                # Diagnostic only: the lock itself is the source of truth.
                os.ftruncate(fd, 0)
                os.write(fd, f"pid={os.getpid()}\n".encode("ascii", errors="ignore"))
                return AdmissionToken(fd=fd)

        if time.monotonic() >= deadline:
            return None
        time.sleep(min(0.025, max(0.001, deadline - time.monotonic())))


def admission_backend() -> str:
    return "flock" if fcntl is not None else "threading"

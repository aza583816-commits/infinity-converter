from __future__ import annotations

import shutil
import tempfile
import threading
import time
from pathlib import Path


DEFAULT_WORKSPACE_PREFIX = "infinity-v7-"
DEFAULT_STALE_WORKSPACE_SECONDS = 6 * 60 * 60
_SWEEP_INTERVAL_SECONDS = 15 * 60


def cleanup_stale_workspaces(
    *,
    root: Path | None = None,
    prefix: str = DEFAULT_WORKSPACE_PREFIX,
    older_than_seconds: int = DEFAULT_STALE_WORKSPACE_SECONDS,
    now: float | None = None,
) -> int:
    """Remove abandoned Infinity scratch directories after crashes/restarts.

    Normal request cleanup remains the primary lifecycle. This sweep is only a
    defensive recovery path for directories left behind by a killed worker or
    container. The default six-hour age is intentionally far above the request
    and Gunicorn timeouts so an active conversion is never a normal candidate.
    Symlinks are ignored and deletion is constrained to the selected temp root.
    """
    if older_than_seconds < 60:
        raise ValueError("older_than_seconds must be at least 60 seconds")

    root_path = Path(root or tempfile.gettempdir()).resolve()
    cutoff = (time.time() if now is None else float(now)) - older_than_seconds
    removed = 0
    try:
        candidates = list(root_path.iterdir())
    except OSError:
        return 0

    for candidate in candidates:
        try:
            if not candidate.name.startswith(prefix) or candidate.is_symlink() or not candidate.is_dir():
                continue
            resolved = candidate.resolve(strict=False)
            if resolved.parent != root_path:
                continue
            if candidate.stat().st_mtime > cutoff:
                continue
            shutil.rmtree(candidate)
            removed += 1
        except (FileNotFoundError, PermissionError, OSError):
            # Another worker may have cleaned it already, or the host may deny
            # deletion. Either case should never break a live request.
            continue
    return removed


class TempWorkspace:
    """Per-request scratch space with explicit lifetime control.

    Flask ``send_file`` can stream after the view returns, so API routes defer
    cleanup until the response iterable closes. A throttled stale-directory
    sweep also repairs scratch space left behind by abnormal worker termination.
    """

    _sweep_lock = threading.Lock()
    _last_sweep_monotonic = 0.0

    def __init__(self, *, prefix: str = DEFAULT_WORKSPACE_PREFIX):
        self._prefix = prefix
        self._tmp: tempfile.TemporaryDirectory | None = None
        self.path: Path | None = None
        self.input_dir: Path | None = None
        self.output_dir: Path | None = None
        self._closed = False

    @classmethod
    def _maybe_sweep_stale_workspaces(cls, *, prefix: str) -> None:
        current = time.monotonic()
        if current - cls._last_sweep_monotonic < _SWEEP_INTERVAL_SECONDS:
            return
        if not cls._sweep_lock.acquire(blocking=False):
            return
        try:
            current = time.monotonic()
            if current - cls._last_sweep_monotonic < _SWEEP_INTERVAL_SECONDS:
                return
            cleanup_stale_workspaces(prefix=prefix)
            cls._last_sweep_monotonic = current
        finally:
            cls._sweep_lock.release()

    def __enter__(self) -> "TempWorkspace":
        if self._tmp is not None:
            return self
        self._maybe_sweep_stale_workspaces(prefix=self._prefix)
        self._tmp = tempfile.TemporaryDirectory(prefix=self._prefix)
        self.path = Path(self._tmp.name).resolve()
        self.input_dir = self.path / "input"
        self.output_dir = self.path / "output"
        self.input_dir.mkdir(mode=0o700)
        self.output_dir.mkdir(mode=0o700)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()

    def cleanup(self) -> None:
        """Delete every temporary file once; safe to call repeatedly."""
        if self._closed:
            return
        self._closed = True
        if self._tmp is not None:
            self._tmp.cleanup()
        self._tmp = None

    def _require_open(self) -> Path:
        if self.path is None or self._closed:
            raise RuntimeError("مساحة المعالجة المؤقتة غير متاحة.")
        return self.path

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
            return True
        except ValueError:
            return False

    def contains(self, path: Path) -> bool:
        root = self._require_open()
        return self._is_within(Path(path), root)

    def contains_input(self, path: Path) -> bool:
        self._require_open()
        assert self.input_dir is not None
        return self._is_within(Path(path), self.input_dir)

    def contains_output(self, path: Path) -> bool:
        self._require_open()
        assert self.output_dir is not None
        return self._is_within(Path(path), self.output_dir)

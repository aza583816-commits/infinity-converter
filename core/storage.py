from __future__ import annotations

import tempfile
from pathlib import Path


class TempWorkspace:
    """Per-request scratch space with explicit lifetime control.

    The original implementation only supported ``with TempWorkspace()``. That
    is convenient for CPU work, but Flask's ``send_file`` can stream the result
    after the view has returned. Deleting the directory in ``__exit__`` can
    therefore race the response on some WSGI servers. 7.1 keeps context-manager
    compatibility while also exposing idempotent ``cleanup`` so API routes can
    defer deletion until the response closes.
    """

    def __init__(self, *, prefix: str = "infinity-v7-"):
        self._prefix = prefix
        self._tmp: tempfile.TemporaryDirectory | None = None
        self.path: Path | None = None
        self.input_dir: Path | None = None
        self.output_dir: Path | None = None
        self._closed = False

    def __enter__(self) -> "TempWorkspace":
        if self._tmp is not None:
            return self
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

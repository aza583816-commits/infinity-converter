import tempfile
from pathlib import Path

class TempWorkspace:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="infinity-v2-")
        self.path = Path(self._tmp.name)
        (self.path / "input").mkdir()
        (self.path / "output").mkdir()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._tmp.cleanup()

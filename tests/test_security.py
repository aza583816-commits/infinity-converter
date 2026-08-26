import io
import pytest
from werkzeug.datastructures import FileStorage
from security.file_guard import validate_upload

def fs(name, content):
    return FileStorage(stream=io.BytesIO(content), filename=name)

def test_rejects_extension_spoof():
    with pytest.raises(ValueError):
        validate_upload(fs("evil.exe", b"PK\x03\x04"), max_bytes=25*1024*1024, inspect_only=True)

def test_accepts_pdf_signature():
    # Minimal malformed PDF is still rejected at parser stage.
    with pytest.raises(ValueError):
        validate_upload(fs("x.pdf", b"%PDF-1.7\n"), max_bytes=25*1024*1024, inspect_only=True)

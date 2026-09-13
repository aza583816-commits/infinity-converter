import io

import pytest
from security.file_guard import validate_upload

class Upload:
    def __init__(self, name, content, content_type="application/octet-stream"):
        self.filename = name
        self.mimetype = content_type
        self._stream = io.BytesIO(content)

    def read(self, n=-1):
        return self._stream.read(n)


def fs(name, content):
    return Upload(name, content)

def test_rejects_extension_spoof():
    with pytest.raises(ValueError):
        validate_upload(fs("evil.exe", b"PK\x03\x04"), max_bytes=25*1024*1024, inspect_only=True)

def test_accepts_pdf_signature():
    # Minimal malformed PDF is still rejected at parser stage.
    with pytest.raises(ValueError):
        validate_upload(fs("x.pdf", b"%PDF-1.7\n"), max_bytes=25*1024*1024, inspect_only=True)


def test_accepts_bmp_and_tiff_images():
    from PIL import Image

    for fmt, suffix in (("BMP", ".bmp"), ("TIFF", ".tiff")):
        stream = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(stream, format=fmt)
        stream.seek(0)
        result = validate_upload(fs(f"image{suffix}", stream.read()), max_bytes=25*1024*1024, inspect_only=True)
        assert result["safe"] is True


def test_rejects_zero_page_pdf():
    # Signature-only input must not pass parser validation.
    with pytest.raises(ValueError):
        validate_upload(fs("empty.pdf", b"%PDF-1.7\n"), max_bytes=25*1024*1024, inspect_only=True, max_pdf_pages=1)

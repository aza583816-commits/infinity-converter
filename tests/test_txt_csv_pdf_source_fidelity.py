"""PDF text/CSV conversion must preserve Arabic, leading zeros and quoted newlines."""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pymupdf
import pytest

from converters import office


@pytest.mark.parametrize(
    ("filename", "payload", "required"),
    [
        ("bilingual.txt", "English 00123\nArabic السلامة 00123\n",
         ("English 00123", "Arabic السلامة 00123")),
        ("quoted.csv",
         'name,code,note\n"اسم، عربي",00123,"contains, comma"\n'
         '"Line break",00999,"line one\nline two"\n',
         ("name", "code", "note", "اسم، عربي", "00123",
          "contains, comma", "Line break", "00999", "line one line two")),
    ],
)
def test_real_pdf_fallback_retains_original_text_and_unicode(
    tmp_path: Path, monkeypatch, filename: str, payload: str, required: tuple[str, ...]
) -> None:
    source = tmp_path / filename
    source.write_text(payload, encoding="utf-8")
    destination = tmp_path / "output"

    def incomplete_native_pdf(command, *, timeout, env):
        candidate = destination / (Path(command[-1]).stem + ".pdf")
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((60, 90), "This PDF does not contain original data")
            document.save(candidate)

    monkeypatch.setattr(office, "_run_libreoffice", incomplete_native_pdf)
    actual = office.office_to_pdf(source, destination, timeout=30)

    with pymupdf.open(actual) as pdf:
        assert len(pdf) >= 1
        rendered = " ".join(
            unicodedata.normalize("NFKC", page.get_text("text")) for page in pdf
        )
        rendered = " ".join(rendered.split())
        for expected in required:
            assert expected in rendered, (filename, expected, rendered)
    assert source.read_text(encoding="utf-8") == payload

"""Regression: source identifiers and Arabic words must not pass as PDF substrings."""
from pathlib import Path

import pymupdf

from converters.office import _pdf_has_text_fragments


def _pdf(tmp_path: Path, body: str) -> Path:
    output = tmp_path / "rendered.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 60), body, fontsize=12)
        pdf.save(output)
    return output


def test_numeric_identifier_must_not_match_prefix_of_another_identifier(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path, "invoice 000012")
    assert not _pdf_has_text_fragments(pdf, ["00001"])
    assert _pdf_has_text_fragments(pdf, ["000012"])


def test_ascii_word_must_not_match_prefix_of_longer_word(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path, "safetychecks")
    assert not _pdf_has_text_fragments(pdf, ["safety"])
    assert _pdf_has_text_fragments(pdf, ["safetychecks"])


def test_complete_multifield_phrase_must_remain_intact(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path, "Safety ID 00123, 1250.50")
    assert _pdf_has_text_fragments(pdf, ["Safety ID 00123", "1250.50"])
    assert not _pdf_has_text_fragments(pdf, ["Safety ID 0012"])


def test_pdf_extractor_joined_arabic_and_ascii_cells_do_not_trigger_false_loss(monkeypatch) -> None:
    """Some PDF table extractors omit whitespace at Arabic/ASCII cell boundaries."""
    class FakePage:
        def get_text(self, kind: str) -> str:
            assert kind == "text"
            return "name\ncode\nاسم، عربي00123\n"

    class FakeDocument:
        def __enter__(self):
            return [FakePage()]

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(pymupdf, "open", lambda _path: FakeDocument())
    source_fields = ["name", "code", "اسم، عربي", "00123"]
    assert _pdf_has_text_fragments(Path("unused.pdf"), source_fields)
    assert not _pdf_has_text_fragments(Path("unused.pdf"), ["0012"])
    assert not _pdf_has_text_fragments(Path("unused.pdf"), ["اسم، عر"])

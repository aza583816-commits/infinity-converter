"""Arabic heading quality must be grounded in actual PDF visual content."""
from pathlib import Path

from converters.office import (
    _expected_html_headings,
    _pdf_contains_headings,
    _render_html_story_fallback,
)


def test_arabic_heading_requires_real_visual_readback(tmp_path: Path) -> None:
    source = tmp_path / "bilingual.html"
    source.write_text(
        '<!doctype html><html lang="ar"><head><meta charset="utf-8"></head>'
        '<body><h1>Infinity &amp; السلامة</h1><p>Safety 00123</p></body></html>',
        encoding="utf-8",
    )
    pdf = tmp_path / "rendered.pdf"
    _render_html_story_fallback(source, pdf)
    headings = _expected_html_headings(source)
    assert headings == ("Infinity & السلامة",)
    assert _pdf_contains_headings(pdf, headings)
    assert not _pdf_contains_headings(pdf, ("Infinity & الحريق",))

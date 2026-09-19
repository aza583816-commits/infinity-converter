"""Regression: HTML/Markdown PDF headings cannot silently disappear.

LibreOffice may render a paragraph while dropping an HTML heading. The
print-only HTML copy must preserve heading text and keep the uploaded file
unchanged before PDF conversion's independent content verification.
"""
from pathlib import Path

from converters.office import _html_pdf_heading_fallback


def test_html_heading_is_preserved_in_print_copy(tmp_path: Path) -> None:
    source = tmp_path / "fixture.html"
    original = ('<!doctype html><html><body>'
                '<h1>Infinity</h1><p>Hello world</p>'
                '<h2 class="secondary">Safety</h2></body></html>')
    source.write_text(original, encoding="utf-8")
    rendered = _html_pdf_heading_fallback(source, tmp_path)
    actual = rendered.read_text(encoding="utf-8")
    assert rendered != source
    assert rendered.suffix == ".html"
    assert "<h1>" not in actual and "<h2" not in actual
    assert '<p style="font-size:24pt;font-weight:bold">Infinity</p>' in actual
    assert '<p class="secondary" style="font-size:20pt;font-weight:bold">Safety</p>' in actual
    assert "<p>Hello world</p>" in actual
    assert source.read_text(encoding="utf-8") == original


def test_no_heading_does_not_rewrite_html(tmp_path: Path) -> None:
    source = tmp_path / "plain.html"
    source.write_text("<p>Hello world</p>", encoding="utf-8")
    assert _html_pdf_heading_fallback(source, tmp_path) == source

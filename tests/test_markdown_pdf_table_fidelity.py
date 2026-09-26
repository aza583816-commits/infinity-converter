"""Markdown PDF table text must remain readable and selectable, even with Arabic."""
from pathlib import Path
import re
import unicodedata

import pymupdf
import pytest
from pypdf import PdfReader

from converters.office import _pdf_contains_headings, markdown_to_html, markdown_to_pdf


_PRESENTATION_FORMS = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
_ARABIC_RUN = re.compile(r"[\u0600-\u06FF]+")


def _logical_pdf_text(text: str) -> str:
    """Canonicalize extractor-only Arabic presentation-form visual order.

    LibreOffice PDFs may expose Arabic presentation forms to pypdf in visual
    glyph order even though the page renders correctly. Correct only runs that
    originated as presentation-form glyphs; logical Arabic source text and
    ASCII/numeric identifiers are left untouched.
    """
    pieces = []
    for token in text.split():
        normalized = unicodedata.normalize("NFKC", token)
        if _PRESENTATION_FORMS.search(token):
            normalized = _ARABIC_RUN.sub(lambda match: match.group(0)[::-1], normalized)
        pieces.append(normalized)
    return " ".join(pieces)


@pytest.mark.parametrize(
    ("headers", "values"),
    [
        (("Name", "Code"), ("Safety", "00123")),
        (("Name", "Code", "Arabic"), ("Safety", "00123", "السلامة")),
        (("الاسم", "Code", "Description"), ("السلامة", "00123", "Fire safety")),
    ],
)
def test_markdown_pdf_table_preserves_complete_cells_without_vertical_letter_wrap(
    tmp_path: Path, headers: tuple[str, ...], values: tuple[str, ...]
) -> None:
    source = tmp_path / "table.md"
    source.write_text(
        "# Infinity / السلامة\n\n"
        + "| " + " | ".join(headers) + " |\n"
        + "| " + " | ".join("---" for _ in headers) + " |\n"
        + "| " + " | ".join(values) + " |\n",
        encoding="utf-8",
    )
    intermediate = tmp_path / "work"
    intermediate.mkdir()
    output = tmp_path / "output"
    pdf_path = markdown_to_pdf(source, intermediate, output, timeout=45)
    html = (intermediate / "table.html").read_text(encoding="utf-8")
    assert '<table width="100%"' in html, "PDF tables require explicit print width"

    reader = PdfReader(str(pdf_path))
    actual = _logical_pdf_text(" ".join(page.extract_text() or "" for page in reader.pages))
    # Arabic PDF text layers can expose visual-order glyphs even when the page
    # itself is correct. Validate Arabic through rendered-page OCR, while
    # requiring ordinary ASCII/numeric cells to remain complete selectable text.
    assert _pdf_contains_headings(pdf_path, ("Infinity / السلامة",)), actual[:350]
    for expected in (*headers, *values):
        if re.search(r"[\u0600-\u06FF]", expected):
            assert _pdf_contains_headings(pdf_path, (expected,)), (expected, actual[:500])
        else:
            assert _logical_pdf_text(expected) in actual, (expected, actual[:500])

    with pymupdf.open(pdf_path) as rendered:
        assert len(rendered) >= 1
        page_words = [word for page in rendered for word in page.get_text("words")]
        assert page_words
        for word in page_words:
            x0, y0, x1, y1 = word[:4]
            assert 0 <= x0 < x1 <= rendered[0].rect.width + 2
            assert 0 <= y0 < y1 <= rendered[0].rect.height + 2
        # The ASCII field must remain a single selectable word, not one
        # vertically stacked character per line in a collapsed table column.
        assert any(word[4] == "00123" for word in page_words), (
            "Code cell split into individual glyphs", page_words[:30]
        )

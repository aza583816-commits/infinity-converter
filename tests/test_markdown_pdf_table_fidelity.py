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
        # In RTL/LTR adjacent cells PyMuPDF can merge separate visible
        # words into one extractor token (for example Arabic+00123). Inspect
        # the rendered character geometry instead: all code digits must sit on
        # one horizontal baseline with real horizontal extent, not stack down
        # a collapsed column.
        code_geometry = None
        for page in rendered:
            raw = page.get_text("rawdict")
            for block in raw.get("blocks", []):
                for line in block.get("lines", []):
                    chars = [
                        char
                        for span in line.get("spans", [])
                        for char in span.get("chars", [])
                    ]
                    text = "".join(char.get("c", "") for char in chars)
                    index = text.find("00123")
                    if index >= 0:
                        code_geometry = chars[index:index + 5]
                        break
                if code_geometry:
                    break
            if code_geometry:
                break
        assert code_geometry and len(code_geometry) == 5, (
            "Code cell missing from rendered glyph geometry", page_words[:30]
        )
        y_centers = [
            (char["bbox"][1] + char["bbox"][3]) / 2 for char in code_geometry
        ]
        x_centers = [
            (char["bbox"][0] + char["bbox"][2]) / 2 for char in code_geometry
        ]
        assert max(y_centers) - min(y_centers) < 4, (
            "Code digits stacked vertically", [char["bbox"] for char in code_geometry]
        )
        assert max(x_centers) - min(x_centers) > 10, (
            "Code digits collapsed horizontally", [char["bbox"] for char in code_geometry]
        )

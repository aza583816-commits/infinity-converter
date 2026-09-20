"""Markdown PDF table text must remain readable and selectable, even with Arabic."""
from pathlib import Path

import pymupdf
import pytest
from pypdf import PdfReader

from converters.office import markdown_to_html, markdown_to_pdf


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
    actual = " ".join(page.extract_text() or "" for page in reader.pages)
    actual = " ".join(actual.split())
    assert "Infinity / السلامة" in actual, actual[:350]
    for expected in (*headers, *values):
        assert expected in actual, (expected, actual[:500])

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

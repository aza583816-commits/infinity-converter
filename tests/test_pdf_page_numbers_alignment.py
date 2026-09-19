"""Regression: right-position page numbers must actually be near the right edge."""
from pathlib import Path

import pymupdf
import pytest

from converters.pdf_advanced import add_page_numbers


@pytest.mark.parametrize(
    ("position", "at_top", "at_right"),
    [
        ("top-center", True, False),
        ("top-right", True, True),
        ("bottom-center", False, False),
        ("bottom-right", False, True),
    ],
)
def test_pdf_page_number_position_is_semantically_correct(
    tmp_path: Path, position: str, at_top: bool, at_right: bool
) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "numbered.pdf"
    with pymupdf.open() as pdf:
        for i in range(2):
            page = pdf.new_page(width=595, height=842)
            page.insert_text((50, 90), f"DOCUMENT PAGE {i + 1}")
        pdf.save(source)
    add_page_numbers(source, target, position)
    with pymupdf.open(target) as pdf:
        assert len(pdf) == 2
        for page_index, page in enumerate(pdf, start=1):
            words = page.get_text("words")
            numbered = [
                item for item in words
                if item[4] == str(page_index)
                and (item[1] < 35 if at_top else item[3] > page.rect.height - 35)
            ]
            assert len(numbered) == 1, (position, page_index, words)
            x0, y0, x1, y1 = numbered[0][:4]
            midpoint = (x0 + x1) / 2
            if at_right:
                assert midpoint > page.rect.width * 0.8, (position, midpoint)
            else:
                assert abs(midpoint - page.rect.width / 2) < page.rect.width * 0.1, (position, midpoint)
            assert "DOCUMENT PAGE" in page.get_text()

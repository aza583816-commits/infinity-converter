from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from converters.pdf_advanced import parse_page_order, reorder_pages


def _fixture(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=300, height=200)
    with path.open("wb") as handle:
        writer.write(handle)


def test_page_order_parser_preserves_user_permutation():
    assert parse_page_order("3,1,2", 3) == [2, 0, 1]


def test_pdf_reorder_changes_real_page_order(tmp_path):
    source = tmp_path / "source.pdf"
    output = tmp_path / "reordered.pdf"
    _fixture(source)
    reorder_pages(source, output, "3,1,2")
    reader = PdfReader(str(output))
    widths = [round(float(page.mediabox.width)) for page in reader.pages]
    assert widths == [300, 100, 200]


@pytest.mark.parametrize("spec", ["1,1,2", "1,2", "4,1,2", "1-3"])
def test_pdf_reorder_rejects_non_permutations(spec):
    with pytest.raises(ValueError):
        parse_page_order(spec, 3)

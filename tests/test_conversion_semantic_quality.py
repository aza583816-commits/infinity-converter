"""Semantic quality regressions for representative PDF, image and structured data inputs.

These are deliberately stronger than file-exists/HTTP-200 smoke checks; they
do not claim exhaustive visual correctness or coverage of all 162 operations.
"""
import csv
import json

import fitz
from PIL import Image
from pypdf import PdfReader

from converters import images, office_advanced, pdf


def _labeled_pdf(path, labels):
    doc = fitz.open()
    for label in labels:
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), label, fontsize=18)
    doc.save(str(path))
    doc.close()


def _page_text(path):
    with fitz.open(str(path)) as doc:
        return [page.get_text("text").strip() for page in doc]


def test_pdf_merge_preserves_page_order_and_text(tmp_path):
    first, second, output = (tmp_path / n for n in ("first.pdf", "second.pdf", "merged.pdf"))
    _labeled_pdf(first, ["FIRST PAGE", "SECOND PAGE"])
    _labeled_pdf(second, ["THIRD PAGE"])
    pdf.merge_pdfs([first, second], output)
    assert len(PdfReader(str(output)).pages) == 3
    texts = _page_text(output)
    assert [next(token for token in ("FIRST", "SECOND", "THIRD") if token in text) for text in texts] == ["FIRST", "SECOND", "THIRD"]


def test_pdf_extract_delete_and_split_preserve_selected_content(tmp_path):
    source = tmp_path / "source.pdf"
    _labeled_pdf(source, ["ALPHA", "BETA", "GAMMA"])
    picked, deleted = tmp_path / "picked.pdf", tmp_path / "deleted.pdf"
    pdf.extract_pdf_pages(source, picked, "1,3")
    pdf.delete_pdf_pages(source, deleted, "2")
    assert all("BETA" not in t for t in _page_text(picked))
    assert len(_page_text(picked)) == 2
    assert ["ALPHA", "GAMMA"] == [t.strip() for t in _page_text(deleted)]
    split_dir = tmp_path / "split"
    split_dir.mkdir()
    pieces = pdf.split_pdf_pages(source, split_dir)
    assert len(pieces) == 3
    assert [text[0].strip() for text in [_page_text(piece) for piece in pieces]] == ["ALPHA", "BETA", "GAMMA"]


def test_transparent_png_to_jpg_uses_white_background_and_retains_dimensions(tmp_path):
    source, output = tmp_path / "transparent.png", tmp_path / "result.jpg"
    image = Image.new("RGBA", (60, 40), (255, 0, 0, 0))
    # JPEG chroma subsampling can wash out a single colored pixel. A solid
    # patch represents an actual visible foreground region in a user image.
    for x in range(12, 29):
        for y in range(12, 29):
            image.putpixel((x, y), (255, 0, 0, 255))
    image.save(source)
    images.convert_image(source, output, "JPEG")
    with Image.open(output) as actual:
        assert actual.size == (60, 40)
        assert actual.format == "JPEG" and actual.mode == "RGB"
        background = actual.getpixel((0, 0))
        assert all(channel >= 245 for channel in background)
        foreground = actual.getpixel((20, 20))
        assert foreground[0] >= 220 and foreground[1] <= 60 and foreground[2] <= 60


def test_image_rotation_swaps_dimensions_and_moves_marker(tmp_path):
    source, output = tmp_path / "original.png", tmp_path / "rotated.png"
    original = Image.new("RGB", (80, 40), "white")
    for x in range(0, 15):
        for y in range(0, 15):
            original.putpixel((x, y), (0, 0, 0))
    original.save(source)
    images.rotate_image(source, output, 90)
    with Image.open(output) as result:
        assert result.size == (40, 80)
        # Clockwise rotation moves original upper-left into upper-right.
        assert result.getpixel((35, 5)) == (0, 0, 0)
        assert result.getpixel((5, 5)) == (255, 255, 255)


def test_csv_json_round_trip_preserves_unicode_and_cell_values(tmp_path):
    source, converted, recovered = [tmp_path / n for n in ("source.csv", "result.json", "again.csv")]
    rows = [{"name": "طالب", "value": "0012", "note": "a,b"}, {"name": "Alice", "value": "12.30", "note": "line\nbreak"}]
    with source.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "value", "note"])
        writer.writeheader()
        writer.writerows(rows)
    office_advanced.csv_to_json(source, converted)
    assert json.loads(converted.read_text(encoding="utf-8")) == rows
    office_advanced.json_to_csv(converted, recovered)
    with recovered.open(encoding="utf-8", newline="") as f:
        assert list(csv.DictReader(f)) == rows

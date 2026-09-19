"""Measured OCR quality using synthetic, non-sensitive ground-truth images.

Run with the same Tesseract English language pack installed in production.
These test both recognition accuracy and page-order retention, unlike simply
checking that OCR returned a nonempty file.
"""
from __future__ import annotations

import re
import shutil

import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont

from converters.ocr import ocr_image, ocr_pdf

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="Real Tesseract runtime required for OCR quality checks",
)

_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _render_text(path, lines):
    font = ImageFont.truetype(_FONT, 66)
    img = Image.new("RGB", (1700, 380), "white")
    draw = ImageDraw.Draw(img)
    for index, line in enumerate(lines):
        draw.text((70, 45 + index * 115), line, font=font, fill="black")
    img.save(path)


def _normalized(text):
    return re.sub(r"[^A-Z0-9 ]+", " ", text.upper()).split()


def _word_recall(reference, prediction):
    words = _normalized(reference)
    found = _normalized(prediction)
    return sum(word in found for word in words) / len(words)


def test_english_ocr_meets_ground_truth_word_recall(tmp_path):
    source, output = tmp_path / "source.png", tmp_path / "result.txt"
    expected = "SAFETY REPORT 2026\nFIRE CODE 101"
    _render_text(source, expected.splitlines())
    ocr_image(source, output, lang="en")
    actual = output.read_text(encoding="utf-8")
    assert _word_recall(expected, actual) >= 0.90, (expected, actual)


def test_scanned_pdf_ocr_keeps_two_pages_and_page_labels(tmp_path):
    source, output = tmp_path / "scan.pdf", tmp_path / "scan.txt"
    pdf = pymupdf.open()
    for label in ("SAFETY PAGE 101", "PHYSICS PAGE 202"):
        canvas = tmp_path / (label.split()[0] + ".png")
        _render_text(canvas, [label])
        page = pdf.new_page(width=595, height=842)
        page.insert_image(pymupdf.Rect(40, 80, 555, 250), filename=str(canvas))
    pdf.save(str(source))
    pdf.close()
    ocr_pdf(source, output, lang="en", max_pages=2, dpi=200)
    result = output.read_text(encoding="utf-8")
    assert "--- صفحة 1 ---" in result and "--- صفحة 2 ---" in result
    first, second = result.split("--- صفحة 2 ---", 1)
    assert "101" in first and "202" in second
    assert "SAFETY" in first.upper() and "PHYSICS" in second.upper()

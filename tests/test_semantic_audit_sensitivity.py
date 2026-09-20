"""Mutation tests: semantic acceptance must reject plausible but WRONG outputs.

A green engine smoke test or correct file extension cannot certify content.
These deliberately corrupted output files exercise the independent source-to-
output oracles themselves, making false-positive test regressions observable.
"""
from io import BytesIO
from pathlib import Path
import zipfile

import pymupdf
import pytest
from PIL import Image, ImageDraw

from scripts.semantic_output_audit import independent_oracle


def test_image_oracle_rejects_blank_image_with_correct_size_and_format(tmp_path: Path):
    source = tmp_path / "source.png"
    with Image.new("RGB", (320, 180), "white") as image:
        ImageDraw.Draw(image).rectangle((20, 20, 160, 100), fill="black")
        image.save(source)
    wrong = tmp_path / "blank.png"
    Image.new("RGB", (320, 180), "white").save(wrong)
    with pytest.raises(AssertionError):
        independent_oracle("image-to-png", source, wrong, tmp_path)


def test_pdf_extract_oracle_rejects_swapped_pages_with_valid_pdf(tmp_path: Path):
    source = tmp_path / "source.pdf"
    wrong = tmp_path / "swapped.pdf"
    with pymupdf.open() as original:
        for i in range(1, 4):
            page = original.new_page()
            page.insert_text((72, 72), f"Page {i} UNIQUE content")
        original.save(source)
    with pymupdf.open(source) as original, pymupdf.open() as reversed_pages:
        reversed_pages.insert_pdf(original, from_page=1, to_page=1)
        reversed_pages.insert_pdf(original, from_page=0, to_page=0)
        reversed_pages.save(wrong)
    with pytest.raises(AssertionError):
        independent_oracle("pdf-extract-pages", source, wrong, tmp_path)


def test_zip_oracle_rejects_valid_archive_that_drops_second_input(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("first input", encoding="utf-8")
    (tmp_path / "second-zip.txt").write_text("second input", encoding="utf-8")
    wrong = tmp_path / "only-one.zip"
    with zipfile.ZipFile(wrong, "w") as archive:
        archive.write(source, arcname="source.txt")
    with pytest.raises(AssertionError):
        independent_oracle("zip-create", source, wrong, tmp_path)


def test_pdf_to_text_oracle_rejects_only_first_page_with_nonempty_output(tmp_path: Path):
    source = tmp_path / "source.pdf"
    text = tmp_path / "incomplete.txt"
    with pymupdf.open() as pdf:
        for index in range(1, 4):
            page = pdf.new_page()
            page.insert_text((70, 80), f"ORIGINAL PAGE {index} UNIQUE")
        pdf.save(source)
    text.write_text("ORIGINAL PAGE 1 UNIQUE", encoding="utf-8")
    with pytest.raises(AssertionError):
        independent_oracle("pdf-to-text", source, text, tmp_path)

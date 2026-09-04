import io
import json
import zipfile

import pytest
import pymupdf
from PIL import Image
from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage

from app_factory import create_app
from converters.ocr import ocr_available


def upload(name, content):
    return (io.BytesIO(content), name)


def make_pdf(pages=1, text=None):
    stream = io.BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    stream.seek(0)
    return stream


def make_image(fmt="PNG", size=(60, 40), color=(30, 120, 200)):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format=fmt)
    stream.seek(0)
    return stream


def post(client, tool, files=None, single=None, param=None):
    data = {"tool": tool}
    if files:
        data["files"] = files
    if single:
        data["file"] = single
    if param is not None:
        data["param"] = param
    return client.post("/api/v2/convert", data=data, content_type="multipart/form-data")


@pytest.fixture
def client():
    return create_app().test_client()


# ---------- PDF engine ----------

def test_pdf_split_produces_one_pdf_per_page(client):
    response = post(client, "pdf-split", single=upload("doc.pdf", make_pdf(3).read()))
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert len(zf.namelist()) == 3


def test_pdf_extract_pages_range(client):
    response = post(client, "pdf-extract-pages", single=upload("doc.pdf", make_pdf(5).read()), param="2-3")
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) == 2


def test_pdf_delete_pages(client):
    response = post(client, "pdf-delete-pages", single=upload("doc.pdf", make_pdf(4).read()), param="1,2")
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) == 2


def test_pdf_delete_pages_requires_param(client):
    response = post(client, "pdf-delete-pages", single=upload("doc.pdf", make_pdf(2).read()))
    assert response.status_code == 400


def test_pdf_rotate(client):
    response = post(client, "pdf-rotate", single=upload("doc.pdf", make_pdf(1).read()), param="90")
    assert response.status_code == 200
    reader = PdfReader(io.BytesIO(response.data))
    assert reader.pages[0].rotation == 90


def test_pdf_compress_produces_valid_pdf(client):
    response = post(client, "pdf-compress", single=upload("doc.pdf", make_pdf(2).read()))
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) == 2


def test_pdf_to_jpg_and_png(client):
    response = post(client, "pdf-to-jpg", single=upload("doc.pdf", make_pdf(2).read()))
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        names = zf.namelist()
        assert len(names) == 2
        with Image.open(io.BytesIO(zf.read(names[0]))) as img:
            assert img.format == "JPEG"

    response = post(client, "pdf-to-png", single=upload("doc.pdf", make_pdf(1).read()))
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert len(zf.namelist()) == 1
        with Image.open(io.BytesIO(zf.read(zf.namelist()[0]))) as img:
            assert img.format == "PNG"


def test_image_to_pdf_combines_multiple_images(client):
    response = post(
        client,
        "image-to-pdf",
        files=[upload("a.png", make_image("PNG").read()), upload("b.jpg", make_image("JPEG").read())],
    )
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) == 2


def test_pdf_to_text_and_html(client):
    text_pdf = io.BytesIO()
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello Infinity Converter")
    doc.save(text_pdf)
    doc.close()
    text_pdf.seek(0)

    response = post(client, "pdf-to-text", single=upload("doc.pdf", text_pdf.read()))
    assert response.status_code == 200
    assert b"Hello" in response.data

    text_pdf.seek(0)
    response = post(client, "pdf-to-html", single=upload("doc.pdf", text_pdf.read()))
    assert response.status_code == 200
    assert b"<html" in response.data.lower()


def test_pdf_metadata_report(client):
    response = post(client, "pdf-metadata", single=upload("doc.pdf", make_pdf(3).read()))
    assert response.status_code == 200
    report = json.loads(response.data)
    assert report["pages"] == 3


# ---------- Image engine ----------

def test_image_resize_shrinks_dimensions(client):
    response = post(client, "image-resize", single=upload("a.png", make_image("PNG", (400, 300)).read()), param="100")
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.data)) as img:
        assert max(img.size) <= 100


def test_image_compress_reduces_size(client):
    big = make_image("PNG", (800, 600)).read()
    response = post(client, "image-compress", single=upload("a.png", big), param="40")
    assert response.status_code == 200
    assert len(response.data) > 0


def test_image_rotate(client):
    response = post(client, "image-rotate", single=upload("a.png", make_image("PNG", (100, 50)).read()), param="90")
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.data)) as img:
        assert img.size == (50, 100)


def test_image_to_webp(client):
    response = post(client, "image-to-webp", single=upload("a.png", make_image("PNG").read()))
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.data)) as img:
        assert img.format == "WEBP"


def test_image_batch_partial_failure_still_returns_zip(client):
    good = make_image("PNG").read()
    response = post(
        client,
        "image-to-jpg",
        files=[upload("a.png", good), upload("b.png", good)],
    )
    assert response.status_code == 200
    assert response.headers.get("X-Batch-Total") == "2"
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert len(zf.namelist()) == 2


# ---------- Archive tools ----------

def test_zip_create_and_extract_roundtrip(client):
    response = post(
        client,
        "zip-create",
        files=[upload("a.txt", b"hello"), upload("b.txt", b"world")],
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert sorted(zf.namelist()) == ["a.txt", "b.txt"]

    response2 = post(client, "zip-extract", single=upload("archive.zip", response.data))
    assert response2.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response2.data)) as zf:
        assert sorted(zf.namelist()) == ["a.txt", "b.txt"]


def test_zip_extract_rejects_path_traversal():
    import zipfile as zf_module

    malicious = io.BytesIO()
    with zf_module.ZipFile(malicious, "w") as zf:
        zf.writestr("../evil.txt", "pwn")
    malicious.seek(0)
    client = create_app().test_client()
    response = post(client, "zip-extract", single=upload("evil.zip", malicious.read()))
    assert response.status_code == 400


# ---------- Document tools ----------

def test_txt_to_pdf(client):
    response = post(client, "txt-to-pdf", single=upload("note.txt", "Hello Infinity\nArabic: اختبار".encode("utf-8")))
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) >= 1


def test_markdown_to_html_and_pdf(client):
    md = b"# Title\n\nSome **bold** text."
    response = post(client, "markdown-to-html", single=upload("note.md", md))
    assert response.status_code == 200
    assert b"<h1>" in response.data or b"<h1 " in response.data

    response = post(client, "markdown-to-pdf", single=upload("note.md", md))
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) >= 1


def test_csv_to_xlsx(client):
    csv_bytes = "name,age\nAli,30\nSara,25\n".encode("utf-8")
    response = post(client, "csv-to-xlsx", single=upload("data.csv", csv_bytes))
    assert response.status_code == 200
    assert len(response.data) > 0


def test_csv_to_pdf(client):
    csv_bytes = "name,age\nAli,30\n".encode("utf-8")
    response = post(client, "csv-to-pdf", single=upload("data.csv", csv_bytes))
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) >= 1


# ---------- Utility tools ----------

def test_file_hash_report(client):
    response = post(client, "file-hash", single=upload("note.txt", b"hello world"))
    assert response.status_code == 200
    report = json.loads(response.data)
    assert len(report["sha256"]) == 64


def test_file_info_report(client):
    response = post(client, "file-info", single=upload("note.txt", b"hello"))
    assert response.status_code == 200
    report = json.loads(response.data)
    assert report["filename"] == "note.txt"


# ---------- Security / edge cases ----------

def test_unicode_and_arabic_filenames_are_supported(client):
    response = post(client, "file-info", single=upload("تقرير مالي.txt", "بيانات عربية".encode("utf-8")))
    assert response.status_code == 200
    report = json.loads(response.data)
    assert "تقرير" in report["filename"]


def test_empty_file_rejected(client):
    response = post(client, "txt-to-pdf", single=upload("empty.txt", b""))
    assert response.status_code == 400


def test_corrupted_pdf_rejected(client):
    response = post(client, "pdf-compress", single=upload("bad.pdf", b"%PDF-1.4\nnot really a pdf"))
    assert response.status_code == 400


def test_invalid_page_spec_rejected(client):
    response = post(client, "pdf-extract-pages", single=upload("doc.pdf", make_pdf(2).read()), param="99")
    assert response.status_code == 400


# ---------- OCR (skipped automatically if tesseract is not installed) ----------

@pytest.mark.skipif(not ocr_available(), reason="tesseract is required for OCR tests")
def test_image_ocr_english(client):
    from PIL import ImageDraw

    img = Image.new("RGB", (300, 80), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 25), "HELLO WORLD", fill="black")
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    stream.seek(0)

    response = post(client, "image-ocr", single=upload("scan.png", stream.read()), param="en")
    assert response.status_code == 200
    assert b"HELLO" in response.data.upper() or b"HELLO" in response.data


@pytest.mark.skipif(not ocr_available(), reason="tesseract is required for OCR tests")
def test_pdf_ocr_english(client):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "INFINITY CONVERTER TEST", fontsize=24)
    stream = io.BytesIO()
    doc.save(stream)
    doc.close()
    stream.seek(0)

    response = post(client, "pdf-ocr", single=upload("scan.pdf", stream.read()), param="en")
    assert response.status_code == 200
    assert b"INFINITY" in response.data.upper()

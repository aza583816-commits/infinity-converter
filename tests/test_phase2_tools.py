import csv
import io
import zipfile

from PIL import Image
from pypdf import PdfReader, PdfWriter

from app_factory import create_app


def _pdf(pages=1):
    stream = io.BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def _image():
    stream = io.BytesIO()
    Image.new("RGB", (300, 100), "steelblue").save(stream, format="PNG")
    return stream.getvalue()


def _post(client, tool, data=None, files=None):
    payload = {"tool": tool, **(data or {})}
    if files:
        payload["files"] = [(io.BytesIO(content), name) for name, content in files]
    return client.post("/api/v2/convert", data=payload, content_type="multipart/form-data")


def test_phase2_pdf_tools_produce_valid_pdfs():
    client = create_app().test_client()
    booklet = _post(client, "pdf-booklet", {"layout": "2"}, [("notes.pdf", _pdf(5))])
    assert booklet.status_code == 200
    assert len(PdfReader(io.BytesIO(booklet.data)).pages) == 4

    optimized = _post(client, "lms-pdf-size-optimizer", {"target": "small"}, [("notes.pdf", _pdf(2))])
    assert optimized.status_code == 200
    assert len(PdfReader(io.BytesIO(optimized.data)).pages) == 2


def test_phase2_pdf_generators_produce_valid_pdfs():
    client = create_app().test_client()
    cover = _post(client, "assignment-cover-page", {"course": "CS101", "assignment": "Project", "student": "Alex", "due_date": "2026-09-01"})
    assert cover.status_code == 200
    assert len(PdfReader(io.BytesIO(cover.data)).pages) == 1

    omr = _post(client, "omr-bubble-sheet", {"questions": "100"})
    assert omr.status_code == 200
    assert len(PdfReader(io.BytesIO(omr.data)).pages) == 1


def test_bulk_certificates_returns_pdf_zip():
    client = create_app().test_client()
    response = _post(client, "bulk-certificate-maker", {"title": "Completion", "issuer": "Academy"}, [("people.csv", b"name\nAda\nGrace\n")])
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert len(archive.namelist()) == 2
        assert len(PdfReader(io.BytesIO(archive.read(archive.namelist()[0]))).pages) == 1


def test_phase2_image_tools_produce_pngs():
    client = create_app().test_client()
    resized = _post(client, "social-media-image-resizer", {"preset": "instagram-story", "fit": "pad"}, [("photo.png", _image())])
    assert resized.status_code == 200
    with Image.open(io.BytesIO(resized.data)) as image:
        assert image.format == "PNG"
        assert image.size == (1080, 1920)

    quote = _post(client, "quote-social-graphic", {"quote": "Make it simple, but significant.", "author": "Don Draper", "preset": "square", "theme": "ink"})
    assert quote.status_code == 200
    with Image.open(io.BytesIO(quote.data)) as image:
        assert image.format == "PNG"
        assert image.size == (1080, 1080)


def test_csv_merge_and_gift_formatter_produce_valid_text_outputs():
    client = create_app().test_client()
    merged = _post(client, "csv-merge-deduplicate", files=[("first.csv", b"name,score\nAda,10\nGrace,9\n"), ("second.csv", b"name,score\nAda,10\nLinus,8\n")])
    assert merged.status_code == 200
    assert list(csv.reader(io.StringIO(merged.data.decode("utf-8")))) == [["name", "score"], ["Ada", "10"], ["Grace", "9"], ["Linus", "8"]]

    gift = _post(client, "lms-question-bank-formatter", files=[("questions.txt", b"Q: What is 2 plus 2?\nA: 4\n\nQ: Capital of France?\nA: Paris\n")])
    assert gift.status_code == 200
    assert b"{=4}" in gift.data
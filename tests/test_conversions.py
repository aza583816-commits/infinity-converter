import io
import os
import shutil
import subprocess
import zipfile

import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage

from app_factory import create_app


def upload(name, content):
    return (io.BytesIO(content), name)


def make_pdf(pages=1):
    stream = io.BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=144, height=144)
    writer.add_metadata({"/Title": "Infinity test"})
    writer.write(stream)
    stream.seek(0)
    return stream


def make_image(format_name, mode="RGBA"):
    stream = io.BytesIO()
    image = Image.new(mode, (24, 16), (20, 120, 70, 128) if mode == "RGBA" else "white")
    image.save(stream, format=format_name)
    stream.seek(0)
    return stream


def _tesseract_has_language(language):
    binary = shutil.which("tesseract")
    if not binary:
        return False
    try:
        result = subprocess.run(
            [binary, "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return language in {line.strip() for line in result.stdout.splitlines()}


def test_pdf_engines_validate_real_outputs():
    client = create_app().test_client()
    response = client.post(
        "/api/v2/convert",
        data={"tool": "pdf-merge", "files": [upload("one.pdf", make_pdf().read()), upload("two.pdf", make_pdf(2).read())]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) == 3

    response = client.post(
        "/api/v2/convert",
        data={"tool": "pdf-split", "file": upload("source.pdf", make_pdf(2).read())},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        names = zf.namelist()
        assert len(names) == 2
        assert len(PdfReader(io.BytesIO(zf.read(names[0]))).pages) == 1


def test_image_engines_validate_real_outputs():
    client = create_app().test_client()
    response = client.post(
        "/api/v2/convert",
        data={"tool": "image-to-jpg", "file": upload("source.png", make_image("PNG").read())},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.data)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"

    response = client.post(
        "/api/v2/convert",
        data={"tool": "image-to-png", "file": upload("source.jpg", make_image("JPEG", "RGB").read())},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.data)) as image:
        assert image.format == "PNG"


def test_tool_rejects_valid_but_wrong_extension():
    client = create_app().test_client()
    response = client.post(
        "/api/v2/convert",
        data={"tool": "image-to-jpg", "file": upload("source.pdf", make_pdf().read())},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "تقبل" in response.get_json()["error"]


@pytest.mark.skipif(shutil.which("libreoffice") is None, reason="LibreOffice is required for Office integration tests")
def test_office_engine_converts_docx(tmp_path):
    from docx import Document

    source = tmp_path / "source.docx"
    document = Document()
    document.add_heading("Infinity conversion", level=1)
    document.add_paragraph("Arabic content: اختبار التحويل")
    document.save(source)

    client = create_app().test_client()
    with source.open("rb") as stream:
        response = client.post(
            "/api/v2/convert",
            data={"tool": "word-to-pdf", "file": FileStorage(stream=stream, filename="source.docx")},
            content_type="multipart/form-data",
        )
    assert response.status_code == 200
    assert len(PdfReader(io.BytesIO(response.data)).pages) >= 1


@pytest.mark.skipif(shutil.which("libreoffice") is None, reason="LibreOffice is required for legacy DOC integration tests")
def test_office_engine_converts_real_legacy_doc(tmp_path):
    """Generate a genuine OLE DOC, then exercise upload validation and conversion."""
    from docx import Document

    source = tmp_path / "legacy-source.docx"
    document = Document()
    document.add_heading("Infinity legacy DOC", level=1)
    document.add_paragraph("Real binary Word 97 input with Arabic: اختبار التحويل")
    document.save(source)

    profile = tmp_path / "fixture-profile"
    fixture = subprocess.run(
        [
            shutil.which("libreoffice"),
            "--headless",
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--convert-to",
            "doc:MS Word 97",
            "--outdir",
            str(tmp_path),
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        },
    )
    legacy = tmp_path / "legacy-source.doc"
    assert fixture.returncode == 0, fixture.stderr[-500:]
    assert legacy.read_bytes().startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")

    client = create_app().test_client()
    with legacy.open("rb") as stream:
        response = client.post(
            "/api/v2/convert",
            data={
                "tool": "word-to-pdf",
                "file": FileStorage(
                    stream=stream,
                    filename="legacy-source.doc",
                    content_type="application/msword",
                ),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/pdf")
    assert len(PdfReader(io.BytesIO(response.data)).pages) >= 1


@pytest.mark.skipif(not _tesseract_has_language("ara"), reason="Arabic Tesseract data is required")
def test_image_ocr_reads_arabic_content():
    """Verify the installed Arabic model does real work, beyond appearing in a package list."""
    image = Image.new("RGB", (1800, 760), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 100)
    lines = ("اختبار التحويل", "ملفات عربية واضحة", "تحويل ملفات")
    for index, line in enumerate(lines):
        position = (1650, 100 + index * 200)
        try:
            draw.text(position, line, fill="black", font=font, anchor="ra", direction="rtl")
        except (KeyError, ValueError):
            draw.text((100, position[1]), line, fill="black", font=font)
    stream = io.BytesIO()
    image.save(stream, format="PNG")

    client = create_app().test_client()
    response = client.post(
        "/api/v2/convert",
        data={"tool": "image-ocr", "param": "ar", "file": upload("arabic-scan.png", stream.getvalue())},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert any("\u0600" <= character <= "\u06ff" for character in text)

import json
import re
from pathlib import Path

import pymupdf
from pypdf import PdfReader, PdfWriter


def merge_pdfs(paths: list[Path], output: Path):
    writer = PdfWriter()
    first_reader = None
    for path in paths:
        reader = PdfReader(str(path))
        if first_reader is None:
            first_reader = reader
        for page in reader.pages:
            writer.add_page(page)
    if first_reader and first_reader.metadata:
        metadata = {
            key: value
            for key, value in first_reader.metadata.items()
            if key.startswith("/") and value is not None
        }
        if metadata:
            writer.add_metadata(metadata)
    with output.open("wb") as fh:
        writer.write(fh)


def _parse_page_spec(spec: str, page_count: int) -> list[int]:
    """Parse "1-3,5,7-8" into a sorted list of unique zero-based page indexes."""
    spec = (spec or "").strip()
    if not spec:
        return list(range(page_count))

    indexes: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", chunk)
        if not match:
            raise ValueError("صيغة نطاق الصفحات غير صالحة. استخدم مثل 1-3,5.")
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"نطاق الصفحات يجب أن يكون بين 1 و {page_count}.")
        indexes.update(range(start - 1, end))
    if not indexes:
        raise ValueError("لم يتم تحديد أي صفحة صالحة.")
    return sorted(indexes)


def split_pdf_pages(path: Path, output_dir: Path) -> list[Path]:
    """Split a PDF into one single-page PDF per page. Returns the produced file paths."""
    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError("ملف PDF لا يحتوي على صفحات.")
    produced = []
    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = output_dir / f"page-{index:03d}.pdf"
        with out_path.open("wb") as fh:
            writer.write(fh)
        produced.append(out_path)
    return produced


def extract_pdf_pages(path: Path, output: Path, page_spec: str = ""):
    reader = PdfReader(str(path))
    indexes = _parse_page_spec(page_spec, len(reader.pages))
    writer = PdfWriter()
    for index in indexes:
        writer.add_page(reader.pages[index])
    with output.open("wb") as fh:
        writer.write(fh)


def delete_pdf_pages(path: Path, output: Path, page_spec: str):
    reader = PdfReader(str(path))
    to_remove = set(_parse_page_spec(page_spec, len(reader.pages)))
    if len(to_remove) >= len(reader.pages):
        raise ValueError("لا يمكن حذف كل صفحات الملف.")
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index not in to_remove:
            writer.add_page(page)
    with output.open("wb") as fh:
        writer.write(fh)


def rotate_pdf(path: Path, output: Path, angle: int):
    if angle % 90 != 0:
        raise ValueError("زاوية الدوران يجب أن تكون من مضاعفات 90.")
    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle % 360)
        writer.add_page(page)
    with output.open("wb") as fh:
        writer.write(fh)


def compress_pdf(path: Path, output: Path):
    """Best-effort, format-safe compression: strips redundant objects and
    deflates streams. Does not re-encode images (keeps visual quality intact)."""
    doc = pymupdf.open(str(path))
    try:
        doc.save(str(output), garbage=4, deflate=True, deflate_images=True, clean=True)
    finally:
        doc.close()


def pdf_to_images(path: Path, output_dir: Path, fmt: str, dpi: int = 150) -> list[Path]:
    fmt = fmt.upper()
    ext = "jpg" if fmt == "JPEG" else fmt.lower()
    doc = pymupdf.open(str(path))
    try:
        if doc.page_count == 0:
            raise ValueError("ملف PDF لا يحتوي على صفحات.")
        produced = []
        zoom = dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(matrix=matrix)
            out_path = output_dir / f"page-{index:03d}.{ext}"
            pixmap.save(str(out_path))
            produced.append(out_path)
        return produced
    finally:
        doc.close()


def images_to_pdf(paths: list[Path], output: Path):
    from PIL import Image, ImageOps

    frames = []
    try:
        for image_path in paths:
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, "white")
                    alpha = img.convert("RGBA")
                    background.paste(alpha, mask=alpha.getchannel("A"))
                    img = background
                else:
                    img = img.convert("RGB")
                frames.append(img.copy())
        if not frames:
            raise ValueError("لم يتم رفع أي صورة صالحة.")
        first, rest = frames[0], frames[1:]
        first.save(output, format="PDF", save_all=True, append_images=rest)
    finally:
        for frame in frames:
            frame.close()


def pdf_to_text(path: Path, output: Path):
    doc = pymupdf.open(str(path))
    try:
        text = "\n\n".join(page.get_text("text") for page in doc)
        output.write_text(text, encoding="utf-8")
    finally:
        doc.close()


def pdf_to_html(path: Path, output: Path):
    doc = pymupdf.open(str(path))
    try:
        parts = ["<!doctype html><html><head><meta charset=\"utf-8\"></head><body>"]
        for page in doc:
            parts.append(page.get_text("html"))
        parts.append("</body></html>")
        output.write_text("\n".join(parts), encoding="utf-8")
    finally:
        doc.close()


def pdf_metadata_report(path: Path, output: Path):
    reader = PdfReader(str(path))
    meta = reader.metadata or {}
    report = {
        "pages": len(reader.pages),
        "encrypted": reader.is_encrypted,
        "metadata": {str(key): str(value) for key, value in dict(meta).items()},
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

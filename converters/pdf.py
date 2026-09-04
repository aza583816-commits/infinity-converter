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


def optimize_pdf_for_lms(path: Path, output: Path, target: str):
    profiles = {
        "small": (180, 120, 45),
        "medium": (240, 160, 65),
        "large": (300, 220, 80),
    }
    if target not in profiles:
        raise ValueError("خيار حجم PDF غير صالح.")
    threshold, dpi, quality = profiles[target]
    doc = pymupdf.open(str(path))
    try:
        doc.rewrite_images(dpi_threshold=threshold, dpi_target=dpi, quality=quality)
        doc.save(str(output), garbage=4, deflate=True, deflate_images=True, clean=True)
    finally:
        doc.close()


def make_booklet(path: Path, output: Path, layout: str):
    if layout not in {"2", "4"}:
        raise ValueError("اختر صفحتين أو أربع صفحات في الورقة.")
    source = pymupdf.open(str(path))
    result = pymupdf.open()
    try:
        if source.page_count < 1:
            raise ValueError("ملف PDF لا يحتوي على صفحات.")
        if layout == "2":
            total = ((source.page_count + 3) // 4) * 4
            imposed = []
            for sheet in range(total // 4):
                imposed.extend(((total - 1) - sheet * 2, sheet * 2, sheet * 2 + 1, (total - 2) - sheet * 2))
            slots = ((36, 36, 401, 559), (441, 36, 806, 559))
            for index in range(0, len(imposed), 2):
                page = result.new_page(width=842, height=595)
                for slot, source_index in zip(slots, imposed[index:index + 2]):
                    if source_index < source.page_count:
                        page.show_pdf_page(pymupdf.Rect(slot), source, source_index, keep_proportion=True)
        else:
            slots = ((30, 30, 287, 401), (308, 30, 565, 401), (30, 441, 287, 812), (308, 441, 565, 812))
            for start in range(0, source.page_count, 4):
                page = result.new_page(width=595, height=842)
                for slot, source_index in zip(slots, range(start, min(start + 4, source.page_count))):
                    page.show_pdf_page(pymupdf.Rect(slot), source, source_index, keep_proportion=True)
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        source.close()


def _english_text(value: str, label: str, *, required: bool = False, limit: int = 160) -> str:
    value = (value or "").strip()
    if required and not value:
        raise ValueError(f"{label} مطلوب.")
    if len(value) > limit or any(ord(char) > 127 for char in value):
        raise ValueError(f"{label} يجب أن يكون نصًا إنجليزيًا قصيرًا.")
    return value


def create_assignment_cover(output: Path, options: dict):
    course = _english_text(options.get("course"), "Course", required=True)
    assignment = _english_text(options.get("assignment"), "Assignment title", required=True)
    student = _english_text(options.get("student"), "Student name", required=True)
    instructor = _english_text(options.get("instructor"), "Instructor")
    due_date = _english_text(options.get("due_date"), "Due date")
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.draw_rect(pymupdf.Rect(48, 48, 547, 794), color=(0.08, 0.18, 0.32), width=1.5)
        page.insert_textbox(pymupdf.Rect(72, 130, 523, 225), "ASSIGNMENT COVER PAGE", fontname="helv", fontsize=24, align=pymupdf.TEXT_ALIGN_CENTER)
        lines = [("Course", course), ("Assignment", assignment), ("Student", student), ("Instructor", instructor or "-"), ("Due date", due_date or "-")]
        top = 305
        for label, value in lines:
            page.insert_text((100, top), f"{label}:", fontname="helv", fontsize=12)
            page.insert_textbox(pymupdf.Rect(205, top - 16, 490, top + 8), value, fontname="helv", fontsize=12)
            page.draw_line((100, top + 14), (490, top + 14), color=(0.55, 0.58, 0.62), width=0.5)
            top += 68
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()


def create_omr_sheet(output: Path, question_count: int):
    if question_count not in {20, 50, 100}:
        raise ValueError("عدد الأسئلة غير صالح.")
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(pymupdf.Rect(50, 35, 545, 65), "OMR ANSWER SHEET", fontname="helv", fontsize=17, align=pymupdf.TEXT_ALIGN_CENTER)
        page.insert_text((55, 92), "Name:", fontname="helv", fontsize=10)
        page.draw_line((95, 94), (300, 94), color=(0, 0, 0), width=0.7)
        page.insert_text((330, 92), "ID:", fontname="helv", fontsize=10)
        page.draw_line((355, 94), (540, 94), color=(0, 0, 0), width=0.7)
        rows_per_column = (question_count + 1) // 2
        for number in range(1, question_count + 1):
            column = 0 if number <= rows_per_column else 1
            row = number - 1 if column == 0 else number - rows_per_column - 1
            x = 65 + column * 270
            y = 130 + row * min(13, 620 / max(rows_per_column, 1))
            page.insert_text((x, y + 3), str(number), fontname="helv", fontsize=7)
            for choice in range(4):
                center = pymupdf.Point(x + 35 + choice * 29, y)
                page.draw_circle(center, 6, color=(0, 0, 0), width=0.7)
                page.insert_text((center.x - 2.4, y + 2.5), "ABCD"[choice], fontname="helv", fontsize=5)
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()


def create_certificate(output: Path, name: str, title: str, issuer: str):
    name = _english_text(name, "CSV name", required=True)
    title = _english_text(title, "Certificate title", required=True)
    issuer = _english_text(issuer, "Issuer")
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=842, height=595)
        page.draw_rect(pymupdf.Rect(28, 28, 814, 567), color=(0.65, 0.48, 0.12), width=3)
        page.insert_textbox(pymupdf.Rect(85, 105, 757, 165), title.upper(), fontname="helv", fontsize=28, align=pymupdf.TEXT_ALIGN_CENTER)
        page.insert_textbox(pymupdf.Rect(100, 205, 742, 235), "This certificate is presented to", fontname="helv", fontsize=15, align=pymupdf.TEXT_ALIGN_CENTER)
        page.insert_textbox(pymupdf.Rect(80, 260, 762, 320), name, fontname="helv", fontsize=30, align=pymupdf.TEXT_ALIGN_CENTER)
        page.insert_textbox(pymupdf.Rect(100, 390, 742, 420), f"Issued by {issuer or 'Infinity Converter'}", fontname="helv", fontsize=13, align=pymupdf.TEXT_ALIGN_CENTER)
        doc.save(str(output), garbage=4, deflate=True)
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

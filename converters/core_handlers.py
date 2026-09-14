"""First-class handlers for the stable core conversion surface.

These adapters are intentionally boring: each one maps one public tool contract to
one focused converter module.  They replace runtime dispatch through the historical
``legacy_handlers`` module without rewriting the proven conversion implementations.
The legacy module stays available as a compatibility layer while migration continues.
"""
from __future__ import annotations

from pathlib import Path

from config.settings import settings
from converters import archive, archive_advanced, images, ocr, office, pdf, utility

_UNSAFE_NAME_CHARS = '\\/:*?"<>|'


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "file").stem.strip()
    cleaned = "".join(ch for ch in stem if ch not in _UNSAFE_NAME_CHARS).strip()
    return (cleaned or "file")[:80]


def _unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while f"{stem}-{counter}{suffix}" in used:
        counter += 1
    unique = f"{stem}-{counter}{suffix}"
    used.add(unique)
    return unique


def _archive_entries(safe_inputs):
    used: set[str] = set()
    entries = []
    for item in safe_inputs:
        name = Path(item["filename"]).name or "file"
        entries.append((item["path"], _unique_name(name, used)))
    return entries


# Multiple inputs -> one output -------------------------------------------------

def pdf_merge(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Merged.pdf"
    pdf.merge_pdfs([item["path"] for item in safe_inputs], output)
    return output, "application/pdf"


def images_to_pdf(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Images.pdf"
    pdf.images_to_pdf([item["path"] for item in safe_inputs], output)
    return output, "application/pdf"


def zip_create(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Archive.zip"
    archive.create_zip(_archive_entries(safe_inputs), output)
    return output, "application/zip"


def tar_create(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Archive.tar"
    archive_advanced.create_tar(_archive_entries(safe_inputs), output)
    return output, "application/x-tar"


CORE_COMBINE_HANDLERS = {
    "pdf-merge": pdf_merge,
    "image-to-pdf": images_to_pdf,
    "zip-create": zip_create,
    "tar-create": tar_create,
}


# One input -> one or more outputs ---------------------------------------------
def pdf_split(safe_input, output_dir, param, timeout, max_pdf_pages):
    pages = pdf.split_pdf_pages(safe_input["path"], output_dir)
    return [(path, "application/pdf") for path in pages]


def pdf_extract_pages(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-extracted.pdf"
    pdf.extract_pdf_pages(safe_input["path"], out, param)
    return [(out, "application/pdf")]


def pdf_delete_pages(safe_input, output_dir, param, timeout, max_pdf_pages):
    if not (param or "").strip():
        raise ValueError("حدد الصفحات المطلوب حذفها، مثل 1-2,5.")
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-edited.pdf"
    pdf.delete_pdf_pages(safe_input["path"], out, param)
    return [(out, "application/pdf")]


def pdf_rotate(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        angle = int((param or "90").strip())
    except ValueError as exc:
        raise ValueError("زاوية الدوران يجب أن تكون رقمًا صحيحًا.") from exc
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-rotated.pdf"
    pdf.rotate_pdf(safe_input["path"], out, angle)
    return [(out, "application/pdf")]


def pdf_compress(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-compressed.pdf"
    pdf.compress_pdf(safe_input["path"], out)
    return [(out, "application/pdf")]


def _pdf_to_images(fmt: str, mime: str):
    def handler(safe_input, output_dir, param, timeout, max_pdf_pages):
        produced = pdf.pdf_to_images(safe_input["path"], output_dir, fmt)
        return [(path, mime) for path in produced]
    return handler


def pdf_to_text(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.txt"
    pdf.pdf_to_text(safe_input["path"], out)
    return [(out, "text/plain")]


def pdf_to_html(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.html"
    pdf.pdf_to_html(safe_input["path"], out)
    return [(out, "text/html")]


def pdf_metadata(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-metadata.json"
    pdf.pdf_metadata_report(safe_input["path"], out)
    return [(out, "application/json")]


def pdf_ocr(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-ocr.txt"
    ocr.ocr_pdf(safe_input["path"], out, lang=param or "ar+en", max_pages=settings.max_ocr_pages)
    return [(out, "text/plain")]


def _image_convert(fmt: str, ext: str, mime: str):
    def handler(safe_input, output_dir, param, timeout, max_pdf_pages):
        out = output_dir / f"{_safe_stem(safe_input['filename'])}.{ext}"
        images.convert_image(safe_input["path"], out, fmt)
        return [(out, mime)]
    return handler


def image_resize(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        max_dimension = int((param or "1600").strip())
    except ValueError as exc:
        raise ValueError("أبعاد الصورة يجب أن تكون رقمًا صحيحًا.") from exc
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-resized.jpg"
    images.resize_image(safe_input["path"], out, max_dimension)
    return [(out, "image/jpeg")]


def image_compress(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        quality = int((param or "70").strip())
    except ValueError as exc:
        raise ValueError("جودة الضغط يجب أن تكون رقمًا صحيحًا.") from exc
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-compressed.jpg"
    images.compress_image(safe_input["path"], out, quality)
    return [(out, "image/jpeg")]


def image_rotate(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        angle = int((param or "90").strip())
    except ValueError as exc:
        raise ValueError("زاوية الدوران يجب أن تكون رقمًا صحيحًا.") from exc
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-rotated.jpg"
    images.rotate_image(safe_input["path"], out, angle)
    return [(out, "image/jpeg")]


def image_ocr(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-ocr.txt"
    ocr.ocr_image(safe_input["path"], out, lang=param or "ar+en")
    return [(out, "text/plain")]


def office_to_pdf(safe_input, output_dir, param, timeout, max_pdf_pages):
    produced = office.office_to_pdf(safe_input["path"], output_dir, timeout=timeout)
    renamed = output_dir / f"{_safe_stem(safe_input['filename'])}.pdf"
    if produced != renamed:
        produced.replace(renamed)
    return [(renamed, "application/pdf")]


def markdown_to_html(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.html"
    office.markdown_to_html(safe_input["path"], out)
    return [(out, "text/html")]


def markdown_to_pdf(safe_input, output_dir, param, timeout, max_pdf_pages):
    workspace_input = safe_input["path"].parent
    produced = office.markdown_to_pdf(safe_input["path"], workspace_input, output_dir, timeout=timeout)
    renamed = output_dir / f"{_safe_stem(safe_input['filename'])}.pdf"
    if produced != renamed:
        produced.replace(renamed)
    return [(renamed, "application/pdf")]


def csv_to_xlsx(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.xlsx"
    office.csv_to_xlsx(safe_input["path"], out)
    return [(out, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]


def zip_extract(safe_input, output_dir, param, timeout, max_pdf_pages):
    extracted = archive.extract_zip(safe_input["path"], output_dir / "extracted")
    return [(path, "application/octet-stream") for path in extracted]


def file_hash(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-hash.json"
    utility.hash_report(safe_input["path"], out, safe_input["filename"])
    return [(out, "application/json")]


def file_info(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-info.json"
    utility.file_info_report(safe_input, out)
    return [(out, "application/json")]


CORE_SINGLE_HANDLERS = {
    "pdf-split": pdf_split,
    "pdf-extract-pages": pdf_extract_pages,
    "pdf-delete-pages": pdf_delete_pages,
    "pdf-rotate": pdf_rotate,
    "pdf-compress": pdf_compress,
    "pdf-to-jpg": _pdf_to_images("JPEG", "image/jpeg"),
    "pdf-to-png": _pdf_to_images("PNG", "image/png"),
    "pdf-to-text": pdf_to_text,
    "pdf-to-html": pdf_to_html,
    "pdf-metadata": pdf_metadata,
    "pdf-ocr": pdf_ocr,
    "image-to-jpg": _image_convert("JPEG", "jpg", "image/jpeg"),
    "image-to-png": _image_convert("PNG", "png", "image/png"),
    "image-to-webp": _image_convert("WEBP", "webp", "image/webp"),
    "image-resize": image_resize,
    "image-compress": image_compress,
    "image-rotate": image_rotate,
    "image-ocr": image_ocr,
    "word-to-pdf": office_to_pdf,
    "excel-to-pdf": office_to_pdf,
    "ppt-to-pdf": office_to_pdf,
    "txt-to-pdf": office_to_pdf,
    "html-to-pdf": office_to_pdf,
    "csv-to-pdf": office_to_pdf,
    "markdown-to-html": markdown_to_html,
    "markdown-to-pdf": markdown_to_pdf,
    "csv-to-xlsx": csv_to_xlsx,
    "zip-extract": zip_extract,
    "file-hash": file_hash,
    "file-info": file_info,
}

MIGRATED_TOOL_IDS = frozenset(CORE_COMBINE_HANDLERS) | frozenset(CORE_SINGLE_HANDLERS)

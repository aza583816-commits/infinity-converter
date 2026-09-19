"""First-class adapters for the 6.x advanced conversion families.

The underlying converter modules remain small and domain-focused. This module owns
only the public-tool-to-function mapping, so the runtime registry no longer needs
to dispatch these 59 tools through the historical compatibility module.
"""
from __future__ import annotations

from pathlib import Path

from converters import (
    archive,
    archive_advanced,
    image_advanced,
    office_advanced,
    ocr_advanced,
    pdf_advanced,
    utility_advanced,
)

_UNSAFE_NAME_CHARS = '\\/:*?"<>|'


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "file").stem.strip()
    cleaned = "".join(ch for ch in stem if ch not in _UNSAFE_NAME_CHARS).strip()
    return (cleaned or "file")[:80]


def pdf(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    mapping = {
        "pdf-reorder-pages": (pdf_advanced.reorder_pages, f"{stem}-reordered.pdf", (param,)),
        "pdf-rotate-selected": (pdf_advanced.rotate_selected, f"{stem}-rotated-pages.pdf", (param or "1", int(options.get("angle", "90")))),
        "pdf-page-numbers": (pdf_advanced.add_page_numbers, f"{stem}-numbered.pdf", (options.get("position", "bottom-center"),)),
        "pdf-watermark-text": (pdf_advanced.watermark_text, f"{stem}-watermarked.pdf", (options.get("text", ""),)),
        "pdf-grayscale": (pdf_advanced.grayscale, f"{stem}-grayscale.pdf", ()),
        "pdf-remove-blank-pages": (pdf_advanced.remove_blank_pages, f"{stem}-no-blank.pdf", ()),
        "pdf-crop-margins": (pdf_advanced.crop_margins, f"{stem}-cropped.pdf", (param or "18",)),
        "pdf-poster-split": (pdf_advanced.poster_tile, f"{stem}-poster-tiles.pdf", (int(options.get("columns", "2")), int(options.get("rows", "2")))),
        "pdf-contact-sheet": (pdf_advanced.contact_sheet, f"{stem}-contact-sheet.pdf", (int(options.get("columns", "2")),)),
        "pdf-password-protect": (pdf_advanced.password_protect, f"{stem}-protected.pdf", (options.get("password", ""),)),
    }
    func, filename, args = mapping[tool_id]
    out = output_dir / filename
    func(safe_input["path"], out, *args)
    return [(out, "application/pdf")]


def image(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    mapping = {
        "image-crop": (image_advanced.crop, f"{stem}-cropped.png", (param or "",)),
        "image-flip": (image_advanced.flip, f"{stem}-flipped.png", (options.get("direction", "horizontal"),)),
        "image-grayscale": (image_advanced.grayscale, f"{stem}-grayscale.png", ()),
        "image-sharpen": (image_advanced.sharpen, f"{stem}-sharpened.png", (options.get("strength", "2"),)),
        "image-auto-contrast": (image_advanced.auto_contrast, f"{stem}-contrast.jpg", ()),
        "image-sepia": (image_advanced.sepia, f"{stem}-sepia.jpg", ()),
        "image-strip-metadata": (image_advanced.strip_metadata, f"{stem}-clean.png", ()),
        "image-favicon-pack": (image_advanced.favicon_pack, "InfinityConverter-Favicon-Pack.zip", ()),
        "image-contact-sheet": (image_advanced.contact_sheet, f"{stem}-contact-sheet.jpg", (options.get("background", "white"),)),
        "image-set-dpi": (image_advanced.set_dpi, f"{stem}-dpi.png", (param or "144",)),
    }
    func, filename, args = mapping[tool_id]
    out = output_dir / filename
    func(safe_input["path"], out, *args)
    mime = "application/zip" if out.suffix == ".zip" else "image/jpeg" if out.suffix in {".jpg", ".jpeg"} else "image/png"
    return [(out, mime)]


def office(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    mapping = {
        "docx-to-text": (office_advanced.docx_to_text, f"{stem}.txt", "text/plain"),
        "docx-to-html": (office_advanced.docx_to_html, f"{stem}.html", "text/html"),
        "xlsx-to-csv": (office_advanced.xlsx_to_csv, f"{stem}.csv", "text/csv"),
        "xlsx-to-json": (office_advanced.xlsx_to_json, f"{stem}.json", "application/json"),
        "pptx-to-text": (office_advanced.pptx_to_text, f"{stem}.txt", "text/plain"),
        "csv-to-json": (office_advanced.csv_to_json, f"{stem}.json", "application/json"),
        "json-to-csv": (office_advanced.json_to_csv, f"{stem}.csv", "text/csv"),
        "json-to-xlsx": (office_advanced.json_to_xlsx, f"{stem}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "xml-to-json": (office_advanced.xml_to_json, f"{stem}.json", "application/json"),
        "text-to-json": (office_advanced.text_to_json, f"{stem}.json", "application/json"),
    }
    func, filename, mime = mapping[tool_id]
    out = output_dir / filename
    func(safe_input["path"], out)
    return [(out, mime)]


def ocr(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    lang = options.get("language", "ar+en")
    mapping = {
        "ocr-image-to-pdf": (ocr_advanced.image_to_searchable_pdf, f"{stem}-searchable.pdf", "application/pdf", (lang,)),
        "ocr-pdf-to-searchable": (ocr_advanced.pdf_to_searchable_pdf, f"{stem}-searchable.pdf", "application/pdf", (lang,)),
        "ocr-image-to-json": (ocr_advanced.image_ocr_json, f"{stem}-ocr.json", "application/json", (lang,)),
        "ocr-pdf-to-json": (ocr_advanced.pdf_ocr_json, f"{stem}-ocr.json", "application/json", (lang,)),
        "ocr-pdf-page-texts": (ocr_advanced.pdf_page_texts, f"{stem}-pages.zip", "application/zip", (lang,)),
        "ocr-image-numbers": (ocr_advanced.ocr_numbers, f"{stem}-numbers.txt", "text/plain", (lang,)),
        "ocr-image-emails": (ocr_advanced.ocr_emails, f"{stem}-emails.txt", "text/plain", (lang,)),
        "ocr-image-urls": (ocr_advanced.ocr_urls, f"{stem}-urls.txt", "text/plain", (lang,)),
        "ocr-image-table-csv": (ocr_advanced.ocr_tables_csv, f"{stem}-table.csv", "text/csv", (lang,)),
        "ocr-image-clean-text": (ocr_advanced.ocr_clean_text, f"{stem}-clean.txt", "text/plain", (lang,)),
    }
    func, filename, mime, args = mapping[tool_id]
    if tool_id == "ocr-pdf-page-texts":
        out_dir = output_dir / "pages"
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = func(safe_input["path"], out_dir, *args)
        zip_path = output_dir / f"{stem}-pages.zip"
        archive.create_zip([(path, path.name) for path in paths], zip_path)
        return [(zip_path, "application/zip")]
    out = output_dir / filename
    func(safe_input["path"], out, *args)
    return [(out, mime)]


def archive_tools(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    mapping = {
        "tar-extract": (archive_advanced.extract_tar, output_dir / "extracted"),
        "gzip-compress": (archive_advanced.gzip_compress, output_dir / f"{stem}.gz"),
        "gzip-decompress": (archive_advanced.gzip_decompress, output_dir / f"{stem}-decompressed.txt"),
        "zip-list": (archive_advanced.zip_list, output_dir / f"{stem}-zip.json"),
        "zip-integrity": (archive_advanced.zip_integrity_report, output_dir / f"{stem}-integrity.json"),
        "zip-flatten": (archive_advanced.zip_flatten, output_dir / f"{stem}-flat.zip"),
        "tar-list": (archive_advanced.tar_list, output_dir / f"{stem}-tar.json"),
        "gzip-info": (archive_advanced.gzip_info, output_dir / f"{stem}-gzip.json"),
        "zip-to-tar": (archive_advanced.zip_to_tar, output_dir / f"{stem}.tar"),
    }
    if tool_id == "tar-extract":
        paths = mapping[tool_id][0](safe_input["path"], mapping[tool_id][1])
        return [(path, "application/octet-stream") for path in paths]
    func, out = mapping[tool_id]
    func(safe_input["path"], out)
    mime = {".gz": "application/gzip", ".tar": "application/x-tar", ".zip": "application/zip", ".json": "application/json", ".txt": "text/plain"}[out.suffix]
    return [(out, mime)]


def utility(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    mapping = {
        "file-mime-report": (utility_advanced.mime_report, f"{stem}-mime.json", "application/json"),
        "text-statistics": (utility_advanced.text_statistics, f"{stem}-stats.json", "application/json"),
        "text-clean": (utility_advanced.clean_text, f"{stem}-clean.txt", "text/plain"),
        "text-deduplicate": (utility_advanced.deduplicate_text, f"{stem}-deduplicated.txt", "text/plain"),
        "text-sort": (utility_advanced.sort_text, f"{stem}-sorted.txt", "text/plain"),
        "filename-normalizer": (utility_advanced.normalize_filename, f"{stem}-filename.json", "application/json"),
        "csv-validator": (utility_advanced.csv_validate, f"{stem}-csv-report.json", "application/json"),
        "json-validator": (utility_advanced.json_validate, f"{stem}-json-report.json", "application/json"),
        "number-list-analyzer": (utility_advanced.number_list_analysis, f"{stem}-numbers.json", "application/json"),
        "text-to-base64": (utility_advanced.text_to_base64, f"{stem}-base64.txt", "text/plain"),
    }
    func, filename, mime = mapping[tool_id]
    out = output_dir / filename
    if tool_id == "text-sort":
        func(safe_input["path"], out, options.get("descending", "0"))
    elif tool_id in {"file-mime-report", "filename-normalizer"}:
        func(safe_input["path"], out, safe_input["filename"])
    else:
        func(safe_input["path"], out)
    return [(out, mime)]

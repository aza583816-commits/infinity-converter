"""Runtime adapters for the 6.x mega-tool families.

The conversion implementations still live in :mod:`converters.mega_tools`; this
module only maps public IDs to those functions. Keeping the mapping out of the
historical compatibility dispatcher gives every production operation a current,
reviewable registration path while preserving output names and MIME contracts.
"""
from __future__ import annotations

from pathlib import Path

from converters import mega_tools

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


def single(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    mapping = {
        "pdf-to-docx": (mega_tools.pdf_to_docx, f"{stem}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ()),
        "pdf-to-markdown": (mega_tools.pdf_to_markdown, f"{stem}.md", "text/markdown", ()),
        "pdf-repair": (mega_tools.pdf_repair, f"{stem}-repaired.pdf", "application/pdf", ()),
        "pdf-image-extract": (mega_tools.pdf_image_extract, f"{stem}-images.zip", "application/zip", ()),
        "pdf-links-report": (mega_tools.pdf_links_report, f"{stem}-links.json", "application/json", ()),
        "pdf-annotations-report": (mega_tools.pdf_annotations_report, f"{stem}-annotations.json", "application/json", ()),
        "pdf-page-size-report": (mega_tools.pdf_page_size_report, f"{stem}-page-sizes.json", "application/json", ()),
        "pdf-redact": (mega_tools.pdf_redact, f"{stem}-redacted.pdf", "application/pdf", (param,)),
        "pdf-unlock": (mega_tools.pdf_unlock, f"{stem}-unlocked.pdf", "application/pdf", (options.get("password", ""),)),
        "image-upscale": (mega_tools.image_upscale, f"{stem}-upscaled.png", "image/png", (param or "2",)),
        "image-blur": (mega_tools.image_blur, f"{stem}-blurred.png", "image/png", (param or "3",)),
        "image-pixelate": (mega_tools.image_pixelate, f"{stem}-pixelated.png", "image/png", (param or "32",)),
        "image-invert": (mega_tools.image_invert, f"{stem}-inverted.png", "image/png", ()),
        "image-posterize": (mega_tools.image_posterize, f"{stem}-posterized.png", "image/png", (param or "4",)),
        "image-color-palette": (mega_tools.image_palette, f"{stem}-palette.json", "application/json", (param or "8",)),
        "image-watermark": (mega_tools.image_watermark, f"{stem}-watermarked.png", "image/png", (param or "INFINITY",)),
        "image-background-cleaner": (mega_tools.image_background_cleaner, f"{stem}-background-clean.png", "image/png", (param or "24",)),
        "image-auto-orient": (mega_tools.image_auto_orient, f"{stem}-oriented.png", "image/png", ()),
        "image-round-corners": (mega_tools.image_round_corners, f"{stem}-rounded.png", "image/png", (param or "40",)),
        "docx-to-markdown": (mega_tools.docx_to_markdown, f"{stem}.md", "text/markdown", ()),
        "docx-table-to-csv": (mega_tools.docx_table_csv, f"{stem}-tables.csv", "text/csv", ()),
        "xlsx-to-html": (mega_tools.xlsx_to_html, f"{stem}.html", "text/html", ()),
        "xlsx-summary": (mega_tools.xlsx_summary, f"{stem}-summary.json", "application/json", ()),
        "csv-to-markdown": (mega_tools.csv_to_markdown, f"{stem}.md", "text/markdown", ()),
        "csv-statistics": (mega_tools.csv_statistics, f"{stem}-stats.json", "application/json", ()),
        "json-to-html": (mega_tools.json_to_html, f"{stem}.html", "text/html", ()),
        "html-to-text": (mega_tools.html_to_text, f"{stem}.txt", "text/plain", ()),
        "markdown-to-text": (mega_tools.markdown_to_text, f"{stem}.txt", "text/plain", ()),
        "pptx-to-markdown": (mega_tools.pptx_to_markdown, f"{stem}.md", "text/markdown", ()),
        "ocr-image-to-html": (mega_tools.ocr_image_to_html, f"{stem}-ocr.html", "text/html", (param or "ar+eng",)),
        "ocr-image-to-markdown": (mega_tools.ocr_image_to_markdown, f"{stem}-ocr.md", "text/markdown", (param or "ar+eng",)),
        "ocr-pdf-to-markdown": (mega_tools.ocr_pdf_to_markdown, f"{stem}-ocr.md", "text/markdown", (param or "ar+eng",)),
        "ocr-pdf-to-csv": (mega_tools.ocr_pdf_to_csv, f"{stem}-ocr.csv", "text/csv", (param or "ar+eng",)),
        "ocr-image-to-csv": (mega_tools.ocr_image_to_csv, f"{stem}-ocr.csv", "text/csv", (param or "ar+eng",)),
        "ocr-receipt-fields": (mega_tools.ocr_receipt_fields, f"{stem}-receipt.json", "application/json", (param or "ar+eng",)),
        "ocr-invoice-fields": (mega_tools.ocr_invoice_fields, f"{stem}-invoice.json", "application/json", (param or "ar+eng",)),
        "ocr-text-deduplicate": (mega_tools.ocr_deduplicate, f"{stem}-ocr-clean.txt", "text/plain", (param or "ar+eng",)),
        "ocr-entities": (mega_tools.ocr_entities, f"{stem}-entities.json", "application/json", (param or "ar+eng",)),
        "ocr-language-report": (mega_tools.ocr_language_report, f"{stem}-language.json", "application/json", (param or "ar+eng",)),
        "bzip2-compress": (mega_tools.bzip2_compress, f"{stem}.bz2", "application/x-bzip2", ()),
        "bzip2-decompress": (mega_tools.bzip2_decompress, f"{stem}-decompressed.txt", "text/plain", ()),
        "xz-compress": (mega_tools.xz_compress, f"{stem}.xz", "application/x-xz", ()),
        "xz-decompress": (mega_tools.xz_decompress, f"{stem}-decompressed.txt", "text/plain", ()),
        "zip-duplicate-report": (mega_tools.zip_duplicate_report, f"{stem}-duplicates.json", "application/json", ()),
        "tar-integrity": (mega_tools.tar_integrity, f"{stem}-integrity.json", "application/json", ()),
        "base64-decode": (mega_tools.base64_decode, f"{stem}-decoded.bin", "application/octet-stream", ()),
        "url-encode": (mega_tools.url_encode, f"{stem}-encoded.txt", "text/plain", ()),
        "url-decode": (mega_tools.url_decode, f"{stem}-decoded.txt", "text/plain", ()),
        "json-minify": (mega_tools.json_minify, f"{stem}-min.json", "application/json", ()),
        "regex-extract": (mega_tools.regex_extract, f"{stem}-matches.txt", "text/plain", (param or r"\b\w+\b",)),
        "file-extension-report": (mega_tools.rename_extension_report, f"{stem}-extension.json", "application/json", ()),
        "hex-encode": (mega_tools.hex_encode, f"{stem}.hex.txt", "text/plain", ()),
    }
    if tool_id in {"tar-gzip-extract", "tar-bzip2-extract"}:
        fn = mega_tools.tar_gzip_extract if tool_id == "tar-gzip-extract" else mega_tools.tar_bzip2_extract
        paths = fn(safe_input["path"], output_dir / "extracted")
        return [(path, "application/octet-stream") for path in paths]
    fn, filename, mime, args = mapping[tool_id]
    out = output_dir / filename
    if tool_id == "file-extension-report":
        # The validated workspace path is a randomized storage filename, not the
        # filename the user uploaded. Report original extension/MIME faithfully.
        fn(safe_input["path"], out, safe_input["filename"])
    else:
        fn(safe_input["path"], out, *args)
    return [(out, mime)]


def combine(safe_inputs, output_dir, param, tool_id, options):
    if tool_id == "pdf-compare":
        out = output_dir / "InfinityConverter-PDF-Diff.txt"
        mega_tools.pdf_compare(safe_inputs[0]["path"], safe_inputs[1]["path"], out)
        return out, "text/plain"
    if tool_id == "text-diff":
        out = output_dir / "InfinityConverter-Text-Diff.txt"
        mega_tools.text_diff(safe_inputs[0]["path"], safe_inputs[1]["path"], out)
        return out, "text/plain"
    if tool_id == "checksum-compare":
        out = output_dir / "InfinityConverter-Checksum-Compare.json"
        mega_tools.checksum_compare(safe_inputs[0]["path"], safe_inputs[1]["path"], out)
        return out, "application/json"
    entries = _archive_entries(safe_inputs)
    if tool_id == "tar-gzip-create":
        out = output_dir / "InfinityConverter-Archive.tar.gz"
        mega_tools.tar_gzip_create(entries, out)
        return out, "application/gzip"
    if tool_id == "tar-bzip2-create":
        out = output_dir / "InfinityConverter-Archive.tar.bz2"
        mega_tools.tar_bzip2_create(entries, out)
        return out, "application/x-bzip2"
    raise ValueError("هذه العملية غير مدعومة.")

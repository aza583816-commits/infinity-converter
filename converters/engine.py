import json
import logging
import threading
import time
import csv
from dataclasses import dataclass, field
from pathlib import Path

from config.settings import settings
from converters import archive, images, ocr, office, pdf, utility
from converters import archive_advanced, image_advanced, office_advanced, ocr_advanced, pdf_advanced, utility_advanced, mega_tools
from converters.validation import validate_output


logger = logging.getLogger(__name__)
CONVERSION_LIMIT = threading.BoundedSemaphore(settings.max_concurrent_conversions)

_UNSAFE_NAME_CHARS = '\\/:*?"<>|'


@dataclass(frozen=True)
class ConversionResult:
    path: Path
    name: str
    mime: str
    engine: str
    duration_ms: int
    input_bytes: int
    output_bytes: int
    details: dict
    batch_total: int = 0
    batch_succeeded: int = 0
    batch_failures: tuple = field(default_factory=tuple)


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "file").stem.strip()
    cleaned = "".join(ch for ch in stem if ch not in _UNSAFE_NAME_CHARS).strip()
    return (cleaned or "file")[:80]


def _unique_name(name: str, used: set) -> str:
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


IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _image_mime(path: Path) -> str:
    return IMAGE_MIME.get(path.suffix.lower(), "application/octet-stream")


# --- Combine handlers: multiple inputs merged into exactly one output. ---

def _h_pdf_merge(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Merged.pdf"
    pdf.merge_pdfs([item["path"] for item in safe_inputs], output)
    return output, "application/pdf"


def _h_images_to_pdf(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Images.pdf"
    pdf.images_to_pdf([item["path"] for item in safe_inputs], output)
    return output, "application/pdf"


def _h_zip_create(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Archive.zip"
    entries = [(item["path"], Path(item["filename"]).name or "file") for item in safe_inputs]
    archive.create_zip(entries, output)
    return output, "application/zip"


def _h_tar_create(safe_inputs, output_dir, param):
    output = output_dir / "InfinityConverter-Archive.tar"
    entries = [(item["path"], Path(item["filename"]).name or "file") for item in safe_inputs]
    archive_advanced.create_tar(entries, output)
    return output, "application/x-tar"


COMBINE_HANDLERS = {
    "pdf-merge": _h_pdf_merge,
    "image-to-pdf": _h_images_to_pdf,
    "zip-create": _h_zip_create,
    "tar-create": _h_tar_create,
}

# --- Single-file handlers: one input can produce one or many outputs.
# Multiple outputs (or multiple input files) are aggregated into a ZIP by
# the engine, so every handler just returns the files it produced. ---

def _h_pdf_split(safe_input, output_dir, param, timeout, max_pdf_pages):
    pages = pdf.split_pdf_pages(safe_input["path"], output_dir)
    return [(p, "application/pdf") for p in pages]


def _h_pdf_extract(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-extracted.pdf"
    pdf.extract_pdf_pages(safe_input["path"], out, param)
    return [(out, "application/pdf")]


def _h_pdf_delete(safe_input, output_dir, param, timeout, max_pdf_pages):
    if not (param or "").strip():
        raise ValueError("حدد الصفحات المطلوب حذفها، مثل 1-2,5.")
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-edited.pdf"
    pdf.delete_pdf_pages(safe_input["path"], out, param)
    return [(out, "application/pdf")]


def _h_pdf_rotate(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        angle = int((param or "90").strip())
    except ValueError:
        raise ValueError("زاوية الدوران يجب أن تكون رقمًا صحيحًا.")
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-rotated.pdf"
    pdf.rotate_pdf(safe_input["path"], out, angle)
    return [(out, "application/pdf")]


def _h_pdf_compress(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-compressed.pdf"
    pdf.compress_pdf(safe_input["path"], out)
    return [(out, "application/pdf")]


def _h_pdf_booklet(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-booklet.pdf"
    pdf.make_booklet(safe_input["path"], out, options["layout"])
    return [(out, "application/pdf")]


def _h_lms_pdf_optimizer(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-lms-optimized.pdf"
    pdf.optimize_pdf_for_lms(safe_input["path"], out, options["target"])
    return [(out, "application/pdf")]


def _h_pdf_to_images(fmt, mime):
    def handler(safe_input, output_dir, param, timeout, max_pdf_pages):
        produced = pdf.pdf_to_images(safe_input["path"], output_dir, fmt)
        return [(p, mime) for p in produced]
    return handler


def _h_pdf_to_text(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.txt"
    pdf.pdf_to_text(safe_input["path"], out)
    return [(out, "text/plain")]


def _h_pdf_to_html(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.html"
    pdf.pdf_to_html(safe_input["path"], out)
    return [(out, "text/html")]


def _h_pdf_metadata(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-metadata.json"
    pdf.pdf_metadata_report(safe_input["path"], out)
    return [(out, "application/json")]


def _h_pdf_ocr(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-ocr.txt"
    ocr.ocr_pdf(safe_input["path"], out, lang=param or "ar+en", max_pages=settings.max_ocr_pages)
    return [(out, "text/plain")]


def _h_image_convert(fmt, ext, mime):
    def handler(safe_input, output_dir, param, timeout, max_pdf_pages):
        out = output_dir / f"{_safe_stem(safe_input['filename'])}.{ext}"
        images.convert_image(safe_input["path"], out, fmt)
        return [(out, mime)]
    return handler


def _h_image_resize(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        max_dimension = int((param or "1600").strip())
    except ValueError:
        raise ValueError("أبعاد الصورة يجب أن تكون رقمًا صحيحًا.")
    ext = safe_input["extension"].lstrip(".")
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-resized{safe_input['extension']}"
    images.resize_image(safe_input["path"], out, max_dimension)
    return [(out, _image_mime(out))]


def _h_image_compress(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        quality = int((param or "70").strip())
    except ValueError:
        raise ValueError("جودة الضغط يجب أن تكون رقمًا صحيحًا.")
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-compressed{safe_input['extension']}"
    images.compress_image(safe_input["path"], out, quality)
    return [(out, _image_mime(out))]


def _h_image_rotate(safe_input, output_dir, param, timeout, max_pdf_pages):
    try:
        angle = int((param or "90").strip())
    except ValueError:
        raise ValueError("زاوية الدوران يجب أن تكون رقمًا صحيحًا.")
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-rotated{safe_input['extension']}"
    images.rotate_image(safe_input["path"], out, angle)
    return [(out, _image_mime(out))]


def _h_image_ocr(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-ocr.txt"
    ocr.ocr_image(safe_input["path"], out, lang=param or "ar+en")
    return [(out, "text/plain")]


def _h_office_to_pdf(safe_input, output_dir, param, timeout, max_pdf_pages):
    produced = office.office_to_pdf(safe_input["path"], output_dir, timeout=timeout)
    renamed = output_dir / f"{_safe_stem(safe_input['filename'])}.pdf"
    if produced != renamed:
        produced.replace(renamed)
    return [(renamed, "application/pdf")]


def _h_markdown_to_html(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.html"
    office.markdown_to_html(safe_input["path"], out)
    return [(out, "text/html")]


def _h_markdown_to_pdf(safe_input, output_dir, param, timeout, max_pdf_pages):
    workspace_input = safe_input["path"].parent
    produced = office.markdown_to_pdf(safe_input["path"], workspace_input, output_dir, timeout=timeout)
    renamed = output_dir / f"{_safe_stem(safe_input['filename'])}.pdf"
    if produced != renamed:
        produced.replace(renamed)
    return [(renamed, "application/pdf")]


def _h_csv_to_xlsx(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}.xlsx"
    office.csv_to_xlsx(safe_input["path"], out)
    return [(out, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]


def _h_zip_extract(safe_input, output_dir, param, timeout, max_pdf_pages):
    extracted = archive.extract_zip(safe_input["path"], output_dir / "extracted")
    return [(p, "application/octet-stream") for p in extracted]


def _h_file_hash(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-hash.json"
    utility.hash_report(safe_input["path"], out, safe_input["filename"])
    return [(out, "application/json")]


def _h_file_info(safe_input, output_dir, param, timeout, max_pdf_pages):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-info.json"
    utility.file_info_report(safe_input, out)
    return [(out, "application/json")]


def _h_social_resize(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-social.png"
    images.resize_for_social(safe_input["path"], out, options["preset"], options["fit"])
    return [(out, "image/png")]


def _h_question_bank(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-gift.txt"
    utility.text_to_gift(safe_input["path"], out)
    return [(out, "text/plain")]


def _h_bulk_certificates(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    certificates = []
    try:
        with safe_input["path"].open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if not reader.fieldnames or "name" not in reader.fieldnames:
                raise ValueError("يجب أن يحتوي CSV على عمود باسم name.")
            for index, row in enumerate(reader, start=1):
                if index > 500:
                    raise ValueError("الحد الأقصى هو 500 شهادة في العملية الواحدة.")
                certificate = output_dir / f"certificate-{index:03d}.pdf"
                pdf.create_certificate(certificate, (row.get("name") or "").strip(), options["title"], options.get("issuer", ""))
                certificates.append((certificate, certificate.name))
    except csv.Error as exc:
        raise ValueError("ملف CSV غير صالح.") from exc
    if not certificates:
        raise ValueError("لا يحتوي CSV على أسماء شهادات.")
    out = output_dir / "InfinityConverter-Certificates.zip"
    archive.create_zip(certificates, out)
    return [(out, "application/zip")]


def _h_assignment_cover(output_dir, options):
    out = output_dir / "InfinityConverter-Assignment-Cover.pdf"
    pdf.create_assignment_cover(out, options)
    return out, "application/pdf"


def _h_omr_sheet(output_dir, options):
    out = output_dir / "InfinityConverter-OMR-Sheet.pdf"
    pdf.create_omr_sheet(out, int(options["questions"]))
    return out, "application/pdf"


def _h_quote_graphic(output_dir, options):
    out = output_dir / "InfinityConverter-Quote.png"
    images.quote_social_graphic(out, options["quote"], options.get("author", ""), options["preset"], options["theme"])
    return out, "image/png"


def _h_csv_merge(safe_inputs, output_dir, param, options=None):
    out = output_dir / "InfinityConverter-Merged.csv"
    utility.merge_and_deduplicate_csv([item["path"] for item in safe_inputs], out)
    return out, "text/csv"



def _h_adv_pdf(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input['filename'])
    mapping = {
        'pdf-reorder-pages': (pdf_advanced.reorder_pages, f'{stem}-reordered.pdf', (param,)),
        'pdf-rotate-selected': (pdf_advanced.rotate_selected, f'{stem}-rotated-pages.pdf', (param or '1', int(options.get('angle','90')))),
        'pdf-page-numbers': (pdf_advanced.add_page_numbers, f'{stem}-numbered.pdf', (options.get('position','bottom-center'),)),
        'pdf-watermark-text': (pdf_advanced.watermark_text, f'{stem}-watermarked.pdf', (options.get('text',''),)),
        'pdf-grayscale': (pdf_advanced.grayscale, f'{stem}-grayscale.pdf', ()),
        'pdf-remove-blank-pages': (pdf_advanced.remove_blank_pages, f'{stem}-no-blank.pdf', ()),
        'pdf-crop-margins': (pdf_advanced.crop_margins, f'{stem}-cropped.pdf', (param or '18',)),
        'pdf-poster-split': (pdf_advanced.poster_tile, f'{stem}-poster-tiles.pdf', (int(options.get('columns','2')), int(options.get('rows','2')))),
        'pdf-contact-sheet': (pdf_advanced.contact_sheet, f'{stem}-contact-sheet.pdf', (int(options.get('columns','2')),)),
        'pdf-password-protect': (pdf_advanced.password_protect, f'{stem}-protected.pdf', (options.get('password',''),)),
    }
    func, filename, args = mapping[tool_id]
    out = output_dir / filename
    func(safe_input['path'], out, *args)
    return [(out, 'application/pdf')]


def _h_adv_image(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input['filename'])
    mapping = {
        'image-crop': (image_advanced.crop, f'{stem}-cropped.png', (param or '',)),
        'image-flip': (image_advanced.flip, f'{stem}-flipped.png', (options.get('direction','horizontal'),)),
        'image-grayscale': (image_advanced.grayscale, f'{stem}-grayscale.png', ()),
        'image-sharpen': (image_advanced.sharpen, f'{stem}-sharpened.png', (options.get('strength','2'),)),
        'image-auto-contrast': (image_advanced.auto_contrast, f'{stem}-contrast.jpg', ()),
        'image-sepia': (image_advanced.sepia, f'{stem}-sepia.jpg', ()),
        'image-strip-metadata': (image_advanced.strip_metadata, f'{stem}-clean.png', ()),
        'image-favicon-pack': (image_advanced.favicon_pack, 'InfinityConverter-Favicon-Pack.zip', ()),
        'image-contact-sheet': (image_advanced.contact_sheet, f'{stem}-contact-sheet.jpg', (options.get('background','white'),)),
        'image-set-dpi': (image_advanced.set_dpi, f'{stem}-dpi.png', (param or '144',)),
    }
    func, filename, args = mapping[tool_id]
    out = output_dir / filename
    func(safe_input['path'], out, *args)
    mime = 'application/zip' if out.suffix == '.zip' else 'image/jpeg' if out.suffix in {'.jpg','.jpeg'} else 'image/png'
    return [(out, mime)]


def _h_adv_office(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input['filename'])
    mapping = {
        'docx-to-text': (office_advanced.docx_to_text, f'{stem}.txt', 'text/plain'),
        'docx-to-html': (office_advanced.docx_to_html, f'{stem}.html', 'text/html'),
        'xlsx-to-csv': (office_advanced.xlsx_to_csv, f'{stem}.csv', 'text/csv'),
        'xlsx-to-json': (office_advanced.xlsx_to_json, f'{stem}.json', 'application/json'),
        'pptx-to-text': (office_advanced.pptx_to_text, f'{stem}.txt', 'text/plain'),
        'csv-to-json': (office_advanced.csv_to_json, f'{stem}.json', 'application/json'),
        'json-to-csv': (office_advanced.json_to_csv, f'{stem}.csv', 'text/csv'),
        'json-to-xlsx': (office_advanced.json_to_xlsx, f'{stem}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        'xml-to-json': (office_advanced.xml_to_json, f'{stem}.json', 'application/json'),
        'text-to-json': (office_advanced.text_to_json, f'{stem}.json', 'application/json'),
    }
    func, filename, mime = mapping[tool_id]
    out = output_dir / filename
    func(safe_input['path'], out)
    return [(out, mime)]


def _h_adv_ocr(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input['filename'])
    lang = options.get('language','ar+en')
    mapping = {
        'ocr-image-to-pdf': (ocr_advanced.image_to_searchable_pdf, f'{stem}-searchable.pdf', 'application/pdf', (lang,)),
        'ocr-pdf-to-searchable': (ocr_advanced.pdf_to_searchable_pdf, f'{stem}-searchable.pdf', 'application/pdf', (lang,)),
        'ocr-image-to-json': (ocr_advanced.image_ocr_json, f'{stem}-ocr.json', 'application/json', (lang,)),
        'ocr-pdf-to-json': (ocr_advanced.pdf_ocr_json, f'{stem}-ocr.json', 'application/json', (lang,)),
        'ocr-pdf-page-texts': (ocr_advanced.pdf_page_texts, f'{stem}-pages.zip', 'application/zip', (lang,)),
        'ocr-image-numbers': (ocr_advanced.ocr_numbers, f'{stem}-numbers.txt', 'text/plain', (lang,)),
        'ocr-image-emails': (ocr_advanced.ocr_emails, f'{stem}-emails.txt', 'text/plain', (lang,)),
        'ocr-image-urls': (ocr_advanced.ocr_urls, f'{stem}-urls.txt', 'text/plain', (lang,)),
        'ocr-image-table-csv': (ocr_advanced.ocr_tables_csv, f'{stem}-table.csv', 'text/csv', (lang,)),
        'ocr-image-clean-text': (ocr_advanced.ocr_clean_text, f'{stem}-clean.txt', 'text/plain', (lang,)),
    }
    func, filename, mime, args = mapping[tool_id]
    if tool_id == 'ocr-pdf-page-texts':
        out_dir = output_dir / 'pages'
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = func(safe_input['path'], out_dir, *args)
        zip_path = output_dir / f'{stem}-pages.zip'
        archive.create_zip([(path, path.name) for path in paths], zip_path)
        return [(zip_path, 'application/zip')]
    out = output_dir / filename
    func(safe_input['path'], out, *args)
    return [(out, mime)]


def _h_adv_archive(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input['filename'])
    mapping = {
        'tar-extract': (archive_advanced.extract_tar, output_dir / 'extracted'),
        'gzip-compress': (archive_advanced.gzip_compress, output_dir / f'{stem}.gz'),
        'gzip-decompress': (archive_advanced.gzip_decompress, output_dir / f'{stem}-decompressed.txt'),
        'zip-list': (archive_advanced.zip_list, output_dir / f'{stem}-zip.json'),
        'zip-integrity': (archive_advanced.zip_integrity_report, output_dir / f'{stem}-integrity.json'),
        'zip-flatten': (archive_advanced.zip_flatten, output_dir / f'{stem}-flat.zip'),
        'tar-list': (archive_advanced.tar_list, output_dir / f'{stem}-tar.json'),
        'gzip-info': (archive_advanced.gzip_info, output_dir / f'{stem}-gzip.json'),
        'zip-to-tar': (archive_advanced.zip_to_tar, output_dir / f'{stem}.tar'),
        'tar-to-zip': (archive_advanced.tar_to_zip, output_dir / f'{stem}.zip'),
    }
    if tool_id == 'tar-extract':
        paths = mapping[tool_id][0](safe_input['path'], mapping[tool_id][1])
        return [(path, 'application/octet-stream') for path in paths]
    func, out = mapping[tool_id]
    func(safe_input['path'], out)
    mime = {'.gz':'application/gzip','.tar':'application/x-tar','.zip':'application/zip','.json':'application/json','.txt':'text/plain'}[out.suffix]
    return [(out, mime)]


def _h_adv_utility(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input['filename'])
    mapping = {
        'file-mime-report': (utility_advanced.mime_report, f'{stem}-mime.json', 'application/json'),
        'text-statistics': (utility_advanced.text_statistics, f'{stem}-stats.json', 'application/json'),
        'text-clean': (utility_advanced.clean_text, f'{stem}-clean.txt', 'text/plain'),
        'text-deduplicate': (utility_advanced.deduplicate_text, f'{stem}-deduplicated.txt', 'text/plain'),
        'text-sort': (utility_advanced.sort_text, f'{stem}-sorted.txt', 'text/plain'),
        'filename-normalizer': (utility_advanced.normalize_filename, f'{stem}-filename.json', 'application/json'),
        'csv-validator': (utility_advanced.csv_validate, f'{stem}-csv-report.json', 'application/json'),
        'json-validator': (utility_advanced.json_validate, f'{stem}-json-report.json', 'application/json'),
        'number-list-analyzer': (utility_advanced.number_list_analysis, f'{stem}-numbers.json', 'application/json'),
        'text-to-base64': (utility_advanced.text_to_base64, f'{stem}-base64.txt', 'text/plain'),
    }
    func, filename, mime = mapping[tool_id]
    out = output_dir / filename
    if tool_id == 'text-sort':
        func(safe_input['path'], out, options.get('descending','0'))
    else:
        func(safe_input['path'], out)
    return [(out, mime)]


def _h_mega(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options):
    stem = _safe_stem(safe_input["filename"])
    pdf_map = {
        "pdf-to-docx": (mega_tools.pdf_to_docx, f"{stem}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ()),
        "pdf-to-markdown": (mega_tools.pdf_to_markdown, f"{stem}.md", "text/markdown", ()),
        "pdf-repair": (mega_tools.pdf_repair, f"{stem}-repaired.pdf", "application/pdf", ()),
        "pdf-image-extract": (mega_tools.pdf_image_extract, f"{stem}-images.zip", "application/zip", ()),
        "pdf-links-report": (mega_tools.pdf_links_report, f"{stem}-links.json", "application/json", ()),
        "pdf-annotations-report": (mega_tools.pdf_annotations_report, f"{stem}-annotations.json", "application/json", ()),
        "pdf-page-size-report": (mega_tools.pdf_page_size_report, f"{stem}-page-sizes.json", "application/json", ()),
        "pdf-redact": (mega_tools.pdf_redact, f"{stem}-redacted.pdf", "application/pdf", (param,)),
        "pdf-unlock": (mega_tools.pdf_unlock, f"{stem}-unlocked.pdf", "application/pdf", (options.get("password",""),)),
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
    if tool_id in {"tar-gzip-extract","tar-bzip2-extract"}:
        fn = mega_tools.tar_gzip_extract if tool_id == "tar-gzip-extract" else mega_tools.tar_bzip2_extract
        paths = fn(safe_input["path"], output_dir / "extracted")
        return [(p, "application/octet-stream") for p in paths]
    fn = pdf_map[tool_id]
    out = output_dir / fn[1]
    fn[0](safe_input["path"], out, *fn[3])
    return [(out, fn[2])]


def _h_mega_combine(safe_inputs, output_dir, param, tool_id, options):
    if tool_id == "pdf-compare":
        out=output_dir / "InfinityConverter-PDF-Diff.txt"; mega_tools.pdf_compare(safe_inputs[0]["path"], safe_inputs[1]["path"], out); return out, "text/plain"
    if tool_id == "text-diff":
        out=output_dir / "InfinityConverter-Text-Diff.txt"; mega_tools.text_diff(safe_inputs[0]["path"], safe_inputs[1]["path"], out); return out, "text/plain"
    if tool_id == "checksum-compare":
        out=output_dir / "InfinityConverter-Checksum-Compare.json"; mega_tools.checksum_compare(safe_inputs[0]["path"], safe_inputs[1]["path"], out); return out, "application/json"
    entries=[(item["path"], Path(item["filename"]).name or "file") for item in safe_inputs]
    if tool_id == "tar-gzip-create":
        out=output_dir / "InfinityConverter-Archive.tar.gz"; mega_tools.tar_gzip_create(entries,out); return out,"application/gzip"
    if tool_id == "tar-bzip2-create":
        out=output_dir / "InfinityConverter-Archive.tar.bz2"; mega_tools.tar_bzip2_create(entries,out); return out,"application/x-bzip2"
    raise ValueError("هذه العملية غير مدعومة.")

SINGLE_HANDLERS = {
    "pdf-split": _h_pdf_split,
    "pdf-extract-pages": _h_pdf_extract,
    "pdf-delete-pages": _h_pdf_delete,
    "pdf-rotate": _h_pdf_rotate,
    "pdf-compress": _h_pdf_compress,
    "pdf-booklet": _h_pdf_booklet,
    "lms-pdf-size-optimizer": _h_lms_pdf_optimizer,
    "pdf-to-jpg": _h_pdf_to_images("JPEG", "image/jpeg"),
    "pdf-to-png": _h_pdf_to_images("PNG", "image/png"),
    "pdf-to-text": _h_pdf_to_text,
    "pdf-to-html": _h_pdf_to_html,
    "pdf-metadata": _h_pdf_metadata,
    "pdf-ocr": _h_pdf_ocr,
    "image-to-jpg": _h_image_convert("JPEG", "jpg", "image/jpeg"),
    "image-to-png": _h_image_convert("PNG", "png", "image/png"),
    "image-to-webp": _h_image_convert("WEBP", "webp", "image/webp"),
    "image-resize": _h_image_resize,
    "image-compress": _h_image_compress,
    "image-rotate": _h_image_rotate,
    "image-ocr": _h_image_ocr,
    "social-media-image-resizer": _h_social_resize,
    "word-to-pdf": _h_office_to_pdf,
    "excel-to-pdf": _h_office_to_pdf,
    "ppt-to-pdf": _h_office_to_pdf,
    "txt-to-pdf": _h_office_to_pdf,
    "html-to-pdf": _h_office_to_pdf,
    "csv-to-pdf": _h_office_to_pdf,
    "markdown-to-html": _h_markdown_to_html,
    "markdown-to-pdf": _h_markdown_to_pdf,
    "csv-to-xlsx": _h_csv_to_xlsx,
    "bulk-certificate-maker": _h_bulk_certificates,
    "lms-question-bank-formatter": _h_question_bank,
    "zip-extract": _h_zip_extract,
    "file-hash": _h_file_hash,
    "file-info": _h_file_info,
}


class ConversionEngine:
    """Selects a specialized local engine and validates its output.

    Two dispatch shapes are supported:
    - COMBINE_HANDLERS: every uploaded file is merged into exactly one output.
    - SINGLE_HANDLERS: each uploaded file is processed independently (one
      failure does not abort the others); results are zipped together when
      there is more than one output file, with a batch-report.json describing
      any failures.
    """

    def convert(self, *, tool, safe_inputs, workspace, timeout, max_pdf_pages, param="", options=None) -> ConversionResult:
        if not CONVERSION_LIMIT.acquire(timeout=timeout):
            raise RuntimeError("عدد عمليات التحويل الحالية تجاوز الحد المؤقت.")
        started = time.perf_counter()
        input_bytes = sum(item["size_bytes"] for item in safe_inputs)
        engine_name = self._engine_name(tool.id)
        output_dir = workspace.path / "output"
        options = options or {}
        try:
            if tool.id == "assignment-cover-page":
                output, mime = _h_assignment_cover(output_dir, options)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = 0, 0, ()
            elif tool.id == "omr-bubble-sheet":
                output, mime = _h_omr_sheet(output_dir, options)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = 0, 0, ()
            elif tool.id == "quote-social-graphic":
                output, mime = _h_quote_graphic(output_dir, options)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = 0, 0, ()
            elif tool.id == "csv-merge-deduplicate":
                output, mime = _h_csv_merge(safe_inputs, output_dir, param, options)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = len(safe_inputs), len(safe_inputs), ()
            elif tool.id in mega_tools.COMBINE_IDS:
                output, mime = _h_mega_combine(safe_inputs, output_dir, param, tool.id, options)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = len(safe_inputs), len(safe_inputs), ()
            elif tool.id in mega_tools.NO_INPUT_IDS:
                out = output_dir / "InfinityConverter-UUIDs.txt"
                mega_tools.uuid_list(param or "10", out)
                details = validate_output(out, expected_extension=out.suffix, expected_mime="text/plain", max_bytes=settings.max_output_mb * 1024 * 1024)
                output, mime = out, "text/plain"
                batch_total, batch_succeeded, batch_failures = 0, 0, ()
            elif tool.id in mega_tools.PDF_IDS or tool.id in mega_tools.IMAGE_IDS or tool.id in mega_tools.OFFICE_IDS or tool.id in mega_tools.OCR_IDS or tool.id in mega_tools.ARCHIVE_IDS or tool.id in mega_tools.UTILITY_IDS:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_mega, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            elif tool.id in COMBINE_HANDLERS:
                output, mime = COMBINE_HANDLERS[tool.id](safe_inputs, output_dir, param)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = len(safe_inputs), len(safe_inputs), ()
            elif tool.id.startswith("pdf-") and tool.id in {"pdf-reorder-pages","pdf-rotate-selected","pdf-page-numbers","pdf-watermark-text","pdf-grayscale","pdf-remove-blank-pages","pdf-crop-margins","pdf-poster-split","pdf-contact-sheet","pdf-password-protect"}:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_adv_pdf, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            elif tool.id.startswith("image-") and tool.id in {"image-crop","image-flip","image-grayscale","image-sharpen","image-auto-contrast","image-sepia","image-strip-metadata","image-favicon-pack","image-contact-sheet","image-set-dpi"}:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_adv_image, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            elif tool.id in {"docx-to-text","docx-to-html","xlsx-to-csv","xlsx-to-json","pptx-to-text","csv-to-json","json-to-csv","json-to-xlsx","xml-to-json","text-to-json"}:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_adv_office, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            elif tool.id.startswith("ocr-") and tool.id in {"ocr-image-to-pdf","ocr-pdf-to-searchable","ocr-image-to-json","ocr-pdf-to-json","ocr-pdf-page-texts","ocr-image-numbers","ocr-image-emails","ocr-image-urls","ocr-image-table-csv","ocr-image-clean-text"}:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_adv_ocr, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            elif tool.id in {"tar-extract","gzip-compress","gzip-decompress","zip-list","zip-integrity","zip-flatten","tar-list","gzip-info","zip-to-tar","tar-to-zip"}:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_adv_archive, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            elif tool.id in {"file-mime-report","text-statistics","text-clean","text-deduplicate","text-sort","filename-normalizer","csv-validator","json-validator","number-list-analyzer","text-to-base64"}:
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_advanced(_h_adv_utility, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip")
            else:
                handler = SINGLE_HANDLERS.get(tool.id)
                if handler is None:
                    raise ValueError("هذه الأداة لم تُوصل بمحرك التحويل بعد.")
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_single(
                    handler, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=tool.output_ext == ".zip"
                )

            duration_ms = round((time.perf_counter() - started) * 1000)
            output_bytes = output.stat().st_size
            logger.info(
                "conversion_completed tool=%s engine=%s duration_ms=%s input_bytes=%s output_bytes=%s "
                "batch_total=%s batch_succeeded=%s",
                tool.id, engine_name, duration_ms, input_bytes, output_bytes, batch_total, batch_succeeded,
            )
            return ConversionResult(
                path=output,
                name=output.name,
                mime=mime,
                engine=engine_name,
                duration_ms=duration_ms,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                details=details,
                batch_total=batch_total,
                batch_succeeded=batch_succeeded,
                batch_failures=tuple(batch_failures),
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.warning(
                "conversion_failed tool=%s engine=%s duration_ms=%s input_bytes=%s error=%s",
                tool.id, engine_name, duration_ms, input_bytes, type(exc).__name__,
            )
            raise
        finally:
            CONVERSION_LIMIT.release()

    @staticmethod
    def _run_advanced(handler, tool, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=False):
        outputs = []
        failures = []
        for index, safe_input in enumerate(safe_inputs):
            item_dir = output_dir / f"item-{index}"
            item_dir.mkdir(parents=True, exist_ok=True)
            try:
                produced = handler(safe_input, item_dir, param, timeout, max_pdf_pages, tool.id, options)
                for path, mime in produced:
                    outputs.append((path, mime, safe_input["filename"]))
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else "تعذرت معالجة هذا الملف."
                failures.append((safe_input["filename"], message))

        if not outputs:
            raise ValueError(failures[0][1] if failures else "تعذر إنتاج أي ملف.")
        if len(outputs) == 1 and not failures and not force_zip:
            path, mime, _ = outputs[0]
            details = validate_output(path, expected_extension=path.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
            return path, mime, details, 1, 1, []
        used_names = set()
        entries = []
        multi_source = len({name for _, _, name in outputs}) > 1
        for path, _, source_name in outputs:
            base = f"{_safe_stem(source_name)}-{path.name}" if multi_source else path.name
            entries.append((path, _unique_name(base, used_names)))
        if failures:
            report = {"succeeded": len(outputs), "failed": [{"file": name, "error": message} for name, message in failures]}
            report_path = output_dir / "batch-report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            entries.append((report_path, "batch-report.json"))
        zip_path = output_dir / "InfinityConverter-Batch.zip"
        archive.create_zip(entries, zip_path)
        details = validate_output(zip_path, expected_extension=".zip", expected_mime="application/zip", max_bytes=settings.max_output_mb * 1024 * 1024)
        total = len(outputs) + len(failures)
        return zip_path, "application/zip", details, total, len(outputs), [name for name, _ in failures]

    @staticmethod
    def _run_single(handler, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, force_zip=False):
        outputs = []  # (path, mime, source_filename)
        failures = []  # (filename, message)
        for index, safe_input in enumerate(safe_inputs):
            # Each input gets its own output subdirectory so same-named
            # uploads in a batch never overwrite each other before zipping.
            item_dir = output_dir / f"item-{index}"
            item_dir.mkdir(parents=True, exist_ok=True)
            try:
                if handler in {_h_pdf_booklet, _h_lms_pdf_optimizer, _h_social_resize, _h_question_bank, _h_bulk_certificates}:
                    produced = handler(safe_input, item_dir, param, timeout, max_pdf_pages, options)
                else:
                    produced = handler(safe_input, item_dir, param, timeout, max_pdf_pages)
                for path, mime in produced:
                    outputs.append((path, mime, safe_input["filename"]))
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else "تعذرت معالجة هذا الملف."
                failures.append((safe_input["filename"], message))

        if not outputs:
            raise ValueError(failures[0][1] if failures else "تعذر إنتاج أي ملف.")

        if len(outputs) == 1 and not failures and not force_zip:
            path, mime, _ = outputs[0]
            details = validate_output(path, expected_extension=path.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
            return path, mime, details, 1, 1, []

        used_names: set = set()
        entries = []
        multi_source = len({name for _, _, name in outputs}) > 1
        for path, _, source_name in outputs:
            base = f"{_safe_stem(source_name)}-{path.name}" if multi_source else path.name
            entries.append((path, _unique_name(base, used_names)))

        if failures:
            report = {
                "succeeded": len(outputs),
                "failed": [{"file": name, "error": message} for name, message in failures],
            }
            report_path = output_dir / "batch-report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            entries.append((report_path, "batch-report.json"))

        zip_path = output_dir / "InfinityConverter-Batch.zip"
        archive.create_zip(entries, zip_path)
        details = validate_output(zip_path, expected_extension=".zip", expected_mime="application/zip", max_bytes=settings.max_output_mb * 1024 * 1024)
        total = len(outputs) + len(failures)
        return zip_path, "application/zip", details, total, len(outputs), [name for name, _ in failures]

    @staticmethod
    def _engine_name(tool_id: str) -> str:
        if tool_id.startswith("pdf-"):
            return "pymupdf+pypdf"
        if tool_id.startswith("image-"):
            return "pillow"
        if tool_id in {"assignment-cover-page", "omr-bubble-sheet", "bulk-certificate-maker"}:
            return "pymupdf"
        if tool_id in {"social-media-image-resizer", "quote-social-graphic"}:
            return "pillow"
        if tool_id in {"csv-merge-deduplicate", "lms-question-bank-formatter"}:
            return "stdlib"
        if tool_id in {"word-to-pdf", "excel-to-pdf", "ppt-to-pdf", "txt-to-pdf", "html-to-pdf", "csv-to-pdf", "markdown-to-pdf"}:
            return "libreoffice"
        if tool_id in {"markdown-to-html"}:
            return "markdown"
        if tool_id == "csv-to-xlsx":
            return "openpyxl"
        if tool_id.startswith("zip-"):
            return "zipfile"
        if tool_id.startswith("file-"):
            return "hashlib"
        if tool_id.startswith("text-"):
            return "stdlib"
        if tool_id.startswith("xml-") or tool_id.startswith("json-") or tool_id.startswith("xlsx-") or tool_id.startswith("docx-") or tool_id.startswith("pptx-"):
            return "office-libraries"
        if tool_id.startswith("ocr-"):
            return "tesseract+pymupdf"
        if tool_id in {"tar-create","tar-extract","tar-list","zip-list","zip-integrity","zip-flatten","zip-to-tar","tar-to-zip","gzip-compress","gzip-decompress","gzip-info"}:
            return "tarfile+zipfile"
        return "unknown"

import json
import logging
import threading
import time
import csv
from dataclasses import dataclass, field
from pathlib import Path

from config.settings import settings
from converters import archive, images, ocr, office, pdf, utility
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


COMBINE_HANDLERS = {
    "pdf-merge": _h_pdf_merge,
    "image-to-pdf": _h_images_to_pdf,
    "zip-create": _h_zip_create,
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
            elif tool.id in COMBINE_HANDLERS:
                output, mime = COMBINE_HANDLERS[tool.id](safe_inputs, output_dir, param)
                details = validate_output(output, expected_extension=output.suffix, expected_mime=mime, max_bytes=settings.max_output_mb * 1024 * 1024)
                batch_total, batch_succeeded, batch_failures = len(safe_inputs), len(safe_inputs), ()
            else:
                handler = SINGLE_HANDLERS.get(tool.id)
                if handler is None:
                    raise ValueError("هذه الأداة لم تُوصل بمحرك التحويل بعد.")
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_single(
                    handler, safe_inputs, output_dir, param, timeout, max_pdf_pages, options
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
    def _run_single(handler, safe_inputs, output_dir, param, timeout, max_pdf_pages, options):
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

        if len(outputs) == 1 and not failures:
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
        return "unknown"

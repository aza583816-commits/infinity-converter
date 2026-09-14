from __future__ import annotations

from typing import Callable

from converters import core_handlers, mega_tools
from converters.contracts import Operation
from converters import legacy_handlers as legacy
from core.tooling.catalog import TOOLS


PDF_ADVANCED_IDS = {
    "pdf-reorder-pages", "pdf-rotate-selected", "pdf-page-numbers",
    "pdf-watermark-text", "pdf-grayscale", "pdf-remove-blank-pages",
    "pdf-crop-margins", "pdf-poster-split", "pdf-contact-sheet",
    "pdf-password-protect",
}
IMAGE_ADVANCED_IDS = {
    "image-crop", "image-flip", "image-grayscale", "image-sharpen",
    "image-auto-contrast", "image-sepia", "image-strip-metadata",
    "image-favicon-pack", "image-contact-sheet", "image-set-dpi",
}
OFFICE_ADVANCED_IDS = {
    "docx-to-text", "docx-to-html", "xlsx-to-csv", "xlsx-to-json",
    "pptx-to-text", "csv-to-json", "json-to-csv", "json-to-xlsx",
    "xml-to-json", "text-to-json",
}
OCR_ADVANCED_IDS = {
    "ocr-image-to-pdf", "ocr-pdf-to-searchable", "ocr-image-to-json",
    "ocr-pdf-to-json", "ocr-pdf-page-texts", "ocr-image-numbers",
    "ocr-image-emails", "ocr-image-urls", "ocr-image-table-csv",
    "ocr-image-clean-text",
}
ARCHIVE_ADVANCED_IDS = {
    "tar-extract", "gzip-compress", "gzip-decompress", "zip-list",
    "zip-integrity", "zip-flatten", "tar-list", "gzip-info",
    "zip-to-tar",
}
UTILITY_ADVANCED_IDS = {
    "file-mime-report", "text-statistics", "text-clean",
    "text-deduplicate", "text-sort", "filename-normalizer",
    "csv-validator", "json-validator", "number-list-analyzer",
    "text-to-base64",
}

_OPTIONS_SINGLE = {
    "pdf-booklet", "lms-pdf-size-optimizer", "social-media-image-resizer",
    "lms-question-bank-formatter", "bulk-certificate-maker",
}


def engine_name_for(tool_id: str) -> str:
    if tool_id in {"assignment-cover-page", "omr-bubble-sheet", "bulk-certificate-maker"}:
        return "pymupdf"
    if tool_id in {"social-media-image-resizer", "quote-social-graphic"}:
        return "pillow"
    if tool_id in {"word-to-pdf", "excel-to-pdf", "ppt-to-pdf", "txt-to-pdf", "html-to-pdf", "csv-to-pdf", "markdown-to-pdf"}:
        return "libreoffice"
    if tool_id == "markdown-to-html":
        return "markdown"
    if tool_id == "csv-to-xlsx":
        return "openpyxl"
    if tool_id.startswith("ocr-") or tool_id in {"pdf-ocr", "image-ocr"}:
        return "tesseract+pymupdf"
    if tool_id.startswith("pdf-"):
        return "pymupdf+pypdf"
    if tool_id.startswith("image-"):
        return "pillow"
    if tool_id.startswith(("zip-", "tar-", "gzip-", "bzip2-", "xz-")):
        return "python-archive"
    if tool_id.startswith(("file-", "checksum-")):
        return "hashlib"
    if tool_id.startswith(("text-", "url-", "base64-", "hex-", "uuid-", "regex-")):
        return "stdlib"
    if tool_id.startswith(("xml-", "json-", "xlsx-", "docx-", "pptx-", "csv-", "html-", "markdown-")):
        return "office-libraries"
    return "stdlib"


def _single(handler: Callable, *, with_options: bool = False) -> Callable:
    def run(safe_input, output_dir, param, timeout, max_pdf_pages, options):
        if with_options:
            return handler(safe_input, output_dir, param, timeout, max_pdf_pages, options)
        return handler(safe_input, output_dir, param, timeout, max_pdf_pages)
    return run


def _advanced(handler: Callable, tool_id: str) -> Callable:
    def run(safe_input, output_dir, param, timeout, max_pdf_pages, options):
        return handler(safe_input, output_dir, param, timeout, max_pdf_pages, tool_id, options)
    return run


def _combine(handler: Callable) -> Callable:
    def run(safe_inputs, output_dir, param, timeout, max_pdf_pages, options):
        return handler(safe_inputs, output_dir, param)
    return run


def _combine_tool(handler: Callable, tool_id: str) -> Callable:
    def run(safe_inputs, output_dir, param, timeout, max_pdf_pages, options):
        return handler(safe_inputs, output_dir, param, tool_id, options)
    return run


def _generator(handler: Callable) -> Callable:
    def run(safe_inputs, output_dir, param, timeout, max_pdf_pages, options):
        return handler(output_dir, options)
    return run


def _uuid_generator(safe_inputs, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / "InfinityConverter-UUIDs.txt"
    mega_tools.uuid_list(param or "10", out)
    return out, "text/plain"


def build_operations() -> dict[str, Operation]:
    operations: dict[str, Operation] = {}

    def add(tool_id: str, mode: str, handler: Callable):
        if tool_id in operations:
            raise RuntimeError(f"Duplicate backend operation: {tool_id}")
        tool = TOOLS.get(tool_id)
        if tool is None:
            raise RuntimeError(f"Backend operation has no public tool: {tool_id}")
        operations[tool_id] = Operation(
            id=tool_id,
            mode=mode,  # type: ignore[arg-type]
            handler=handler,
            engine=engine_name_for(tool_id),
            force_zip=tool.output_ext == ".zip",
        )

    # Stable core paths now bypass the historical compatibility dispatcher.
    for tool_id, handler in core_handlers.CORE_COMBINE_HANDLERS.items():
        add(tool_id, "combine", _combine(handler))
    for tool_id, handler in legacy.COMBINE_HANDLERS.items():
        if tool_id not in core_handlers.CORE_COMBINE_HANDLERS:
            add(tool_id, "combine", _combine(handler))

    add("csv-merge-deduplicate", "combine", lambda safe_inputs, output_dir, param, timeout, max_pdf_pages, options: legacy._h_csv_merge(safe_inputs, output_dir, param, options))

    for tool_id in mega_tools.COMBINE_IDS:
        add(tool_id, "combine", _combine_tool(legacy._h_mega_combine, tool_id))

    # No-upload generators.
    add("assignment-cover-page", "generator", _generator(legacy._h_assignment_cover))
    add("omr-bubble-sheet", "generator", _generator(legacy._h_omr_sheet))
    add("quote-social-graphic", "generator", _generator(legacy._h_quote_graphic))
    for tool_id in mega_tools.NO_INPUT_IDS:
        add(tool_id, "generator", _uuid_generator)

    # Stable classic handlers are first-class modules; remaining legacy paths
    # stay wrapped until their implementation is migrated domain by domain.
    for tool_id, handler in core_handlers.CORE_SINGLE_HANDLERS.items():
        add(tool_id, "single", _single(handler))
    for tool_id, handler in legacy.SINGLE_HANDLERS.items():
        if tool_id not in core_handlers.CORE_SINGLE_HANDLERS:
            add(tool_id, "single", _single(handler, with_options=tool_id in _OPTIONS_SINGLE))

    # 6.x advanced groups now register declaratively rather than living in a
    # giant ConversionEngine if/elif chain.
    for tool_id in PDF_ADVANCED_IDS:
        add(tool_id, "single", _advanced(legacy._h_adv_pdf, tool_id))
    for tool_id in IMAGE_ADVANCED_IDS:
        add(tool_id, "single", _advanced(legacy._h_adv_image, tool_id))
    for tool_id in OFFICE_ADVANCED_IDS:
        add(tool_id, "single", _advanced(legacy._h_adv_office, tool_id))
    for tool_id in OCR_ADVANCED_IDS:
        add(tool_id, "single", _advanced(legacy._h_adv_ocr, tool_id))
    for tool_id in ARCHIVE_ADVANCED_IDS:
        add(tool_id, "single", _advanced(legacy._h_adv_archive, tool_id))
    for tool_id in UTILITY_ADVANCED_IDS:
        add(tool_id, "single", _advanced(legacy._h_adv_utility, tool_id))

    mega_single_ids = (
        set(mega_tools.PDF_IDS)
        | set(mega_tools.IMAGE_IDS)
        | set(mega_tools.OFFICE_IDS)
        | set(mega_tools.OCR_IDS)
        | set(mega_tools.ARCHIVE_IDS)
        | set(mega_tools.UTILITY_IDS)
    ) - set(mega_tools.COMBINE_IDS) - set(mega_tools.NO_INPUT_IDS)
    for tool_id in mega_single_ids:
        add(tool_id, "single", _advanced(legacy._h_mega, tool_id))

    return operations


OPERATIONS = build_operations()


def get_operation(tool_id: str) -> Operation | None:
    return OPERATIONS.get(tool_id)


def operation_ids() -> frozenset[str]:
    return frozenset(OPERATIONS)

from collections import Counter

from converters.engine import COMBINE_HANDLERS, SINGLE_HANDLERS
from converters.validation import MIME_BY_EXTENSION
from core.tool_registry import TOOLS, list_tools, PREMIUM_TOOL_IDS
from security.file_guard import ALLOWED_SIGNATURES
from converters import mega_tools

ADVANCED_GROUPS = {
    "pdf": {"pdf-reorder-pages","pdf-rotate-selected","pdf-page-numbers","pdf-watermark-text","pdf-grayscale","pdf-remove-blank-pages","pdf-crop-margins","pdf-poster-split","pdf-contact-sheet","pdf-password-protect"},
    "images": {"image-crop","image-flip","image-grayscale","image-sharpen","image-auto-contrast","image-sepia","image-strip-metadata","image-favicon-pack","image-contact-sheet","image-set-dpi"},
    "office": {"docx-to-text","docx-to-html","xlsx-to-csv","xlsx-to-json","pptx-to-text","csv-to-json","json-to-csv","json-to-xlsx","xml-to-json","text-to-json"},
    "ocr": {"ocr-image-to-pdf","ocr-pdf-to-searchable","ocr-image-to-json","ocr-pdf-to-json","ocr-pdf-page-texts","ocr-image-numbers","ocr-image-emails","ocr-image-urls","ocr-image-table-csv","ocr-image-clean-text"},
    "archive": {"tar-create","tar-extract","gzip-compress","gzip-decompress","zip-list","zip-integrity","zip-flatten","tar-list","gzip-info","zip-to-tar"},
    "utilities": {"file-mime-report","text-statistics","text-clean","text-deduplicate","text-sort","filename-normalizer","csv-validator","json-validator","number-list-analyzer","text-to-base64"},
}
SPECIAL = {"assignment-cover-page","omr-bubble-sheet","quote-social-graphic","csv-merge-deduplicate"}

def test_registry_integrity_and_category_expansion():
    assert len(TOOLS) == 162
    counts = Counter(tool.category for tool in TOOLS.values())
    assert counts == {"pdf": 36, "images": 28, "office": 32, "ocr": 22, "archive": 22, "utilities": 22}
    assert all(len(group) == 10 and group <= set(TOOLS) for group in ADVANCED_GROUPS.values())
    slugs = [item["slug"] for item in list_tools()]
    assert len(slugs) == len(set(slugs)) == 162
    assert PREMIUM_TOOL_IDS <= set(TOOLS)

    for tool in TOOLS.values():
        assert tool.output_ext in MIME_BY_EXTENSION
        assert all(ext in ALLOWED_SIGNATURES or ext in {".*", "*"} for ext in tool.input_ext)
        mega_ids = (mega_tools.PDF_IDS | mega_tools.IMAGE_IDS | mega_tools.OFFICE_IDS | mega_tools.OCR_IDS | mega_tools.ARCHIVE_IDS | mega_tools.UTILITY_IDS | mega_tools.COMBINE_IDS | mega_tools.NO_INPUT_IDS)
        assert tool.id in COMBINE_HANDLERS or tool.id in SINGLE_HANDLERS or tool.id in SPECIAL or tool.id in mega_ids or any(tool.id in group for group in ADVANCED_GROUPS.values())
        for field in tool.fields:
            if field.type == "select":
                assert field.choices
                assert field.default in {choice[0] for choice in field.choices}

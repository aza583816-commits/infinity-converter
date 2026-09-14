from collections import Counter

from converters.operations import operation_ids
from converters.validation import MIME_BY_EXTENSION
from core.tool_registry import TOOLS, list_tools, PREMIUM_TOOL_IDS
from security.file_guard import ALLOWED_SIGNATURES

ADVANCED_GROUPS = {
    "pdf": {"pdf-reorder-pages","pdf-rotate-selected","pdf-page-numbers","pdf-watermark-text","pdf-grayscale","pdf-remove-blank-pages","pdf-crop-margins","pdf-poster-split","pdf-contact-sheet","pdf-password-protect"},
    "images": {"image-crop","image-flip","image-grayscale","image-sharpen","image-auto-contrast","image-sepia","image-strip-metadata","image-favicon-pack","image-contact-sheet","image-set-dpi"},
    "office": {"docx-to-text","docx-to-html","xlsx-to-csv","xlsx-to-json","pptx-to-text","csv-to-json","json-to-csv","json-to-xlsx","xml-to-json","text-to-json"},
    "ocr": {"ocr-image-to-pdf","ocr-pdf-to-searchable","ocr-image-to-json","ocr-pdf-to-json","ocr-pdf-page-texts","ocr-image-numbers","ocr-image-emails","ocr-image-urls","ocr-image-table-csv","ocr-image-clean-text"},
    "archive": {"tar-create","tar-extract","gzip-compress","gzip-decompress","zip-list","zip-integrity","zip-flatten","tar-list","gzip-info","zip-to-tar"},
    "utilities": {"file-mime-report","text-statistics","text-clean","text-deduplicate","text-sort","filename-normalizer","csv-validator","json-validator","number-list-analyzer","text-to-base64"},
}


def test_registry_integrity_and_category_expansion():
    assert len(TOOLS) == 162
    counts = Counter(tool.category for tool in TOOLS.values())
    assert counts == {"pdf": 36, "images": 28, "office": 32, "ocr": 22, "archive": 22, "utilities": 22}
    assert all(len(group) == 10 and group <= set(TOOLS) for group in ADVANCED_GROUPS.values())
    slugs = [item["slug"] for item in list_tools()]
    assert len(slugs) == len(set(slugs)) == 162
    assert PREMIUM_TOOL_IDS <= set(TOOLS)

    # The declarative Operation registry is the runtime source of truth. Every
    # public server tool must have exactly one registered operation; legacy
    # compatibility dictionaries are intentionally not imported here.
    operations = operation_ids()
    assert operations == set(TOOLS)

    for tool in TOOLS.values():
        assert tool.output_ext in MIME_BY_EXTENSION
        assert all(ext in ALLOWED_SIGNATURES or ext in {".*", "*"} for ext in tool.input_ext)
        for field in tool.fields:
            if field.type == "select":
                assert field.choices
                assert field.default in {choice[0] for choice in field.choices}

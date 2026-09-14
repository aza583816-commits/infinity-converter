from pathlib import Path

from converters import product_handlers
from converters.operations import get_operation

ROOT = Path(__file__).resolve().parents[1]


def test_product_specific_workflows_are_first_class_operations():
    expected = {
        "csv-merge-deduplicate",
        "pdf-booklet",
        "lms-pdf-size-optimizer",
        "social-media-image-resizer",
        "bulk-certificate-maker",
        "lms-question-bank-formatter",
        "assignment-cover-page",
        "omr-bubble-sheet",
        "quote-social-graphic",
    }
    assert all(get_operation(tool_id) is not None for tool_id in expected)
    assert set(product_handlers.OPTION_SINGLE_HANDLERS) == {
        "pdf-booklet",
        "lms-pdf-size-optimizer",
        "social-media-image-resizer",
        "bulk-certificate-maker",
        "lms-question-bank-formatter",
    }
    assert set(product_handlers.GENERATOR_HANDLERS) == {
        "assignment-cover-page", "omr-bubble-sheet", "quote-social-graphic"
    }


def test_runtime_registry_does_not_use_legacy_product_helpers():
    source = (ROOT / "converters/operations.py").read_text(encoding="utf-8")
    for name in (
        "legacy._h_csv_merge",
        "legacy._h_assignment_cover",
        "legacy._h_omr_sheet",
        "legacy._h_quote_graphic",
    ):
        assert name not in source
    assert "product_handlers.csv_merge_deduplicate" in source
    assert "product_handlers.GENERATOR_HANDLERS" in source
    assert "product_handlers.OPTION_SINGLE_HANDLERS" in source

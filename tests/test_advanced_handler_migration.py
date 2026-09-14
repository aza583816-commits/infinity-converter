from pathlib import Path

from converters import advanced_handlers
from converters.operations import (
    ARCHIVE_ADVANCED_IDS,
    IMAGE_ADVANCED_IDS,
    OCR_ADVANCED_IDS,
    OFFICE_ADVANCED_IDS,
    PDF_ADVANCED_IDS,
    UTILITY_ADVANCED_IDS,
    get_operation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_all_advanced_families_are_registered_after_first_class_migration():
    ids = (
        PDF_ADVANCED_IDS
        | IMAGE_ADVANCED_IDS
        | OFFICE_ADVANCED_IDS
        | OCR_ADVANCED_IDS
        | ARCHIVE_ADVANCED_IDS
        | UTILITY_ADVANCED_IDS
    )
    assert len(ids) == 59
    assert all(get_operation(tool_id) is not None for tool_id in ids)


def test_operations_no_longer_route_advanced_families_through_legacy_dispatcher():
    source = (ROOT / "converters/operations.py").read_text(encoding="utf-8")
    for legacy_name in (
        "legacy._h_adv_pdf",
        "legacy._h_adv_image",
        "legacy._h_adv_office",
        "legacy._h_adv_ocr",
        "legacy._h_adv_archive",
        "legacy._h_adv_utility",
    ):
        assert legacy_name not in source
    assert "advanced_handlers.pdf" in source
    assert "advanced_handlers.image" in source
    assert "advanced_handlers.office" in source
    assert "advanced_handlers.ocr" in source
    assert "advanced_handlers.archive_tools" in source
    assert "advanced_handlers.utility" in source


def test_advanced_handler_module_exposes_each_domain_adapter():
    assert callable(advanced_handlers.pdf)
    assert callable(advanced_handlers.image)
    assert callable(advanced_handlers.office)
    assert callable(advanced_handlers.ocr)
    assert callable(advanced_handlers.archive_tools)
    assert callable(advanced_handlers.utility)

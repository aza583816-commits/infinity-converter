from pathlib import Path

from converters import mega_handlers, mega_tools
from converters.operations import get_operation, operation_ids
from core.tooling.catalog import TOOLS

ROOT = Path(__file__).resolve().parents[1]


def test_production_operation_registry_has_no_legacy_dispatch_dependency():
    source = (ROOT / "converters/operations.py").read_text(encoding="utf-8")
    assert "legacy_handlers" not in source
    assert "legacy._h_" not in source
    assert "mega_handlers.single" in source
    assert "mega_handlers.combine" in source


def test_mega_runtime_adapter_covers_every_mega_operation_shape():
    single_ids = (
        set(mega_tools.PDF_IDS)
        | set(mega_tools.IMAGE_IDS)
        | set(mega_tools.OFFICE_IDS)
        | set(mega_tools.OCR_IDS)
        | set(mega_tools.ARCHIVE_IDS)
        | set(mega_tools.UTILITY_IDS)
    ) - set(mega_tools.COMBINE_IDS) - set(mega_tools.NO_INPUT_IDS)
    assert len(single_ids) == 54
    assert len(mega_tools.COMBINE_IDS) == 5
    assert len(mega_tools.NO_INPUT_IDS) == 1
    assert callable(mega_handlers.single)
    assert callable(mega_handlers.combine)
    assert all(get_operation(tool_id) is not None for tool_id in single_ids | set(mega_tools.COMBINE_IDS) | set(mega_tools.NO_INPUT_IDS))


def test_every_public_server_tool_still_has_exactly_one_operation():
    assert operation_ids() == frozenset(TOOLS)
    assert len(operation_ids()) == 162

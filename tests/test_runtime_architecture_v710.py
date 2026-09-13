from collections import Counter
from pathlib import Path

from converters.operations import operation_ids
from core.tooling import TOOLS
from core.tooling.registry import validate_catalog
from core.tooling.runtime import runtime_coverage

ROOT = Path(__file__).resolve().parents[1]


def test_public_tool_registry_has_backend_operation_for_every_tool():
    coverage = runtime_coverage()
    assert coverage.tools == 162
    assert coverage.operations == 162
    assert coverage.missing == ()
    assert coverage.orphaned == ()
    assert coverage.catalog_errors == ()
    assert coverage.healthy
    assert operation_ids() == frozenset(TOOLS)


def test_catalog_is_split_by_domain_with_stable_counts():
    counts = Counter(tool.category for tool in TOOLS.values())
    assert counts == {
        "pdf": 36,
        "images": 28,
        "office": 32,
        "ocr": 22,
        "archive": 22,
        "utilities": 22,
    }
    assert validate_catalog() == ()
    for domain in counts:
        assert (ROOT / "core" / "tooling" / "catalog" / f"{domain}.py").exists()


def test_old_registry_and_engine_are_compatibility_orchestration_layers_only():
    legacy_registry = (ROOT / "core" / "tool_registry.py").read_text(encoding="utf-8")
    engine = (ROOT / "converters" / "engine.py").read_text(encoding="utf-8")
    assert "Compatibility layer" in legacy_registry
    assert "Tool(" not in legacy_registry
    assert "Generic orchestrator" in engine
    assert "elif tool.id" not in engine
    assert "get_operation(tool.id)" in engine

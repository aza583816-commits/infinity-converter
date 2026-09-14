"""Fast, dependency-light repository audit for Infinity Converter 7.1+."""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runtime_tool_ids() -> set[str]:
    tooling = importlib.import_module("core.tooling")
    return set(tooling.TOOLS)


def runtime_operation_ids() -> set[str]:
    operations = importlib.import_module("converters.operations")
    return set(operations.operation_ids())


def runtime_mega_ids() -> set[str]:
    """Retained only to report migration progress, not architecture coverage."""
    mega = importlib.import_module("converters.mega_tools")
    ids = set().union(
        mega.PDF_IDS,
        mega.IMAGE_IDS,
        mega.OFFICE_IDS,
        mega.OCR_IDS,
        mega.ARCHIVE_IDS,
        mega.UTILITY_IDS,
    )
    ids |= mega.COMBINE_IDS | mega.NO_INPUT_IDS
    return ids


def main() -> int:
    python_files = [
        path for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts and "venv" not in path.parts and "__pycache__" not in path.parts
    ]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))

    tools = runtime_tool_ids()
    operations = runtime_operation_ids()
    missing = tools - operations
    orphaned = operations - tools

    registry = importlib.import_module("core.tooling.registry")
    catalog_errors = tuple(registry.validate_catalog())

    print(f"Python syntax: OK ({len(python_files)} files scanned)")
    print(f"Registered tools: {len(tools)}")
    print(f"Backend operations: {len(operations)}")
    print(f"Legacy high-value implementations retained: {len(runtime_mega_ids() & tools)}")
    print(f"Missing backend operations: {len(missing)}")
    print(f"Orphan backend operations: {len(orphaned)}")
    print(f"Catalog integrity errors: {len(catalog_errors)}")
    if missing:
        print("  missing: " + ", ".join(sorted(missing)))
    if orphaned:
        print("  orphaned: " + ", ".join(sorted(orphaned)))
    if catalog_errors:
        print("  catalog: " + "; ".join(catalog_errors))
    if len(tools) != 162 or len(operations) != 162 or missing or orphaned or catalog_errors:
        return 1

    required = [
        ROOT / "core/tooling/models.py",
        ROOT / "core/tooling/registry.py",
        ROOT / "core/tooling/runtime.py",
        ROOT / "core/tooling/catalog/pdf.py",
        ROOT / "core/tooling/catalog/images.py",
        ROOT / "core/tooling/catalog/office.py",
        ROOT / "core/tooling/catalog/ocr.py",
        ROOT / "core/tooling/catalog/archive.py",
        ROOT / "core/tooling/catalog/utilities.py",
        ROOT / "converters/contracts.py",
        ROOT / "converters/operations.py",
        ROOT / "converters/engine.py",
        ROOT / "security/file_guard.py",
        ROOT / "static/css/app.css",
        ROOT / "static/js/app.js",
        ROOT / "templates/base.html",
        ROOT / "templates/index.html",
        ROOT / "templates/tool.html",
        ROOT / "api/ai.py",
        ROOT / "SECURITY_AND_ARCHITECTURE_AUDIT.md",
    ]
    missing_assets = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing_assets:
        print("Missing required files:", ", ".join(missing_assets))
        return 1

    flags = (ROOT / ".env.example").read_text(encoding="utf-8")
    if "PUBLIC_AUTH_ENABLED=0" not in flags or "PUBLIC_BILLING_ENABLED=0" not in flags:
        print("Public auth/billing defaults are not disabled.")
        return 1
    from config.settings import settings
    if f"APP_VERSION={settings.app_version}" not in flags:
        print(".env.example release version is not synchronized.")
        return 1

    print("Public auth/billing defaults: hidden")
    print("Required architecture/assets/docs: OK")
    print("Repository audit PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fast, dependency-light repository audit for Infinity Converter 6.0."""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runtime_tool_ids() -> set[str]:
    registry = importlib.import_module("core.tool_registry")
    return {tool.id for tool in registry.TOOLS.values()}


def runtime_mega_ids() -> set[str]:
    mega = importlib.import_module("converters.mega_tools")
    ids = set().union(mega.PDF_IDS, mega.IMAGE_IDS, mega.OFFICE_IDS, mega.OCR_IDS, mega.ARCHIVE_IDS, mega.UTILITY_IDS)
    ids |= mega.COMBINE_IDS | mega.NO_INPUT_IDS
    return ids


def source_engine_ids() -> set[str]:
    tree = ast.parse((ROOT / "converters/engine.py").read_text(encoding="utf-8"))
    ids: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            ids.add(node.value)
    return ids


def main() -> int:
    python_files = [
        path for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    ]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"))

    tools = runtime_tool_ids()
    mega = runtime_mega_ids()
    engine_strings = source_engine_ids()
    covered = (mega & tools) | {value for value in engine_strings if value in tools}
    missing = tools - covered

    print(f"Python syntax: OK ({len(python_files)} files scanned)")
    print(f"Registered tools: {len(tools)}")
    print(f"New mega tools: {len(mega & tools)}")
    print(f"Engine source references: {len(engine_strings & tools)}")
    print(f"Missing handler references: {len(missing)}")
    if missing:
        print("  " + ", ".join(sorted(missing)))
        return 1

    required = [
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

    print("Public auth/billing defaults: hidden")
    print("Required assets/docs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fast, dependency-light repository audit for Infinity Converter."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tool_ids() -> set[str]:
    tree = ast.parse((ROOT / "core/tool_registry.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "TOOLS" for target in node.targets
        ):
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    return set()


def handler_ids() -> set[str]:
    tree = ast.parse((ROOT / "converters/engine.py").read_text(encoding="utf-8"))
    ids = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"COMBINE_HANDLERS", "SINGLE_HANDLERS"}
            for target in node.targets
        ) and isinstance(node.value, ast.Dict):
            ids.update(
                key.value for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Attribute):
            continue
        if not isinstance(node.left.value, ast.Name) or node.left.value.id != "tool" or node.left.attr != "id":
            continue
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                ids.add(comparator.value)
    return ids


def main() -> int:
    python_files = [
        path for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    ]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"))

    tools = tool_ids()
    handlers = handler_ids()
    missing = tools - handlers
    print(f"Python syntax: OK ({len(python_files)} files scanned)")
    print(f"Registered tools: {len(tools)}")
    print(f"Engine handlers: {len(handlers)}")
    print(f"Missing handlers: {len(missing)}")
    if missing:
        print("  " + ", ".join(sorted(missing)))
        return 1

    required = [
        ROOT / "static/css/app.css",
        ROOT / "static/js/app.js",
        ROOT / "templates/base.html",
        ROOT / "SECURITY_AND_ARCHITECTURE_AUDIT.md",
    ]
    missing_assets = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing_assets:
        print("Missing required files:", ", ".join(missing_assets))
        return 1
    print("Required assets/docs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

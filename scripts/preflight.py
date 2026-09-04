"""Production preflight checks for the Python 3.11 Railway runtime."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []

for path in ROOT.rglob("*.py"):
    if "__pycache__" in path.parts:
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))
    except SyntaxError as exc:
        errors.append(f"{path}: Python 3.11 syntax error: {exc}")

if errors:
    print("PRODUCTION PREFLIGHT FAILED")
    print("\n".join(errors))
    sys.exit(1)

print("Production preflight: Python 3.11 syntax OK")

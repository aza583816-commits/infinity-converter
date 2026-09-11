"""Production preflight checks for the Python 3.11 Railway runtime.

This intentionally checks more than syntax: it imports the production app with
an isolated SQLite database, renders representative routes, and verifies the
Railway health endpoint before an image can be built.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import sys
import tempfile

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

print(f"Production preflight: Python 3.11 syntax OK ({sum(1 for _ in ROOT.rglob('*.py'))} files scanned)")

# Import/startup smoke test. Use an isolated SQLite database so the Docker
# build never depends on Railway/Postgres availability.
with tempfile.TemporaryDirectory(prefix="infinity-preflight-") as tmp:
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tmp) / 'preflight.db'}")
    os.environ.setdefault("PUBLIC_AUTH_ENABLED", "0")
    os.environ.setdefault("PUBLIC_BILLING_ENABLED", "0")
    os.environ.setdefault("SECRET_KEY", "preflight-only-secret")
    sys.path.insert(0, str(ROOT))
    try:
        from app_factory import create_app
        app = create_app()
        app.testing = True
        client = app.test_client()
        checks = {
            "/api/v2/healthz": 200,
            "/": 200,
            "/tools": 200,
            "/blog": 200,
            "/about": 200,
            "/robots.txt": 200,
            "/sitemap.xml": 200,
            "/definitely-not-a-real-page": 404,
        }
        for path, expected in checks.items():
            actual = client.get(path).status_code
            if actual != expected:
                errors.append(f"startup route {path}: expected {expected}, got {actual}")
        if not errors:
            health = client.get("/api/v2/healthz").get_json() or {}
            if health.get("status") != "ok":
                errors.append(f"health endpoint returned unexpected payload: {health}")
    except Exception as exc:
        errors.append(f"application startup smoke test failed: {type(exc).__name__}: {exc}")

if errors:
    print("PRODUCTION PREFLIGHT FAILED")
    print("\n".join(errors))
    sys.exit(1)

print("Production preflight: app startup + representative routes OK")

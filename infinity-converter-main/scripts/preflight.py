from __future__ import annotations

import ast
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def syntax_check():
    count = 0
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))
        count += 1
    print(f"Python 3.11 syntax OK: {count} files")

def startup_routes():
    with tempfile.TemporaryDirectory(prefix="infinity-preflight-") as temp:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(temp) / 'preflight.db'}"
        os.environ["PUBLIC_AUTH_ENABLED"] = "0"
        os.environ["PUBLIC_BILLING_ENABLED"] = "0"
        os.environ.setdefault("SECRET_KEY", "preflight-only-secret-not-for-production")
        sys.path.insert(0, str(ROOT))
        from app_factory import create_app
        app = create_app()
        app.config.update(TESTING=True)
        routes = ["/api/v2/healthz", "/", "/tools", "/blog", "/about", "/privacy", "/robots.txt", "/tools/word-to-pdf"]
        with app.test_client() as client:
            for route in routes:
                response = client.get(route)
                if response.status_code != 200:
                    raise RuntimeError(f"startup route {route} returned {response.status_code}")
                print(f"startup route {route} OK")

def main():
    syntax_check()
    startup_routes()
    print("Production preflight PASS")

if __name__ == "__main__":
    main()

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
        # A harmless test-shaped publisher ID lets the build verify that the
        # loader appears only on approved content surfaces. Production still
        # reads the real value from Railway Variables.
        os.environ.setdefault("ADSENSE_CLIENT_ID", "ca-pub-0000000000000000")
        sys.path.insert(0, str(ROOT))
        from app_factory import create_app

        app = create_app()
        app.config.update(TESTING=True)
        routes = [
            "/api/v2/healthz",
            "/",
            "/tools",
            "/blog",
            "/blog/word-to-pdf-without-losing-formatting",
            "/about",
            "/trust",
            "/editorial",
            "/contact",
            "/privacy",
            "/robots.txt",
            "/sitemap.xml",
            "/ads.txt",
            "/sw.js",
            "/tools/word-to-pdf",
        ]
        with app.test_client() as client:
            for route in routes:
                response = client.get(route)
                if response.status_code != 200:
                    raise RuntimeError(f"startup route {route} returned {response.status_code}")
                print(f"startup route {route} OK")

            home = client.get("/").get_data(as_text=True)
            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in home:
                raise RuntimeError("AdSense content-page loader guard did not allow homepage")

            article = client.get("/blog/word-to-pdf-without-losing-formatting").get_data(as_text=True)
            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in article:
                raise RuntimeError("AdSense content-page loader guard did not allow article")

            error = client.get("/this-page-does-not-exist")
            error_html = error.get_data(as_text=True)
            if error.status_code != 404 or "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in error_html:
                raise RuntimeError("404 page must not load AdSense serving script")
            if 'name="robots" content="noindex,follow"' not in error_html:
                raise RuntimeError("404 page must be noindex,follow")

            browser = client.get("/browser-tools/unit-converter")
            browser_html = browser.get_data(as_text=True)
            if browser.status_code != 200:
                raise RuntimeError("browser tool route failed")
            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in browser_html:
                raise RuntimeError("thin browser tool must not load AdSense serving script")
            if 'name="robots" content="noindex,follow"' not in browser_html:
                raise RuntimeError("thin browser tool must be noindex,follow")

            legacy = client.get("/length/meter/inch/100")
            if legacy.status_code != 301 or "/browser-tools/unit-converter" not in legacy.headers.get("Location", ""):
                raise RuntimeError("legacy unit URL redirect guard failed")

            old_tool = client.get("/split-pdf")
            if old_tool.status_code != 301 or "/tools/split-pdf" not in old_tool.headers.get("Location", ""):
                raise RuntimeError("legacy top-level tool redirect guard failed")

            old_alias = client.get("/html-entity")
            if old_alias.status_code != 301 or "/browser-tools/html-entity-converter" not in old_alias.headers.get("Location", ""):
                raise RuntimeError("legacy top-level alias redirect guard failed")

            reviewed = client.get("/tools/word-to-pdf")
            reviewed_html = reviewed.get_data(as_text=True)
            if 'name="robots" content="noindex,follow"' in reviewed_html:
                raise RuntimeError("reviewed tool page must remain indexable")
            for marker in ("PROCESSING TRANSPARENCY", "load-sample", "result-metrics"):
                if marker not in reviewed_html:
                    raise RuntimeError(f"reviewed tool experience is missing {marker}")
            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in reviewed_html:
                raise RuntimeError("reviewed indexable tool should allow AdSense loader")

            unreviewed = client.get("/tools/pdf-to-markdown")
            if unreviewed.status_code != 200:
                raise RuntimeError("unreviewed tool route failed")
            unreviewed_html = unreviewed.get_data(as_text=True)
            if 'name="robots" content="noindex,follow"' not in unreviewed_html:
                raise RuntimeError("unreviewed tool must be noindex,follow")
            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in unreviewed_html:
                raise RuntimeError("unreviewed tool must not load AdSense serving script")

            english_home = client.get("/?lang=en").get_data(as_text=True)
            if 'hreflang="en"' not in english_home or '?lang=en' not in english_home:
                raise RuntimeError("crawlable English URL/hreflang guard failed")
            if "/set-language/en" in english_home:
                raise RuntimeError("visible language switch must not depend on cookie-only route")
            if "v.infinityconverter@gmail.com" not in home:
                raise RuntimeError("official support email missing from public shell")

            robots = client.get("/robots.txt").get_data(as_text=True)
            if "Sitemap:" not in robots or "Disallow: /set-language/" not in robots:
                raise RuntimeError("robots.txt quality guard failed")
            ads = client.get("/ads.txt").get_data(as_text=True)
            if "google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0" not in ads:
                raise RuntimeError("ads.txt publisher-format guard failed")
            service_worker = client.get("/sw.js").get_data(as_text=True)
            if "infinity-static-v6.1.2" not in service_worker or "url.pathname.startsWith('/static/')" not in service_worker:
                raise RuntimeError("safe static-only service worker guard failed")

            from core.editorial import TOOL_EDITORIAL
            for editorial in TOOL_EDITORIAL.values():
                for sample_url in editorial.get("sample_urls", []):
                    sample = client.get(sample_url)
                    if sample.status_code != 200 or not sample.data:
                        raise RuntimeError(f"reviewed sample asset failed: {sample_url}")

            sitemap = client.get("/sitemap.xml").get_data(as_text=True)
            if "/browser-tools/" in sitemap or "/developer-tools/" in sitemap:
                raise RuntimeError("thin utility surfaces must stay out of sitemap")
            if "/blog/word-to-pdf-without-losing-formatting" not in sitemap:
                raise RuntimeError("Knowledge Center article missing from sitemap")
            if "/trust" not in sitemap or "/editorial" not in sitemap:
                raise RuntimeError("trust/editorial publisher pages missing from sitemap")
            indexed_tool_urls = [line for line in sitemap.split("<url>") if "/tools/" in line]
            if len(indexed_tool_urls) != len(TOOL_EDITORIAL):
                raise RuntimeError("sitemap reviewed-tool count does not match editorial review set")
            print("AdSense/search quality + 6.1.2 experience guards OK")


def main():
    syntax_check()
    startup_routes()
    print("Production preflight PASS")


if __name__ == "__main__":
    main()

from __future__ import annotations

import ast
import io
import json
import os
import shutil
import subprocess
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



def system_dependency_check():
    """Verify external engines that production tools advertise are truly present."""
    for binary in ("libreoffice", "tesseract"):
        resolved = shutil.which(binary)
        if not resolved:
            raise RuntimeError(f"required conversion engine is missing: {binary}")
        print(f"external engine {binary} OK: {resolved}")

    try:
        languages = subprocess.run(
            ["tesseract", "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.lower()
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError("could not verify Tesseract language packs") from exc
    missing = {lang for lang in ("ara", "eng") if lang not in {line.strip() for line in languages.splitlines()}}
    if missing:
        raise RuntimeError(f"required Tesseract languages missing: {sorted(missing)}")
    print("Tesseract ara+eng language packs OK")

    try:
        version = subprocess.run(
            ["libreoffice", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError("LibreOffice executable is present but not runnable") from exc
    if not version:
        raise RuntimeError("LibreOffice version check returned no output")
    print(f"LibreOffice runtime OK: {version}")

def startup_routes():
    with tempfile.TemporaryDirectory(prefix="infinity-preflight-") as temp:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(temp) / 'preflight.db'}"
        os.environ["PUBLIC_AUTH_ENABLED"] = "0"
        os.environ["PUBLIC_BILLING_ENABLED"] = "0"
        os.environ.setdefault("SECRET_KEY", "preflight-only-secret-not-for-production")
        os.environ.setdefault("ADSENSE_CLIENT_ID", "ca-pub-0000000000000000")
        sys.path.insert(0, str(ROOT))

        from app_factory import create_app
        from config.settings import settings
        from core.tooling.runtime import assert_runtime_coverage

        coverage = assert_runtime_coverage()
        if coverage.tools != 162 or coverage.operations != 162:
            raise RuntimeError(
                f"runtime registry expected 162/162, got {coverage.tools}/{coverage.operations}"
            )
        print("runtime registry 162/162 OK")

        app = create_app()
        app.config.update(TESTING=True)
        routes = [
            "/api/v2/healthz",
            "/",
            "/assistant",
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

            health = client.get("/api/v2/healthz").get_json()
            if health.get("version") != settings.app_version:
                raise RuntimeError("healthz version does not match Settings.app_version")
            architecture = health.get("architecture") or {}
            if not architecture.get("healthy") or architecture.get("tools") != 162 or architecture.get("operations") != 162:
                raise RuntimeError("healthz runtime architecture guard failed")

            tools_payload = client.get("/api/v2/tools").get_json()
            if tools_payload.get("version") != settings.app_version or len(tools_payload.get("tools", [])) != 162:
                raise RuntimeError("tools API/version registry guard failed")
            if not (tools_payload.get("runtime") or {}).get("healthy"):
                raise RuntimeError("tools API reports backend registry drift")

            # Every public registry entry must resolve to a real independent tool page.
            for tool_payload in tools_payload.get("tools", []):
                slug = tool_payload.get("slug")
                response = client.get(f"/tools/{slug}")
                if response.status_code != 200:
                    raise RuntimeError(f"tool page /tools/{slug} returned {response.status_code}")
            print("all 162 public tool pages resolve OK")

            # Real upload -> validation -> converter -> output-validation -> download
            # smoke path. file-hash is deterministic and requires no external engine.
            inspect_response = client.post(
                "/api/v2/inspect",
                data={"file": (io.BytesIO(b"Infinity preflight\n"), "preflight.txt")},
                content_type="multipart/form-data",
            )
            if inspect_response.status_code != 200 or not (inspect_response.get_json() or {}).get("safe"):
                raise RuntimeError("inspect pipeline smoke test failed")

            convert_response = client.post(
                "/api/v2/convert",
                data={
                    "tool": "file-hash",
                    "files": (io.BytesIO(b"Infinity preflight\n"), "preflight.txt"),
                },
                content_type="multipart/form-data",
                buffered=True,
            )
            if convert_response.status_code != 200:
                raise RuntimeError(f"convert pipeline smoke test failed: {convert_response.status_code}")
            try:
                hash_report = json.loads(convert_response.get_data(as_text=True))
            except json.JSONDecodeError as exc:
                raise RuntimeError("convert smoke output is not valid JSON") from exc
            if not isinstance(hash_report, dict) or not hash_report:
                raise RuntimeError("convert smoke output is empty")
            if not convert_response.headers.get("X-Conversion-Engine"):
                raise RuntimeError("conversion observability headers missing")
            convert_response.close()
            print("inspect -> convert -> validate -> download smoke path OK")

            def real_conversion(tool_id: str, sample_names: tuple[str, ...], extra: dict | None = None):
                uploads = []
                for sample_name in sample_names:
                    sample_path = ROOT / "static" / "samples" / sample_name
                    if not sample_path.is_file() or sample_path.stat().st_size == 0:
                        raise RuntimeError(f"preflight sample missing: {sample_name}")
                    uploads.append((io.BytesIO(sample_path.read_bytes()), sample_name))
                data = {"tool": tool_id}
                if extra:
                    data.update(extra)
                data["files"] = uploads if len(uploads) > 1 else uploads[0]
                response = client.post(
                    "/api/v2/convert",
                    data=data,
                    content_type="multipart/form-data",
                    buffered=True,
                )
                if response.status_code != 200:
                    detail = response.get_json(silent=True) or response.get_data(as_text=True)[:300]
                    raise RuntimeError(f"representative conversion {tool_id} failed: {response.status_code} {detail}")
                body = response.get_data()
                if not body or not response.headers.get("X-Conversion-Engine"):
                    raise RuntimeError(f"representative conversion {tool_id} returned incomplete output")
                response.close()
                print(f"representative conversion {tool_id} OK ({len(body)} bytes)")

            # Exercise each major backend family with tiny bundled samples. This
            # catches UI-only tools and missing system binaries during image build.
            real_conversion("pdf-merge", ("sample-a.pdf", "sample-b.pdf"))
            real_conversion("image-to-png", ("sample-image.jpg",))
            real_conversion("word-to-pdf", ("sample-word.docx",))
            real_conversion("image-ocr", ("sample-scan.png",))
            real_conversion("zip-create", ("sample-note.txt", "sample-image-small.png"))

            home = client.get("/").get_data(as_text=True)
            for marker in ("v7-intelligence-console", "SMART FILE ROUTER", "INFINITY FLOW", 'id="tool-search"'):
                if marker not in home:
                    raise RuntimeError(f"current Intelligence Workspace is missing {marker}")

            arabic_device = client.get("/", headers={"Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8"}).get_data(as_text=True)
            english_device = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"}).get_data(as_text=True)
            unsupported_device = client.get("/", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}).get_data(as_text=True)
            if '<html lang="ar" dir="rtl">' not in arabic_device:
                raise RuntimeError("Arabic browser language did not resolve to Arabic/RTL")
            if '<html lang="en" dir="ltr">' not in english_device or '<html lang="en" dir="ltr">' not in unsupported_device:
                raise RuntimeError("English/unsupported browser language fallback policy failed")

            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in home:
                raise RuntimeError("AdSense content-page loader guard did not allow homepage")

            assistant = client.get("/assistant")
            assistant_html = assistant.get_data(as_text=True)
            if assistant.status_code != 200 or "INFINITY INTELLIGENCE" not in assistant_html:
                raise RuntimeError("Infinity Intelligence workspace route failed")
            if 'name="robots" content="noindex,follow"' not in assistant_html:
                raise RuntimeError("Infinity Intelligence workspace must remain noindex")
            if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in assistant_html:
                raise RuntimeError("Infinity Intelligence workspace must not load AdSense serving script")

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
            for marker in ('id="processing-title"', 'id="load-sample"', 'id="result-metrics"'):
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
            # Public content must not accidentally block search/ad crawlers.
            blocked_agents = ("googlebot", "adsbot-google", "mediapartners-google")
            lower_robots = robots.lower()
            if any(f"user-agent: {agent}\ndisallow: /" in lower_robots for agent in blocked_agents):
                raise RuntimeError("robots.txt blocks a Google crawler from public content")

            ads = client.get("/ads.txt").get_data(as_text=True)
            if "google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0" not in ads:
                raise RuntimeError("ads.txt publisher-format guard failed")

            service_worker = client.get("/sw.js").get_data(as_text=True)
            expected_cache = f"infinity-static-v{settings.app_version}"
            if expected_cache not in service_worker or "url.pathname.startsWith('/static/')" not in service_worker:
                raise RuntimeError("safe static-only service worker/version guard failed")

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
            print(f"AdSense/search quality + {settings.app_version} experience guards OK")


def main():
    syntax_check()
    system_dependency_check()
    startup_routes()
    print("Production preflight PASS")


if __name__ == "__main__":
    main()

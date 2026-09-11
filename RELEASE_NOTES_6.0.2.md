# Infinity Converter 6.0.2 — Production hardening release

This release builds on 6.0.1 with changes focused on deploy safety, crawler correctness, knowledge-center UX, structured SEO data, and archive/XML hardening.

## What changed

- Railway Docker preflight now performs Python 3.11 syntax checks **and** an application startup smoke test using isolated SQLite, including `/api/v2/healthz`, core pages, `/robots.txt`, `/sitemap.xml`, and a 404 route.
- Added a real root `/robots.txt` endpoint. The previous `static/robots.txt` asset remains as a source artifact, but crawlers now receive the file at the required origin root.
- Knowledge Center expanded to 15 curated bilingual articles, with search, category filters, table of contents, reading progress, editorial attribution, review date, and stronger Article/Breadcrumb structured data.
- Tool pages now expose WebApplication, BreadcrumbList, and FAQPage structured data.
- Added WebSite structured data globally.
- Infinity AI copy no longer claims a live Gemini connection merely because an environment variable exists; the panel performs the real server status check.
- XML entity/DOCTYPE rejection now scans the complete uploaded XML payload rather than only the first 2 MiB.
- BZIP2/XZ decompression is bounded to the configured archive expansion limit.
- TAR.GZ/TAR.BZ2 extraction now rejects unsafe/special entries and enforces entry and expanded-size limits before extraction.
- Added static regression coverage for the above production safeguards.

## Verification

- Python 3.11 AST preflight: PASS in the available environment.
- `python -m compileall -q .`: PASS.
- JavaScript `node --check static/js/app.js`: PASS.
- Registry audit: PASS — 162 tools, 0 missing handler references.
- Static regression suite: 14 passed.
- Full Flask/integration suite: not executable in this inspection environment because required runtime packages (Flask/Werkzeug and other dependencies) are not installed and outbound package installation is unavailable. The Docker build must run the enhanced startup preflight in a dependency-complete environment.

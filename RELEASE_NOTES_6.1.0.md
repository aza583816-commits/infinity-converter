# Infinity Converter 6.1.0 — Premium + AdSense-ready release candidate

## Premium experience
- Added a responsive premium visual system with restrained ambient motion, glass surfaces, stronger hierarchy, refined upload/conversion states, and mobile/iPad-friendly touch targets.
- Added persistent light/dark themes and `prefers-reduced-motion` support.
- Added a global Infinity AI dock across public pages.

## Infinity AI
- Public UI/API wording uses **Infinity AI** only; Gemini/provider/model details remain internal server implementation details.
- Public readiness is based on the real server status probe rather than the presence of a key.
- Added a short probe cache to reduce unnecessary provider checks.
- Kept server-side secrets, bounded prompts, rate limiting, and the correct canonical tool slugs in AI recommendations.

## Knowledge Center & SEO
- Expanded the curated bilingual Knowledge Center to 15 original guides.
- Added server-side article search and category filtering.
- Added article table of contents, reading progress, editorial attribution, review date, and related guides.
- Added root `/robots.txt` with canonical sitemap declaration.
- Added global WebSite schema plus Organization schema, tool BreadcrumbList/FAQPage/WebApplication schema, and article BreadcrumbList/Article schema.

## AdSense readiness
- AdSense code remains disabled until real `ADSENSE_CLIENT_ID` and real slot IDs are supplied.
- Added optional clearly labeled home/tool/article ad zones separated from conversion and download controls.
- No fake publisher IDs, ad slots, traffic claims, click prompts, or approval guarantees are bundled.
- `ADSENSE_READINESS.md` documents content, navigation, privacy, consent/CMP, and pre-submission checks.

## Security / reliability
- Kept the production `render_template` error-page fix.
- Added fail-fast startup/route checks to the Docker build preflight.
- XML DOCTYPE/ENTITY rejection scans the entire payload.
- BZIP2/XZ decompression is bounded by the configured expanded-size limit.
- TAR.GZ/TAR.BZ2 extraction rejects traversal, links/special entries, excessive entry counts, and excessive expanded size, and extracts files manually.

## Verification performed for this archive
- Python compile/syntax: PASS.
- JavaScript syntax: PASS.
- Jinja template parse: PASS (15 templates).
- Registry audit: PASS — 162 registered tools, 161 engine references, 0 missing handler references.
- Static quality/AI/SEO/AdSense/Word support/phase-6 tests: PASS — 18 tests.
- Tool registry integrity test: PASS — 1 test.
- Archive security smoke (BZIP2, XZ, safe TAR + traversal rejection): PASS.
- Full Flask/Werkzeug test suite cannot execute in this inspection container because those runtime packages are unavailable here; the production Dockerfile installs them and now runs startup-route preflight during image build.
- A real Infinity AI request must be verified after deployment against the Railway secret.
- No deployment is included in this archive.

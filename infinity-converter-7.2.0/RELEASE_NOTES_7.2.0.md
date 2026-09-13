# Infinity Converter 7.2.0 — Production Cohesion

7.2.0 continues directly from the 7.1 architecture-hardening line. It does not replace the product, remove working tools, or revive an older interface. This release closes contract, entitlement, language, and visual-consistency gaps found during the final production review.

## Backend correctness

- Public catalog remains **162 tools** with **162 declarative backend operations** and zero missing/orphaned routes.
- `ConversionEngine` now enforces the public output contract after conversion: final filename suffix and MIME must agree with the Tool Registry, while intentional multi-file batch containers remain ZIP downloads.
- Fixed Resize Image, Compress Image, and Rotate Image so their actual artifact is JPEG when the registry advertises `.jpg`; image encoding now follows the requested output extension rather than silently preserving the source encoding.
- Archive creation now de-duplicates same-named input members instead of emitting duplicate ZIP/TAR member names.
- Existing zero-trust input/workspace/output guards, per-artifact validation, output size limits, LibreOffice isolation, OCR timeouts, archive-bomb controls, and cleanup behavior remain intact.

## Future account safety without changing today's free product

- `PUBLIC_AUTH_ENABLED=0` and `PUBLIC_BILLING_ENABLED=0` remain the default public state.
- If account mode is enabled later, premium-operation entitlement checks now run before upload/conversion work: anonymous requests receive 401 and free accounts receive 403 for protected tools.
- Existing per-plan file/batch limits and credit consumption remain behind the feature switches.

## Language behavior

- Explicit `?lang=` choice still wins, followed by the saved language cookie.
- Arabic browser/device language resolves to Arabic + RTL.
- English browser/device language resolves to English + LTR.
- Any unsupported primary browser language now falls back to English, matching the product language policy.
- No IP/geographic lookup is used to choose language.

## Design completion

- Preserved the 7.x Intelligence Workspace, Infinity Intelligence, Smart File Router, Quick Jump, drag/drop, batch flows, favorites/recent tools, light/dark themes, RTL/LTR, Knowledge Center, Trust/Editorial pages, and independent tool pages.
- Added a final shared visual-cohesion layer across Tools, Collections, Knowledge Center, articles, How It Works, legal/info pages, auth/account, pricing (still hidden publicly), browser/developer tools, errors, forms, cards, result states, and footer.
- Strengthened small-screen spacing, horizontal-overflow protection, touch target sizing, responsive pricing/cards, focus states, dark-mode parity, and reduced-motion behavior.
- Active assets now report/cache-bust as **7.2.0**; the page shell exposes the same release through `data-release`.

## SEO / AdSense

- Canonical URLs, AR/EN hreflang, robots directives, quality-first sitemap policy, WebSite/Organization/tool/article/FAQ structured data, `ads.txt`, and AdSense page guards are preserved.
- Public content is not globally blocked for Googlebot, AdsBot-Google, or Mediapartners-Google.
- Ad serving remains off assistant, thin/noindex, browser-tool, and error surfaces.

## Release verification

Local release verification completed against the actual 7.2 source tree:

- Python compileall: **PASS**.
- JavaScript syntax: **PASS**.
- Manifest JSON: **PASS**.
- Jinja syntax: **16/16 templates PASS**.
- CSS parser: **0 errors**.
- Repository architecture audit: **PASS — 162 tools / 162 operations / 0 drift**.
- Dependency-light architecture/security/SEO/AdSense/AI/release suite: **63 PASS**.
- Exhaustive direct backend conversion smoke through `validate_upload -> TempWorkspace -> ConversionEngine -> validate_output`: **162/162 PASS**, including LibreOffice and Arabic/English Tesseract tool families.
- The production Dockerfile still runs `python scripts/preflight.py` and complete `pytest -q` inside the exact Python 3.11 dependency image; either failing stops the image build before deployment.

## Production note

No production deployment or DNS change is part of this archive. Railway remains the final environment-specific gate because the local inspection Python environment does not include the Flask/Werkzeug web stack. The Docker build installs the pinned project dependencies and rejects the release if the full Flask regression/preflight suite fails.

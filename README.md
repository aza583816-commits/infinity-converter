# Current release: 7.2.3

This release continues the latest verified `main` history; it does not recreate
the project or roll back the modular handler, Smart Flow, resilience, editorial,
security, accessibility, and performance work already merged. Read
[current release notes](RELEASE_NOTES_7.2.3.md) and the final 7.2.3 audit before
deployment. Earlier reports below are historical evidence only.

Exact 7.2.3 validation evidence is recorded in `FINAL_AUDIT_7.2.3.md` after the
production-image and live deployment gates complete.

Production gates remain mandatory:

```sh
docker build --progress=plain -t infinity-verified .
docker run --rm --network none infinity-verified python scripts/full_operation_smoke.py
docker run --rm --network none infinity-verified python scripts/api_operation_smoke.py
node tests/browser-calculations.cjs
```

# Infinity Converter

Infinity Converter is a Flask 3 file-conversion service deployed on Railway. The frontend is Arabic/English with RTL/LTR support, while conversion remains behind the `/api/v2` API.

## Current product snapshot

- **162 registered tools** across 6 sections.
- **60 additional high-value tools:** 10 each for PDF, Images, Office/Documents/Data, OCR, Archive, and Utilities.
- Local processing with shared upload/output validation.
- Public authentication and billing are **hidden by default**, but their code paths are retained for a future launch.
- Canonical `/tools/<slug>` URLs; legacy `/tool/<id>` URLs redirect to the canonical page.
- Category links can deep-link into filtered tool listings.
- **15 original bilingual Knowledge Center guides** are the main editorial layer, with article structured data and relevant tool links.
- Search indexing is intentionally quality-first: the sitemap focuses on core content plus **21 manually reviewed converter pages**, while the full 162-tool catalog remains available to users.
- AdSense serving is restricted to content-rich, indexable pages; verification metadata remains available without serving ads on thin/error/navigation-only surfaces.

## Tool architecture

The public catalog is split by domain under `core/tooling/catalog/` and is joined by one metadata-backed registry. Every public Tool ID must have exactly one declarative backend `Operation`; `core/tooling/runtime.py` fails health/preflight if the two registries drift. `ConversionEngine` is now a generic orchestrator for concurrency, workspace containment, batch isolation, artifact validation, and observability rather than a tool-specific `if/elif` dispatcher. The old `core/tool_registry.py` path remains only as a compatibility facade while legacy implementation modules are migrated gradually.

| Capability | Main engines | Validation |
| --- | --- | --- |
| PDF | pypdf / PyMuPDF | PDF parser + page checks |
| Images | Pillow | format-aware decode/verify |
| Office | LibreOffice / python-docx / openpyxl / python-pptx | parser + output validation |
| OCR | Tesseract + PyMuPDF | text/searchable-PDF validation |
| Archive | zipfile / tarfile / gzip | traversal, ratio, size and type checks |
| Utilities | Python standard library | type/format validation |

## Local development

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. flask --app app run
PYTHONPATH=. pytest -q
```

Office and OCR integration checks require the corresponding system packages. The production Docker image installs LibreOffice, Arabic/English Tesseract data, and fonts.

## Limits and security

Runtime limits are environment-driven: file size, request size, PDF/OCR pages, archive entry counts, archive expanded size, compression ratio, subprocess timeout, concurrency, and output size. Uploads are checked by extension, signatures, parser validation, and safe-archive inspection. ZIP/TAR archives reject path traversal and special/link entries. Conversion responses are private/no-store.

## Public product state

Public auth/billing is disabled by default:

```text
PUBLIC_AUTH_ENABLED=0
PUBLIC_BILLING_ENABLED=0
```

When disabled, public `/login`, `/register`, `/account`, and `/pricing` routes return 404 and pricing is omitted from the sitemap. The underlying authentication, Paddle, entitlement, and credits code remains in the repository for future activation.

## Deployment

Railway is the production platform. `railway.toml` uses the Dockerfile builder and `/api/v2/healthz` as the health check. The current synchronous API is protected by bounded concurrency and subprocess/request timeouts; a future durable queue can be added behind the same conversion boundary.

## 7.2.0 Production Cohesion

7.2 completes the final release review on top of the current Intelligence Workspace architecture. The 162-tool/162-operation contract remains intact, public output suffix/MIME drift is now rejected, image transform outputs follow their declared format, duplicate archive members are normalized, future entitlement gates are correct while auth/billing stay hidden by default, unsupported browser languages fall back to English, and a shared 7.2 visual layer unifies the remaining public/support surfaces.

Release verification: **162/162 direct conversion smoke PASS**, **63 locally runnable regression tests PASS**, Python/JS/JSON/Jinja/CSS checks PASS, and repository audit reports **162 tools / 162 operations / zero drift**. The shipped Dockerfile remains the final environment-specific gate: it runs production preflight and complete `pytest -q` after installing the pinned Python 3.11 + LibreOffice + Tesseract runtime.

See `RELEASE_NOTES_7.2.0.md` and `FINAL_RELEASE_AUDIT_7.2.0.md`. For an exhaustive local backend gate, run `PYTHONPATH=. python scripts/full_operation_smoke.py`.

## 7.1.0 Architecture Hardening

7.1 completes the architectural part of the Intelligence Workspace rebuild without removing the 162-tool product surface. Tool catalogs are modular by domain, backend operations are declarative and one-to-one with public tools, uploads must cross the shared security gate before conversion, every produced artifact is contained and validated before download/batch packaging, and temporary workspaces now live until streamed responses close.

Security hardening adds MIME/signature/structural validation, Office external-resource guards, isolated LibreOffice profiles with network-deny proxy environment, bounded OCR/compression work, spreadsheet formula-injection neutralization, image pixel limits, encrypted-PDF routing, and non-root Docker execution. Railway's image build now runs production preflight plus the complete pytest regression suite before an image can be deployed.

See `RELEASE_NOTES_7.1.0.md` and `FINAL_RELEASE_AUDIT_7.1.0.md`.

### 7.1 local verification snapshot

- Public tools: **162**.
- Backend operations: **162**; missing/orphaned: **0/0**.
- Direct validated conversion smoke: **162/162 tools PASS** using generated/bundled safe fixtures, including LibreOffice and Tesseract families.
- Dependency-light architecture/security/SEO/AdSense/AI tests: **56 PASS**.
- Python compileall, JavaScript syntax, manifest JSON, 16 Jinja templates, CSS parse: PASS.
- Full Flask route/preflight and complete pytest suite are enforced again inside the Railway/Docker Python 3.11 image.

## 7.0.0 Intelligence Workspace

The current release rebuilds the product around **Infinity Intelligence** while preserving the full 162-tool converter catalog and its existing security/validation boundaries. Users can describe an outcome in natural language, use the Smart File Router, browse all tools directly, or continue from converter results/errors with contextual guidance. A local Smart Core provides common intent routing even when the enhanced AI provider is unavailable.

See `RELEASE_NOTES_7.0.0.md` and `FINAL_RELEASE_AUDIT_7.0.0.md` for the complete redesign, AI architecture, privacy boundary, and verification record.

### 7.0 validation snapshot

- Version: 7.0.0
- Registered tools: 162.
- Missing handler references: 0.
- Python compileall: PASS.
- JavaScript syntax: PASS.
- Jinja parse: 16 templates PASS.
- Static quality/SEO/AdSense/AI regression selection: 41/41 PASS.
- Full Flask startup/preflight remains a Docker/Railway-environment check because the inspection container does not include Flask/Werkzeug.

## Previous 6.1.2 AdSense quality hardening

See `FINAL_RELEASE_AUDIT_6.1.2.md` for the quality-hardening verification matrix, `RELEASE_NOTES_6.1.2.md` for the patch summary, and `ADSENSE_READINESS.md` for the final monetization-readiness checklist.

### Highlights

- 162 registered tools across PDF, Images, Office & Data, OCR, Archive, and Utilities.
- 21 manually reviewed/indexable converter pages with implementation-specific bilingual guidance, processing transparency, safe samples, and result metrics.
- Quiet Luxury / Living Interface redesign with ambient aurora/cell motion, restrained premium palette, light/dark themes, RTL/LTR, keyboard/touch support, and reduced-motion behavior.
- Smart File Router inspects basic file metadata locally and suggests compatible reviewed tools without uploading the file.
- Global Quick Jump command palette, local recent/favorite shortcuts, static-only PWA caching, and finished Infinity Flow workflow cards.
- Infinity AI is the only public AI brand; the external provider and model remain server-side implementation details.
- 15 original bilingual Knowledge Center guides plus Trust & Security and Editorial Policy pages.
- AdSense serving is limited to content-rich/indexable surfaces; thin/noindex/error/navigation-only surfaces do not load the ad-serving script.
- Root robots/sitemap discovery, canonical/hreflang metadata, WebSite/Organization/tool/article/FAQ structured data, legacy redirects, and fail-fast production preflight.
- Internal future ideas are documented in `PRODUCT_VISION_6.2_PLUS.md` and are intentionally not exposed as public unfinished features.

### Release validation

- Version: 6.1.2
- Python AST: 59 source files PASS.
- Python compileall: PASS.
- JavaScript syntax (`app.js`, `sw.js`): PASS.
- Jinja parse: 15 templates PASS.
- Static quality/SEO/AdSense regression suite: 41 tests PASS.
- Registry audit: 162 tools, 0 missing handler references.
- Reviewed safe-sample integration: 21/21 real conversions PASS, including LibreOffice and Tesseract-backed workflows.
- Full Flask route/preflight verification is repeated in the Railway Docker build because Flask/Werkzeug are production dependencies rather than bundled inspection-environment packages.

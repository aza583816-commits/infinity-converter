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
- Search indexing is intentionally quality-first: the sitemap focuses on core content and a curated converter set while the full 162-tool catalog remains available to users.
- AdSense serving is restricted to content-rich, indexable pages; verification metadata remains available without serving ads on thin/error/navigation-only surfaces.

## Tool architecture

`ConversionEngine` routes each registered tool to a specialized local engine and validates the generated output before download. Advanced capability modules keep the registry compact while allowing the catalog to grow without duplicating dispatch logic.

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

## 6.1.1 AdSense quality hardening

See `FINAL_RELEASE_AUDIT_6.1.1.md` for the quality-hardening verification matrix, `RELEASE_NOTES_6.1.1.md` for the patch summary, and `ADSENSE_READINESS.md` for the final monetization-readiness checklist.

### Highlights

- 162 registered tools across PDF, Images, Office & Data, OCR, Archive, and Utilities.
- Premium responsive interface with Arabic/English RTL/LTR, light/dark themes, keyboard/touch support, and reduced-motion behavior.
- Infinity AI is the only public AI brand; the external provider and model remain server-side implementation details.
- 15 original bilingual Knowledge Center guides with search, category filtering, article navigation, structured data, and editorial review metadata.
- AdSense integration is intentionally dormant until real publisher/slot IDs are configured; ad placements are labeled and separated from primary conversion/download actions.
- Root robots/sitemap discovery, canonical/hreflang metadata, WebSite/Organization/tool/article structured data, and fail-fast production preflight.
- Archive/XML hardening carried forward and expanded for bounded decompression and safe compressed-TAR extraction.

### Release validation

- Version: 6.1.1
- Python 3.11 source syntax: verified.
- JavaScript syntax: verified.
- Registry audit: 162 tools, 0 missing handler references.
- Static quality suite: verified.
- Full Flask/Docker and live Infinity AI verification are deployment-time checks because production dependencies/secrets are intentionally not bundled in this archive.

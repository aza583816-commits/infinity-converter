# Infinity Converter

Infinity Converter is a Flask 3 file-conversion service deployed on Railway. The frontend is Arabic/English with RTL/LTR support, while conversion remains behind the `/api/v2` API.

## Current product snapshot

- **162 registered tools** across 6 sections.
- **60 newly added tools in this phase** in this phase: 10 each for PDF, Images, Office/Documents/Data, OCR, Archive, and Utilities.
- Local processing with shared upload/output validation.
- Public authentication and billing are **hidden by default**, but their code paths are retained for a future launch.
- Canonical `/tools/<slug>` URLs; legacy `/tool/<id>` URLs redirect to the canonical page.
- Category links can deep-link into filtered tool listings.

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

## Phase 5 recommendations

See `FULL_AUDIT_6.0.1.md` for the full audit, verification matrix, current limitations, competitive feature analysis, and the product ideas backlog. See `RELEASE_NOTES_6.0.1.md` for this release's change summary.

## 6.0.1 highlights

- 162 tools across PDF, Images, Office & Data, OCR, Archive, and Utilities.
- 60 new high-value tools, including PDF redaction, PDF comparison, image upscale, background cleaning, spreadsheet profiling, OCR extraction, modern archive codecs, and developer utilities.
- Infinity AI command center powered server-side by Gemini. Configure `GEMINI_API_KEY` in Railway and optionally `GEMINI_MODEL`; the default is `gemini-3.8-flash`.
- Authentication and billing remain feature-flagged off publicly while the underlying code is preserved for a future launch.

## Release validation

- Version: 6.0.1
- Legacy `.doc` and modern `.docx` are both accepted by Word → PDF.
- Gemini 3.8 Flash uses the current `generateContent` REST-compatible configuration.

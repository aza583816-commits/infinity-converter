# Infinity Converter

Infinity Converter is a Flask 3 file-conversion service deployed on Railway. The Arabic-first frontend uses Jinja templates and lightweight browser JavaScript; conversion remains behind the existing `/api/v2` API.

## Conversion architecture

`ConversionEngine` selects a specialized local engine for each registered tool and validates the output before it is returned:

| Operation | Engine | Validation |
| --- | --- | --- |
| PDF merge/split | pypdf | PDF opens and contains at least one page |
| PNG/JPEG/WebP conversion | Pillow | Image opens, verifies, and has valid dimensions |
| DOCX/XLSX/PPTX to PDF | LibreOffice headless | PDF opens and contains at least one page |

The engine logs tool, engine, duration, input bytes, output bytes, and failure type without logging file contents or server paths. A bounded semaphore limits concurrent heavy conversions per application process. Temporary workspaces are isolated per request and cleaned by the context manager on success or failure.

## Local development

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. flask --app app run
PYTHONPATH=. pytest -q
```

Office integration tests run when `libreoffice` is installed. The Railway Docker image installs LibreOffice, Arabic and English Tesseract packages, and Noto fonts. No external conversion service or second deployment platform is required.

## Limits and security

File size, request size, output size, page count, subprocess timeout, allowed origins, and conversion concurrency are controlled by environment variables. Uploads are checked by extension, signature, archive structure, size, and parser validation before conversion. Outputs are checked by extension, MIME type, and a format-aware parser before download.

## Deployment

Railway is the production platform. `railway.toml` uses the Dockerfile builder and `/api/v2/healthz` as the health check. The application does not include a background queue yet because the existing API contract is synchronous and returns the converted file in the same request; the bounded process limit and subprocess timeout prevent unbounded work while a future job API can be added without changing the engine boundary.

## Foundation hardening (4.0.0)

The 2.1 foundation pass adds stronger upload/parser validation, BMP/TIFF support consistency, archive symlink rejection, streamed ZIP extraction, output-size limits, private/no-store conversion responses, CSP-safe i18n bootstrapping, configurable public URL generation, and explicit rate-limit storage configuration. See `docs/SECURITY_AND_ARCHITECTURE_AUDIT.md` for verified findings and the remaining high-priority roadmap.

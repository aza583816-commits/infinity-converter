# Infinity Converter 6.0.1 — Premium Free Toolbox + Infinity AI

## Product expansion

- Catalog expanded to **162 registered tools** across six core sections.
- Added exactly **10 new tools per section** (60 new tools total): PDF, Images, Office/Documents/Data, OCR, Archive, Utilities.
- New features inspired by the strongest capabilities commonly found in leading document/file platforms: PDF comparison, redaction, repair, embedded-image extraction, image enhancement, spreadsheet profiling, structured OCR extraction, archive codecs, and developer utilities.
- Added smart workflow cards and an Infinity AI command center.

## Public product state

- Pricing, Login, Register, and Account remain hidden from the public by default.
- Auth, billing, Paddle, entitlements, and credits code remain in the repository for future activation.
- `/pricing`, `/login`, `/register`, and `/account` are not publicly advertised while the feature flags are disabled.

## AI

- Added `/api/v2/ai/status` and `/api/v2/ai/ask`.
- Gemini key stays server-side; it is never embedded in HTML or client JavaScript.
- Default model is configurable with `GEMINI_MODEL` and currently defaults to `gemini-3.8-flash`.
- AI requests are rate-limited to 8 requests/minute per client through the existing limiter.

## Security and correctness

- Added BZIP2/XZ/TGZ/TBZ2 file signatures and safe decompression checks.
- Added safer compressed-archive inspection with expanded-size limits.
- Fixed compound archive extension routing (`.tar.gz`, `.tar.bz2`) to match the upload validation model.
- Fixed JSON-to-HTML to emit complete valid HTML.
- Fixed identical PDF/text comparison outputs so they produce a human-readable report instead of failing output validation.
- Normalized OCR language aliases (`ar+en`, `ar`, `en`, `ara+eng`, `eng`) before passing them to Tesseract.
- Updated repository integrity tests for the 162-tool catalog.

## UI / UX

- Added a dark glass ambient layer with restrained motion, card spotlights, animated format orbit, AI command-center panel, workflow cards, and reduced-motion fallbacks.
- Search/count/category surfaces are driven from the live registry rather than hard-coded catalog totals.

## Verification

- Python syntax audit: PASS — 49 Python files scanned.
- Repository audit: PASS — 162 registered tools, 60 new tools, 0 missing handler references.
- New-tool engine smoke test: **60/60 PASS** using representative real files plus output validation.
- Registry integrity test: PASS.
- The complete Flask/pytest suite could not be executed in the inspection container because Flask/Werkzeug dependencies are not installed there and package installation is unavailable offline.

## Deployment note

On Railway, keep the existing `GEMINI_API_KEY` secret in Variables. Set `GEMINI_MODEL` only when you want to override the default. Never move the key to frontend environment variables or commit it to Git.

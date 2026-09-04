# Infinity Converter 5.0.0 — Global Toolbox Expansion

## Product

- Expanded the catalog from the previous foundation to **102 tools**.
- Added **60 new tools**, exactly 10 in each section:
  - PDF
  - Images
  - Office/Documents/Data
  - OCR
  - Archive
  - Utilities
- Added advanced capability modules so new tools share validation and dispatch infrastructure instead of duplicating the core engine.

## UX / SEO

- Public Pricing/Login/Register/Account are hidden by default.
- Auth/billing code remains available behind feature flags for future launch.
- Legacy `/tool/<id>` URLs redirect to canonical `/tools/<slug>` pages.
- Tool JSON-LD now uses canonical tool URLs.
- Homepage category links deep-link into filtered tool listings.
- Homepage tool count is generated from the registry instead of hard-coded copy.

## Security / correctness

- TAR uploads now receive entry-count, traversal, special-file, expanded-size, and compression-ratio checks using centralized archive limits.
- Advanced TAR/GZIP processing uses the same centralized limits.
- XML-to-JSON rejects DTD/ENTITY payloads for a safer parsing baseline.
- GZIP text decompression validates UTF-8 and caps expanded output.
- ZIP-like outputs are wrapped as ZIP when the tool contract declares `.zip`, including single-item results.
- Image conversion honors the actual output extension.
- Image crop now accepts an optional crop spec without a singleton-tuple bug.
- PDF password-protect output validation recognizes encrypted PDFs.

## Verification

- Python compilation: PASS.
- JavaScript syntax: PASS.
- Registry integrity: PASS.
- Direct conversion integration: **102/102 PASS** with real representative inputs and output validation.
- The complete Flask/pytest suite remains environment-dependent; the inspection container does not include the project's Flask stack and cannot install packages from the network.

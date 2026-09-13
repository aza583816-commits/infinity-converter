# Infinity Converter 7.1.0 — Architecture Hardening

7.1.0 continues directly from the 7.0.0 Intelligence Workspace release. It does not replace the product or remove existing tools; it completes the backend/validation architecture behind the current interface.

## Architecture

- Split the 162-tool catalog into domain modules under `core/tooling/catalog/`: PDF, Images, Office, OCR, Archive, and Utilities.
- Added typed tooling models, materialized metadata, a central registry, and runtime catalog-integrity checks.
- Kept `core/tool_registry.py` as a small compatibility facade so older internal imports can migrate without breaking working features.
- Added `converters/contracts.py` and a declarative `converters/operations.py` registry.
- Rebuilt `ConversionEngine` as a generic orchestrator. Tool-specific routing no longer lives in a giant `if/elif` chain.
- Runtime health now requires exactly one backend operation for each public tool. Release state: 162 tools / 162 operations / 0 missing / 0 orphaned.
- Preserved proven converter implementations in a clearly marked legacy compatibility layer while migration continues by domain.

## Conversion pipeline and security

The conversion path is now explicitly gated as:

`upload -> file validation -> private TempWorkspace/input -> operation -> TempWorkspace/output -> artifact validation -> download`

Hardening includes:

- extension, MIME hint, binary signature, parser, and structural checks;
- PDF page/encryption checks and encrypted-PDF routing to the unlock workflow;
- Pillow decode/verify plus image pixel limits;
- OOXML structure checks plus rejection of external embedded package/resources (ordinary hyperlinks remain allowed);
- ZIP/TAR traversal, symlink, special-file, encryption, entry-count, expanded-size, and compression-ratio controls;
- bounded GZIP/BZIP2/XZ validation;
- output containment, symlink rejection, MIME/extension checks, parser validation, and output-size limits;
- validation of every individual artifact before it is inserted into a batch ZIP;
- private per-request temporary directories with idempotent cleanup;
- streamed downloads keep the workspace alive until the response closes;
- isolated LibreOffice user profiles, process-group timeout cleanup, and deny-by-default proxy environment for document rendering;
- Tesseract call timeouts and OCR page limits;
- CSV/JSON to XLSX formula-injection neutralization;
- validated free-form parameters and a defensive nested-regex guard.

## UI and release consistency

- Kept the 7.0 Intelligence Workspace design, Smart File Router, Quick Jump, drag/drop, batch conversion, favorites/recent tools, RTL/LTR, dark/light modes, Knowledge Center, Trust/Editorial pages, and contextual Infinity Intelligence.
- Improved conversion loading/error/success state handling, client timeout behavior, result metrics reset, and accessible busy states.
- Removed old internal `v612` UI tokens from the runtime surface without changing product functionality.
- Static asset cache-busting, Service Worker cache name, manifest, settings, health API, footer/version context, and release data now track 7.1.0 consistently.

## SEO and AdSense

- Canonical URLs, AR/EN hreflang, robots directives, sitemap policy, structured data, `ads.txt`, and AdSense page guards are preserved.
- Public content remains crawlable; Googlebot/AdsBot/Mediapartners are not globally blocked.
- AdSense serving remains restricted to content-rich/indexable pages and remains off assistant/thin/noindex/error surfaces.

## Railway / production gate

- Docker runtime now runs as a non-root application user.
- Docker build verifies LibreOffice and Tesseract + Arabic/English language packs.
- Production preflight checks architecture health, all 162 tool pages, APIs, a real inspect/convert/download pipeline, representative PDF/Image/Office/OCR/Archive conversions, SEO/robots/sitemap, AdSense guards, and PWA versioning.
- The Docker image then runs the complete pytest regression suite. A failing preflight or test prevents the image from being deployed.

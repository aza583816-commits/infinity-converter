# Infinity Converter — Foundation Audit (3.0.0)

## Scope

This audit covers the uploaded repository before the next product phase: application factory, API, converters, upload validation, temporary storage, frontend, i18n, deployment configuration, and test coverage.

## Verified findings

### Fixed in 3.0.0

- **CSP / frontend bootstrap:** the previous inline JavaScript bootstrap for `window.I18N` conflicted with the application's `script-src 'self'` policy. i18n data is now delivered through a non-script HTML metadata element, while JSON-LD uses a per-response CSP nonce.
- **Private conversion responses:** conversion downloads now send `Cache-Control: no-store, private` and `Pragma: no-cache` to reduce accidental caching of user documents.
- **Language cookie security:** the language-selection route now marks the cookie `Secure` when served over HTTPS.
- **Configurable canonical origin:** public URL generation is centralized in `PUBLIC_BASE_URL` instead of being hard-coded throughout page/sitemap generation.
- **PDF validation limit:** upload validation now receives the configured `MAX_PDF_PAGES` instead of silently hard-coding 1000 pages.
- **BMP/TIFF support:** the registry advertised BMP/TIFF support, but the upload guard did not allow those extensions. They are now validated through Pillow.
- **Image decodability:** raster uploads are parser-validated before processing, not only checked by filename/signature.
- **Archive symlinks:** ZIP validation/extraction rejects symbolic-link entries.
- **Archive extraction memory:** ZIP extraction now streams entries in 1 MiB chunks instead of reading a whole uncompressed entry into RAM.
- **Output size guard:** generated files are checked against `MAX_OUTPUT_MB` before being returned.
- **ZIP-create filenames:** archive entry names are flattened to safe basenames instead of trusting user-supplied path components.
- **Explicit rate-limit storage:** Flask-Limiter now uses `RATE_LIMIT_STORAGE_URI` when configured, with an explicit memory fallback for single-instance deployments.
- **Application secret:** a Flask secret key is initialized from `SECRET_KEY` or a random process-local value, ready for future signed/session features.

## Structural verification

- 33 registered tools.
- 33/33 registered tools have an engine handler.
- Python source compiles successfully with `py_compile`.
- Browser JavaScript passes `node --check`.
- Templates reference existing CSS/JS assets.

## Test execution status

The repository contains smoke, security, conversion, and stage-2 tests. Full pytest execution could not be completed in this inspection container because the runtime environment does not have the project's Flask stack installed and outbound package installation is unavailable. The conversion engine was nevertheless exercised directly across all 33 registered tools, with representative real inputs and output validation. See `docs/TEST_REPORT_3.0.0.md`.

Run in the project environment:

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

## Remaining high-priority work

1. **HTML-to-PDF hardening:** untrusted HTML should be sanitized or processed in a stronger sandbox before handing it to LibreOffice, especially to reduce local-file/remote-resource access risks.
2. **Resource budgets per tool:** expensive PDF rendering/OCR should have explicit page/pixel/output budgets instead of relying mainly on request size.
3. **Background jobs:** long-running conversions should eventually move to a queue/job model so web workers are not occupied for the full conversion duration.
4. **Distributed limits:** production multi-instance rate limiting should use Redis or another shared backend.
5. **Observability:** add structured request IDs, latency/error metrics, and health/readiness separation without logging document contents.
6. **Accounts and billing:** subscriptions, entitlements, credits, invoices, and payment webhooks are not implemented yet.
7. **AdSense readiness:** legal pages, consent strategy where required, content depth, and ad placement need a dedicated review before monetization.
8. **Product expansion:** the current 33 tools are a solid base, not the final global toolbox.

## Design principle for the next phase

Do not rewrite the working converter core just for novelty. Expand it through explicit capability modules, shared validation, predictable contracts, tests, and measurable performance budgets.

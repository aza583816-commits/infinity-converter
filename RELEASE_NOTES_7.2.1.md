# Infinity Converter 7.2.1 — hardening candidate

This release continues the verified 7.2.0 source at GitHub commit
`00ae9b35cce7ac7e11fe7737fe21211025f49ac1`. It does not recreate the product.
The supplied ZIP was compared against every blob in that commit's tree and
matched. Historical release reports are retained as history, not current proof.

## Changes

- Repair Docker's Python import path; invoke `python -m pytest -q -p no:cacheprovider` as appuser. Keep both preflight and pytest build gates. Provision only the writable SQLite instance directory, not the entire source tree.
- Add a GitHub Actions production-image build, every-operation engine/API smoke tests, JavaScript syntax and browser calculation checks.
- Validate legacy DOC using an OLE parser and Word streams; reject encrypted/macro/embedded-object variants. Production CI generates a genuine Word 97/OLE DOC and verifies its validated DOC-to-PDF path.
- Reject archive drive paths, traversal endings, special files, duplicates, CRC failures and oversized expansion before use. Check full concatenated BZIP2/XZ streams and compressed TAR contents. Accept legitimate compressed-TAR MIME hints while still verifying signatures/structure.
- Apply archive expansion limits to ZIP outputs; verify output image format and pixel limits. Check each single-file output contract before batch packaging.
- Attach temporary-directory cleanup to the WSGI download iterator as well as response close. Keep batch counts based on source inputs. Avoid double-wrapping an already packaged certificate ZIP.
- Move arbitrary regular expressions into a disposable subprocess with a three-second deadline and bounded result count/size. Support capture groups without tuple-join failures.
- Restrict AI context to allowed metadata. Drop filenames, arbitrary free text, passwords/settings and raw errors. Bound provider responses, validate request objects, preserve local fallback, canonicalize tool links and reject incompatible workflow steps.
- Correct the homepage OCR-to-Word route to searchable PDF → DOCX. Use one best local recommendation when no explicit compatible workflow is known.
- Correct English → Arabic switching, explicit Arabic canonical/hreflang URLs, and persistent language selection.
- Add repeat-download action while result bytes remain in page memory. Improve shared keyboard focus, mobile form text size, long-text wrapping and reduced-motion behavior. No visual sign-off is claimed.
- Repair the dormant account logout form and CSRF token. Public auth and billing remain off.
- Improve browser calculations: reject empty/nonfinite numeric inputs, negative GPA credits and invalid weights; include study breaks within available time; normalize pace rounding.

## Validation and release status

Production-image CI passes 175/175 pytest tests, 162/162 engine operations and 162/162 HTTP operation paths. It includes genuine legacy DOC conversion and Arabic OCR content gates. Browser calculation coverage is 99/101 in a VM plus 10 known-answer/negative checks; full visual browser QA remains open.

See `FINAL_AUDIT_7.2.1.md`, `release/TOOL_STATUS.json`, and the included test evidence.
A source ZIP is not a claim that production is ready. Only completed gates count.
The broader redesign, worker isolation and intelligent file workspace roadmap
are not represented as complete by this patch.

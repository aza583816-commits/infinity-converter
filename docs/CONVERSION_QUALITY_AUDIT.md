# Conversion quality audit and release gate

Status: IN PROGRESS — no production rollout from this branch until visual and functional acceptance.

## Verified gap
- The previous PDF-to-DOCX implementation concatenated extracted page text into a single paragraph, so it could not preserve tables, page geometry, columns, or pictures.
- Existing 162-operation smoke tests validate that calls finish and outputs are structurally readable. They **do not** establish semantic correctness or visual fidelity across realistic documents.
- Output validation checks PDF page count, DOCX package structure, and image decodability, not document layout fidelity.
- A Word-to-PDF round trip made from a DOCX already damaged by PDF-to-DOCX cannot isolate a Word-to-PDF defect.

## Required quality gates by family
1. PDF/Office: clean source PDF and DOC/DOCX, portrait/landscape, multiline tables, merged cells, Arabic+English bidirectional text, embedded images/fonts, headers/footers, multi-page files, scanned files. Assert extracted content, row/column ordering where meaningful, page count/geometry, and visual comparison at multiple DPI. Classify editable-layout versus exact-appearance output separately.
2. Images: transparent RGBA to JPEG with explicit background policy, EXIF rotation, ICC/color, animation/multipage formats, compression fidelity, dimension and orientation changes, and intentionally unsupported inputs.
3. OCR: Arabic, English, mixed scripts, rotated pages, low contrast, scanned PDFs, tables and noisy images. Measure character/word error rate against known ground truth; separate searchable-PDF versus plain-text expectations.
4. Spreadsheet/CSV/JSON: delimiter/encoding, Unicode, formulas (including injection), merged cells, multiple sheets, dates, empty cells, precision, and schema round trips. Validate expected lossiness explicitly.
5. Archives: nested directories, non-ASCII names, empty archives, traversal/symlink/zip bomb and truncated inputs. Confirm safe rejection and preservation of valid entry names and data.
6. Browser/developer tools: deterministic known-answer vectors, overflow/Unicode/locale and accessibility; no conversion-backend smoke test can validate these independently.
7. AI: grounding and fallback behavior, invalid or oversized inputs, privacy boundaries, cost ceilings, and error transparency. AI outputs cannot be expected to be deterministically identical.

## Release discipline
- Create small synthetic non-sensitive gold-standard fixtures; do not commit user-submitted records, names, student identifiers or raw uploads.
- For each operation record: accepted MIME/extension, engine, transformation contract, acceptable losses, reference corpus, numerical/content assertions, visual checks if applicable, and clear errors for unsupported inputs.
- Run the entire current test suite and the new per-family quality corpus in an isolated branch. Compare release and baseline output; visually review at least representative complex bilingual files.
- Only merge and deploy after no important quality regression; document features that still have limitations honestly in UI.
- No claim that all possible files are guaranteed to preserve original formatting. A PDF does not encode original Word structure, so editable reconstruction always carries limitations.

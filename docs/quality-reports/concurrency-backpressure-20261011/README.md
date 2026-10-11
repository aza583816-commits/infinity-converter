# Conversion backpressure — 2026-10-11

Base: `aa6ab54946856d528240bfc0dd43ee64606beb41` (PR #37 deployed successfully).

Four simultaneous OCR requests previously blocked readiness for **41.547 seconds**. General slots were acquired before the OCR-specific slot, and both waits used the native conversion timeout. The change acquires scarce workload capacity first and shares one **250 ms** admission deadline, independently of native execution time. Busy callers receive the existing HTTP 503 response and Retry-After: 3; admitted jobs retain their existing execution deadlines. Exceptions release both pools.

## Pre-merge evidence

- Full pytest command completed with exit 0; separate collection confirms 399 tests. The workspace-backed stdout log is truncated, so no passing-count summary is inferred from that log. See `local-full-status.json`; final image summary will be obtained from Railway.
- Focused real-lock/API checks: 31 passed, plus the additional shared-deadline test passed. These exercise both rejection stages, capacity release after handler failure, HTTP retry hint, workspace cleanup and readiness.
- Baseline, mixed and dense independent semantic audits: **162/162 each**, no failed or missing oracle.
- Real isolated Gunicorn, **2 workers × 2 threads**, four different 12/10/8/6-page scanned PDFs, exactly **36 pages**: all English records, amounts, leading-zero codes and required Arabic words verified in order. Three busy requests were retried sequentially only after the admitted request finished.
- Final pressure run: readiness **0.742 s**, 2400×2100 BMP→PNG **0.805 s**, pixel-identical image, peak **one Tesseract process**, sampled server/child PSS **736400 KiB**. No temporary conversion workspaces remained in either worker or the parent.
- Initial probe corrections are explicitly recorded: the first light image used unsupported same-format PNG, and its memory sampler confused PID namespaces. Neither is used as baseline evidence. Workspace-backed temp directories also produced inconsistent post-deletion entries; native `/tmp` and worker/parent verification corrected the probe. Health and image response budgets remain below 2 seconds.

## Scope

The local Office runtime is bundled LODev, not Debian LibreOffice in production. Existing Docker build gates repeat full pytest, all three 162-tool audits, and all seven native Office/document tools in English, Arabic and mixed corpora before the image can activate. No test or content oracle was weakened. Local pressure measurements certify this synthetic workload, not global Railway capacity, arbitrary uploads, or every possible file.

Production validation is recorded after deployment; no heavy burst is sent to production. Prior AdSense site-foundation checks remain valid; account approval and region-specific certified-CMP behavior remain unverified.

## Published production proof

PR #38 merged as `59b418501d44de99bc5f78927245c164081b3c24`. Railway deployment `82f09807-3a86-493b-b1db-dac398675a08` reached **SUCCESS**. Final Debian production image: **399 passed + 16 subtests**, all three full semantic audits **162/162**, and native English/Arabic/mixed corpora **7/7 each**.

Four actual published-site conversions passed independent content checks: 12 scanned bilingual OCR pages, mixed EXIF receipt (email/date/money/normalized phone), pixel-exact 2400×2100 BMP→PNG, and a Word document containing **205 paragraphs + 194 table cells**, rendered as **23 PDF pages** with all paragraph/cell strings preserved. A second OCR request while one was active returned HTTP **503 + Retry-After: 3**; readiness remained HTTP 200 before/during/after. Client readiness round trips were about 6 seconds both idle and during OCR, while Railway proxy records have unchanged raw totalDuration=2; the report keeps those measurements separate from isolated server latency.

This post-deployment evidence is committed on the quality branch only to avoid an evidence-only production rebuild. Code in main is the tested and verified deployed revision.

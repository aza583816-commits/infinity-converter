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

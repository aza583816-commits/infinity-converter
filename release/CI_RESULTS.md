# Verified production-image CI

Implementation SHA: `9c1e16781a5d1e33838ed87119b4dfe508ede5c3`

Run: https://github.com/aza583816-commits/infinity-converter/actions/runs/34813281168  
Job: `103878683255` — completed successfully on 2026-09-14 UTC.

- Python 3.11 Docker build, mandatory production preflight and pytest: **passed**.
- pytest: **175 passed**, with no failure or skip in the production image.
- A genuine binary Word 97/OLE `.doc` was generated, security-validated, uploaded and converted to a valid PDF: **passed**.
- A generated Arabic scan was processed with the installed `ara` OCR model and produced Arabic text: **passed**.
- Engine representative conversions: **162/162 passed**.
- HTTP upload → validation → conversion → output validation → streamed download/cleanup: **162/162 passed**.
- Browser calculation catalog in a Node VM: **99 passed**; timer and canvas cleanup require a real browser.
- Browser known-answer and negative calculations: **10 passed**.

The engine and HTTP smoke containers ran with `--network none`. That CI restriction does not prove equivalent Railway runtime isolation. Local dependency failures and skips remain preserved in `LOCAL_RESULTS.json`; the production image contains the required LibreOffice and Arabic/English Tesseract packages. This run is not a Railway deployment or visual browser sign-off.

## Exact log excerpts

```text
2026-09-14T06:23:48.4648975Z 10 known-answer and negative browser-calculation tests passed
2026-09-14T06:24:49.3728553Z #13 0.350 Tesseract ara+eng language packs OK
2026-09-14T06:24:49.3729117Z #13 0.437 LibreOffice runtime OK: LibreOffice 7.4.7.2 40(Build:2)
2026-09-14T06:24:50.2939731Z #13 1.508 runtime registry 162/162 OK
2026-09-14T06:24:53.5902461Z #13 4.654 Production preflight PASS
2026-09-14T06:25:12.5962904Z #14 18.82 175 passed in 18.30s
2026-09-14T06:25:39.6786411Z RESULT 162/162 pass
2026-09-14T06:26:05.3974834Z API RESULT 162/162
```

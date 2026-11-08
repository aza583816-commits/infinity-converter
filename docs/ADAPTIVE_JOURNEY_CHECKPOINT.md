# Adaptive Journey — implementation checkpoint

Base main commit: 59b418501d44de99bc5f78927245c164081b3c24.
Branch: design/adaptive-journey-home. This is NOT a production release.

Replaced the homepage's competing hero/console/router blocks with one selected
design surface. Kept the existing AI plan endpoint, local metadata-only router,
tool catalog, workflows, knowledge, favorites, footer and AdSense guards.
Homepage-only styles leave conversion-page styling and backend unchanged.
Added accessible input label, attachment action and empty-submit feedback.

Assets: Cairo (SIL OFL, license in static/fonts/OFL.txt), Phosphor regular icons
(MIT, license in static/icons/LICENSE), generated 11.4 KiB WebP backdrop.
Background prompt: extract only the original mockup backdrop; remove all text,
controls and icons; preserve upper-left emerald arc, mint glow, off-white
center and icy blue lower-right sweep. Built-in image generation was used.

Local preview: create .venv, install requirements.txt, then npm run dev --
--host 0.0.0.0 --port 4173 --strictPort. Production still uses Gunicorn.

Verification: initial focused suite 37 passed; four new surface/asset/privacy
contracts passed separately. Full run initially 362 passed, 30 failed, 7 skipped,
16 subtests passed. One failure was an obsolete literal-heading assertion;
replaced with include and stable functional markers (not removed).
Remaining conversion failures include unavailable LibreOffice and missing ara
Tesseract data. Do not label them passed or infer production is broken.

Release blockers: see design-qa.md. No version bump until release acceptance.

Final rerun: 367 passed, 29 failed, 7 skipped, 16 subtests passed.
JavaScript syntax and git diff whitespace checks passed.
The git HTTPS push could not authenticate (no terminal credential available).
Changes are committed locally only; origin/main and Railway were not changed.

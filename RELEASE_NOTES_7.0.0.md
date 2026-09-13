# Infinity Converter 7.0.0 — Intelligence Workspace

## Product direction

Infinity Converter 7.0.0 rebuilds the public experience around one principle: **the user describes the outcome; Infinity maps it to the right tools and workflow**. The conversion catalog and engines remain intact while the interface, AI orchestration, discovery, and result guidance are redesigned as one coherent workspace.

## What stays intact

- All **162 registered tools** remain available.
- Existing converter handlers, validation, output checks, security boundaries, reviewed tool pages, Knowledge Center, Trust/Editorial pages, bilingual Arabic/English support, light/dark themes, AdSense guards, local favorites/recent tools, Quick Jump, PWA static caching, and future hidden auth/billing code remain in place.
- Existing `/api/v2/ai/ask` remains available for compatibility.

## Infinity Intelligence

- Added a dedicated `/assistant` workspace for longer natural-language file tasks.
- Added `/api/v2/ai/plan`, which returns a structured plan instead of a generic chat answer.
- AI plans can include real tool IDs, canonical tool URLs, ordered steps, explanations, tips, and follow-up questions.
- The catalog prompt is generated from the live registry, so the intelligence layer knows the real tool inventory rather than relying on a manually copied list.
- Added contextual modes for planning, explaining, optimizing, troubleshooting, and choosing the best next step.
- Added a per-tool Copilot so every converter can explain the current tool, suggest settings, diagnose a failed operation, or recommend the next step after a result.
- Added result/error context so users do not need to re-explain what just happened.

## Smart Core fallback

Infinity Intelligence no longer becomes useless when the enhanced AI provider is unavailable. A local **Smart Core** performs intent routing and fuzzy catalog matching for common Arabic and English goals, including OCR, PDF compression, redaction, repair, image-to-PDF, Office/PDF conversions, archive tasks, and common data utilities.

The enhanced provider can refine a workflow when available, but the site can still map common goals to real Infinity tools without it.

## Privacy model

- Conversion files are **not automatically attached to AI requests**.
- The contextual frontend sends bounded safe metadata such as extension, MIME type, size, current tool/settings, result metrics, and short error messages.
- Filenames and file contents are explicitly excluded from the automatic AI context.
- The Gemini key remains server-side.

## Design rebuild

- Rebuilt the homepage as an **Intelligence Workspace** rather than a traditional converter landing page.
- Introduced a goal-first hero console, visible direct-tool path, Smart File Router, workflow cards, personal shortcuts, tool explorer, knowledge layer, and contextual AI dock.
- Rebuilt the global shell/header/footer while preserving SEO, hreflang, canonical, structured-data, CSP, AdSense and accessibility behaviors.
- Added a full-screen Intelligence workspace and contextual assistant panels to tool pages.
- Kept direct access to every tool: AI is an acceleration layer, not a gate.
- Responsive layouts, reduced-motion behavior, RTL/LTR, keyboard/touch interactions, and light/dark themes remain supported.

## Versioning / cache

- Application version: **7.0.0**.
- Static asset cache keys and template asset query versions updated to 7.0.0.
- Service worker cache updated to `infinity-static-v7.0.0`.

## Verification

- Python compileall: PASS.
- JavaScript syntax (`static/js/app.js`): PASS.
- Jinja parse: PASS — 16 templates.
- Registry audit: PASS — 162 tools, 0 missing handler references.
- Static quality/SEO/AdSense/AI regression selection: **41/41 PASS**.
- Smart Core intent checks: scanned PDF → searchable OCR → DOCX; PDF email compression → PDF Compress; sensitive PDF → Redact; images → single PDF; broken PDF → Repair.
- Full Flask startup/preflight could not be executed in the inspection container because Flask/Werkzeug are not installed there. The production preflight script has been updated with `/assistant` guards and remains intended to run in the Railway/Docker dependency environment.

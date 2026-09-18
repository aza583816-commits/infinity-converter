# Infinity Converter 8.0.0 — Smart Workspace

Infinity 8 continues from the verified 7.2.3 production history. It does not
replace the converter architecture or restore an old snapshot.

## Product changes

- Adds a goal-first `/workspace` entry point.
- Adds safe multi-file inspection using the existing hardened upload validation
  boundary.
- Adds a unified public discovery catalog for all server converters and
  browser-local tools.
- Adds catalog-grounded recommendations rather than free-form invented actions.
- Adds a visual workflow builder that only offers compatible, non-interactive
  converter steps.
- Adds Balanced, Smallest, Editable-first, and Clean & safe workflow profiles.
- Allows Infinity Intelligence plans to execute compatible server-converter
  chains directly after the user selects a file.
- Re-validates every intermediate artifact before it enters the next step.
- Adds local-only recent file-type memory. Names and contents are not persisted.
- Adds a multi-file project board for inspection within the current page session.
- Adds a multi-file processing queue with per-file status, continue-on-error behavior, and retry without restarting the full batch.
- Adds safe session-plan recovery using only extension + workflow tool IDs; file bytes are never persisted and must be re-selected after reload.
- Adds goal templates for student submissions, business sharing, and creator web assets, all compatibility-filtered before execution.
- Adds strict allowlisted product-event telemetry for Workspace actions; only event name and safe path are logged, while filenames, prompts, file metadata, account data, and free text are ignored.
- Promotes Students, Business, Creators, and Developers as goal-based collections.
- Adds nine new bilingual Knowledge Center guides, bringing the current editorial
  guide set to 24.
- Keeps the manually reviewed/indexable converter-page strategy quality-first;
  the existing reviewed set is already above the 30-page target.

## Workflow security rules

Dynamic workflows are not arbitrary code execution.

- 1–4 steps only.
- Every step must be an existing server converter tool.
- Browser-local tools cannot be inserted into server file chains.
- Duplicate steps are rejected.
- Tools that require an interactive required option without a safe default are
  excluded.
- Each output extension must be accepted by the next tool.
- The server repeats all validation even if the browser already filtered the plan.
- Every intermediate file is treated as untrusted input and validated again.
- Existing entitlement checks, upload limits, concurrency limits, timeouts,
  output validation, temporary workspaces, and no-store download behavior remain
  in force.

## Privacy boundary

The File Inspector and Infinity Intelligence remain deliberately separate.
Only bounded technical metadata may be carried into the assistant context:
extension, MIME type, size, page count, encryption/safety flags, and bounded
numeric state. File contents and filenames are not automatically attached to the
external AI provider.

Local recents store only extension, size, page count, and time in browser local
storage. The multi-file project board may display a filename in the current page
session but does not persist it in local recents or AI context.

## PWA and navigation

- Workspace is linked from desktop navigation, mobile navigation, footer, and the
  homepage primary CTA.
- Workspace JavaScript is covered by the production syntax gate and PWA static
  cache.
- Cache/version keys move to 8.0.0 so Safari and installed PWA clients do not keep
  the 7.2.3 JavaScript bundle.

## Editorial / search

- Nine manually written bilingual guides add PDF repair, OCR output choice, image
  metadata privacy, XLSX/CSV, CSV/JSON, favicons, PDF reorder/numbering, safe
  workflow chaining, and browser-local privacy topics.
- Interactive Workspace remains `noindex,follow` for the first production
  release. It is a product surface, not a search landing page.
- Existing quality-first sitemap rules remain: reviewed converter pages and
  substantive editorial pages are indexable; thin browser/assistant/account/error
  surfaces are not promoted to the sitemap merely because they exist.

## External controls intentionally not claimed complete

The following require live infrastructure or account-side changes and are not
silently marked complete by this release:

- shared Redis before horizontal scaling,
- a dedicated renderer/OCR worker with infrastructure-level outbound denial,
- GA4 account-side connection,
- Google-certified CMP activation/live consent verification,
- Search Console retirement of historical HTTP sitemap entries and recrawl
  validation.

These are operational follow-ups, not reasons to weaken the current application
security boundaries.

## Release gates

8.0.0 may merge to `main` only after:

1. JavaScript/browser gates pass.
2. Dependency audit/SBOM generation passes.
3. Mobile asset budget passes.
4. Python 3.11 production image builds.
5. Full pytest suite passes.
6. Installed dependency consistency passes.
7. Native renderer limiter check passes.
8. 162/162 direct operation smoke passes.
9. 162/162 HTTP operation smoke passes.

After merge, Railway deployment must reach terminal `SUCCESS`, the
`/api/v2/readyz` probe must return healthy, and live Workspace/discovery/AI status
checks must succeed before the release is recorded as deployed.

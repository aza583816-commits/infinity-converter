# Infinity 8 — Smart Workspace roadmap

Infinity 8 moves Infinity Converter from a large converter catalog into a goal-first
workspace. The release must preserve the existing security boundaries, 162/162
server-operation contract, browser-tool catalog, bilingual UX and quality-first
indexing strategy.

## Phase A — shipped in this branch

- [x] Goal-first `/workspace` surface.
- [x] Safe File Inspector built on the existing hardened upload validation boundary.
- [x] Unified discovery API for converter + browser-tool namespaces.
- [x] Catalog-grounded recommendations instead of invented actions.
- [x] Safe metadata bridge into Infinity Intelligence; no filenames or file contents.
- [x] AI plans can execute compatible converter-only chains through the verified
      workflow handoff boundary.
- [x] Goal-based collection entry points for Students, Business, Creators, Developers.
- [x] Workspace promoted in desktop/mobile navigation and homepage CTA.
- [x] PWA cache + CI syntax/test coverage for the new surface.

## Phase B — project workspace

- [x] Local-first multi-file inspection board with safe metadata kept in the current page session.
- [x] Multi-file queue with explicit per-file status, sequential progress and per-item retry.
- [x] Reusable workflow presets stored locally by default (extension + tool IDs only).
- [x] Session recovery for extension + safe tool IDs only; users explicitly re-select files because file bytes are never persisted.
- [ ] Optional account-backed project sync only after auth/storage retention UX is ready.

## Phase C — richer orchestration

- [x] Visual workflow builder over the real compatible converter graph.
- [x] Project-queue retry/continue rules are implemented. In-chain conditional branching stays deliberately excluded from 8.0 so server execution remains deterministic and re-validatable.
- [x] Quality profiles (Balanced, Smallest, Editable first, Clean & safe) with compatibility filtering.
- [x] Deterministic client/server compatibility preflight before a dynamic chain executes.
- [x] Browser-tool steps remain local and are rejected from server file handoffs.

## Phase D — search and content authority

- [x] Maintain a manually reviewed hero-tool set above the 30-page target (36+ reviewed converter pages).
- [x] Expand topic clusters across PDF, OCR, data/Office, images, privacy, security, and workflow verification (24 bilingual guides total).
- [x] Every reviewed/indexed converter page is release-gated for processing transparency, implementation-specific guidance, FAQ structured data, safe samples where uploads are required, and internal related-tool links.
- [x] Keep thin utility surfaces noindex until they meet the quality bar.
- [ ] Validate canonical/hreflang/sitemap changes in live Search Console after release.

## Phase E — infrastructure hardening

These items require live infrastructure or account-side configuration and are not
considered complete merely because application code supports them.

- [ ] Shared Redis for global request-rate limits and global AI budget before horizontal scaling.
- [ ] Dedicated renderer/OCR worker with infrastructure-level outbound-network denial.
- [ ] Uniform disposable-worker CPU/memory budgets for heavy native/parser paths.
- [x] Crash-recovery/TTL sweep for abandoned temporary workspaces, with path/prefix/age guards and throttled cleanup.
- [ ] Continue SBOM, dependency audit and exact production-image evidence.

## Phase F — product growth

- [x] Installable PWA onboarding on Workspace; existing static-only service worker remains conservative.
- [x] Privacy-preserving local recents and reusable local workflow presets in Workspace.
- [x] Outcome templates for student submissions, business sharing and creator web publishing, all filtered through the same compatibility graph.
- [x] Allowlisted product-event telemetry that logs event + safe path only and ignores all free-form/file/account fields.
- [ ] Turn on public accounts/billing only when account, retention, support and checkout UX
      are ready; existing hidden code remains disabled until then.

## Release rules

1. Main remains the production source of truth.
2. Every Infinity 8 phase lands through a reviewed branch/PR.
3. Production quality gates must pass before merge.
4. Railway deployment is not considered successful until terminal SUCCESS and live probes pass.
5. AdSense acceptance is never claimed or guaranteed; quality and compliance are verified instead.

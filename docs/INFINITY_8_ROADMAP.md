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

- [ ] Local-first project board for multiple files with file handles/metadata kept on-device
      where browser capabilities allow.
- [ ] Multi-file queue with explicit per-file actions, progress and retry.
- [ ] Reusable workflow presets stored locally by default.
- [ ] Session recovery that never stores uploaded file bytes in server history.
- [ ] Optional account-backed project sync only after auth/storage retention UX is ready.

## Phase C — richer orchestration

- [ ] Visual workflow builder over the real operation graph.
- [ ] Branching/retry rules for compatible steps.
- [ ] Quality profiles (smallest, balanced, preserve-layout, editable-first).
- [ ] Deterministic preflight explaining why a chain is executable before upload.
- [ ] Browser-tool steps remain local and must never be faked as server file handoffs.

## Phase D — search and content authority

- [ ] Expand the manually reviewed hero-tool set gradually from 21 toward 30–40.
- [ ] Build topic clusters around PDF, OCR, Office, images, privacy and verification.
- [ ] Every indexed tool page needs implementation-specific guidance, examples,
      FAQs, internal links and relevant workflows.
- [ ] Keep thin utility surfaces noindex until they meet the quality bar.
- [ ] Validate canonical/hreflang/sitemap changes in live Search Console after release.

## Phase E — infrastructure hardening

These items require live infrastructure or account-side configuration and are not
considered complete merely because application code supports them.

- [ ] Shared Redis for global request-rate limits and global AI budget before horizontal scaling.
- [ ] Dedicated renderer/OCR worker with infrastructure-level outbound-network denial.
- [ ] Uniform disposable-worker CPU/memory budgets for heavy native/parser paths.
- [ ] Crash-recovery/TTL sweep validation for abandoned temporary workspaces.
- [ ] Continue SBOM, dependency audit and exact production-image evidence.

## Phase F — product growth

- [ ] Installable PWA onboarding and offline-first browser utilities.
- [ ] Privacy-preserving local recents/favorites expanded into workspace shortcuts.
- [ ] Template collections for student submissions, business documents and creator exports.
- [ ] Usage analytics limited to product events; never file contents.
- [ ] Turn on public accounts/billing only when account, retention, support and checkout UX
      are ready; existing hidden code remains disabled until then.

## Release rules

1. Main remains the production source of truth.
2. Every Infinity 8 phase lands through a reviewed branch/PR.
3. Production quality gates must pass before merge.
4. Railway deployment is not considered successful until terminal SUCCESS and live probes pass.
5. AdSense acceptance is never claimed or guaranteed; quality and compliance are verified instead.

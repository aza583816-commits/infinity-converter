# Infinity Converter 7.2.2

Version 7.2.2 promotes the latest real `main` architecture and fixes the iPad
tools-category bar without reverting any conversion, Smart Flow, security,
accessibility, SEO, or production hardening work.

## User experience

- Fixed category filtering on Safari/iPadOS by making the HTML `hidden`
  attribute an explicit author-level state contract. The rule also protects
  result panels, mobile navigation, dialogs, and other stateful components from
  conflicting `display` declarations.
- Rebuilt category controls as crawlable, shareable links with instant
  JavaScript filtering. They still render the correct category when JavaScript
  or browser storage is unavailable.
- Added a live visible-tool count, synchronized accessible selection state,
  validated filter input, 44 px touch targets, comfortable horizontal scrolling,
  and a quieter premium active state in light and dark themes.
- Removed the nested search-field border visible on iPad and preserved native
  mobile input behavior, RTL/LTR flow, and reduced-motion preferences.
- Guarded theme, favorite, and recent-tool storage so Safari privacy modes cannot
  stop the rest of the interface from initializing.

## Platform carried into this release

- 162 registry tools remain wired one-to-one to 162 backend operations.
- Stable, advanced, mega, and product workflows are split into modular handler
  groups; the legacy dispatcher is no longer part of the production registry.
- Infinity Intelligence and Quick Jump use the unified converter/browser tool
  catalog, while Smart Flow provides a privacy-first next-step handoff.
- Heavy Office/OCR workload gates, temporary-workspace recovery, readiness
  probes, worker recycling, dependency checks, and mobile asset budgets remain
  enabled.
- The expanded manually reviewed editorial surface and quality-first sitemap
  policy remain intact for sustainable SEO and AdSense readiness.

## Release gates

The production Docker image must complete preflight, the full pytest suite,
dependency consistency, all-operation engine/API smoke tests, browser calculation
checks, and the shared mobile asset budget before merge. Production status and
the exact tested/not-tested boundary are recorded in `FINAL_AUDIT_7.2.2.md`.

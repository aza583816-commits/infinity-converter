# Infinity Converter 7.2.3

This small reliability follow-up preserves the complete 7.2.2 iPad filter and
visual refresh, then closes two state-lifecycle issues found during live
post-deployment browser testing.

- “Process another file” now revokes the previous in-memory Blob URL and hides
  the repeat-download action immediately, avoiding stale download state and
  unnecessary browser-memory retention.
- Quick Jump now moves keyboard focus reliably into its search field after
  opening and restores focus to the invoking control when it closes.
- Static asset and service-worker versions move together to 7.2.3 so Safari
  cannot keep the earlier JavaScript under the 7.2.2 cache key.

All production-image, operation, API, browser-calculation, performance, and live
smoke gates remain mandatory. See `FINAL_AUDIT_7.2.3.md` for final evidence.

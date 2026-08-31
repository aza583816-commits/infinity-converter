# Infinity Converter 4.0 — Production Roadmap

## Included in this foundation
- Hardened upload validation and archive safety.
- Centralized runtime limits via environment configuration.
- Bounded concurrent conversion semaphore.
- Private/no-store conversion responses.
- Request IDs for troubleshooting.
- Health endpoint exposing safe operational limits.
- Versioned static assets.
- Arabic/English and RTL/LTR support.
- 33 registered conversion tools with local engines.

## Next production layers
1. External durable queue/worker system (Redis/RQ/Celery or equivalent) for heavy jobs.
2. Durable user accounts and usage ledger.
3. Server-side plan/entitlement enforcement.
4. Payment provider + signed webhook processing.
5. Object storage only if required; otherwise keep temporary files ephemeral.
6. Per-user and per-IP rate limits backed by Redis in multi-instance deployments.
7. Automated integration/E2E conversion fixtures in CI.
8. Performance budgets and load tests before scaling.
9. Smart engine routing based on file characteristics and resource budgets.
10. Expanded tool catalog based on demand and conversion-quality benchmarks.

## Cost principle
Prefer local/open-source processing over paid APIs when quality is comparable. Keep heavy processing off request threads once traffic justifies a worker queue. Never introduce an external API solely for convenience when an equivalent local engine meets the quality and security requirements.

## Billing note
The pricing UI is intentionally presentation-only until a payment provider and merchant account are configured. Never treat client-side prices as proof of payment; entitlement must be verified server-side from signed provider events.

# Infinity Converter 4.0.0 — Global Foundation

This release consolidates the production foundation without pretending that billing or a durable queue is already live.

### Hardened
- Centralized and validated resource limits.
- Safe upload validation and archive protections inherited from 3.x.
- Bounded concurrent conversion execution.
- Private/no-store conversion downloads.
- Request IDs for support and diagnostics.
- Health endpoint reports safe runtime limits.
- Versioned static assets and application version.

### Product foundation
- Refined global UI/UX system.
- Arabic/English and RTL/LTR support.
- 33 local conversion tools.
- Monthly/yearly pricing presentation (payment provider intentionally not activated).

### Deliberately not enabled yet
- Real payment processing.
- Durable user accounts.
- Durable usage/credits ledger.
- External queue infrastructure.
- Production Redis-backed rate limiting.

These require deployment/provider credentials and should be introduced only after the corresponding production architecture is selected.

"""Static delivery budget for the shared production experience.

This is intentionally dependency-free so it can run before the Docker build. It
is not a substitute for field Core Web Vitals, but it prevents accidental asset
bloat from silently making the mobile experience heavier release after release.
"""
from __future__ import annotations

import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BUDGETS = {
    "static/js/app.js": (320_000, 100_000),
    "static/js/smart-flow.js": (80_000, 28_000),
    "static/css/app.css": (260_000, 85_000),
    "static/css/a11y.css": (30_000, 12_000),
}
TOTAL_RAW_BUDGET = 650_000
TOTAL_GZIP_BUDGET = 200_000


def main() -> int:
    total_raw = 0
    total_gzip = 0
    failures: list[str] = []
    for relative, (raw_budget, gzip_budget) in BUDGETS.items():
        payload = (ROOT / relative).read_bytes()
        raw_size = len(payload)
        gzip_size = len(gzip.compress(payload, compresslevel=9))
        total_raw += raw_size
        total_gzip += gzip_size
        print(f"{relative}: raw={raw_size} gzip={gzip_size}")
        if raw_size > raw_budget:
            failures.append(f"{relative} raw {raw_size} > {raw_budget}")
        if gzip_size > gzip_budget:
            failures.append(f"{relative} gzip {gzip_size} > {gzip_budget}")

    print(f"shared-assets: raw={total_raw} gzip={total_gzip}")
    if total_raw > TOTAL_RAW_BUDGET:
        failures.append(f"shared raw total {total_raw} > {TOTAL_RAW_BUDGET}")
    if total_gzip > TOTAL_GZIP_BUDGET:
        failures.append(f"shared gzip total {total_gzip} > {TOTAL_GZIP_BUDGET}")
    if failures:
        raise SystemExit("performance budget failed: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

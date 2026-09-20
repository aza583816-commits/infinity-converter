"""Exercise actual HTTP upload/download for all conversion tools on diverse corpora.

Uses the Flask in-process test client with isolated database and temporary
uploads, never the public production endpoint or real customer documents.
"""
from __future__ import annotations
import os

import scripts.full_operation_smoke as smoke
import scripts.api_operation_smoke as api
from scripts.output_input_matrix import matrix_make_fixtures


if __name__ == "__main__":
    if os.environ.get("IC_TEST_FIXTURE_PROFILE") not in ("mixed", "dense"):
        raise SystemExit("Set IC_TEST_FIXTURE_PROFILE to mixed or dense")
    smoke.make_fixtures = matrix_make_fixtures
    print("HTTP QUALITY INPUT PROFILE:", os.environ["IC_TEST_FIXTURE_PROFILE"], flush=True)
    api.run()

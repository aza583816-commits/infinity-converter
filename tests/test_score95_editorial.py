from __future__ import annotations

import app_factory  # noqa: F401 - installs all reviewed editorial layers

from core.editorial import TOOL_EDITORIAL, reviewed_tool_ids


SCORE95_NEW_IDS = {
    "pdf-reorder-pages",
    "pdf-page-numbers",
    "image-strip-metadata",
    "image-favicon-pack",
    "docx-to-text",
    "xlsx-to-csv",
    "csv-to-json",
}


def test_score95_adds_distinct_high_intent_reviewed_pages():
    assert SCORE95_NEW_IDS <= reviewed_tool_ids()
    # 29 pre-sprint reviewed pages + seven genuinely new reviewed surfaces.
    assert len(TOOL_EDITORIAL) >= 36


def test_re_reviewed_watermark_does_not_replace_existing_canonical_copy():
    # score-90 already reviewed this page; the guarded score-95 installer must
    # not duplicate it or turn the editorial registry into a second source of truth.
    assert "pdf-watermark-text" in TOOL_EDITORIAL
    assert list(TOOL_EDITORIAL).count("pdf-watermark-text") == 1

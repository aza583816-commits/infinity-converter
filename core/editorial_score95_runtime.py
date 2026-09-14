"""Safe installer for the score-95 editorial layer.

The score-90 layer already reviewed ``pdf-watermark-text``.  The score-95 draft also
contains that page because it was independently re-reviewed while auditing high-intent
surfaces.  Runtime installation keeps the older canonical review and only adds truly
new IDs; any future unexpected overlap still fails loudly.
"""
from __future__ import annotations

from core.editorial_score95 import SCORE95_TOOL_EDITORIAL

_EXPECTED_EXISTING = frozenset({"pdf-watermark-text"})


def install() -> None:
    from core import editorial

    overlap = set(SCORE95_TOOL_EDITORIAL).intersection(editorial.TOOL_EDITORIAL)
    unexpected = overlap - _EXPECTED_EXISTING
    if unexpected:
        raise RuntimeError(f"Unexpected score-95 editorial overlap: {sorted(unexpected)}")
    additions = {
        tool_id: payload
        for tool_id, payload in SCORE95_TOOL_EDITORIAL.items()
        if tool_id not in editorial.TOOL_EDITORIAL
    }
    editorial.TOOL_EDITORIAL.update(additions)

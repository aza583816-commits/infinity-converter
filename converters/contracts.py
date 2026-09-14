from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

OperationMode = Literal["single", "combine", "generator"]


class ConversionBusyError(RuntimeError):
    """Raised when bounded conversion capacity is temporarily exhausted."""


@dataclass(frozen=True)
class ConversionResult:
    path: Path
    name: str
    mime: str
    engine: str
    duration_ms: int
    input_bytes: int
    output_bytes: int
    details: dict
    batch_total: int = 0
    batch_succeeded: int = 0
    batch_failures: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class Operation:
    """One executable backend operation for exactly one public Tool ID.

    ``handler`` is normalized by :mod:`converters.operations` so the engine only
    needs to understand three execution shapes instead of tool-specific branches.
    """

    id: str
    mode: OperationMode
    handler: Callable
    engine: str
    force_zip: bool = False

"""Runtime architecture integrity checks for Infinity Converter 7.1+."""
from __future__ import annotations

from dataclasses import dataclass

from converters.operations import operation_ids
from core.tooling.catalog import TOOLS
from core.tooling.registry import validate_catalog


@dataclass(frozen=True)
class RuntimeCoverage:
    tools: int
    operations: int
    missing: tuple[str, ...]
    orphaned: tuple[str, ...]
    catalog_errors: tuple[str, ...] = ()

    @property
    def healthy(self) -> bool:
        return (
            self.tools == self.operations
            and not self.missing
            and not self.orphaned
            and not self.catalog_errors
        )

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "tools": self.tools,
            "operations": self.operations,
            "missing": list(self.missing),
            "orphaned": list(self.orphaned),
            "catalog_errors": list(self.catalog_errors),
        }


def runtime_coverage() -> RuntimeCoverage:
    tools = set(TOOLS)
    operations = set(operation_ids())
    return RuntimeCoverage(
        tools=len(tools),
        operations=len(operations),
        missing=tuple(sorted(tools - operations)),
        orphaned=tuple(sorted(operations - tools)),
        catalog_errors=validate_catalog(),
    )


def assert_runtime_coverage() -> RuntimeCoverage:
    coverage = runtime_coverage()
    if not coverage.healthy:
        raise RuntimeError(
            "Tool/backend registry drift: "
            f"missing={coverage.missing}, orphaned={coverage.orphaned}, "
            f"catalog_errors={coverage.catalog_errors}"
        )
    return coverage

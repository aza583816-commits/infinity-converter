from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path


def normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(".", "-")


def load_constraints(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise SystemExit(f"constraint is not exact: {line}")
        name, version = line.split("==", 1)
        expected[normalize(name)] = version.strip()
    return expected


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "constraints.txt")
    expected = load_constraints(path)
    mismatches: list[str] = []
    checked = 0
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or ""
        key = normalize(name)
        if key not in expected:
            continue
        checked += 1
        actual = dist.version
        if actual != expected[key]:
            mismatches.append(f"{name}: installed={actual} constrained={expected[key]}")
    if mismatches:
        print("Constraint verification FAILED")
        for item in sorted(mismatches):
            print(f" - {item}")
        return 1
    if checked < 20:
        print(f"Constraint verification FAILED: only {checked} constrained packages were installed")
        return 1
    print(f"Constraint verification PASS ({checked} installed packages matched exact reviewed versions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

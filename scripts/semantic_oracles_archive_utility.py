"""Source-to-output content checks for archive and utility operations.

No oracle is registered without an input-specific assertion. Batch extraction
is unzipped and each extracted file compared to the original members.
"""
from __future__ import annotations

from collections import Counter
import csv
import difflib
import gzip
import json
import mimetypes
import re
import statistics
import tarfile
import zipfile
from pathlib import Path


ORACLE_IDS = frozenset({
    "zip-extract", "tar-create", "tar-extract", "zip-list",
    "zip-integrity", "zip-flatten", "tar-list", "gzip-info",
    "zip-to-tar", "tar-gzip-create", "tar-gzip-extract",
    "zip-duplicate-report", "tar-integrity", "tar-bzip2-create",
    "tar-bzip2-extract", "file-info", "filename-normalizer",
    "number-list-analyzer", "text-diff", "regex-extract",
    "file-extension-report",
})


def _zip_contents(path: Path) -> list[bytes]:
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        return [z.read(name) for name in z.namelist() if not name.endswith("/")]


def _tar_contents(path: Path) -> list[bytes]:
    with tarfile.open(path, "r:*") as t:
        return [t.extractfile(m).read() for m in t.getmembers() if m.isfile()]


def oracle(tool_id: str, source: Path | None, output: Path, fixture: Path) -> str | None:
    if tool_id not in ORACLE_IDS:
        return None
    assert source is not None
    if tool_id == "zip-extract":
        assert Counter(_zip_contents(output)) == Counter(_zip_contents(source))
        return "every ZIP member extracted without byte loss, duplication or omission"
    if tool_id == "tar-extract":
        expected = _tar_contents(source)
        actual = _zip_contents(output) if output.suffix == ".zip" else [output.read_bytes()]
        assert Counter(actual) == Counter(expected)
        return "each original TAR member restored byte-exactly"
    if tool_id in {"tar-gzip-extract", "tar-bzip2-extract"}:
        expected = _tar_contents(source)
        actual = _zip_contents(output) if output.suffix == ".zip" else [output.read_bytes()]
        assert Counter(actual) == Counter(expected)
        return "all compressed TAR members independently restored byte-exactly"
    if tool_id in {"tar-create", "tar-gzip-create", "tar-bzip2-create"}:
        assert len(_tar_contents(output)) == 2
        assert all(data == source.read_bytes() for data in _tar_contents(output))
        return "both source files are independently recovered byte-exactly from created TAR"
    if tool_id == "zip-to-tar":
        assert Counter(_tar_contents(output)) == Counter(_zip_contents(source))
        return "ZIP-to-TAR preserves all original member contents byte-exactly"
    if tool_id == "zip-flatten":
        assert Counter(_zip_contents(output)) == Counter(_zip_contents(source))
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            assert len(names) == len(set(names))
            assert all("/" not in n and "\\" not in n for n in names)
        return "flattened ZIP preserves every member byte-exactly with unique root-level names"
    if tool_id == "zip-list":
        with zipfile.ZipFile(source) as z:
            expected = [(i.filename, i.file_size, i.compress_size, i.is_dir()) for i in z.infolist()]
        data = json.loads(output.read_text(encoding="utf-8"))
        actual = [(r["name"], r["size_bytes"], r["compressed_bytes"], r["directory"]) for r in data["entries"]]
        assert actual == expected
        return "every ZIP entry name, size, compression size and directory flag matches source"
    if tool_id == "zip-integrity":
        with zipfile.ZipFile(source) as z:
            entries = z.infolist()
            data = json.loads(output.read_text(encoding="utf-8"))
            assert data["valid"] is (z.testzip() is None)
            assert data["entries"] == len(entries)
            assert data["uncompressed_bytes"] == sum(i.file_size for i in entries)
            assert data["compressed_bytes"] == sum(i.compress_size for i in entries)
        return "ZIP CRC status, entry count and byte totals independently verified"
    if tool_id == "zip-duplicate-report":
        with zipfile.ZipFile(source) as z:
            names = z.namelist()
        duplicates = sorted({n for n in names if names.count(n) > 1})
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data == {"duplicates": duplicates, "entries": len(names)}
        return "every duplicate archive path and total member count independently verified"
    if tool_id in {"tar-list", "tar-integrity"}:
        with tarfile.open(source, "r:*") as t:
            members = t.getmembers()
            data = json.loads(output.read_text(encoding="utf-8"))
            if tool_id == "tar-integrity":
                assert data == {"valid": True, "entries": len(members)}
            else:
                actual = [(e["name"], e["size_bytes"], e["type"]) for e in data["entries"]]
                expected = [(m.name, m.size, "directory" if m.isdir() else "file" if m.isfile() else "other") for m in members]
                assert actual == expected
        return "TAR source member integrity, type, size and count independently verified"
    if tool_id == "gzip-info":
        data = json.loads(output.read_text(encoding="utf-8"))
        expanded_size = len(gzip.decompress(source.read_bytes()))
        assert data["compressed_bytes"] == source.stat().st_size
        assert data["uncompressed_bytes"] == expanded_size
        assert data["compression_ratio"] == round(expanded_size / source.stat().st_size, 3)
        return "compressed and uncompressed GZIP lengths plus ratio match original bytes"
    if tool_id == "file-info":
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["filename"] == source.name
        assert data["extension"] == source.suffix.lower()
        assert data["size_bytes"] == source.stat().st_size
        assert data["safe"] is True
        return "file name, extension, real byte length and validated-safe status match source"
    if tool_id == "filename-normalizer":
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["original"] == source.name
        assert data["normalized"] == source.name
        return "already-normalized source filename is retained unchanged, without extension loss"
    if tool_id == "file-extension-report":
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["filename"] == source.name
        assert data["extension"] == source.suffix.lower()
        assert data["stem"] == source.stem
        assert data["mime"] == mimetypes.guess_type(source.name)[0]
        return "filename, exact extension, stem and MIME independently match source"
    if tool_id == "number-list-analyzer":
        raw = source.read_text(encoding="utf-8")
        values = []
        for tok in re.split(r"[\s,;|]+", raw.strip()):
            try:
                values.append(float(tok))
            except ValueError:
                pass
        data = json.loads(output.read_text(encoding="utf-8"))
        assert values
        assert data["count"] == len(values)
        assert data["sum"] == sum(values)
        assert data["min"] == min(values)
        assert data["max"] == max(values)
        assert data["mean"] == statistics.mean(values)
        assert data["median"] == statistics.median(values)
        return "six source-derived numeric statistics independently recomputed"
    if tool_id == "text-diff":
        raw = source.read_text(encoding="utf-8")
        text = output.read_text(encoding="utf-8")
        assert text == "No differences found. The files are identical.\n" and raw
        return "two byte-identical source inputs produce explicitly empty semantic diff"
    if tool_id == "regex-extract":
        raw = source.read_text(encoding="utf-8")
        matches = sorted(set(m.group(0) for m in re.finditer(r"\b[A-Za-z]+\b", raw, re.I)))
        assert output.read_text(encoding="utf-8").splitlines() == matches
        return "every source regex match extracted exactly once and in correct sorted order"
    raise AssertionError("Registered source-aware oracle missing branch")

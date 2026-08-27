import hashlib
import json
from pathlib import Path


def hash_report(source: Path, output: Path, original_name: str):
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with source.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    report = {
        "filename": original_name,
        "size_bytes": source.stat().st_size,
        "sha256": sha256.hexdigest(),
        "md5": md5.hexdigest(),
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def file_info_report(details: dict, output: Path):
    report = {
        key: (str(value) if not isinstance(value, (int, float, bool, str, type(None))) else value)
        for key, value in details.items()
        if key != "path"
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

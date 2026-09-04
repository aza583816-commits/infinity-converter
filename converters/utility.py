import hashlib
import json
import csv
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


def merge_and_deduplicate_csv(paths: list[Path], output: Path):
    headers = None
    rows = []
    seen = set()
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                file_headers = next(reader)
            except StopIteration as exc:
                raise ValueError("ملف CSV فارغ.") from exc
            if not file_headers or any(not column.strip() for column in file_headers):
                raise ValueError("رؤوس أعمدة CSV غير صالحة.")
            if headers is None:
                headers = file_headers
            elif file_headers != headers:
                raise ValueError("يجب أن تتطابق رؤوس الأعمدة في جميع ملفات CSV.")
            for row in reader:
                if len(row) != len(headers):
                    raise ValueError("يحتوي CSV على صف بعدد أعمدة غير متوافق.")
                key = tuple(row)
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
                    if len(rows) > 100000:
                        raise ValueError("عدد صفوف CSV يتجاوز الحد الآمن.")
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def text_to_gift(source: Path, output: Path):
    text = source.read_text(encoding="utf-8").strip()
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    questions = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) != 2 or not lines[0].startswith("Q:") or not lines[1].startswith("A:"):
            raise ValueError("استخدم لكل سؤال سطرين: Q: السؤال ثم A: الإجابة، وافصل بين الأسئلة بسطر فارغ.")
        question, answer = lines[0][2:].strip(), lines[1][2:].strip()
        if not question or not answer or len(question) > 1000 or len(answer) > 1000:
            raise ValueError("السؤال أو الإجابة غير صالحين.")
        escape = lambda value: value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("=", "\\=").replace("~", "\\~")
        questions.append(f"::Question {len(questions) + 1}::{escape(question)} {{={escape(answer)}}}")
    if not questions:
        raise ValueError("لم يتم العثور على أسئلة صالحة.")
    output.write_text("\n\n".join(questions) + "\n", encoding="utf-8")

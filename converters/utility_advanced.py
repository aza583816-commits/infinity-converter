import hashlib
import json
import mimetypes
import re
import unicodedata
from pathlib import Path


def mime_report(source: Path, output: Path):
    mime, _ = mimetypes.guess_type(source.name)
    raw = source.read_bytes()[:32]
    output.write_text(json.dumps({'filename': source.name, 'extension': source.suffix.lower(), 'mime_type_guess': mime or 'application/octet-stream', 'signature_hex': raw.hex(), 'size_bytes': source.stat().st_size}, ensure_ascii=False, indent=2), encoding='utf-8')


def text_statistics(source: Path, output: Path):
    text = source.read_text(encoding='utf-8')
    words = re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE)
    lines = text.splitlines()
    paragraphs = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    stats = {'characters': len(text), 'characters_without_spaces': len(re.sub(r'\s+', '', text)), 'words': len(words), 'lines': len(lines), 'paragraphs': len(paragraphs), 'bytes_utf8': len(text.encode('utf-8'))}
    output.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_text(source: Path, output: Path):
    text = source.read_text(encoding='utf-8').replace('\r\n', '\n').replace('\r', '\n')
    lines = [' '.join(line.split()) for line in text.splitlines()]
    cleaned = '\n'.join(lines).strip() + '\n'
    output.write_text(cleaned, encoding='utf-8')


def deduplicate_text(source: Path, output: Path):
    seen = set()
    out = []
    for line in source.read_text(encoding='utf-8').splitlines():
        key = line.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(line.rstrip())
    if not out:
        raise ValueError('لم يتم العثور على أسطر نصية.')
    output.write_text('\n'.join(out) + '\n', encoding='utf-8')


def sort_text(source: Path, output: Path, descending: str = '0'):
    reverse = descending == '1'
    lines = source.read_text(encoding='utf-8').splitlines()
    lines.sort(key=lambda value: unicodedata.normalize('NFKC', value).casefold(), reverse=reverse)
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def normalize_filename(source: Path, output: Path):
    cleaned = unicodedata.normalize('NFKC', source.stem)
    cleaned = re.sub(r'[^\w\-. ]+', '', cleaned, flags=re.UNICODE)
    cleaned = re.sub(r'\s+', '-', cleaned).strip('-_.') or 'file'
    name = (cleaned[:90] + source.suffix.lower())
    output.write_text(json.dumps({'original': source.name, 'normalized': name}, ensure_ascii=False, indent=2), encoding='utf-8')


def csv_validate(source: Path, output: Path):
    import csv
    with source.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.reader(fh, strict=True)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError('CSV فارغ.')
        errors = []
        count = 0
        for row in reader:
            count += 1
            if len(row) != len(header):
                errors.append({'row': count + 1, 'columns': len(row), 'expected': len(header)})
                if len(errors) >= 100:
                    break
    report = {'valid': not errors, 'columns': len(header), 'rows_checked': count, 'errors': errors}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def json_validate(source: Path, output: Path):
    raw = source.read_text(encoding='utf-8')
    try:
        data = json.loads(raw)
        report = {'valid': True, 'root_type': type(data).__name__, 'keys': len(data) if isinstance(data, dict) else None}
    except json.JSONDecodeError as exc:
        report = {'valid': False, 'root_type': None, 'line': exc.lineno, 'column': exc.colno, 'error': exc.msg}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def number_list_analysis(source: Path, output: Path):
    text = source.read_text(encoding='utf-8')
    values = []
    for token in re.split(r'[\s,;|]+', text.strip()):
        if not token:
            continue
        try:
            values.append(float(token))
        except ValueError:
            pass
    if not values:
        raise ValueError('لم نجد أرقامًا قابلة للتحليل.')
    values.sort()
    n = len(values)
    median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
    mean = sum(values) / n
    report = {'count': n, 'sum': sum(values), 'min': values[0], 'max': values[-1], 'mean': mean, 'median': median}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def text_to_base64(source: Path, output: Path):
    import base64
    text = source.read_text(encoding='utf-8')
    if not text:
        raise ValueError('ملف TXT فارغ.')
    encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
    output.write_text(encoded + '\n', encoding='ascii')

import gzip
import json
import os
import tarfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from config.settings import settings


def create_tar(files: list[tuple[Path, str]], output: Path):
    with tarfile.open(output, 'w') as tf:
        for path, arcname in files:
            tf.add(path, arcname=Path(arcname).name)


def _safe_tar_members(tf: tarfile.TarFile):
    members = tf.getmembers()
    if len(members) > settings.max_archive_entries:
        raise ValueError('الأرشيف يحتوي على عدد ملفات غير طبيعي.')
    total = 0
    for member in members:
        name = member.name.replace('\\', '/')
        if name.startswith('/') or name.startswith('../') or '/..' in name:
            raise ValueError('الأرشيف يحتوي على مسار غير آمن.')
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise ValueError('الأرشيف يحتوي على روابط أو ملفات خاصة غير مدعومة.')
        total += max(0, member.size)
        if member.size > settings.max_archive_uncompressed_bytes or total > settings.max_archive_uncompressed_bytes:
            raise ValueError('حجم محتوى الأرشيف بعد فك الضغط يتجاوز الحد الآمن.')
    return members


def extract_tar(source: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source, 'r:*') as tf:
        members = _safe_tar_members(tf)
        outputs = []
        for member in members:
            if not member.isfile():
                continue
            target = output_dir / Path(member.name).name
            counter = 1
            while target.exists():
                target = output_dir / f'{target.stem}-{counter}{target.suffix}'
                counter += 1
            with tf.extractfile(member) as src, target.open('wb') as dst:
                if src is not None:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
            outputs.append(target)
    if not outputs:
        raise ValueError('الأرشيف لا يحتوي ملفات قابلة للاستخراج.')
    return outputs


def gzip_compress(source: Path, output: Path):
    with source.open('rb') as src, gzip.open(output, 'wb', compresslevel=9) as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)


def gzip_decompress(source: Path, output: Path):
    chunks = []
    total = 0
    try:
        with gzip.open(source, 'rb') as src:
            while chunk := src.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_archive_uncompressed_bytes:
                    raise ValueError('حجم الملف بعد فك الضغط كبير جدًا.')
                chunks.append(chunk)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('ملف GZIP غير صالح أو تالف.') from exc
    raw = b''.join(chunks)
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('هذه الأداة مخصصة لملفات GZIP النصية بترميز UTF-8.') from exc
    output.write_bytes(raw)


def zip_list(source: Path, output: Path):
    with ZipFile(source) as zf:
        rows = []
        for info in zf.infolist():
            rows.append({'name': info.filename, 'size_bytes': info.file_size, 'compressed_bytes': info.compress_size, 'directory': info.is_dir()})
        output.write_text(json.dumps({'entries': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


def zip_flatten(source: Path, output: Path):
    with ZipFile(source) as src, ZipFile(output, 'w', ZIP_DEFLATED) as dst:
        used = set()
        for info in src.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name or 'file'
            base = Path(name)
            candidate = name
            i = 1
            while candidate in used:
                candidate = f'{base.stem}-{i}{base.suffix}'
                i += 1
            used.add(candidate)
            dst.writestr(candidate, src.read(info))


def zip_integrity_report(source: Path, output: Path):
    with ZipFile(source) as zf:
        bad = zf.testzip()
        infos = zf.infolist()
        report = {
            'valid': bad is None,
            'first_bad_entry': bad,
            'entries': len(infos),
            'compressed_bytes': sum(i.compress_size for i in infos),
            'uncompressed_bytes': sum(i.file_size for i in infos),
        }
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def tar_list(source: Path, output: Path):
    with tarfile.open(source, 'r:*') as tf:
        members = _safe_tar_members(tf)
        rows = [{'name': m.name, 'size_bytes': m.size, 'type': 'directory' if m.isdir() else 'file' if m.isfile() else 'other'} for m in members]
    output.write_text(json.dumps({'entries': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


def gzip_info(source: Path, output: Path):
    raw_size = source.stat().st_size
    with gzip.open(source, 'rb') as fh:
        uncompressed = 0
        while chunk := fh.read(1024 * 1024):
            uncompressed += len(chunk)
            if uncompressed > settings.max_archive_uncompressed_bytes:
                raise ValueError('حجم البيانات غير المضغوطة كبير جدًا.')
    report = {'compressed_bytes': raw_size, 'uncompressed_bytes': uncompressed, 'compression_ratio': round(uncompressed / raw_size, 3) if raw_size else None}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def zip_to_tar(source: Path, output: Path):
    with ZipFile(source) as zf, tarfile.open(output, 'w') as tf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name or 'file'
            data = zf.read(info)
            import io
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))


def tar_to_zip(source: Path, output: Path):
    with tarfile.open(source, 'r:*') as tf, ZipFile(output, 'w', ZIP_DEFLATED) as zf:
        members = _safe_tar_members(tf)
        used = set()
        for member in members:
            if not member.isfile():
                continue
            name = Path(member.name).name or 'file'
            base = name
            i = 1
            while name in used:
                p = Path(base)
                name = f'{p.stem}-{i}{p.suffix}'
                i += 1
            used.add(name)
            fh = tf.extractfile(member)
            if fh:
                zf.writestr(name, fh.read())

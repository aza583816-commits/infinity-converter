import zipfile
from pathlib import Path

MAX_ENTRIES = 2000
MAX_ENTRY_BYTES = 200 * 1024 * 1024
MAX_TOTAL_BYTES = 300 * 1024 * 1024


def create_zip(files: list[tuple[Path, str]], output: Path):
    """files: list of (path_on_disk, arcname) pairs."""
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in files:
            zf.write(path, arcname=arcname)


def extract_zip(source: Path, output_dir: Path) -> list[Path]:
    """Safely extract a zip archive, rejecting traversal, encryption, and resource exhaustion."""
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(source) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError("الأرشيف يحتوي على عدد ملفات غير طبيعي.")

        total = 0
        for info in infos:
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or name.startswith("../") or "/../" in name:
                raise ValueError("الأرشيف يحتوي على مسار غير آمن.")
            if info.flag_bits & 0x1:
                raise ValueError("الأرشيفات المشفرة غير مدعومة.")
            total += info.file_size
            if info.file_size > MAX_ENTRY_BYTES or total > MAX_TOTAL_BYTES:
                raise ValueError("حجم محتوى الأرشيف بعد فك الضغط يتجاوز الحد الآمن.")

        for info in infos:
            if info.is_dir():
                continue
            name = Path(info.filename.replace("\\", "/")).name  # flatten, drop directories
            if not name:
                continue
            target = output_dir / name
            counter = 1
            while target.exists():
                target = output_dir / f"{Path(name).stem}-{counter}{Path(name).suffix}"
                counter += 1
            with zf.open(info) as source_fh, target.open("wb") as target_fh:
                target_fh.write(source_fh.read())
            extracted.append(target)

    if not extracted:
        raise ValueError("الأرشيف لا يحتوي على ملفات قابلة للاستخراج.")
    return extracted

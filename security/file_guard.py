from pathlib import Path
from uuid import uuid4
import io
import zipfile

from pypdf import PdfReader
from PIL import Image, UnidentifiedImageError
from config.settings import settings

ALLOWED_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    # Pillow performs format-aware validation for raster formats whose
    # container signatures vary (BMP/TIFF).
    ".bmp": None,
    ".tiff": None,
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".txt": None,
    ".csv": None,
    ".md": None,
    ".markdown": None,
    ".log": None,
    ".html": None,
    ".htm": None,
    ".json": None,
    ".xml": None,
    ".tar": None,
    ".gz": (b"\x1f\x8b",),
    ".tgz": (b"\x1f\x8b",),
    ".bz2": (b"BZh",),
    ".tbz2": (b"BZh",),
    ".xz": (b"\xfd7zXZ\x00",),
}

# Formats validated by decodability instead of a binary signature.
TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".markdown", ".log", ".html", ".htm", ".json", ".xml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
MAX_TEXT_BYTES = 15 * 1024 * 1024

OFFICE_REQUIRED = {
    ".docx": "[Content_Types].xml",
    ".xlsx": "[Content_Types].xml",
    ".pptx": "[Content_Types].xml",
}

def _validate_text(raw: bytes) -> dict:
    if len(raw) > MAX_TEXT_BYTES:
        raise ValueError("حجم الملف النصي يتجاوز الحد الآمن.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("الملف النصي ليس بترميز UTF-8 صالح.") from exc
    if not text.strip():
        raise ValueError("الملف النصي فارغ.")
    # Reject binary content masquerading as text (control chars other than tab/newline/CR).
    if any(ord(ch) < 9 or (13 < ord(ch) < 32) for ch in text[:200000]):
        raise ValueError("محتوى الملف لا يبدو نصًا صالحًا.")
    return {"safe": True, "characters": len(text)}

def _safe_generic_zip(raw: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            infos = zf.infolist()
            if len(infos) > 2000:
                raise ValueError("الأرشيف يحتوي على عدد ملفات غير طبيعي.")
            total_uncompressed = 0
            for info in infos:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or name.startswith("../") or "/../" in name:
                    raise ValueError("الأرشيف يحتوي على مسار غير آمن.")
                if info.flag_bits & 0x1:
                    raise ValueError("الأرشيفات المشفرة غير مدعومة.")
                total_uncompressed += info.file_size
                if info.file_size > 200 * 1024 * 1024 or total_uncompressed > 300 * 1024 * 1024:
                    raise ValueError("حجم محتوى الأرشيف بعد فك الضغط يتجاوز الحد الآمن.")
            if len(raw) and total_uncompressed / len(raw) > 150:
                raise ValueError("تم رفض الأرشيف بسبب نسبة ضغط غير طبيعية.")
            return {"container_entries": len(infos), "safe": True}
    except zipfile.BadZipFile as exc:
        raise ValueError("الأرشيف تالف أو غير صالح.") from exc

def _safe_zip(raw: bytes, suffix: str) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            infos = zf.infolist()
            if len(infos) > 5000:
                raise ValueError("الملف المضغوط يحتوي على عدد عناصر غير طبيعي.")

            total_uncompressed = 0
            names = set()
            for info in infos:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or name.startswith("../") or "/../" in name:
                    raise ValueError("الملف يحتوي على مسار غير آمن.")
                if info.flag_bits & 0x1:
                    raise ValueError("الملفات المضغوطة المشفرة غير مدعومة.")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("الملف المضغوط يحتوي على روابط رمزية غير مدعومة.")
                total_uncompressed += info.file_size
                if info.file_size > 50 * 1024 * 1024 or total_uncompressed > 100 * 1024 * 1024:
                    raise ValueError("حجم المحتوى بعد فك الضغط يتجاوز الحد الآمن.")
                names.add(name)

            if len(raw) and total_uncompressed / len(raw) > 100:
                raise ValueError("تم رفض الملف بسبب نسبة ضغط غير طبيعية.")

            required = OFFICE_REQUIRED.get(suffix)
            if required and required not in names:
                raise ValueError("بنية ملف Office غير صالحة.")
            if suffix == ".docx" and "word/document.xml" not in names:
                raise ValueError("ملف DOCX غير مكتمل.")
            if suffix == ".xlsx" and "xl/workbook.xml" not in names:
                raise ValueError("ملف XLSX غير مكتمل.")
            if suffix == ".pptx" and "ppt/presentation.xml" not in names:
                raise ValueError("ملف PPTX غير مكتمل.")
            return {"container_entries": len(infos), "safe": True}
    except zipfile.BadZipFile as exc:
        raise ValueError("الملف المضغوط تالف أو غير صالح.") from exc

def _validate_image(raw: bytes) -> dict:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            image_format = (image.format or "").upper()
            image.verify()
        if width < 1 or height < 1:
            raise ValueError("أبعاد الصورة غير صالحة.")
        return {"width": width, "height": height, "format": image_format, "safe": True}
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("ملف الصورة غير صالح أو تالف.") from exc

def _validate_pdf(raw: bytes, max_pages: int) -> dict:
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = len(reader.pages)
        if pages > max_pages:
            raise ValueError("عدد صفحات PDF يتجاوز الحد المسموح.")
        return {"pages": pages, "safe": True}
    except Exception as exc:
        raise ValueError("ملف PDF غير صالح أو تالف.") from exc

def validate_upload(uploaded, *, max_bytes: int, inspect_only: bool, workspace=None, max_pdf_pages: int = 1000):
    name = (uploaded.filename or "").strip()
    if not name:
        raise ValueError("اسم الملف غير صالح.")

    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SIGNATURES:
        raise ValueError("نوع الملف غير مدعوم في هذه الأداة.")

    raw = uploaded.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"الحد الأقصى للملف هو {max_bytes // (1024 * 1024)}MB.")

    if suffix in TEXT_EXTENSIONS or suffix in IMAGE_EXTENSIONS and suffix in {".bmp", ".tiff"}:
        valid_signature = True
    elif suffix == ".webp":
        valid_signature = len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    else:
        signatures = ALLOWED_SIGNATURES[suffix]
        valid_signature = True if signatures is None else any(raw.startswith(sig) for sig in signatures)
    if not valid_signature:
        raise ValueError("توقيع الملف لا يطابق امتداده.")

    details = {"filename": name, "extension": suffix, "size_bytes": len(raw)}

    if suffix == ".pdf":
        details.update(_validate_pdf(raw, max_pdf_pages))
    elif suffix in IMAGE_EXTENSIONS:
        details.update(_validate_image(raw))
    elif suffix in OFFICE_REQUIRED:
        details.update(_safe_zip(raw, suffix))
    elif suffix == ".zip":
        details.update(_safe_generic_zip(raw))
    elif suffix in {".gz", ".tgz"}:
        try:
            import gzip
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as fh:
                fh.read(1)
        except Exception as exc:
            raise ValueError("ملف GZIP غير صالح أو تالف.") from exc
        details.update({"safe": True})
    elif suffix in {".bz2", ".tbz2", ".xz"}:
        try:
            import bz2, lzma
            decoder = bz2.BZ2Decompressor() if suffix in {".bz2", ".tbz2"} else lzma.LZMADecompressor()
            sample = decoder.decompress(raw, settings.max_archive_uncompressed_bytes + 1)
            if len(sample) > settings.max_archive_uncompressed_bytes:
                raise ValueError("حجم المحتوى بعد فك الضغط يتجاوز الحد الآمن.")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("ملف الضغط غير صالح أو تالف.") from exc
        details.update({"safe": True, "decompressed_sample_bytes": len(sample)})
    elif suffix == ".tar":
        try:
            import tarfile
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
                members = tf.getmembers()
                if len(members) > settings.max_archive_entries:
                    raise ValueError("أرشيف TAR يحتوي على عدد عناصر غير طبيعي.")
                total_uncompressed = 0
                for member in members:
                    name = member.name.replace("\\", "/")
                    if name.startswith("/") or name.startswith("../") or "/../" in name:
                        raise ValueError("أرشيف TAR يحتوي على مسار غير آمن.")
                    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                        raise ValueError("أرشيف TAR يحتوي على ملف خاص أو رابط غير مدعوم.")
                    total_uncompressed += max(0, member.size)
                    if member.size > settings.max_archive_uncompressed_bytes or total_uncompressed > settings.max_archive_uncompressed_bytes:
                        raise ValueError("حجم محتوى أرشيف TAR بعد الاستخراج يتجاوز الحد الآمن.")
                if len(raw) and total_uncompressed / len(raw) > settings.max_archive_ratio:
                    raise ValueError("تم رفض أرشيف TAR بسبب نسبة ضغط غير طبيعية.")
                details.update({"container_entries": len(members), "safe": True})
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("أرشيف TAR غير صالح أو تالف.") from exc
    elif suffix in TEXT_EXTENSIONS:
        details.update(_validate_text(raw))

    if inspect_only:
        return details

    if workspace is None:
        raise ValueError("مساحة المعالجة غير متاحة.")

    target = workspace / "input" / f"{uuid4().hex}{suffix}"
    target.write_bytes(raw)
    details["path"] = target
    return details

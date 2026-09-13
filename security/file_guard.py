from __future__ import annotations

import io
import warnings
import zipfile
from pathlib import Path
from uuid import uuid4

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
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
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

TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".markdown", ".log", ".html", ".htm", ".json", ".xml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
MAX_TEXT_BYTES = 15 * 1024 * 1024

OFFICE_REQUIRED = {
    ".docx": "[Content_Types].xml",
    ".xlsx": "[Content_Types].xml",
    ".pptx": "[Content_Types].xml",
}

# MIME is a secondary signal only. Browsers can legally send an empty value or
# application/octet-stream, so those are intentionally accepted after magic /
# structural validation succeeds.
MIME_HINTS = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".webp": {"image/webp"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
    ".tiff": {"image/tiff"},
    ".doc": {"application/msword", "application/x-ole-storage"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip"},
    ".zip": {"application/zip", "application/x-zip-compressed"},
    ".gz": {"application/gzip", "application/x-gzip"},
    ".tgz": {"application/gzip", "application/x-gzip", "application/x-compressed-tar"},
    ".bz2": {"application/x-bzip2", "application/octet-stream"},
    ".tbz2": {"application/x-bzip2", "application/octet-stream"},
    ".xz": {"application/x-xz", "application/octet-stream"},
    ".tar": {"application/x-tar", "application/octet-stream"},
}


def _clean_client_filename(value: str) -> str:
    value = (value or "").replace("\\", "/").strip()
    if not value:
        raise ValueError("اسم الملف غير صالح.")
    if "\x00" in value or any(ord(ch) < 32 for ch in value):
        raise ValueError("اسم الملف يحتوي على محارف غير صالحة.")
    name = value.rsplit("/", 1)[-1].strip()
    if not name or name in {".", ".."} or len(name) > 255:
        raise ValueError("اسم الملف غير صالح.")
    return name


def _validate_mime_hint(uploaded, suffix: str) -> None:
    mime = (getattr(uploaded, "mimetype", "") or "").split(";", 1)[0].strip().lower()
    if not mime or mime == "application/octet-stream" or suffix in TEXT_EXTENSIONS:
        return
    allowed = MIME_HINTS.get(suffix)
    if allowed and mime not in allowed:
        raise ValueError("نوع MIME المرسل لا يطابق امتداد الملف.")


def _validate_text(raw: bytes) -> dict:
    if len(raw) > MAX_TEXT_BYTES:
        raise ValueError("حجم الملف النصي يتجاوز الحد الآمن.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("الملف النصي ليس بترميز UTF-8 صالح.") from exc
    if not text.strip():
        raise ValueError("الملف النصي فارغ.")
    if any(ord(ch) < 9 or (13 < ord(ch) < 32) for ch in text[:200000]):
        raise ValueError("محتوى الملف لا يبدو نصًا صالحًا.")
    return {"safe": True, "characters": len(text)}


def _unsafe_zip_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename.replace("\\", "/")
    if not name or name.startswith("/") or name.startswith("../") or "/../" in name:
        return True
    unix_type = (info.external_attr >> 16) & 0o170000
    return unix_type == 0o120000  # symlink


def _safe_generic_zip(raw: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            infos = zf.infolist()
            if not infos:
                raise ValueError("الأرشيف فارغ.")
            if len(infos) > settings.max_archive_entries:
                raise ValueError("الأرشيف يحتوي على عدد ملفات غير طبيعي.")
            total_uncompressed = 0
            for info in infos:
                if _unsafe_zip_member(info):
                    raise ValueError("الأرشيف يحتوي على مسار أو رابط غير آمن.")
                if info.flag_bits & 0x1:
                    raise ValueError("الأرشيفات المشفرة غير مدعومة.")
                total_uncompressed += info.file_size
                if info.file_size > settings.max_archive_uncompressed_bytes or total_uncompressed > settings.max_archive_uncompressed_bytes:
                    raise ValueError("حجم محتوى الأرشيف بعد فك الضغط يتجاوز الحد الآمن.")
            if len(raw) and total_uncompressed / len(raw) > settings.max_archive_ratio:
                raise ValueError("تم رفض الأرشيف بسبب نسبة ضغط غير طبيعية.")
            return {"container_entries": len(infos), "expanded_bytes": total_uncompressed, "safe": True}
    except zipfile.BadZipFile as exc:
        raise ValueError("الأرشيف تالف أو غير صالح.") from exc


def _office_has_unsafe_external_resource(zf: zipfile.ZipFile) -> bool:
    """Reject external package relationships except ordinary hyperlinks.

    Office hyperlink relationships are user-visible text links and are not
    fetched to render a document. Other TargetMode=External relationships can
    point at remote images, packages, templates or linked workbooks and are
    rejected before the file reaches LibreOffice or an Office parser.
    """
    import xml.etree.ElementTree as ET

    for name in zf.namelist():
        normalized = name.replace("\\", "/").lower()
        if not normalized.endswith(".rels"):
            continue
        try:
            root = ET.fromstring(zf.read(name))
        except (ET.ParseError, KeyError) as exc:
            raise ValueError("علاقات ملف Office غير صالحة.") from exc
        for relationship in root.iter():
            if not relationship.tag.lower().endswith("relationship"):
                continue
            mode = (relationship.attrib.get("TargetMode") or relationship.attrib.get("targetmode") or "").lower()
            if mode != "external":
                continue
            rel_type = (relationship.attrib.get("Type") or relationship.attrib.get("type") or "").lower()
            if not rel_type.endswith("/hyperlink"):
                return True
    return False


def _safe_zip(raw: bytes, suffix: str) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            infos = zf.infolist()
            if not infos:
                raise ValueError("الملف المضغوط فارغ.")
            if len(infos) > min(5000, max(settings.max_archive_entries, 1000)):
                raise ValueError("الملف المضغوط يحتوي على عدد عناصر غير طبيعي.")

            total_uncompressed = 0
            names = set()
            for info in infos:
                if _unsafe_zip_member(info):
                    raise ValueError("الملف يحتوي على مسار أو رابط غير آمن.")
                if info.flag_bits & 0x1:
                    raise ValueError("الملفات المضغوطة المشفرة غير مدعومة.")
                total_uncompressed += info.file_size
                if info.file_size > settings.max_archive_uncompressed_bytes or total_uncompressed > settings.max_archive_uncompressed_bytes:
                    raise ValueError("حجم المحتوى بعد فك الضغط يتجاوز الحد الآمن.")
                names.add(info.filename.replace("\\", "/"))

            if len(raw) and total_uncompressed / len(raw) > settings.max_archive_ratio:
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
            if _office_has_unsafe_external_resource(zf):
                raise ValueError("ملف Office يحتوي على مورد خارجي مضمن غير مسموح للمعالجة الآمنة.")
            return {"container_entries": len(infos), "expanded_bytes": total_uncompressed, "safe": True}
    except zipfile.BadZipFile as exc:
        raise ValueError("الملف المضغوط تالف أو غير صالح.") from exc


def _validate_image(raw: bytes) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                width, height = image.size
                image_format = (image.format or "").upper()
                pixels = width * height
                if width < 1 or height < 1 or pixels > settings.max_image_pixels:
                    raise ValueError("أبعاد الصورة تتجاوز الحد الآمن.")
                image.verify()
        return {"width": width, "height": height, "pixels": pixels, "format": image_format, "safe": True}
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("ملف الصورة غير صالح أو تالف.") from exc


def _validate_pdf(raw: bytes, max_pages: int) -> dict:
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:
            # Keep encrypted PDFs available to the dedicated unlock tool. Other
            # PDF operations can return a normal conversion error if no password
            # was supplied.
            return {"pages": None, "encrypted": True, "safe": True}
        pages = len(reader.pages)
        if pages < 1:
            raise ValueError("ملف PDF لا يحتوي على صفحات.")
        if pages > max_pages:
            raise ValueError("عدد صفحات PDF يتجاوز الحد المسموح.")
        return {"pages": pages, "encrypted": False, "safe": True}
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("ملف PDF غير صالح أو تالف.") from exc


def _validate_compressed_stream(raw: bytes, suffix: str) -> dict:
    """Fully bound stream expansion instead of validating only the first byte."""
    limit = settings.max_archive_uncompressed_bytes
    try:
        if suffix in {".gz", ".tgz"}:
            import gzip
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as fh:
                expanded = fh.read(limit + 1)
        elif suffix in {".bz2", ".tbz2"}:
            import bz2
            expanded = bz2.BZ2Decompressor().decompress(raw, limit + 1)
        else:
            import lzma
            expanded = lzma.LZMADecompressor().decompress(raw, limit + 1)
    except Exception as exc:
        raise ValueError("ملف الضغط غير صالح أو تالف.") from exc
    if len(expanded) > limit:
        raise ValueError("حجم المحتوى بعد فك الضغط يتجاوز الحد الآمن.")
    if len(raw) and len(expanded) / len(raw) > settings.max_archive_ratio:
        raise ValueError("تم رفض الملف بسبب نسبة ضغط غير طبيعية.")
    return {"expanded_sample_bytes": len(expanded), "safe": True}


def validate_upload(uploaded, *, max_bytes: int, inspect_only: bool, workspace=None, max_pdf_pages: int = 1000):
    name = _clean_client_filename(getattr(uploaded, "filename", ""))
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SIGNATURES:
        raise ValueError("نوع الملف غير مدعوم في هذه الأداة.")

    _validate_mime_hint(uploaded, suffix)

    raw = uploaded.read(max_bytes + 1)
    if not raw:
        raise ValueError("الملف فارغ.")
    if len(raw) > max_bytes:
        raise ValueError(f"الحد الأقصى للملف هو {max_bytes // (1024 * 1024)}MB.")

    if suffix in TEXT_EXTENSIONS or (suffix in IMAGE_EXTENSIONS and suffix in {".bmp", ".tiff"}):
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
    elif suffix in {".gz", ".tgz", ".bz2", ".tbz2", ".xz"}:
        details.update(_validate_compressed_stream(raw, suffix))
    elif suffix == ".tar":
        try:
            import tarfile
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
                members = tf.getmembers()
                if not members:
                    raise ValueError("أرشيف TAR فارغ.")
                if len(members) > settings.max_archive_entries:
                    raise ValueError("أرشيف TAR يحتوي على عدد عناصر غير طبيعي.")
                total_uncompressed = 0
                for member in members:
                    member_name = member.name.replace("\\", "/")
                    if member_name.startswith("/") or member_name.startswith("../") or "/../" in member_name:
                        raise ValueError("أرشيف TAR يحتوي على مسار غير آمن.")
                    if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                        raise ValueError("أرشيف TAR يحتوي على ملف خاص أو رابط غير مدعوم.")
                    total_uncompressed += max(0, member.size)
                    if member.size > settings.max_archive_uncompressed_bytes or total_uncompressed > settings.max_archive_uncompressed_bytes:
                        raise ValueError("حجم محتوى أرشيف TAR بعد الاستخراج يتجاوز الحد الآمن.")
                if len(raw) and total_uncompressed / len(raw) > settings.max_archive_ratio:
                    raise ValueError("تم رفض أرشيف TAR بسبب نسبة ضغط غير طبيعية.")
                details.update({"container_entries": len(members), "expanded_bytes": total_uncompressed, "safe": True})
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("أرشيف TAR غير صالح أو تالف.") from exc
    elif suffix in TEXT_EXTENSIONS:
        details.update(_validate_text(raw))

    if not details.get("safe"):
        raise ValueError("تعذر إثبات سلامة الملف قبل المعالجة.")

    if inspect_only:
        return details

    if workspace is None:
        raise ValueError("مساحة المعالجة غير متاحة.")
    input_dir = Path(workspace).resolve(strict=False) / "input"
    input_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = (input_dir / f"{uuid4().hex}{suffix}").resolve(strict=False)
    try:
        target.relative_to(input_dir.resolve(strict=False))
    except ValueError as exc:
        raise ValueError("مسار ملف الإدخال غير آمن.") from exc
    target.write_bytes(raw)
    details["path"] = target
    return details

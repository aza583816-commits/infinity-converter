from __future__ import annotations

import json
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader
from config.settings import settings
from security.file_guard import _safe_generic_zip, _unsafe_archive_name


MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".html": "text/html",
    ".json": "application/json",
    ".zip": "application/zip",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".log": "text/plain",
    ".gz": "application/gzip",
    ".tar.gz": "application/gzip",
    ".tgz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".tar.bz2": "application/x-bzip2",
    ".tbz2": "application/x-bzip2",
    ".xz": "application/x-xz",
    ".bin": "application/octet-stream",
    ".tar": "application/x-tar",
}


class OutputValidationError(ValueError):
    """Raised when a converter produces an unusable or unsafe output file."""


def _safe_zip_output(path: Path, *, office_kind: str | None = None) -> dict:
    try:
        _safe_generic_zip(path.read_bytes())
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if not infos:
                raise OutputValidationError("الملف المضغوط الناتج فارغ.")
            bad = zf.testzip()
            if bad is not None:
                raise OutputValidationError("الملف المضغوط الناتج تالف.")
            names = {info.filename.replace("\\", "/") for info in infos}
            for info in infos:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or name.startswith("../") or "/../" in name:
                    raise OutputValidationError("الملف المضغوط الناتج يحتوي على مسار غير آمن.")
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise OutputValidationError("الملف المضغوط الناتج يحتوي على رابط رمزي غير مسموح.")
            if office_kind == "docx" and not {"[Content_Types].xml", "word/document.xml"} <= names:
                raise OutputValidationError("ملف DOCX الناتج غير مكتمل.")
            if office_kind == "xlsx" and not {"[Content_Types].xml", "xl/workbook.xml"} <= names:
                raise OutputValidationError("ملف XLSX الناتج غير مكتمل.")
            return {"entries": len(infos)}
    except OutputValidationError:
        raise
    except Exception as exc:
        raise OutputValidationError("الملف المضغوط الناتج غير صالح.") from exc


def validate_output(path: Path, *, expected_extension: str, expected_mime: str, max_bytes: int | None = None) -> dict:
    path = Path(path)
    if path.is_symlink():
        raise OutputValidationError("محرك التحويل أعاد رابطًا رمزيًا بدل ملف ناتج.")
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        raise OutputValidationError("لم يُنتج محرك التحويل ملفًا صالحًا.")

    size = path.stat().st_size
    if max_bytes is not None and size > max_bytes:
        raise OutputValidationError("حجم الملف الناتج يتجاوز الحد الآمن.")

    extension = path.suffix.lower()
    if extension != expected_extension.lower():
        raise OutputValidationError("امتداد الملف الناتج لا يطابق العملية المطلوبة.")

    expected_by_extension = MIME_BY_EXTENSION.get(extension)
    if expected_by_extension and expected_by_extension != expected_mime:
        raise OutputValidationError("نوع الملف الناتج غير متوافق مع امتداده.")

    if extension == ".pdf":
        try:
            reader = PdfReader(str(path), strict=False)
            if reader.is_encrypted:
                return {"encrypted": True, "bytes": size}
            pages = len(reader.pages)
        except Exception as exc:
            raise OutputValidationError("ملف PDF الناتج غير صالح.") from exc
        if pages < 1:
            raise OutputValidationError("ملف PDF الناتج لا يحتوي على صفحات.")
        return {"pages": pages, "encrypted": False, "bytes": size}

    if extension in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            with Image.open(path) as image:
                width, height = image.size
                expected_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[extension]
                if image.format != expected_format or width * height > settings.max_image_pixels:
                    raise OutputValidationError("تنسيق الصورة الناتجة أو أبعادها غير صالحة.")
                image.verify()
        except Exception as exc:
            raise OutputValidationError("ملف الصورة الناتج غير صالح.") from exc
        if width < 1 or height < 1:
            raise OutputValidationError("أبعاد الصورة الناتجة غير صالحة.")
        return {"width": width, "height": height, "bytes": size}

    if extension in {".txt", ".csv", ".md", ".markdown", ".log"}:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            raise OutputValidationError("الملف النصي الناتج غير صالح.") from exc
        if not text.strip():
            raise OutputValidationError("الملف النصي الناتج فارغ.")
        return {"characters": len(text), "bytes": size}

    if extension == ".html":
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            raise OutputValidationError("ملف HTML الناتج غير صالح.") from exc
        lowered = text.lower()
        if "<html" not in lowered or "</html>" not in lowered:
            raise OutputValidationError("ملف HTML الناتج غير صالح.")
        return {"characters": len(text), "bytes": size}

    if extension == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise OutputValidationError("ملف JSON الناتج غير صالح.") from exc
        return {"keys": len(data) if isinstance(data, dict) else 0, "bytes": size}

    if extension == ".zip":
        details = _safe_zip_output(path)
        details["bytes"] = size
        return details

    if extension == ".docx":
        details = _safe_zip_output(path, office_kind="docx")
        details["bytes"] = size
        return details

    if extension in {".gz", ".bz2", ".xz"}:
        limit = max_bytes or (300 * 1024 * 1024)
        try:
            if extension == ".gz":
                import gzip
                with gzip.open(path, "rb") as fh:
                    expanded = fh.read(limit + 1)
            elif extension == ".bz2":
                import bz2
                with bz2.open(path, "rb") as fh:
                    expanded = fh.read(limit + 1)
            else:
                import lzma
                with lzma.open(path, "rb") as fh:
                    expanded = fh.read(limit + 1)
        except Exception as exc:
            raise OutputValidationError("ملف الضغط الناتج غير صالح.") from exc
        if len(expanded) > limit:
            raise OutputValidationError("حجم المحتوى الناتج بعد فك الضغط يتجاوز الحد الآمن.")
        return {"bytes": size, "expanded_sample_bytes": len(expanded)}

    if extension == ".tar":
        import tarfile
        try:
            with tarfile.open(path, "r:") as tf:
                entries = tf.getmembers()
        except Exception as exc:
            raise OutputValidationError("ملف TAR الناتج غير صالح.") from exc
        if not entries:
            raise OutputValidationError("ملف TAR الناتج فارغ.")
        if len(entries) > settings.max_archive_entries or sum(m.size for m in entries) > settings.max_archive_uncompressed_bytes:
            raise OutputValidationError("الأرشيف الناتج يتجاوز الحدود الآمنة.")
        for member in entries:
            name = member.name.replace("\\", "/")
            if _unsafe_archive_name(name) or not (member.isfile() or member.isdir()):
                raise OutputValidationError("ملف TAR الناتج يحتوي على مسار أو رابط غير آمن.")
        return {"entries": len(entries), "bytes": size}

    if extension == ".xlsx":
        _safe_zip_output(path, office_kind="xlsx")
        try:
            workbook = load_workbook(path, read_only=True, data_only=False)
            sheet_count = len(workbook.sheetnames)
            workbook.close()
        except Exception as exc:
            raise OutputValidationError("ملف XLSX الناتج غير صالح.") from exc
        if sheet_count < 1:
            raise OutputValidationError("ملف XLSX الناتج لا يحتوي على أوراق عمل.")
        return {"sheets": sheet_count, "bytes": size}

    return {"bytes": size, "extension": extension}

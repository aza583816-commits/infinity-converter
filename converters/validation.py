from pathlib import Path

from PIL import Image
from pypdf import PdfReader


MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class OutputValidationError(ValueError):
    """Raised when a converter produces an unusable output file."""


def validate_output(path: Path, *, expected_extension: str, expected_mime: str) -> dict:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        raise OutputValidationError("لم يُنتج محرك التحويل ملفًا صالحًا.")

    extension = path.suffix.lower()
    if extension != expected_extension.lower():
        raise OutputValidationError("امتداد الملف الناتج لا يطابق العملية المطلوبة.")

    expected_by_extension = MIME_BY_EXTENSION.get(extension)
    if expected_by_extension and expected_by_extension != expected_mime:
        raise OutputValidationError("نوع الملف الناتج غير متوافق مع امتداده.")

    if extension == ".pdf":
        try:
            pages = len(PdfReader(str(path), strict=False).pages)
        except Exception as exc:
            raise OutputValidationError("ملف PDF الناتج غير صالح.") from exc
        if pages < 1:
            raise OutputValidationError("ملف PDF الناتج لا يحتوي على صفحات.")
        return {"pages": pages}

    if extension in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            with Image.open(path) as image:
                image.verify()
                width, height = image.size
        except Exception as exc:
            raise OutputValidationError("ملف الصورة الناتج غير صالح.") from exc
        if width < 1 or height < 1:
            raise OutputValidationError("أبعاد الصورة الناتجة غير صالحة.")
        return {"width": width, "height": height}

    raise OutputValidationError("نوع الملف الناتج غير مدعوم للتحقق.")

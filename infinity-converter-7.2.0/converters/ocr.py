import shutil
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from config.settings import settings

LANG_MAP = {
    "ar": "ara",
    "en": "eng",
    "ar+en": "ara+eng",
}


def _tesseract_lang(lang: str) -> str:
    return LANG_MAP.get(lang, "ara+eng")


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_string(image: Image.Image, *, lang: str) -> str:
    try:
        return pytesseract.image_to_string(
            image,
            lang=_tesseract_lang(lang),
            timeout=settings.ocr_timeout_seconds,
        )
    except RuntimeError as exc:
        # pytesseract raises RuntimeError when the subprocess exceeds timeout.
        raise RuntimeError("استغرق OCR وقتًا أطول من المسموح.") from exc


def ocr_image(source: Path, output: Path, lang: str = "ar+en"):
    if not ocr_available():
        raise RuntimeError("محرك OCR غير مثبت على الخادم.")
    with Image.open(source) as img:
        text = _ocr_string(img, lang=lang)
    text = text.strip()
    if not text:
        raise ValueError("لم يتم التعرف على أي نص في الصورة.")
    output.write_text(text, encoding="utf-8")


def ocr_pdf(source: Path, output: Path, lang: str = "ar+en", max_pages: int = 25, dpi: int = 200):
    if not ocr_available():
        raise RuntimeError("محرك OCR غير مثبت على الخادم.")
    doc = pymupdf.open(str(source))
    try:
        if doc.page_count > max_pages:
            raise ValueError(f"عدد صفحات OCR يتجاوز الحد المسموح ({max_pages}).")
        zoom = dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        chunks = []
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            try:
                page_text = _ocr_string(image, lang=lang).strip()
            finally:
                image.close()
            chunks.append(f"--- صفحة {index} ---\n{page_text}")
        text = "\n\n".join(chunks).strip()
        if not text:
            raise ValueError("لم يتم التعرف على أي نص في الملف.")
        output.write_text(text, encoding="utf-8")
    finally:
        doc.close()

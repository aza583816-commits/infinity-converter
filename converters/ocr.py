import shutil
import csv
import io
import re
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
        text, tsv = pytesseract.run_and_get_multiple_output(
            image,
            extensions=['txt', 'tsv'],
            lang=_tesseract_lang(lang),
            timeout=settings.ocr_timeout_seconds,
        )
        rows = [row for row in csv.DictReader(io.StringIO(tsv), delimiter='\t')
                if row.get('text', '').strip() and float(row['conf']) >= 0]
        # Mixed-script headings can be segmented incorrectly by PSM 3. Retry
        # only observed low-confidence Arabic words; retain the original pass
        # unless confidence improves and every confident source token survives.
        if rows and any(float(row['conf']) < 35 and re.search(r'[\u0600-\u06ff]', row['text'])
                        for row in rows):
            alternative = pytesseract.image_to_data(
                image, lang=_tesseract_lang(lang), config='--psm 6',
                output_type=pytesseract.Output.DICT,
                timeout=settings.ocr_timeout_seconds,
            )
            words = [(i, value) for i, value in enumerate(alternative['text']) if value.strip()]
            mean = lambda values: sum(values) / len(values) if values else 0
            certain = {row['text'] for row in rows if float(row['conf']) >= 75}
            found = {value for _, value in words}
            if (certain <= found and
                    mean([float(alternative['conf'][i]) for i, _ in words]) >
                    mean([float(row['conf']) for row in rows])):
                lines = {}
                for i, value in words:
                    key = tuple(alternative[name][i] for name in ('block_num', 'par_num', 'line_num'))
                    lines.setdefault(key, []).append(value)
                return '\n'.join(' '.join(values) for values in lines.values())
        return text
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
        recognized = False
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            try:
                native = page.get_text('text').strip()
                page_text = native if native and not page.get_images() else _ocr_string(image, lang=lang).strip()
            finally:
                image.close()
            recognized = recognized or bool(page_text)
            chunks.append(f"--- صفحة {index} ---\n{page_text}")
        # Headers are not OCR content: an image-only blank PDF must not be
        # returned to the user as a successfully recognized document.
        if not recognized:
            raise ValueError("لم يتم التعرف على أي نص في الملف.")
        output.write_text("\n\n".join(chunks).strip(), encoding="utf-8")
    finally:
        doc.close()

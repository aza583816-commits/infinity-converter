import shutil
import csv
import io
import re
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageOps

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


def _recover_truncated_phone_line(image: Image.Image, text: str, rows: list[dict], lang: str) -> str:
    """Re-read an observed short phone line, without replacing other content."""
    pattern = re.compile(r"^(\s*(?:Phone|Tel|Telephone)\s*:?\s*)([+\d /().-]+)\s*$", re.I)
    lines = text.splitlines()
    groups = {}
    for row in rows:
        key = tuple(row[name] for name in ('block_num', 'par_num', 'line_num'))
        groups.setdefault(key, []).append(row)
    candidates = []
    for group in groups.values():
        observed_line = pattern.fullmatch(' '.join(row['text'] for row in group))
        if observed_line:
            candidates.append((re.sub(r'\D', '', observed_line[2]), group))
    for index, line in enumerate(lines):
        matched = pattern.fullmatch(line)
        if not matched or len(re.sub(r"\D", "", matched[2])) >= 8:
            continue
        found = next((entry for entry in candidates
                      if entry[0] == re.sub(r'\D', '', matched[2])), None)
        if found is None:
            continue
        candidates.remove(found)
        observed = found[1]
        left = max(0, min(int(r['left']) for r in observed) - 25)
        top = max(0, min(int(r['top']) for r in observed) - 20)
        right = min(image.width, max(int(r['left']) + int(r['width']) for r in observed) + 25)
        bottom = min(image.height, max(int(r['top']) + int(r['height']) for r in observed) + 20)
        with image.crop((left, top, right, bottom)) as crop:
            grayscale = ImageOps.grayscale(crop)
            enhanced = ImageOps.autocontrast(grayscale)
            grayscale.close()
            try:
                if max(enhanced.size) <= 2200:
                    enlarged = enhanced.resize((enhanced.width * 2, enhanced.height * 2), Image.Resampling.LANCZOS)
                    enhanced.close()
                    enhanced = enlarged
                candidate = pytesseract.image_to_string(
                    enhanced, lang=_tesseract_lang(lang), config='--psm 7',
                    timeout=settings.ocr_timeout_seconds).strip()
            finally:
                enhanced.close()
        recovered = pattern.fullmatch(candidate)
        if recovered and 8 <= len(re.sub(r"\D", "", recovered[2])) <= 15:
            lines[index] = matched[1] + recovered[2].strip()
    return '\n'.join(lines)


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
                text = '\n'.join(' '.join(values) for values in lines.values())
        return _recover_truncated_phone_line(image, text, rows, lang)
    except RuntimeError as exc:
        # pytesseract raises RuntimeError when the subprocess exceeds timeout.
        raise RuntimeError("استغرق OCR وقتًا أطول من المسموح.") from exc


def _load_display_image(source: Path) -> Image.Image:
    """Decode camera pixels in their declared display orientation, privately."""
    with Image.open(source) as opened:
        ImageOps.exif_transpose(opened, in_place=True)
        if opened.mode == 'RGBA' or 'transparency' in opened.info:
            # Tesseract displays alpha-backed text on white. Preserve that
            # behavior while normalizing camera orientation and RGB mode.
            with opened.convert('RGBA') as rgba:
                decoded = Image.new('RGB', rgba.size, 'white')
                with rgba.getchannel('A') as alpha:
                    decoded.paste(rgba, mask=alpha)
        else:
            decoded = opened.convert('RGB')
        # The pixels now carry the displayed orientation. Do not pass a
        # stale EXIF transform to downstream PDF/image encoders.
        decoded.info.pop('exif', None)
        return decoded


def ocr_image(source: Path, output: Path, lang: str = "ar+en"):
    if not ocr_available():
        raise RuntimeError("محرك OCR غير مثبت على الخادم.")
    with _load_display_image(source) as img:
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

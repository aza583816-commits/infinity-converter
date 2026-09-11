import json
import re
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from converters.ocr import _tesseract_lang, ocr_available

FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
)


def _fontfile() -> str | None:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _ocr_text(image: Image.Image, lang: str) -> str:
    if not ocr_available():
        raise RuntimeError('محرك OCR غير مثبت على الخادم.')
    return pytesseract.image_to_string(image, lang=_tesseract_lang(lang)).strip()


def image_to_searchable_pdf(source: Path, output: Path, lang: str = 'ar+en'):
    text = ''
    with Image.open(source) as img:
        img = img.convert('RGB')
        text = _ocr_text(img, lang)
        png = Path(output).with_suffix('.source.png')
        img.save(png, format='PNG', optimize=True)
        try:
            doc = pymupdf.open()
            page = doc.new_page(width=img.width * 72 / 96, height=img.height * 72 / 96)
            page.insert_image(page.rect, filename=str(png))
            if text:
                fontfile = _fontfile()
                kwargs = dict(fontname='helv', fontsize=8, color=(1, 1, 1), render_mode=3, overlay=True)
                if fontfile:
                    kwargs['fontfile'] = fontfile
                page.insert_textbox(page.rect, text, **kwargs)
            doc.save(str(output), garbage=4, deflate=True)
            doc.close()
        finally:
            png.unlink(missing_ok=True)


def pdf_to_searchable_pdf(source: Path, output: Path, lang: str = 'ar+en', dpi: int = 180):
    source_doc = pymupdf.open(str(source))
    result = pymupdf.open()
    try:
        if source_doc.page_count > 25:
            raise ValueError('الحد الأقصى للأداة هو 25 صفحة.')
        zoom = dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        for page in source_doc:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            text = _ocr_text(image, lang)
            new_page = result.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pix)
            if text:
                fontfile = _fontfile()
                kwargs = dict(fontname='helv', fontsize=7, color=(1, 1, 1), render_mode=3, overlay=True)
                if fontfile:
                    kwargs['fontfile'] = fontfile
                new_page.insert_textbox(new_page.rect, text, **kwargs)
        if result.page_count == 0:
            raise ValueError('ملف PDF فارغ.')
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        source_doc.close()


def image_ocr_json(source: Path, output: Path, lang: str = 'ar+en'):
    with Image.open(source) as img:
        img = img.convert('RGB')
        data = pytesseract.image_to_data(img, lang=_tesseract_lang(lang), output_type=pytesseract.Output.DICT)
        words = []
        for i, text in enumerate(data.get('text', [])):
            text = text.strip()
            if not text:
                continue
            words.append({'text': text, 'confidence': float(data['conf'][i]), 'left': int(data['left'][i]), 'top': int(data['top'][i]), 'width': int(data['width'][i]), 'height': int(data['height'][i])})
        output.write_text(json.dumps({'text': ' '.join(item['text'] for item in words), 'words': words}, ensure_ascii=False, indent=2), encoding='utf-8')


def pdf_ocr_json(source: Path, output: Path, lang: str = 'ar+en'):
    doc = pymupdf.open(str(source))
    try:
        if doc.page_count > 25:
            raise ValueError('الحد الأقصى للأداة هو 25 صفحة.')
        pages = []
        matrix = pymupdf.Matrix(2, 2)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            text = _ocr_text(image, lang)
            pages.append({'page': index, 'text': text})
        output.write_text(json.dumps({'pages': pages}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        doc.close()


def pdf_page_texts(source: Path, output_dir: Path, lang: str = 'ar+en') -> list[Path]:
    doc = pymupdf.open(str(source))
    outputs = []
    try:
        if doc.page_count > 25:
            raise ValueError('الحد الأقصى للأداة هو 25 صفحة.')
        matrix = pymupdf.Matrix(2, 2)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            text = _ocr_text(image, lang)
            out = output_dir / f'page-{index:03d}.txt'
            out.write_text(text or '(لا يوجد نص)', encoding='utf-8')
            outputs.append(out)
    finally:
        doc.close()
    return outputs


def ocr_extract_pattern(source: Path, output: Path, lang: str, pattern: str):
    with Image.open(source) as img:
        text = _ocr_text(img.convert('RGB'), lang)
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    unique = list(dict.fromkeys(matches))
    output.write_text('\n'.join(unique) + ('\n' if unique else ''), encoding='utf-8')
    if not unique:
        raise ValueError('لم يتم العثور على عناصر مطابقة في النص المستخرج.')


def ocr_numbers(source: Path, output: Path, lang: str = 'ar+en'):
    ocr_extract_pattern(source, output, lang, r'(?<!\w)\d+(?:[.,]\d+)*(?:%|\b)')


def ocr_emails(source: Path, output: Path, lang: str = 'ar+en'):
    ocr_extract_pattern(source, output, lang, r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}')


def ocr_urls(source: Path, output: Path, lang: str = 'ar+en'):
    ocr_extract_pattern(source, output, lang, r'https?://[^\s\u200f\u200e]+|www\.[^\s\u200f\u200e]+')


def ocr_tables_csv(source: Path, output: Path, lang: str = 'ar+en'):
    with Image.open(source) as img:
        data = pytesseract.image_to_data(img.convert('RGB'), lang=_tesseract_lang(lang), output_type=pytesseract.Output.DICT)
    rows: dict[int, list[tuple[int, str]]] = {}
    for i, text in enumerate(data.get('text', [])):
        text = text.strip()
        if not text:
            continue
        conf = float(data['conf'][i])
        if conf < 20:
            continue
        line = int(data['line_num'][i])
        left = int(data['left'][i])
        rows.setdefault(line, []).append((left, text))
    if not rows:
        raise ValueError('لم نتعرف على بيانات جدول.')
    import csv
    with output.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        for line in sorted(rows):
            writer.writerow([text for _, text in sorted(rows[line])])


def ocr_clean_text(source: Path, output: Path, lang: str = 'ar+en'):
    from converters.utility_advanced import clean_text
    import tempfile
    with Image.open(source) as img:
        text = _ocr_text(img.convert('RGB'), lang)
    temp = output.with_suffix('.raw.txt')
    temp.write_text(text, encoding='utf-8')
    try:
        clean_text(temp, output)
    finally:
        temp.unlink(missing_ok=True)

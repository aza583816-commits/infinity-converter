import json
import re
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from config.settings import settings
from converters.ocr import _ocr_string, _tesseract_lang, ocr_available

FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
)


def _fontfile() -> str | None:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _insert_searchable_text(page, text: str, fontsize: float) -> None:
    """Never silently discard an overflowing invisible OCR text layer."""
    # MuPDF extracts unshaped Arabic runs in reverse order. Preorder only the
    # Arabic letters (never numbers) and isolate the following Latin boundary.
    arabic_letters = r'[\u0621-\u065f\u066e-\u06d3]'
    text = re.sub(arabic_letters + r'+(?: +' + arabic_letters + r'+)*',
                  lambda match: match.group(0)[::-1] + '\u200e', text)
    fontfile = _fontfile()
    kwargs = dict(fontname='OCRUnicode' if fontfile else 'helv',
                  color=(1, 1, 1), render_mode=3, overlay=True)
    if fontfile:
        kwargs['fontfile'] = fontfile
    for size in (fontsize, fontsize * .75, fontsize * .5, fontsize * .25, 1):
        if page.insert_textbox(page.rect, text, fontsize=size, **kwargs) >= 0:
            return
    raise ValueError('تعذر إدراج طبقة النص كاملة في PDF القابل للبحث.')


def _ocr_text(image: Image.Image, lang: str) -> str:
    if not ocr_available():
        raise RuntimeError('محرك OCR غير مثبت على الخادم.')
    return _ocr_string(image, lang=lang).strip()


def _ocr_data(image: Image.Image, lang: str) -> dict:
    if not ocr_available():
        raise RuntimeError('محرك OCR غير مثبت على الخادم.')
    try:
        return pytesseract.image_to_data(
            image,
            lang=_tesseract_lang(lang),
            output_type=pytesseract.Output.DICT,
            timeout=settings.ocr_timeout_seconds,
        )
    except RuntimeError as exc:
        raise RuntimeError('استغرق OCR وقتًا أطول من المسموح.') from exc


def image_to_searchable_pdf(source: Path, output: Path, lang: str = 'ar+en'):
    with Image.open(source) as opened:
        img = opened.convert('RGB')
    try:
        text = _ocr_text(img, lang)
        png = Path(output).with_suffix('.source.png')
        img.save(png, format='PNG', optimize=True)
        try:
            doc = pymupdf.open()
            try:
                page = doc.new_page(width=img.width * 72 / 96, height=img.height * 72 / 96)
                page.insert_image(page.rect, filename=str(png))
                if text:
                    _insert_searchable_text(page, text, 8)
                doc.save(str(output), garbage=4, deflate=True)
            finally:
                doc.close()
        finally:
            png.unlink(missing_ok=True)
    finally:
        img.close()


def pdf_to_searchable_pdf(source: Path, output: Path, lang: str = 'ar+en', dpi: int = 180):
    source_doc = pymupdf.open(str(source))
    result = pymupdf.open()
    try:
        if source_doc.page_count > settings.max_ocr_pages:
            raise ValueError(f'الحد الأقصى للأداة هو {settings.max_ocr_pages} صفحة.')
        zoom = dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        for page in source_doc:
            native = page.get_text('text').strip()
            if native and not page.get_images():
                # Copy the original text layer byte-for-byte rather than
                # reconstructing shaped Arabic / mixed-script glyphs.
                result.insert_pdf(source_doc, from_page=page.number, to_page=page.number)
                background = page.get_pixmap(matrix=matrix, alpha=False)
                result[-1].insert_image(result[-1].rect, pixmap=background, overlay=False)
                continue
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            try:
                # Digital PDF text is already exact; OCR is needed only when
                # the page has no selectable source text.
                text = _ocr_text(image, lang)
            finally:
                image.close()
            new_page = result.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pix)
            if text:
                _insert_searchable_text(new_page, text, 7)
        if result.page_count == 0:
            raise ValueError('ملف PDF فارغ.')
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        source_doc.close()


def image_ocr_json(source: Path, output: Path, lang: str = 'ar+en'):
    with Image.open(source) as opened:
        img = opened.convert('RGB')
    try:
        data = _ocr_data(img, lang)
    finally:
        img.close()
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
        if doc.page_count > settings.max_ocr_pages:
            raise ValueError(f'الحد الأقصى للأداة هو {settings.max_ocr_pages} صفحة.')
        pages = []
        matrix = pymupdf.Matrix(2, 2)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            try:
                text = _ocr_text(image, lang)
            finally:
                image.close()
            pages.append({'page': index, 'text': text})
        output.write_text(json.dumps({'pages': pages}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        doc.close()


def pdf_page_texts(source: Path, output_dir: Path, lang: str = 'ar+en') -> list[Path]:
    doc = pymupdf.open(str(source))
    outputs = []
    try:
        if doc.page_count > settings.max_ocr_pages:
            raise ValueError(f'الحد الأقصى للأداة هو {settings.max_ocr_pages} صفحة.')
        matrix = pymupdf.Matrix(2, 2)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            try:
                text = _ocr_text(image, lang)
            finally:
                image.close()
            out = output_dir / f'page-{index:03d}.txt'
            out.write_text(text or '(لا يوجد نص)', encoding='utf-8')
            outputs.append(out)
    finally:
        doc.close()
    return outputs


def ocr_extract_pattern(source: Path, output: Path, lang: str, pattern: str):
    with Image.open(source) as opened:
        img = opened.convert('RGB')
    try:
        text = _ocr_text(img, lang)
    finally:
        img.close()
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
    with Image.open(source) as opened:
        img = opened.convert('RGB')
    try:
        data = _ocr_data(img, lang)
    finally:
        img.close()
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
    with Image.open(source) as opened:
        img = opened.convert('RGB')
    try:
        text = _ocr_text(img, lang)
    finally:
        img.close()
    temp = output.with_suffix('.raw.txt')
    temp.write_text(text, encoding='utf-8')
    try:
        clean_text(temp, output)
    finally:
        temp.unlink(missing_ok=True)

import re
from pathlib import Path

import pymupdf
from pypdf import PdfReader, PdfWriter


def parse_pages(spec: str, page_count: int) -> list[int]:
    spec = (spec or '').strip()
    if not spec:
        return list(range(page_count))
    result: set[int] = set()
    for chunk in spec.split(','):
        match = re.fullmatch(r'(\d+)(?:-(\d+))?', chunk.strip())
        if not match:
            raise ValueError('صيغة الصفحات غير صالحة. استخدم مثل 1-3,5.')
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start or end > page_count:
            raise ValueError(f'الصفحات يجب أن تكون بين 1 و {page_count}.')
        result.update(range(start - 1, end))
    if not result:
        raise ValueError('لم يتم تحديد أي صفحة.')
    return sorted(result)


def reorder_pages(source: Path, output: Path, spec: str):
    reader = PdfReader(str(source), strict=False)
    order = parse_pages(spec, len(reader.pages))
    if len(order) != len(reader.pages):
        raise ValueError('يجب أن يتضمن ترتيب الصفحات جميع صفحات الملف مرة واحدة.')
    if len(set(order)) != len(order):
        raise ValueError('لا يمكن تكرار صفحة في الترتيب.')
    writer = PdfWriter()
    for index in order:
        writer.add_page(reader.pages[index])
    with output.open('wb') as fh:
        writer.write(fh)


def rotate_selected(source: Path, output: Path, spec: str, angle: int):
    if angle % 90 != 0:
        raise ValueError('زاوية الدوران يجب أن تكون من مضاعفات 90.')
    reader = PdfReader(str(source), strict=False)
    selected = set(parse_pages(spec, len(reader.pages)))
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index in selected:
            page.rotate(angle % 360)
        writer.add_page(page)
    with output.open('wb') as fh:
        writer.write(fh)


def add_page_numbers(source: Path, output: Path, position: str = 'bottom-center'):
    doc = pymupdf.open(str(source))
    try:
        positions = {
            'bottom-center': lambda r: (r.x0, r.y1 - 24, r.x1, r.y1 - 8),
            'bottom-right': lambda r: (r.x0, r.y1 - 24, r.x1 - 22, r.y1 - 8),
            'top-center': lambda r: (r.x0, r.y0 + 8, r.x1, r.y0 + 24),
            'top-right': lambda r: (r.x0, r.y0 + 8, r.x1 - 22, r.y0 + 24),
        }
        if position not in positions:
            raise ValueError('موضع رقم الصفحة غير صالح.')
        for number, page in enumerate(doc, start=1):
            rect = pymupdf.Rect(*positions[position](page.rect))
            page.insert_textbox(rect, str(number), fontname='helv', fontsize=9, align=pymupdf.TEXT_ALIGN_CENTER, color=(0.3, 0.3, 0.3))
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()


def _unicode_fontfile() -> str | None:
    for candidate in (
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ):
        if Path(candidate).exists():
            return candidate
    return None


def watermark_text(source: Path, output: Path, text: str, opacity: float = 0.18):
    text = (text or '').strip()
    if not text or len(text) > 120:
        raise ValueError('نص العلامة المائية مطلوب وبحد أقصى 120 حرفًا.')
    doc = pymupdf.open(str(source))
    try:
        for page in doc:
            rect = page.rect
            kwargs = dict(fontname='helv', fontsize=max(28, min(64, rect.width / 7)), align=pymupdf.TEXT_ALIGN_CENTER, color=(0.45, 0.45, 0.45), fill_opacity=opacity, overlay=True)
            fontfile = _unicode_fontfile()
            if fontfile:
                kwargs['fontfile'] = fontfile
            box = pymupdf.Rect(rect.x0 + rect.width * 0.08, rect.y0 + rect.height * 0.40, rect.x1 - rect.width * 0.08, rect.y0 + rect.height * 0.60)
            page.insert_textbox(box, text, **kwargs)
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()


def grayscale(source: Path, output: Path):
    source_doc = pymupdf.open(str(source))
    result = pymupdf.open()
    try:
        for page in source_doc:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), colorspace=pymupdf.csGRAY, alpha=False)
            new_page = result.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pix)
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        source_doc.close()


def remove_blank_pages(source: Path, output: Path, threshold: int = 30):
    src = pymupdf.open(str(source))
    result = pymupdf.open()
    kept = 0
    try:
        for page in src:
            text = page.get_text('text').strip()
            if text:
                result.insert_pdf(src, from_page=page.number, to_page=page.number)
                kept += 1
                continue
            pix = page.get_pixmap(matrix=pymupdf.Matrix(0.6, 0.6), colorspace=pymupdf.csGRAY, alpha=False)
            samples = pix.samples
            avg_dark = sum(255 - value for value in samples) / max(1, len(samples))
            if avg_dark > threshold:
                result.insert_pdf(src, from_page=page.number, to_page=page.number)
                kept += 1
        if kept == 0:
            raise ValueError('لم نجد صفحات تحتوي على محتوى.')
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        src.close()


def crop_margins(source: Path, output: Path, margin: float):
    try:
        margin = float(margin)
    except ValueError:
        raise ValueError('الهامش يجب أن يكون رقمًا.')
    if margin < 0 or margin > 200:
        raise ValueError('الهامش يجب أن يكون بين 0 و200 نقطة.')
    doc = pymupdf.open(str(source))
    try:
        for page in doc:
            r = page.rect
            if r.width <= 2 * margin or r.height <= 2 * margin:
                raise ValueError('الهامش كبير جدًا بالنسبة إلى حجم الصفحة.')
            page.set_cropbox(pymupdf.Rect(r.x0 + margin, r.y0 + margin, r.x1 - margin, r.y1 - margin))
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()


def poster_tile(source: Path, output: Path, columns: int = 2, rows: int = 2):
    if columns not in {2, 3, 4} or rows not in {2, 3, 4}:
        raise ValueError('اختر شبكة بين 2×2 و4×4.')
    src = pymupdf.open(str(source))
    result = pymupdf.open()
    try:
        for original in src:
            page_w, page_h = original.rect.width, original.rect.height
            tile_w, tile_h = page_w / columns, page_h / rows
            for row in range(rows):
                for col in range(columns):
                    tile = result.new_page(width=tile_w, height=tile_h)
                    rect = pymupdf.Rect(-col * tile_w, -row * tile_h, (columns - col) * tile_w, (rows - row) * tile_h)
                    tile.show_pdf_page(tile.rect, src, original.number, clip=pymupdf.Rect(col * tile_w, row * tile_h, (col + 1) * tile_w, (row + 1) * tile_h))
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        src.close()


def contact_sheet(source: Path, output: Path, columns: int = 2):
    if columns not in {2, 3, 4}:
        raise ValueError('عدد الأعمدة يجب أن يكون 2 أو 3 أو 4.')
    doc = pymupdf.open(str(source))
    result = pymupdf.open()
    try:
        thumb_w, thumb_h = 180, 240
        rows = (doc.page_count + columns - 1) // columns
        page = result.new_page(width=columns * thumb_w, height=rows * thumb_h)
        for i, source_page in enumerate(doc):
            col = i % columns
            row = i // columns
            slot = pymupdf.Rect(col * thumb_w + 8, row * thumb_h + 8, (col + 1) * thumb_w - 8, (row + 1) * thumb_h - 8)
            page.show_pdf_page(slot, doc, source_page.number, keep_proportion=True)
            page.insert_text((slot.x0, slot.y1 - 8), str(source_page.number + 1), fontname='helv', fontsize=8, color=(0.2, 0.2, 0.2))
        result.save(str(output), garbage=4, deflate=True)
    finally:
        result.close()
        doc.close()


def password_protect(source: Path, output: Path, password: str):
    password = (password or '').strip()
    if len(password) < 6 or len(password) > 128:
        raise ValueError('كلمة المرور يجب أن تكون بين 6 و128 حرفًا.')
    reader = PdfReader(str(source), strict=False)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    with output.open('wb') as fh:
        writer.write(fh)

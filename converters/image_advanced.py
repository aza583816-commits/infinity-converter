import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _save_like(img: Image.Image, output: Path, source_format: str | None = None):
    # The requested output extension always wins. This prevents a JPEG source
    # from accidentally being written as JPEG bytes under a .png filename.
    ext = output.suffix.lower()
    fmt = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP', '.png': 'PNG'}.get(
        ext, (source_format or img.format or 'PNG').upper()
    )
    if fmt in {'JPEG', 'JPG'}:
        if img.mode not in {'RGB', 'L'}:
            img = ImageOps.exif_transpose(img).convert('RGB')
        img.save(output, format='JPEG', quality=92, optimize=True, progressive=True)
    elif fmt == 'WEBP':
        if img.mode not in {'RGB', 'RGBA', 'L'}:
            img = img.convert('RGBA')
        img.save(output, format='WEBP', quality=90, method=6)
    else:
        img.save(output, format='PNG', optimize=True)


def crop(source: Path, output: Path, spec: str):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        if not (spec or '').strip():
            _save_like(img.copy(), output, img.format)
            return
        parts = [int(x.strip()) for x in spec.split(',')]
        if len(parts) != 4:
            raise ValueError('اكتب القص بصيغة left,top,right,bottom.')
        l, t, r, b = parts
        if not (0 <= l < r <= img.width and 0 <= t < b <= img.height):
            raise ValueError('إحداثيات القص خارج حدود الصورة.')
        _save_like(img.crop((l, t, r, b)), output, img.format)


def flip(source: Path, output: Path, direction: str):
    if direction not in {'horizontal', 'vertical'}:
        raise ValueError('اتجاه القلب غير صالح.')
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        out = ImageOps.mirror(img) if direction == 'horizontal' else ImageOps.flip(img)
        _save_like(out, output, img.format)


def grayscale(source: Path, output: Path):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        out = ImageOps.grayscale(img)
        _save_like(out, output, 'PNG' if output.suffix.lower() == '.png' else 'JPEG')


def sharpen(source: Path, output: Path, strength: str):
    level = int(strength or '2')
    if level not in {1, 2, 3}:
        raise ValueError('اختر حدة من 1 إلى 3.')
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        out = img.filter(ImageFilter.UnsharpMask(radius=1 + level, percent=90 + level * 45, threshold=3))
        _save_like(out, output, img.format)


def auto_contrast(source: Path, output: Path):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        out = ImageOps.autocontrast(img.convert('RGB'))
        _save_like(out, output, 'JPEG')


def sepia(source: Path, output: Path):
    with Image.open(source) as img:
        gray = ImageOps.grayscale(ImageOps.exif_transpose(img))
        out = ImageOps.colorize(gray, black='#24160f', white='#f4d9aa')
        out.save(output, format='JPEG', quality=92, optimize=True)


def strip_metadata(source: Path, output: Path):
    with Image.open(source) as img:
        data = list(img.getdata())
        clean = Image.new(img.mode, img.size)
        clean.putdata(data)
        _save_like(clean, output, img.format)


def favicon_pack(source: Path, output: Path):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img).convert('RGBA')
        with ZipFile(output, 'w', ZIP_DEFLATED) as zf:
            for size in (16, 32, 48, 180, 192, 512):
                canvas = ImageOps.contain(img, (size, size), Image.LANCZOS)
                square = Image.new('RGBA', (size, size), (255, 255, 255, 0))
                square.alpha_composite(canvas, ((size - canvas.width) // 2, (size - canvas.height) // 2))
                target = Path(source.stem + f'-{size}.png')
                import io
                buf = io.BytesIO()
                square.save(buf, format='PNG', optimize=True)
                zf.writestr(target.name, buf.getvalue())
            ico = io.BytesIO()
            img.save(ico, format='ICO', sizes=[(16,16), (32,32), (48,48)])
            zf.writestr('favicon.ico', ico.getvalue())


def contact_sheet(source: Path, output: Path, background: str = 'white'):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img).convert('RGB')
        thumb = ImageOps.contain(img, (600, 450), Image.LANCZOS)
        canvas = Image.new('RGB', (640, 490), background)
        canvas.paste(thumb, ((640-thumb.width)//2, 20 + (450-thumb.height)//2))
        canvas.save(output, format='JPEG', quality=92, optimize=True)


def set_dpi(source: Path, output: Path, dpi: str):
    value = int(dpi or '144')
    if value < 36 or value > 1200:
        raise ValueError('الدقة يجب أن تكون بين 36 و1200 DPI.')
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        fmt = 'PNG' if output.suffix.lower() == '.png' else 'JPEG'
        if fmt == 'JPEG':
            img = img.convert('RGB')
        if fmt == 'JPEG':
            img.save(output, format=fmt, dpi=(value, value), quality=92, optimize=True)
        else:
            img.save(output, format=fmt, dpi=(value, value), optimize=True)


def color_palette(source: Path, output: Path, count: str = '6'):
    n = int(count or '6')
    if n < 2 or n > 12:
        raise ValueError('عدد الألوان يجب أن يكون بين 2 و12.')
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img).convert('RGB').resize((160, 160))
        quant = img.quantize(colors=n)
        palette = quant.getpalette()
        colors = []
        for pixel_count, palette_index in quant.getcolors():
            rgb = tuple(palette[palette_index * 3:palette_index * 3 + 3])
            colors.append({'hex': '#%02X%02X%02X' % rgb, 'pixels': pixel_count})
        colors.sort(key=lambda item: item['pixels'], reverse=True)
        output.write_text(json.dumps({'colors': colors}, ensure_ascii=False, indent=2), encoding='utf-8')

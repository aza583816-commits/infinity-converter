from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, "white")
        alpha = img.convert("RGBA")
        background.paste(alpha, mask=alpha.getchannel("A"))
        return background
    return img.convert("RGB")




def _save_for_output(img: Image.Image, output: Path, *, quality: int = 92) -> None:
    """Encode using the requested output extension, never the source format.

    This keeps the backend artifact, Content-Type and public Tool contract in
    sync for transforms such as resize/compress/rotate.
    """
    suffix = output.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        flattened = _flatten_to_rgb(img)
        flattened.save(output, format="JPEG", quality=max(10, min(quality, 95)), optimize=True, progressive=True)
    elif suffix == ".webp":
        img.save(output, format="WEBP", quality=max(10, min(quality, 95)), method=6)
    elif suffix == ".png":
        img.save(output, format="PNG", optimize=True)
    else:
        raise ValueError("امتداد الصورة الناتجة غير مدعوم.")


def convert_image(source: Path, output: Path, fmt: str):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        if fmt == "JPEG":
            img = _flatten_to_rgb(img)
            img.save(output, format="JPEG", quality=92, optimize=True, progressive=True)
        elif fmt == "WEBP":
            img.save(output, format="WEBP", quality=90, method=6)
        else:
            img.save(output, format="PNG", optimize=True)


def resize_image(source: Path, output: Path, max_dimension: int):
    if max_dimension < 16 or max_dimension > 8000:
        raise ValueError("أبعاد الصورة المطلوبة غير منطقية.")
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
        _save_for_output(img, output, quality=92)


def compress_image(source: Path, output: Path, quality: int = 70):
    quality = max(10, min(quality, 95))
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        _save_for_output(img, output, quality=quality)


def rotate_image(source: Path, output: Path, angle: int):
    if angle % 90 != 0:
        raise ValueError("زاوية الدوران يجب أن تكون من مضاعفات 90.")
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        rotated = img.rotate(-angle, expand=True)
        _save_for_output(rotated, output, quality=92)

def resize_for_social(source: Path, output: Path, preset: str, fit: str):
    dimensions = {"instagram-post": (1080, 1080), "instagram-story": (1080, 1920), "linkedin": (1200, 627), "x": (1600, 900)}
    if preset not in dimensions or fit not in {"crop", "pad"}:
        raise ValueError("خيار مقاس الصورة غير صالح.")
    with Image.open(source) as img:
        image = ImageOps.exif_transpose(img).convert("RGBA")
        size = dimensions[preset]
        if fit == "crop":
            rendered = ImageOps.fit(image, size, Image.LANCZOS, centering=(0.5, 0.5))
        else:
            rendered = Image.new("RGBA", size, "white")
            contained = ImageOps.contain(image, size, Image.LANCZOS)
            rendered.alpha_composite(contained, ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2))
        rendered.convert("RGB").save(output, format="PNG", optimize=True)


def quote_social_graphic(output: Path, quote: str, author: str, preset: str, theme: str):
    if preset not in {"square", "portrait"} or theme not in {"ink", "paper", "ocean"}:
        raise ValueError("خيار تصميم الصورة غير صالح.")
    quote = (quote or "").strip()
    author = (author or "").strip()
    if not quote or len(quote) > 600 or len(author) > 100 or any(ord(char) > 127 for char in quote + author):
        raise ValueError("الاقتباس واسم صاحبه يجب أن يكونا نصًا إنجليزيًا قصيرًا.")
    size = (1080, 1080) if preset == "square" else (1080, 1350)
    palettes = {"ink": ("#14213d", "#f8f7f2"), "paper": ("#f3ead7", "#2e4057"), "ocean": ("#0b6e69", "#f7f4e9")}
    background, foreground = palettes[theme]
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=42)
    author_font = ImageFont.load_default(size=26)
    max_width = size[0] - 160
    words, lines, current = quote.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if not current:
                raise ValueError("توجد كلمة طويلة جدًا في الاقتباس.")
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    line_height = 58
    top = (size[1] - len(lines) * line_height) // 2 - 25
    for line in lines:
        width = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((size[0] - width) // 2, top), line, font=font, fill=foreground)
        top += line_height
    if author:
        label = f"- {author}"
        width = draw.textbbox((0, 0), label, font=author_font)[2]
        draw.text(((size[0] - width) // 2, min(size[1] - 115, top + 38)), label, font=author_font, fill=foreground)
    image.save(output, format="PNG", optimize=True)


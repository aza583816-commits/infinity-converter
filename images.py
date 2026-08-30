from pathlib import Path
from PIL import Image, ImageOps


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, "white")
        alpha = img.convert("RGBA")
        background.paste(alpha, mask=alpha.getchannel("A"))
        return background
    return img.convert("RGB")


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
        fmt = (img.format or "PNG").upper()
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
        if fmt in ("JPEG", "JPG"):
            img = _flatten_to_rgb(img)
            img.save(output, format="JPEG", quality=92, optimize=True, progressive=True)
        elif fmt == "WEBP":
            img.save(output, format="WEBP", quality=90, method=6)
        else:
            img.save(output, format="PNG", optimize=True)


def compress_image(source: Path, output: Path, quality: int = 70):
    quality = max(10, min(quality, 95))
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        fmt = (img.format or "JPEG").upper()
        if fmt == "PNG":
            img.save(output, format="PNG", optimize=True)
        elif fmt == "WEBP":
            img.save(output, format="WEBP", quality=quality, method=6)
        else:
            img = _flatten_to_rgb(img)
            img.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)


def rotate_image(source: Path, output: Path, angle: int):
    if angle % 90 != 0:
        raise ValueError("زاوية الدوران يجب أن تكون من مضاعفات 90.")
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        fmt = (img.format or "PNG").upper()
        rotated = img.rotate(-angle, expand=True)
        if fmt in ("JPEG", "JPG"):
            rotated = _flatten_to_rgb(rotated)
            rotated.save(output, format="JPEG", quality=92, optimize=True)
        elif fmt == "WEBP":
            rotated.save(output, format="WEBP", quality=90, method=6)
        else:
            rotated.save(output, format="PNG", optimize=True)


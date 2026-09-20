"""Source-aware image output fidelity across transparency and EXIF rotation.

All cases run against the same conversion functions used by registered tools.
Check actual encoded pixels, not just the file's declared extension.
"""
from pathlib import Path

from PIL import Image, ImageOps

from converters.images import convert_image


def test_png_to_jpeg_flattens_transparency_on_white_not_black(tmp_path: Path):
    source = tmp_path / "transparent.png"
    out = tmp_path / "converted.jpg"
    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    for x in range(20, 108):
        for y in range(20, 108):
            image.putpixel((x, y), (250, 22, 22, 255))
    image.save(source)
    convert_image(source, out, "JPEG")
    with Image.open(out) as actual:
        assert actual.format == "JPEG" and actual.size == image.size
        white = actual.convert("RGB").getpixel((5, 5))
        red = actual.convert("RGB").getpixel((64, 64))
        assert all(channel > 245 for channel in white), white
        assert red[0] > 220 and red[1] < 50 and red[2] < 50, red


def test_image_to_png_preserves_all_rgba_pixel_values(tmp_path: Path):
    source = tmp_path / "alpha.png"
    out = tmp_path / "converted.png"
    image = Image.new("RGBA", (40, 24))
    for y in range(image.height):
        for x in range(image.width):
            image.putpixel((x, y), ((x * 3) % 256, (y * 7) % 256, 91, (x * y) % 256))
    image.save(source)
    convert_image(source, out, "PNG")
    with Image.open(out) as actual:
        assert actual.format == "PNG"
        assert actual.mode == "RGBA"
        assert actual.size == image.size
        assert list(actual.getdata()) == list(image.getdata())


def test_jpeg_exif_orientation_is_applied_before_png_conversion(tmp_path: Path):
    source = tmp_path / "rotated.jpg"
    out = tmp_path / "oriented.png"
    image = Image.new("RGB", (90, 60), "white")
    for x in range(0, 45):
        for y in range(0, 60):
            image.putpixel((x, y), (200, 20, 20))
    exif = image.getexif()
    exif[274] = 6
    image.save(source, "JPEG", quality=98, exif=exif.tobytes())
    with Image.open(source) as original:
        expected = ImageOps.exif_transpose(original)
        expected_pixels = list(expected.getdata())
        expected_size = expected.size
    convert_image(source, out, "PNG")
    with Image.open(out) as actual:
        assert actual.format == "PNG" and actual.size == expected_size == (60, 90)
        assert list(actual.getdata()) == expected_pixels
        assert actual.getexif().get(274, 1) == 1

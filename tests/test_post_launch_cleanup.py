from pathlib import Path

from PIL import Image

from converters.image_advanced import strip_metadata


def test_strip_metadata_preserves_pixels_and_size(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "clean.png"
    img = Image.new("RGB", (3, 2), (12, 34, 56))
    img.save(source, format="PNG", pnginfo=None)

    strip_metadata(source, output)

    with Image.open(output) as cleaned:
        assert cleaned.size == (3, 2)
        assert cleaned.mode == "RGB"
        pixels = [cleaned.getpixel((x, y)) for y in range(cleaned.height) for x in range(cleaned.width)]
        assert pixels == [(12, 34, 56)] * 6

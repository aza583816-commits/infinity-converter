"""Focused content, geometry and security oracles for PDF and visual tools."""
from __future__ import annotations
import csv
import difflib
import html
import io
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
import pytesseract


ORACLE_IDS = frozenset({
    "pdf-to-html", "assignment-cover-page", "omr-bubble-sheet",
    "pdf-to-markdown", "pdf-compare", "pdf-annotations-report",
    "quote-social-graphic", "image-sharpen", "image-auto-contrast",
    "image-sepia", "image-blur", "image-pixelate", "image-posterize",
    "image-color-palette", "image-watermark", "image-background-cleaner",
    "image-auto-orient", "image-round-corners",
})


def _error(a: Image.Image, b: Image.Image) -> float:
    assert a.size == b.size
    return max(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean)


def oracle(tool_id: str, source: Path | None, output: Path, fixture: Path) -> str | None:
    if tool_id not in ORACLE_IDS:
        return None
    if tool_id == "pdf-to-html":
        assert source is not None
        from html.parser import HTMLParser
        class TextCollector(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.fragments = []
            def handle_data(self, value):
                if value.strip(): self.fragments.append(value)
        result = output.read_text(encoding="utf-8")
        parser = TextCollector()
        parser.feed(result)
        visible = " ".join(" ".join(parser.fragments).split())
        with pymupdf.open(source) as doc:
            for page in doc:
                for line in page.get_text("text").splitlines():
                    if line.strip():
                        assert " ".join(line.split()) in visible, (line, visible[:600])
            assert result.lower().count("<div") >= len(doc)
        return "every source PDF page's text survives inside independently parsed HTML markup"
    if tool_id == "assignment-cover-page":
        assert source is None
        with pymupdf.open(output) as pdf:
            assert len(pdf) == 1
            text = pdf[0].get_text()
            assert all(k in text for k in ("ASSIGNMENT COVER PAGE", "Engineering", "Safety Report", "Student"))
        return "requested course, assignment and student appear on one PDF cover page"
    if tool_id == "omr-bubble-sheet":
        assert source is None
        with pymupdf.open(output) as pdf:
            assert len(pdf) == 1
            page = pdf[0]
            words = page.get_text("words")
            numbers = {int(w[4]) for w in words if w[4].isdigit() and 1 <= int(w[4]) <= 50}
            assert numbers == set(range(1, 51))
            assert len([w for w in words if w[4] in {"A", "B", "C", "D"}]) >= 200
            assert len(page.get_drawings()) >= 200
        return "50 numbered questions and four drawn answer choices per question"
    if tool_id == "pdf-to-markdown":
        assert source is not None
        markdown = output.read_text(encoding="utf-8")
        with pymupdf.open(source) as doc:
            for i, page in enumerate(doc, 1):
                assert f"## Page {i}" in markdown
                section = markdown.split(f"## Page {i}", 1)[1].split("## Page", 1)[0]
                assert page.get_text("text").strip() in section, (i, page.get_text("text"), section)
        return "each PDF page's original textual marker survives in correct Markdown section"
    if tool_id == "pdf-compare":
        assert source is not None
        with pymupdf.open(source) as doc:
            assert len(doc) >= 3 and all(p.get_text("text").strip() for p in doc)
        assert output.read_text(encoding="utf-8") == "No differences found. The PDF texts are identical.\n"
        return "two identical PDF texts correctly yield no additions or deletions"
    if tool_id == "pdf-annotations-report":
        assert source is not None
        data = json.loads(output.read_text(encoding="utf-8"))
        with pymupdf.open(source) as pdf:
            expected = [(i + 1, a.info.get("title"), a.info.get("content"))
                        for i, page in enumerate(pdf)
                        for a in (list(page.annots() or []))]
        actual = [(a["page"], a["name"], a["content"]) for a in data["annotations"]]
        assert expected and actual == expected
        assert any("QUALITY ANNOTATION" in (a[2] or "") for a in actual)
        return "annotated PDF's real page, author and comment recovered exactly"
    if tool_id == "quote-social-graphic":
        assert source is None
        with Image.open(output) as image:
            assert image.format == "PNG" and image.size == (1080, 1080)
            assert len(set(image.getdata())) > 3
            recognized = pytesseract.image_to_string(image.convert("RGB"), lang="eng")
            assert "Quality" in recognized and "verification" in recognized.lower(), recognized
        return "requested quote is visibly rendered and read back independently by OCR"
    assert source is not None
    if tool_id == "image-color-palette":
        report = json.loads(output.read_text(encoding="utf-8"))
        colors = report["colors"]
        with Image.open(source) as original:
            assert colors and len(colors) <= 8
            assert sum(row["pixels"] for row in colors) == original.width * original.height
            assert all(row["hex"] == "#%02x%02x%02x" % tuple(row["rgb"]) for row in colors)
        return "palette frequencies total source pixels and each reported RGB maps to its hex code"
    with Image.open(source) as opened, Image.open(output) as result:
        original = ImageOps.exif_transpose(opened).convert("RGB")
        if tool_id == "image-sharpen":
            expected = original.filter(ImageFilter.UnsharpMask(radius=3, percent=180, threshold=3))
            assert result.size == original.size and _error(expected, result) <= 1.1
            return "independent unsharp-mask reference matches actual sharpened pixels"
        if tool_id == "image-auto-contrast":
            expected = ImageOps.autocontrast(original)
            assert result.size == original.size and _error(expected, result) <= 8
            return "source histogram autocontrast matches independently rendered JPEG within encoding tolerance"
        if tool_id == "image-sepia":
            assert result.size == original.size
            for x, y in ((0, 0), (original.width // 2, original.height // 2)):
                red, green, blue = result.convert("RGB").getpixel((x, y))
                assert red > green > blue
            assert _error(original, result) > 5
            return "original geometry retained and sampled colors truly transformed into warm sepia"
        if tool_id == "image-blur":
            expected = original.filter(ImageFilter.GaussianBlur(3))
            assert result.size == original.size and _error(expected, result) <= 1
            assert _error(original, result) > 0
            return "Gaussian-blurred pixels match independent radius-three reference and differ from source"
        if tool_id == "image-pixelate":
            down = original.resize((max(1, original.width // 32), max(1, original.height // 32)), Image.Resampling.BILINEAR)
            expected = down.resize(original.size, Image.Resampling.NEAREST)
            assert result.size == original.size and _error(expected, result) <= 1
            return "nearest-neighbor pixel mosaic independently reconstructed from original source"
        if tool_id == "image-posterize":
            after = result.convert("RGB")
            assert after.size == original.size
            assert all(channel % 16 == 0 for x, y in [(0, 0), (100, 100), (300, 300)]
                       for channel in after.getpixel((x, y)))
            assert _error(original, after) > 0
            return "four-bit channel quantization actually changes source colors at known points"
        if tool_id == "image-color-palette":
            raise AssertionError("palette report must be handled without decoding it as an image")
        if tool_id == "image-watermark":
            assert result.size == original.size
            diff = ImageChops.difference(original, result.convert("RGB"))
            assert diff.getbbox() is not None
            assert diff.crop((original.width // 2, original.height // 2, *original.size)).getbbox() is not None
            return "watermark visibly modifies lower-right source pixels without changing dimensions"
        if tool_id == "image-background-cleaner":
            rgba = result.convert("RGBA")
            assert rgba.size == original.size
            assert rgba.getpixel((0, 0))[3] == 0
            assert rgba.getchannel("A").getextrema() == (0, 255)
            return "white background actually transparent while foreground opacity survives"
        if tool_id == "image-auto-orient":
            expected = ImageOps.exif_transpose(opened)
            assert result.size == expected.size
            assert _error(expected, result) <= 3
            assert result.getexif().get(274, 1) == 1
            return "EXIF rotation applied to decoded pixels and orientation flag cleared"
        if tool_id == "image-round-corners":
            assert result.size == original.size
            rgba = result.convert("RGBA")
            assert all(rgba.getpixel(c)[3] == 0 for c in [(0,0),(0,rgba.height-1),(rgba.width-1,0),(rgba.width-1,rgba.height-1)])
            assert rgba.getpixel((rgba.width // 2, rgba.height // 2))[3] == 255
            return "four corners transparent, original central subject opaque and geometry unchanged"
    raise AssertionError("Registered tool has no matching independent visual oracle")

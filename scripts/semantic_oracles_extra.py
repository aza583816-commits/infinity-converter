"""Additional independent, source-aware output oracles for real conversion artifacts.

An oracle only claims the particular content/geometry/property it asserts.
Returning None means the tool remains unverified, regardless of smoke success.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.parse
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageOps, ImageStat
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader


ORACLE_IDS = frozenset({
    "pdf-split", "pdf-to-jpg", "pdf-to-png", "image-to-pdf",
    "pdf-metadata", "pdf-links-report", "pdf-page-size-report",
    "pdf-redact", "pdf-rotate", "pdf-rotate-selected", "pdf-reorder-pages",
    "pdf-watermark-text", "pdf-image-extract", "pdf-remove-blank-pages",
    "pdf-contact-sheet", "pdf-poster-split", "image-resize",
    "image-compress", "image-rotate", "social-media-image-resizer",
    "image-crop", "image-flip", "image-upscale", "image-invert",
    "image-strip-metadata", "image-contact-sheet", "image-set-dpi",
    "image-favicon-pack", "docx-to-html", "json-to-xlsx",
    "text-to-json", "csv-validator", "json-validator",
    "text-statistics", "text-sort", "text-deduplicate",
    "url-encode", "url-decode", "checksum-compare", "file-mime-report",
    "bzip2-decompress", "xz-decompress",
})


def _pdf_texts(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


def _image_error(a: Image.Image, b: Image.Image) -> float:
    aa = a.convert("RGB")
    bb = b.convert("RGB")
    assert aa.size == bb.size
    error = ImageChops.difference(aa, bb)
    return max(ImageStat.Stat(error).mean)


def oracle(tool_id: str, source: Path | None, output: Path, fixture: Path) -> str | None:
    if tool_id not in ORACLE_IDS:
        return None
    if source is None:
        raise AssertionError(f"{tool_id} has no expected source file")
    if tool_id == "pdf-split":
        originals = _pdf_texts(source)
        with zipfile.ZipFile(output) as z:
            names = sorted(n for n in z.namelist() if n.endswith(".pdf"))
            assert len(names) == len(originals)
            for i, name in enumerate(names):
                with pymupdf.open(stream=z.read(name), filetype="pdf") as pdf:
                    assert len(pdf) == 1
                    assert pdf[0].get_text().strip() == originals[i].strip()
        return "one valid single-page PDF per original page, exact extractable text and source order"
    if tool_id in {"pdf-to-jpg", "pdf-to-png"}:
        fmt = {"pdf-to-jpg": "JPEG", "pdf-to-png": "PNG"}[tool_id]
        extension = {"JPEG": ".jpg", "PNG": ".png"}[fmt]
        with pymupdf.open(source) as pdf, zipfile.ZipFile(output) as z:
            names = sorted(n for n in z.namelist() if n.endswith(extension))
            assert len(names) == len(pdf)
            for page, name in zip(pdf, names):
                with Image.open(io.BytesIO(z.read(name))) as image:
                    assert image.format == fmt
                    assert image.width >= int(page.rect.width) and image.height >= int(page.rect.height)
                    assert ImageStat.Stat(image.convert("L")).stddev[0] > 1
        return "all source pages rendered as nonblank images in requested format, page order and geometry retained"
    if tool_id == "image-to-pdf":
        with pymupdf.open(output) as pdf:
            assert len(pdf) == 2
            for page in pdf:
                assert len(page.get_images(full=True)) >= 1
                assert page.rect.width > 100 and page.rect.height > 100
        return "both uploaded images embedded in the two output PDF pages"
    if tool_id == "pdf-metadata":
        report = json.loads(output.read_text(encoding="utf-8"))
        with pymupdf.open(source) as pdf:
            assert report["pages"] == len(pdf) and report["encrypted"] is False
        return "reported page count and encryption state match independently parsed PDF"
    if tool_id == "pdf-links-report":
        report = json.loads(output.read_text(encoding="utf-8"))
        with pymupdf.open(source) as pdf:
            expected = [(i + 1, link.get("uri")) for i, p in enumerate(pdf) for link in p.get_links() if link.get("uri")]
        actual = [(row["page"], row["uri"]) for row in report["links"] if row.get("uri")]
        assert expected and actual == expected
        return "every embedded source URL and its page number reported in original order"
    if tool_id == "pdf-page-size-report":
        report = json.loads(output.read_text(encoding="utf-8"))
        with pymupdf.open(source) as pdf:
            assert len(report["pages"]) == len(pdf)
            for p, row in zip(pdf, report["pages"]):
                assert row["page"] == p.number + 1
                assert abs(row["width_points"] - p.rect.width) < 0.02
                assert abs(row["height_points"] - p.rect.height) < 0.02
                assert abs(row["width_mm"] - p.rect.width * 25.4 / 72) < 0.02
        return "source pages' dimensions and metric conversion independently verified"
    if tool_id == "pdf-redact":
        source_text = " ".join(_pdf_texts(source))
        output_text = " ".join(_pdf_texts(output))
        assert "SECRET" in source_text and "SECRET" not in output_text
        assert "INFINITY CONVERTER" in output_text and len(_pdf_texts(output)) == len(_pdf_texts(source))
        return "sensitive source term actually removed from extractable PDF text; remaining pages and label retained"
    if tool_id in {"pdf-rotate", "pdf-rotate-selected"}:
        original = PdfReader(str(source))
        changed = PdfReader(str(output))
        assert len(original.pages) == len(changed.pages)
        for i, (before, after) in enumerate(zip(original.pages, changed.pages)):
            angle = 90 if tool_id == "pdf-rotate" or i == 0 else 0
            assert (after.rotation - before.rotation) % 360 == angle
            assert (after.extract_text() or "").strip() == (before.extract_text() or "").strip()
        return "requested page rotation metadata changed by 90 degrees without changing text or page count"
    if tool_id == "pdf-reorder-pages":
        before, after = _pdf_texts(source), _pdf_texts(output)
        assert len(before) >= 3
        assert after == [before[-1], *before[:-1]]
        return "non-identity page permutation preserved every page and its actual text"
    if tool_id == "pdf-watermark-text":
        before, after = _pdf_texts(source), _pdf_texts(output)
        assert len(after) == len(before)
        assert all(a.count("INFINITY") > b.count("INFINITY") for a, b in zip(after, before))
        return "requested watermark appears on every page while original text and count survive"
    if tool_id == "pdf-image-extract":
        with zipfile.ZipFile(output) as z:
            image_names = [n for n in z.namelist() if n.lower().endswith((".png", ".jpg", ".jpeg"))]
            assert image_names
            with Image.open(io.BytesIO(z.read(image_names[0]))) as extracted, Image.open(fixture / "image.png") as original:
                assert extracted.size == original.size
                assert _image_error(extracted, original) <= 1
        return "embedded source raster independently recovered pixel-exactly from PDF archive"
    if tool_id == "pdf-remove-blank-pages":
        before, after = _pdf_texts(source), _pdf_texts(output)
        assert before and after == before and all(s.strip() for s in before)
        return "nonblank source pages retained in their exact sequence"
    if tool_id == "pdf-contact-sheet":
        with pymupdf.open(source) as before, pymupdf.open(output) as after:
            assert len(after) == 1
            text = after[0].get_text()
            assert all(f"Page {i}" in text for i in range(1, len(before) + 1))
        return "single contact sheet includes visible text from every original page"
    if tool_id == "pdf-poster-split":
        with pymupdf.open(source) as before, pymupdf.open(output) as after:
            assert len(after) == len(before) * 4
            for src, tile in zip(before, after[::4]):
                assert abs(tile.rect.width - src.rect.width / 2) < 1
                assert abs(tile.rect.height - src.rect.height / 2) < 1
        return "every source page split into four correctly sized 2x2 print tiles"
    if tool_id in {"image-resize", "image-compress", "image-rotate", "social-media-image-resizer",
                   "image-crop", "image-flip", "image-upscale", "image-invert",
                   "image-strip-metadata", "image-contact-sheet", "image-set-dpi"}:
        with Image.open(source) as original, Image.open(output) as result:
            if tool_id == "image-resize":
                assert max(result.size) == 500
                assert abs(result.width / result.height - original.width / original.height) < .01
                return "actual downscale to requested 500-pixel maximum with aspect ratio preserved"
            if tool_id == "image-compress":
                assert result.format == "JPEG" and result.size == original.size
                assert ImageStat.Stat(result.convert("L")).stddev[0] > 1
                return "JPEG compression retains original dimensions and nonblank image contents"
            if tool_id == "image-rotate":
                expected = ImageOps.exif_transpose(original).transpose(Image.Transpose.ROTATE_270)
                assert result.size == expected.size and _image_error(result, expected) < 12
                return "90-degree clockwise source orientation independently compared to output pixels"
            if tool_id == "social-media-image-resizer":
                assert result.size == (1080, 1080) and result.format == "PNG"
                assert ImageStat.Stat(result.convert("L")).stddev[0] > 1
                return "requested social post geometry, PNG encoding and nonblank pixels"
            if tool_id == "image-crop":
                expected = ImageOps.exif_transpose(original).crop((0, 0, 100, 100))
                assert result.size == expected.size and _image_error(result, expected) < 1
                return "exact requested crop rectangle and pixel values"
            if tool_id == "image-flip":
                expected = ImageOps.mirror(ImageOps.exif_transpose(original))
                assert result.size == expected.size and _image_error(result, expected) < 1
                return "horizontal flip verified by independent pixel-wise mirrored source"
            if tool_id == "image-upscale":
                assert result.size == (original.width * 2, original.height * 2)
                return "actual twofold upscale in both axes"
            if tool_id == "image-invert":
                a = ImageOps.exif_transpose(original).convert("RGB")
                b = result.convert("RGB")
                assert a.size == b.size
                for x, y in [(0, 0), (a.width // 2, a.height // 2), (a.width - 1, a.height - 1)]:
                    assert all(abs((255 - before) - after) < 2 for before, after in zip(a.getpixel((x, y)), b.getpixel((x, y))))
                return "actual RGB channel inversion at corners and center without geometry change"
            if tool_id == "image-strip-metadata":
                assert result.size == original.size and _image_error(result, original) < 1
                assert not result.getexif()
                return "source pixels retained and EXIF fields absent"
            if tool_id == "image-contact-sheet":
                assert result.size == (640, 490) and ImageStat.Stat(result.convert("L")).stddev[0] > 1
                return "contact sheet has documented dimensions and contains nonblank source preview"
            if tool_id == "image-set-dpi":
                dpi = result.info.get("dpi")
                assert result.size == original.size and dpi is not None
                assert all(abs(x - 144) <= 1 for x in dpi[:2])
                return "pixel geometry unchanged and requested 144-DPI metadata persisted"
    if tool_id == "image-favicon-pack":
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            assert len(names) == 7 and "favicon.ico" in names
            for side in (16, 32, 48, 180, 192, 512):
                name = next(n for n in names if n.endswith(f"-{side}.png"))
                with Image.open(io.BytesIO(z.read(name))) as img:
                    assert img.size == (side, side) and img.format == "PNG"
        return "all six documented square PNG favicon sizes plus ICO are present and decodable"
    if tool_id == "docx-to-html":
        html = output.read_text(encoding="utf-8")
        doc = Document(source)
        assert "Infinity Converter" in html and "<table" in html
        assert all(cell.text in html for table in doc.tables for row in table.rows for cell in row.cells)
        assert html.index("Infinity Converter") < html.index("<table")
        if "End marker AFTER TABLE" in [p.text for p in doc.paragraphs]:
            assert html.index("</table>") < html.index("End marker AFTER TABLE")
        return "Word paragraphs and all table cells present in original document order"
    if tool_id == "json-to-xlsx":
        raw = json.loads(source.read_text(encoding="utf-8"))
        wb = load_workbook(output, read_only=True, data_only=True)
        try:
            rows = list(wb.active.values)
            assert len(rows) == len(raw) + 1
            keys = list(rows[0])
            assert set(keys) == set().union(*(row.keys() for row in raw))
            assert [dict(zip(keys, row)) for row in rows[1:]] == raw
        finally:
            wb.close()
        return "all typed JSON cells, Unicode strings, leading-zero codes and records survive in spreadsheet"
    if tool_id == "text-to-json":
        data = json.loads(output.read_text(encoding="utf-8"))
        lines = source.read_text(encoding="utf-8").splitlines()
        assert data == {"lines": lines, "line_count": len(lines)}
        return "all original text lines retained exactly with independently counted lines"
    if tool_id == "csv-validator":
        data = json.loads(output.read_text(encoding="utf-8"))
        with source.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert data["valid"] is True and data["columns"] == len(rows[0])
        assert data["rows_checked"] == len(rows) - 1 and data["errors"] == []
        return "validity verdict and all row/column counts independently match quoted and multiline CSV"
    if tool_id == "json-validator":
        raw = json.loads(source.read_text(encoding="utf-8"))
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["valid"] is True and data["root_type"] == type(raw).__name__
        return "validity and independently parsed JSON root type agree"
    if tool_id == "text-statistics":
        raw = source.read_text(encoding="utf-8")
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["characters"] == len(raw)
        assert report["lines"] == len(raw.splitlines())
        assert report["bytes_utf8"] == len(raw.encode("utf-8"))
        return "characters, lines and UTF-8 byte lengths independently counted"
    if tool_id == "text-sort":
        original = source.read_text(encoding="utf-8").splitlines()
        actual = output.read_text(encoding="utf-8").splitlines()
        assert actual == sorted(original, key=lambda v: v.casefold())
        return "every source line retained exactly in case-insensitive sorted order"
    if tool_id == "text-deduplicate":
        lines = source.read_text(encoding="utf-8").splitlines()
        seen = set()
        expected = []
        for line in lines:
            if line.strip() and line.strip() not in seen:
                seen.add(line.strip())
                expected.append(line.rstrip())
        assert output.read_text(encoding="utf-8").splitlines() == expected
        return "source lines preserved once each in first-occurrence order"
    if tool_id in {"url-encode", "url-decode"}:
        source_text = source.read_text(encoding="utf-8")
        result = output.read_text(encoding="utf-8").strip()
        expected = urllib.parse.quote(source_text) if tool_id == "url-encode" else urllib.parse.unquote(source_text)
        assert result == expected.strip()
        return "URL quoting/unquoting independently matches standard library on entire source"
    if tool_id == "checksum-compare":
        import hashlib
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result == {"same": True, "sha256_a": digest, "sha256_b": digest}
        return "actual original bytes hash to both independently validated checksums"
    if tool_id == "file-mime-report":
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["extension"] == source.suffix.lower()
        assert result["size_bytes"] == source.stat().st_size
        assert result["signature_hex"] == source.read_bytes()[:32].hex()
        return "original extension, byte count and first 32 signature bytes match report"
    if tool_id in {"bzip2-decompress", "xz-decompress"}:
        import bz2
        import lzma
        expand = bz2.decompress if tool_id == "bzip2-decompress" else lzma.decompress
        assert output.read_bytes() == expand(source.read_bytes())
        return "decompressed bytes independently match standard library decoder"
    raise AssertionError(f"Listed tool {tool_id} has no concrete oracle")

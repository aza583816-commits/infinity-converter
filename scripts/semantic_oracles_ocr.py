"""Known-answer OCR regression oracles over synthetic, privacy-safe image/PDF fixtures.

Only assert independently known visible source words and structure; OCR success
is not assumed just because a generated document is decodable.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image


ORACLE_IDS = frozenset({
    "pdf-ocr", "image-ocr", "ocr-image-to-pdf", "ocr-pdf-to-searchable",
    "ocr-image-to-json", "ocr-pdf-to-json", "ocr-pdf-page-texts",
    "ocr-image-numbers", "ocr-image-emails", "ocr-image-urls",
    "ocr-image-table-csv", "ocr-image-clean-text",
    "ocr-image-to-html", "ocr-image-to-markdown",
    "ocr-pdf-to-markdown", "ocr-pdf-to-csv", "ocr-image-to-csv",
    "ocr-receipt-fields", "ocr-invoice-fields",
    "ocr-text-deduplicate", "ocr-entities", "ocr-language-report",
})


def _has_marker(text: str, *, page: int | None = None):
    simplified = " ".join(text.upper().split())
    assert "INFINITY CONVERTER" in simplified, simplified[:500]
    if page is not None:
        assert re.search(r"\bPAGE\s*"+str(page)+r"\b", simplified), simplified[:500]


def _has_pdf_source_marker(text: str, source_pdf: pymupdf.Document, page_number: int):
    """Verify the heading actually printed on this input page, not a hardcoded 3-page fixture."""
    original = " ".join(source_pdf[page_number - 1].get_text("text").upper().split())
    normalized = " ".join(text.upper().split())
    if "INFINITY CONVERTER" in original:
        try:
            _has_marker(text, page=page_number)
        except AssertionError as error:
            raise AssertionError(("source PDF heading vs OCR mismatch", page_number, original[:500], normalized[:500])) from error
    elif "LANDSCAPE PAGE FOUR" in original:
        assert "LANDSCAPE PAGE FOUR" in normalized, ("landscape page OCR mismatch", page_number, original[:500], normalized[:500])
    else:
        expected = f"EXTRA PAGE {page_number}"
        assert expected in original and expected in normalized, ("additional PDF page OCR mismatch", page_number, original[:500], normalized[:500])


def _has_invoice(text: str):
    assert re.search(r"\bINVOICE\s*12345\b", text.upper()), text[:500]


def oracle(tool_id: str, source: Path | None, output: Path, fixture: Path) -> str | None:
    if tool_id not in ORACLE_IDS:
        return None
    assert source is not None
    if tool_id == "image-ocr":
        text = output.read_text(encoding="utf-8")
        _has_marker(text)
        _has_invoice(text)
        return "known image heading and invoice number independently recovered as actual OCR text"
    if tool_id == "pdf-ocr":
        text = output.read_text(encoding="utf-8")
        with pymupdf.open(source) as original:
            assert len(original) >= 3
            assert text.count("--- صفحة ") == len(original)
            for page in range(1, len(original)+1):
                recognized = text.split(f"--- صفحة {page} ---",1)[1].split("--- صفحة",1)[0]
                _has_pdf_source_marker(recognized, original, page)
        return "each original PDF page yields its numbered heading in real OCR text"
    if tool_id in {"ocr-image-to-pdf", "ocr-pdf-to-searchable"}:
        with pymupdf.open(output) as pdf:
            if tool_id == "ocr-pdf-to-searchable":
                with pymupdf.open(source) as source_pdf:
                    assert len(pdf) == len(source_pdf)
            else:
                with Image.open(source) as opened:
                    assert len(pdf) == 1 and abs(pdf[0].rect.width/pdf[0].rect.height-opened.width/opened.height)<.01
            for page_no, page in enumerate(pdf, 1):
                assert page.get_images(full=True), "OCR PDF lost the original visual background"
                if tool_id == "ocr-pdf-to-searchable":
                    with pymupdf.open(source) as original:
                        _has_pdf_source_marker(page.get_text("text"), original, page_no)
                else:
                    _has_marker(page.get_text("text"))
        return "actual source image/pages remain visible in PDF while a selectable OCR text layer is present"
    if tool_id == "ocr-image-to-json":
        data = json.loads(output.read_text(encoding="utf-8"))
        _has_marker(data["text"])
        _has_invoice(data["text"])
        with Image.open(source) as image:
            assert data["words"] and " ".join(w["text"] for w in data["words"]) == data["text"]
            assert all(0 <= w["left"] < image.width and 0 <= w["top"] < image.height
                       and w["width"] > 0 and w["height"] > 0
                       and w["left"]+w["width"] <= image.width
                       and w["top"]+w["height"] <= image.height
                       and -1 <= w["confidence"] <= 100 for w in data["words"])
        return "known image text recognized with real confidence and in-bounds word bounding boxes"
    if tool_id == "ocr-pdf-to-json":
        data = json.loads(output.read_text(encoding="utf-8"))
        with pymupdf.open(source) as pdf:
            assert len(data["pages"]) == len(pdf)
            for i, item in enumerate(data["pages"], 1):
                assert item["page"] == i
                _has_pdf_source_marker(item["text"], pdf, i)
        return "all PDF pages ordered in JSON, each with its independently known page marker"
    if tool_id == "ocr-pdf-page-texts":
        with pymupdf.open(source) as original, zipfile.ZipFile(output) as archive:
            names = sorted(n for n in archive.namelist() if n.endswith(".txt"))
            assert len(names) == len(original)
            for i,name in enumerate(names,1):
                _has_pdf_source_marker(archive.read(name).decode("utf-8"), original, i)
        return "one separate OCR TXT per original PDF page, with correct known page marker"
    if tool_id == "ocr-image-numbers":
        values = output.read_text(encoding="utf-8").splitlines()
        assert "12345" in values and "1250.50" in values and "100" in values and "200" in values
        assert all(re.fullmatch(r"\d+(?:[.,]\d+)*%?", number) for number in values)
        return "four known numeric fields recovered from image as numeric-only lines"
    if tool_id == "ocr-image-emails":
        emails = output.read_text(encoding="utf-8").splitlines()
        assert emails == ["test@example.com"]
        return "exact visible email extracted without surrounding label or unrelated text"
    if tool_id == "ocr-image-urls":
        urls = output.read_text(encoding="utf-8").splitlines()
        assert urls == ["https://example.com"]
        return "exact visible source URL extracted, retaining https scheme and hostname"
    if tool_id == "ocr-image-table-csv":
        with output.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert len(rows) >= 3
        assert any("Name" in row and "Amount" in row for row in rows)
        assert any("Alice" in row and "100" in row for row in rows)
        assert any("Bob" in row and "200" in row for row in rows)
        return "known table header and two name/amount rows preserved as editable CSV fields"
    if tool_id == "ocr-image-clean-text":
        text = output.read_text(encoding="utf-8")
        _has_marker(text)
        _has_invoice(text)
        assert all(line == line.strip() and "  " not in line for line in text.splitlines())
        return "known OCR words survive normalized whitespace without duplicate spaces"
    if tool_id == "ocr-image-to-html":
        result = output.read_text(encoding="utf-8")
        assert result.lower().startswith("<!doctype html>") and "<pre>" in result and "</pre>" in result
        _has_marker(result)
        _has_invoice(result)
        return "HTML contains the visible source heading and invoice field in a valid text container"
    if tool_id == "ocr-image-to-markdown":
        result = output.read_text(encoding="utf-8")
        assert result.startswith("# OCR Result")
        _has_marker(result)
        _has_invoice(result)
        return "Markdown heading and original known invoice/image text retained"
    if tool_id == "ocr-pdf-to-markdown":
        result = output.read_text(encoding="utf-8")
        with pymupdf.open(source) as pdf:
            for i in range(1,len(pdf)+1):
                assert f"## Page {i}" in result
                section = result.split(f"## Page {i}",1)[1].split("## Page",1)[0]
                _has_pdf_source_marker(section, pdf, i)
        return "Markdown sections preserve every independently known source PDF page heading"
    if tool_id == "ocr-pdf-to-csv":
        with output.open(encoding="utf-8",newline="") as f:
            data=list(csv.DictReader(f))
        with pymupdf.open(source) as pdf:
            assert len(data)==len(pdf)
            for i,row in enumerate(data,1):
                assert row["page"] == str(i)
                _has_pdf_source_marker(row["text"], pdf, i)
        return "CSV includes exactly one numbered text row for each original PDF page"
    if tool_id == "ocr-image-to-csv":
        with output.open(encoding="utf-8",newline="") as f:
            data=list(csv.DictReader(f))
        assert len(data)>=6
        assert [int(row["line"]) for row in data]==list(range(1,len(data)+1))
        assert any("INFINITY CONVERTER" in row["text"] for row in data)
        assert any("Alice 100" in row["text"] for row in data)
        return "recognized image text preserved in actual ordered, numbered CSV lines"
    if tool_id == "ocr-receipt-fields":
        data=json.loads(output.read_text(encoding="utf-8"))
        assert "test@example.com" in data["emails"]
        assert "SAR 1250.50" in data["money"], data
        assert all(isinstance(data[key],list) for key in ("emails","phones","dates","money"))
        return "known source email and printed currency amount extracted into correct receipt fields"
    if tool_id == "ocr-invoice-fields":
        data=json.loads(output.read_text(encoding="utf-8"))
        assert data["invoice_number"]=="12345" and data["total"]=="1250.50"
        _has_invoice(data["raw"])
        return "known invoice ID and total match exact visible source values and raw OCR text"
    if tool_id == "ocr-text-deduplicate":
        lines=output.read_text(encoding="utf-8").splitlines()
        assert lines and len(lines)==len(set(line.strip().casefold() for line in lines))
        assert len([line for line in lines if line.strip().upper()=="INFINITY CONVERTER"])==1
        assert len([line for line in lines if "Invoice 12345" in line])==1
        return "deliberately duplicated heading and invoice lines each recovered exactly once"
    if tool_id == "ocr-entities":
        data=json.loads(output.read_text(encoding="utf-8"))
        assert "test@example.com" in data["emails"]
        assert "https://example.com" in data["urls"]
        assert all(isinstance(data[k],list) and data[k]==sorted(set(data[k]))
                   for k in ("emails","urls","phones","dates"))
        return "actual source email and URL independently recognized, classified and deduplicated"
    if tool_id == "ocr-language-report":
        data=json.loads(output.read_text(encoding="utf-8"))
        assert data["detected"]=="en"
        assert data["arabic_ratio"]==0 and data["english_ratio"]==1
        return "known English-only printed source correctly classified with 100% English letters"
    raise AssertionError("Registered OCR operation has no independent known-answer assertion")

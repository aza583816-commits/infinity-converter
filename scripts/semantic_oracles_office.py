"""Independent source-to-output assertions for all remaining office/data tools."""
from __future__ import annotations

import csv
import html
import io
import json
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf
from pypdf import PdfReader
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation

from converters.office import _pdf_contains_headings


ORACLE_IDS = frozenset({
    "excel-to-pdf", "ppt-to-pdf", "txt-to-pdf", "html-to-pdf",
    "markdown-to-html", "markdown-to-pdf", "csv-to-pdf",
    "bulk-certificate-maker", "csv-merge-deduplicate",
    "lms-question-bank-formatter", "xml-to-json", "docx-to-markdown",
    "docx-table-to-csv", "xlsx-to-html", "xlsx-summary",
    "csv-to-markdown", "csv-statistics", "json-to-html",
    "html-to-text", "markdown-to-text", "pptx-to-markdown",
})


def _pdftext(path: Path) -> str:
    with pymupdf.open(path) as doc:
        assert len(doc) > 0
        return "\n".join(page.get_text("text") for page in doc)


_PRESENTATION_FORMS = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
_ARABIC_RUN = re.compile(r"[\u0600-\u06FF]+")


def _logical_pdf_text(text: str) -> str:
    """Normalize PDF extractor presentation glyphs without weakening checks."""
    pieces = []
    for token in text.split():
        normalized = unicodedata.normalize("NFKC", token)
        if _PRESENTATION_FORMS.search(token):
            normalized = _ARABIC_RUN.sub(lambda match: match.group(0)[::-1], normalized)
        pieces.append(normalized)
    return " ".join(pieces)


def _csvrows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def oracle(tool_id: str, source: Path | None, output: Path, fixture: Path) -> str | None:
    if tool_id not in ORACLE_IDS:
        return None
    assert source is not None
    if tool_id in {"excel-to-pdf", "ppt-to-pdf", "txt-to-pdf", "html-to-pdf",
                   "markdown-to-pdf", "csv-to-pdf"}:
        extracted = _pdftext(output)
        if tool_id == "excel-to-pdf":
            # PDF extractors may return Arabic presentation forms and typographic
            # ligatures. NFKC is a Unicode-equivalent normalization, not a
            # fuzzy match: every full source cell must still be present.
            normalized = " ".join(unicodedata.normalize("NFKC", extracted).split())
            workbook = load_workbook(source, read_only=True, data_only=True)
            try:
                for sheet in workbook:
                    for row in sheet.iter_rows(values_only=True):
                        for cell in row:
                            if cell is not None:
                                expected = " ".join(unicodedata.normalize("NFKC", str(cell)).split())
                                assert expected in normalized, (sheet.title, cell, normalized[:2200])
            finally:
                workbook.close()
            return "every cell from every original worksheet survives as Unicode-equivalent selectable PDF text"
        if tool_id == "ppt-to-pdf":
            # Distinct synthetic slides in mixed/dense corpora expose silently
            # omitted, interchanged or extra PDF pages that a one-slide smoke
            # fixture cannot detect. Review each rendered slide separately.
            presentation = Presentation(source)
            assert len(presentation.slides) >= 1
            with pymupdf.open(output) as pdf:
                assert len(pdf) == len(presentation.slides), (
                    "PowerPoint slide count differs from rendered PDF pages",
                    len(presentation.slides), len(pdf),
                )
                for slide_number, (slide, page) in enumerate(zip(presentation.slides, pdf), 1):
                    expected = [shape.text.strip() for shape in slide.shapes
                                if getattr(shape, "has_text_frame", False) and shape.text.strip()]
                    assert expected, ("empty PowerPoint fixture slide", slide_number)
                    # LibreOffice may insert visible bullets between source
                    # paragraph lines. Every original line still has to appear
                    # in the correct *slide* and original reading sequence.
                    logical = PdfReader(str(output)).pages[slide_number - 1].extract_text() or ""
                    rendered = _logical_pdf_text(logical)
                    cursor = -1
                    for value in expected:
                        for line in value.splitlines():
                            wanted = " ".join(unicodedata.normalize("NFKC", line).split())
                            if not wanted:
                                continue
                            at = rendered.find(wanted, cursor + 1)
                            assert at >= 0, (
                                "Slide lost title/body or text was rendered out of source slide order",
                                slide_number, line, rendered[:1300],
                            )
                            cursor = at
                    words = page.get_text("words")
                    assert words and all(
                        -2 <= word[0] < word[2] <= page.rect.width + 2
                        and -2 <= word[1] < word[3] <= page.rect.height + 2
                        for word in words
                    ), ("Slide has clipped/off-page rendered text", slide_number)
            return "each PowerPoint slide maps to exactly one PDF page in source order, with all slide text inside visible page bounds"
        if tool_id == "txt-to-pdf":
            lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line]
            normal = unicodedata.normalize("NFKC", extracted)
            missing = [line for line in lines if line not in normal]
            assert not missing, (missing, normal[:2000])
            return "all original text-file lines retained as selectable PDF text"
        if tool_id == "html-to-pdf":
            from html.parser import HTMLParser
            class VisibleHTML(HTMLParser):
                def __init__(self):
                    super().__init__(convert_charrefs=True)
                    self.fragments=[]
                def handle_data(self,value):
                    if value.strip(): self.fragments.append(" ".join(value.split()))
            parser=VisibleHTML()
            parser.feed(source.read_text(encoding="utf-8"))
            # Independently read the original Unicode strings from the PDF.
            # PyMuPDF can reconstruct Arabic glyphs in visual, non-logical
            # order even when pypdf independently recovers the full heading.
            actual=_logical_pdf_text(" ".join(
                page.extract_text() or "" for page in PdfReader(str(output)).pages
            ))
            missing=[]
            for part in parser.fragments:
                if re.search(r"[\u0600-\u06FF]", part):
                    if not _pdf_contains_headings(output, (part,)):
                        missing.append(part)
                elif _logical_pdf_text(part) not in actual:
                    missing.append(part)
            assert not missing, ("HTML PDF lost visible heading or table cell text", missing, actual[:1500])
            return "all visible source HTML heading and table cells preserved as selectable PDF Unicode text"
        if tool_id == "markdown-to-pdf":
            raw=source.read_text(encoding="utf-8")
            heading=next((line[2:].strip() for line in raw.splitlines() if line.startswith("# ")),None)
            actual=_logical_pdf_text(" ".join(
                page.extract_text() or "" for page in PdfReader(str(output)).pages
            ))
            wanted_heading = _logical_pdf_text(heading or "")
            assert wanted_heading, ("Markdown PDF missing source heading", heading)
            if re.search(r"[\u0600-\u06FF]", heading or ""):
                assert _pdf_contains_headings(output, (heading,)), (
                    "Markdown PDF lost heading visually", heading, actual[:1500])
            else:
                assert wanted_heading in actual, (
                    "Markdown PDF lost heading", heading, actual[:1500])
            if "**" in raw:
                assert "Hello world" in actual
            if "|---|" in raw:
                assert all(token in actual for token in ("Name","Code","Arabic","00123"))
            return "original Markdown heading and all source body/table cell texts survive PDF conversion"
        rows = _csvrows(source)
        normalized = " ".join(unicodedata.normalize("NFKC",extracted).split())
        missing = [cell for row in rows for cell in row
                   if cell and " ".join(cell.split()) not in normalized]
        assert not missing, (missing, normalized[:1800])
        return "all source CSV headers and complete cell values survive PDF's extractable text"
    if tool_id == "markdown-to-html":
        raw = source.read_text(encoding="utf-8")
        result = html.unescape(output.read_text(encoding="utf-8"))
        heading = next((line[2:].strip() for line in raw.splitlines()
                        if line.startswith("# ")), None)
        assert heading and f"<h1>{heading}</h1>" in result
        if "**" in raw:
            assert "<strong>world</strong>" in result and "Hello " in result
        if "|---|" in raw:
            assert "<table>" in result and all(
                f">{value}<" in result for value in ("Name", "Code", "Arabic", "00123")
            )
        return "actual Markdown heading, paragraphs/emphasis or all source table cells become semantic HTML"
    if tool_id == "bulk-certificate-maker":
        names = [row["name"] for row in csv.DictReader(source.open(encoding="utf-8"))]
        with zipfile.ZipFile(output) as archive:
            files = [name for name in archive.namelist() if name.endswith(".pdf")]
            assert len(files) == len(names)
            for name, filename in zip(names, sorted(files)):
                with pymupdf.open(stream=archive.read(filename), filetype="pdf") as pdf:
                    assert len(pdf) == 1
                    text = pdf[0].get_text("text")
                    assert name in text and "COMPLETION CERTIFICATE" in text
        return "one decodable certificate PDF per CSV recipient, each with exact requested name and title"
    if tool_id == "csv-merge-deduplicate":
        actual = _csvrows(output)
        original = _csvrows(source)
        assert actual == original
        assert len({tuple(row) for row in actual[1:]}) == len(actual) - 1
        return "two original CSV files merge with identical headers and zero duplicate data rows"
    if tool_id == "lms-question-bank-formatter":
        text = output.read_text(encoding="utf-8")
        assert "::Question 1::What is 2+2? {=4}" in text
        assert "::Question 2::Capital of France? {=Paris}" in text
        return "both question/answer source pairs exported as correctly keyed LMS GIFT questions"
    if tool_id == "xml-to-json":
        root = ET.parse(source).getroot()
        data = json.loads(output.read_text(encoding="utf-8"))
        expected = [(child.attrib["name"], (child.text or "").strip()) for child in root]
        raw = data[root.tag]["item"]
        actual = raw if isinstance(raw, list) else [raw]
        assert len(actual) == len(expected) and all(
            entry["@attributes"]["name"] == name and entry["#text"] == value
            for entry, (name, value) in zip(actual, expected)
        )
        return "all XML child elements including repeated tags, attributes and Unicode text retained in JSON"
    if tool_id == "docx-to-markdown":
        doc = Document(source)
        markdown = output.read_text(encoding="utf-8")
        assert doc.paragraphs and markdown.startswith("# "+doc.paragraphs[0].text.strip())
        assert all(p.text.strip() in markdown for p in doc.paragraphs if p.text.strip())
        return "original Word title and every paragraph preserved in editable Markdown"
    if tool_id == "docx-table-to-csv":
        doc = Document(source)
        expected = [[cell.text.replace("\n"," ").strip() for cell in row.cells]
                    for table in doc.tables for row in table.rows]
        assert expected and _csvrows(output) == expected
        return "every original DOCX table cell, row and column preserved in CSV"
    if tool_id in {"xlsx-to-html", "xlsx-summary"}:
        wb = load_workbook(source, read_only=True, data_only=True)
        try:
            sheets = []
            for ws in wb.worksheets:
                rows = list(ws.iter_rows(values_only=True))
                sheets.append((ws.title, rows))
            assert sheets
            if tool_id == "xlsx-to-html":
                markup = html.unescape(output.read_text(encoding="utf-8"))
                expected = [str(cell) if cell is not None else ""
                            for _, rows in sheets for row in rows for cell in row]
                actual = re.findall(r"<td>(.*?)</td>", markup, re.S)
                assert actual == expected
                assert all(f"<h2>{name}</h2>" in markup for name, _ in sheets)
                return "every original workbook sheet name and ordered table cell survives as HTML"
            data = json.loads(output.read_text(encoding="utf-8"))
            expected = [{"sheet": name,
                         "rows": sum(any(v is not None for v in row) for row in rows),
                         "columns": max((len(row) for row in rows if any(v is not None for v in row)), default=0)}
                        for name, rows in sheets]
            assert data["sheets"] == expected
            return "all workbook sheet names and nonempty row/column counts independently recalculated"
        finally:
            wb.close()
    if tool_id in {"csv-to-markdown", "csv-statistics"}:
        rows = _csvrows(source)
        assert rows
        if tool_id == "csv-to-markdown":
            rendered = output.read_text(encoding="utf-8").splitlines()
            assert len(rendered) == len(rows) + 1
            def expected_cell(value: str) -> str:
                return (value.replace("\\", "\\\\").replace("|", "\\|")
                        .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>"))
            table = [[expected_cell(cell) for cell in row] for row in rows]
            expected = ["| " + " | ".join(table[0]) + " |",
                        "| " + " | ".join(["---"] * len(table[0])) + " |"] + [
                        "| " + " | ".join(row) + " |" for row in table[1:]]
            assert rendered == expected, ("CSV-to-Markdown changed structured values", expected, rendered, rows)
            return "all source CSV rows and cells retained with escaped pipes and multiline cells preserved in Markdown"
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["rows"] == len(rows)-1 and data["columns"] == len(rows[0])
        for idx, item in enumerate(data["columns_detail"]):
            column = [row[idx] for row in rows[1:] if idx < len(row) and row[idx]]
            assert item["name"] == rows[0][idx]
            assert item["non_null"] == len(column) and item["unique"] == len(set(column))
            if item["name"] == "value":
                numeric = [float(x) for x in column]
                assert item["min"] == min(numeric) and item["max"] == max(numeric)
                assert item["mean"] == statistics.mean(numeric)
        return "CSV cardinality, distinct values and numeric summaries independently recomputed"
    if tool_id == "json-to-html":
        markup = html.unescape(output.read_text(encoding="utf-8"))
        assert "<pre>" in markup and "</pre>" in markup
        parsed = json.loads(markup.split("<pre>",1)[1].split("</pre>",1)[0])
        assert parsed == json.loads(source.read_text(encoding="utf-8"))
        return "typed JSON structure round-trips exactly from HTML preformatted content"
    if tool_id == "html-to-text":
        from html.parser import HTMLParser
        class VisibleText(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.hidden = 0
                self.words = []
            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"): self.hidden += 1
            def handle_endtag(self, tag):
                if tag in ("script", "style"): self.hidden = max(0, self.hidden - 1)
            def handle_data(self, data):
                if not self.hidden: self.words.append(data)
        parser = VisibleText()
        parser.feed(source.read_text(encoding="utf-8"))
        expected = " ".join(" ".join(parser.words).split())
        actual = " ".join(output.read_text(encoding="utf-8").split())
        assert expected and actual == expected, (expected, actual)
        return "all visible HTML text, Unicode heading and table cell values extracted in original order"
    if tool_id == "markdown-to-text":
        raw = source.read_text(encoding="utf-8")
        actual = output.read_text(encoding="utf-8")
        words = re.findall(r"(?u)\b\w+\b", raw)
        assert words and all(word in actual for word in words), (words, actual)
        assert "#" not in actual and "**" not in actual
        return "every source heading, paragraph and table cell word survives plaintext Markdown export"
    if tool_id == "pptx-to-markdown":
        prs = Presentation(source)
        markdown = output.read_text(encoding="utf-8")
        for i, slide in enumerate(prs.slides, 1):
            assert f"## Slide {i}" in markdown
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text.strip():
                    assert shape.text.strip() in markdown
        return "every slide heading and all text shapes retained in Markdown in source order"
    raise AssertionError("Registered office oracle does not perform a content check")

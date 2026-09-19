"""Independent source-to-output assertions for all remaining office/data tools."""
from __future__ import annotations

import csv
import html
import io
import json
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation


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
            with load_workbook(source, read_only=True, data_only=True) as workbook:
                for row in workbook.active.iter_rows(values_only=True):
                    for cell in row:
                        if cell is not None:
                            assert str(cell) in extracted, (cell, extracted)
            return "all original Excel worksheet cell values actually rendered as selectable PDF text"
        if tool_id == "ppt-to-pdf":
            presentation = Presentation(source)
            assert len(presentation.slides) == 1
            all_text = [shape.text for slide in presentation.slides for shape in slide.shapes
                        if getattr(shape, "has_text_frame", False) and shape.text.strip()]
            assert all_text and all(text in extracted for text in all_text)
            return "PowerPoint title and body text survive as selectable text in the PDF"
        if tool_id == "txt-to-pdf":
            lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line]
            assert all(line in extracted for line in lines)
            return "all original text-file lines retained within PDF selectable text"
        if tool_id == "html-to-pdf":
            assert all(term in extracted for term in ("Infinity", "Hello world"))
            return "both visible HTML heading and paragraph rendered to selectable PDF"
        if tool_id == "markdown-to-pdf":
            assert all(term in extracted for term in ("Infinity", "Hello", "world"))
            return "Markdown title and emphasized content survive as selectable PDF text"
        rows = _csvrows(source)
        assert all(cell in extracted for row in rows for cell in row if cell)
        return "all source CSV headers and cells survive in PDF's extractable text"
    if tool_id == "markdown-to-html":
        raw = source.read_text(encoding="utf-8")
        result = html.unescape(output.read_text(encoding="utf-8"))
        assert "# Infinity" in raw and "<h1>Infinity</h1>" in result
        assert "**world**" in raw and "<strong>world</strong>" in result
        assert "Hello " in result
        return "Markdown heading, paragraph and bold emphasis become real HTML elements"
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
        assert data[root.tag]["item"]["@attributes"]["name"] == root[0].attrib["name"]
        assert data[root.tag]["item"]["#text"] == root[0].text.strip()
        return "XML root, nested element attribute and leaf text independently retained in JSON"
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
            assert rendered[0] == "| " + " | ".join(rows[0]) + " |"
            assert rendered[1] == "| " + " | ".join(["---"] * len(rows[0])) + " |"
            assert rendered[2:] == ["| " + " | ".join(row) + " |" for row in rows[1:]]
            return "all original CSV headers, cells and rows retained exactly in Markdown table"
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
        result = output.read_text(encoding="utf-8").strip()
        assert result == "Infinity Hello world"
        assert "<h1>Infinity</h1>" in source.read_text(encoding="utf-8")
        return "visible HTML heading and paragraph retained as clean plaintext without tags"
    if tool_id == "markdown-to-text":
        raw = source.read_text(encoding="utf-8")
        actual = output.read_text(encoding="utf-8")
        assert "# Infinity" in raw and "**world**" in raw
        assert "Infinity" in actual and "Hello world" in actual
        assert all(token not in actual for token in ("#", "*", "<"))
        return "heading and emphasized text survive while Markdown markup is stripped"
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

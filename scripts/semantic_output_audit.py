"""Independent source-to-output assertions over actual engine results.

Complements (does not replace) smoke checks. Only the explicitly listed
tool IDs have a semantic oracle here; unlisted IDs are reported as uncovered,
not mislabeled as quality-certified. Synthetic, non-sensitive fixtures.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from config.settings import settings
from core.storage import TempWorkspace
from core.tooling import TOOLS
from security.file_guard import validate_upload
from converters.engine import ConversionEngine
from scripts import full_operation_smoke as smoke
from scripts.output_input_matrix import diversify
from scripts.semantic_oracles_extra import ORACLE_IDS, oracle as extra_oracle
from scripts.semantic_oracles_archive_utility import ORACLE_IDS as ARCHIVE_UTILITY_IDS, oracle as archive_utility_oracle

PDF_TEXT = "INFINITY CONVERTER"
IMG_IDS = {"image-to-jpg", "image-to-png", "image-to-webp"}
PDF_KEEP = {"pdf-reorder-pages", "pdf-rotate", "pdf-rotate-selected", "pdf-grayscale", "pdf-page-numbers", "pdf-watermark-text", "pdf-compress", "lms-pdf-size-optimizer", "pdf-crop-margins", "pdf-repair", "pdf-booklet"}
PDF_TO_PAGES = {"pdf-to-jpg", "pdf-to-png"}
CSV_JSON = {"csv-to-json", "json-to-csv", "json-to-xlsx", "csv-to-xlsx", "xlsx-to-csv", "xlsx-to-json"}
TEXT_PRESERVING = {"pdf-to-text", "pdf-to-html", "pdf-to-markdown", "docx-to-text", "docx-to-html", "docx-to-markdown", "markdown-to-html", "markdown-to-text", "pptx-to-text", "pptx-to-markdown"}


def downloaded_payload(path: Path) -> Path:
    if path.suffix.lower() != ".zip":
        return path
    # Single operations can also return a ZIP for expected multi-file results.
    # The individual reports should not silently pass based solely on ZIP size.
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        assert all(not p.startswith("/") and ".." not in Path(p).parts for p in zf.namelist())
    return path


def independent_oracle(tool_id: str, source: Path | None, output: Path, fixture: Path) -> str | None:
    """Return a description of a verified source-to-output property or None."""
    output = downloaded_payload(output)
    checked = archive_utility_oracle(tool_id, source, output, fixture)
    if checked is not None:
        return checked
    checked = extra_oracle(tool_id, source, output, fixture)
    if checked is not None:
        return checked
    if tool_id == "pdf-merge":
        with pymupdf.open(str(output)) as pdf:
            assert len(pdf) == 6
            assert all(PDF_TEXT in p.get_text() for p in pdf)
        return "merged six pages without losing source page text"
    if tool_id == "pdf-extract-pages":
        with pymupdf.open(str(output)) as pdf:
            assert len(pdf) == 2 and "Page 1" in pdf[0].get_text() and "Page 2" in pdf[1].get_text()
        return "requested page count, original order and text"
    if tool_id == "pdf-delete-pages":
        with pymupdf.open(str(output)) as pdf:
            assert len(pdf) == 2 and "Page 3" not in " ".join(p.get_text() for p in pdf)
        return "removed requested page while preserving others"
    if tool_id == "pdf-to-docx":
        doc = Document(str(output))
        extracted = " ".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for row in t.rows for c in row.cells])
        assert PDF_TEXT in extracted
        assert abs(doc.sections[0].page_width.inches - 595 / 72) < .25
        return "editable Word text retained and source page width reconstructed"
    if tool_id == "pdf-grayscale":
        with pymupdf.open(str(source)) as original, pymupdf.open(str(output)) as converted:
            assert len(converted) == len(original)
            for a, b in zip(original, converted):
                assert abs(a.rect.width - b.rect.width) <= 1
                assert abs(a.rect.height - b.rect.height) <= 1
                pix = b.get_pixmap(matrix=pymupdf.Matrix(.4, .4), colorspace=pymupdf.csRGB)
                samples = pix.samples
                assert all(abs(samples[i]-samples[i+1]) <= 1 and abs(samples[i+1]-samples[i+2]) <= 1
                    for i in range(0, len(samples), 3))
        return "all pages retain their geometry and are visually grayscale; warning: renderer rasterizes searchable text"
    if tool_id in PDF_KEEP:
        with pymupdf.open(str(output)) as pdf:
            assert len(pdf) >= 1 and any(PDF_TEXT in p.get_text() for p in pdf)
        return "source PDF text survives transformation"
    if tool_id == "pdf-unlock":
        reader = PdfReader(str(output))
        assert not reader.is_encrypted and len(reader.pages) >= 1
        return "encrypted source unlocked"
    if tool_id == "pdf-password-protect":
        reader = PdfReader(str(output))
        assert reader.is_encrypted and reader.decrypt("secret")
        return "password actually protects output and requested secret unlocks it"
    if tool_id in IMG_IDS:
        with Image.open(source) as before, Image.open(output) as after:
            assert before.size == after.size
            assert after.format == {"image-to-jpg":"JPEG", "image-to-png":"PNG", "image-to-webp":"WEBP"}[tool_id]
        return "correct image format without changing input dimensions"
    if tool_id == "image-grayscale":
        with Image.open(output) as img:
            rgb=img.convert("RGB")
            for p in [(0,0),(rgb.width//2,rgb.height//2)]:
                a,b,c=rgb.getpixel(p)
                assert max(a,b,c)-min(a,b,c)<=1
        return "output pixels really grayscale"
    if tool_id == "file-hash":
        expected=hashlib.sha256(source.read_bytes()).hexdigest()
        assert expected in output.read_text(encoding="utf-8").lower()
        return "reported SHA-256 matches independent hash of original bytes"
    if tool_id in {"text-to-base64","base64-decode","hex-encode"}:
        import base64
        actual=output.read_text(encoding="utf-8").strip()
        if tool_id=="text-to-base64":
            assert base64.b64decode(actual).decode("utf-8") == source.read_text(encoding="utf-8")
        elif tool_id=="base64-decode":
            assert actual == base64.b64decode(source.read_text(encoding="utf-8").strip()).decode("utf-8")
        else:
            assert bytes.fromhex(actual).decode("utf-8") == source.read_text(encoding="utf-8")
        return "encoded or decoded content is independently byte-exact"
    if tool_id=="csv-to-json":
        with source.open(encoding="utf-8",newline="") as f: expected=list(csv.DictReader(f))
        actual=json.loads(output.read_text(encoding="utf-8"))
        assert actual==expected
        return "every CSV cell, row and header preserved as JSON"
    if tool_id=="json-to-csv":
        expected=json.loads(source.read_text(encoding="utf-8"))
        with output.open(encoding="utf-8",newline="") as f: actual=list(csv.DictReader(f))
        assert len(actual)==len(expected) and all(all(str(v)==actual[i][k] for k,v in row.items()) for i,row in enumerate(expected))
        return "JSON row values retained when serialized into CSV"
    if tool_id=="xlsx-to-json":
        source_book=load_workbook(source,read_only=True,data_only=True)
        actual=json.loads(output.read_text(encoding="utf-8"))
        try:
            assert set(actual)==set(source_book.sheetnames)
            for sheet in source_book:
                rows=list(sheet.values)
                keys=[str(x).strip() for x in rows[0]]
                assert actual[sheet.title] == [dict(zip(keys,row)) for row in rows[1:]]
        finally: source_book.close()
        return "all sheets, records and typed cells retained in JSON"
    if tool_id=="csv-to-xlsx":
        with source.open(encoding="utf-8",newline="") as f: expected=list(csv.reader(f))
        wb=load_workbook(output,read_only=True)
        try:
            actual=[["" if cell is None else str(cell) for cell in row] for row in wb.active.values]
            assert actual==expected
        finally: wb.close()
        return "CSV row/column boundaries and string values retained in XLSX"
    if tool_id=="xlsx-to-csv":
        wb=load_workbook(source,read_only=True,data_only=True)
        try: expected=[["" if v is None else str(v) for v in row] for row in wb.active.values]
        finally: wb.close()
        with output.open(encoding="utf-8-sig",newline="") as f: actual=list(csv.reader(f))
        assert actual==expected
        return "first sheet values retain their row and column boundaries"
    if tool_id=="text-clean":
        source_lines=source.read_text(encoding="utf-8").replace("\r\n","\n").replace("\r","\n").splitlines()
        expected="\n".join(" ".join(line.split()) for line in source_lines).strip()+"\n"
        actual=output.read_text(encoding="utf-8")
        assert actual==expected, (expected, actual)
        return "whitespace normalized without losing or reordering original tokens"
    if tool_id=="docx-to-text":
        text=output.read_text(encoding="utf-8")
        assert "Infinity Converter" in text and "Hello world" in text and "Alice" in text
        return "original Word paragraphs and table cell content retained"
    if tool_id=="pptx-to-text":
        text=output.read_text(encoding="utf-8")
        assert "Infinity Converter" in text and "Presentation test" in text
        return "slide title and body text retained"
    if tool_id=="word-to-pdf":
        with pymupdf.open(str(output)) as pdf:
            text=" ".join(p.get_text() for p in pdf)
            assert "Infinity Converter" in text and "Alice" in text and "100" in text
        return "rendered Word paragraph and table cells visible in PDF"
    if tool_id=="pdf-to-text":
        text=output.read_text(encoding="utf-8")
        assert "Page 1" in text and "Page 3" in text and text.index("Page 1")<text.index("Page 3")
        return "all page text retained in source sequence"
    if tool_id=="zip-create":
        with zipfile.ZipFile(output) as z:
            assert z.testzip() is None and len(z.infolist())>=2
            assert any(source.read_bytes()==z.read(name) for name in z.namelist() if not name.endswith("/"))
        return "at least one original member survives exactly, and ZIP CRCs pass"
    if tool_id=="gzip-compress":
        assert gzip.decompress(output.read_bytes())==source.read_bytes()
        return "compressed original bytes round-trip exactly"
    if tool_id=="gzip-decompress":
        assert output.read_bytes()==gzip.decompress(source.read_bytes())
        return "decompressed bytes match independent standard library"
    if tool_id=="bzip2-compress":
        import bz2
        assert bz2.decompress(output.read_bytes())==source.read_bytes()
        return "bzip2 content round-trips byte-exact"
    if tool_id=="xz-compress":
        import lzma
        assert lzma.decompress(output.read_bytes())==source.read_bytes()
        return "xz content round-trips byte-exact"
    if tool_id=="json-minify":
        assert json.loads(output.read_text(encoding="utf-8"))==json.loads(source.read_text(encoding="utf-8"))
        return "JSON structural meaning unchanged by minification"
    if tool_id=="uuid-list-generator":
        import uuid
        uuids=[v.strip() for v in output.read_text(encoding="utf-8").splitlines() if v.strip()]
        assert len(uuids)==len(set(uuids)) and len(uuids)>0
        for val in uuids: uuid.UUID(val)
        return "generated UUIDs are valid and unique"
    return None


def run():
    profile=os.environ.get("IC_TEST_FIXTURE_PROFILE","baseline")
    with tempfile.TemporaryDirectory(prefix="ic-semantic-audit-") as directory:
        fixture=Path(directory)/"fixtures"
        smoke.make_fixtures(fixture)
        if profile!="baseline": diversify(fixture,profile)
        failures=[]; verified={}; unverified=[]
        engine=ConversionEngine()
        for index,tool in enumerate(TOOLS.values(),1):
            if tool.id not in {
                "pdf-merge","pdf-extract-pages","pdf-delete-pages","pdf-to-docx",
                "pdf-unlock","pdf-password-protect","image-grayscale","file-hash",
                "text-to-base64","base64-decode","hex-encode","csv-to-json",
                "json-to-csv","xlsx-to-json","csv-to-xlsx","xlsx-to-csv",
                "text-clean","docx-to-text","pptx-to-text","word-to-pdf",
                "pdf-to-text","zip-create","gzip-compress","gzip-decompress",
                "bzip2-compress","xz-compress","json-minify","uuid-list-generator",
            } | IMG_IDS | PDF_KEEP | ORACLE_IDS | ARCHIVE_UTILITY_IDS:
                unverified.append(tool.id)
                continue
            with TempWorkspace() as workspace:
                try:
                    inputs=[]
                    original=None
                    if tool.input_required:
                        original=smoke.choose_fixture(tool,fixture)
                        count=2 if tool.id in {"pdf-merge","zip-create","image-to-pdf","checksum-compare","tar-create","tar-gzip-create","tar-bzip2-create","text-diff"} else 1
                        for n in range(count):
                            up=smoke.Upload(original.name,original.read_bytes())
                            inputs.append(validate_upload(up,max_bytes=settings.max_file_bytes,inspect_only=False,
                                workspace=workspace.path,max_pdf_pages=settings.max_pdf_pages))
                    requested_param = smoke.param_for(tool)
                    if tool.id == "pdf-reorder-pages":
                        with pymupdf.open(original) as source_pdf:
                            total_pages = len(source_pdf)
                        requested_param = ",".join(map(str, [total_pages, *range(1, total_pages)]))
                    elif tool.id == "image-resize":
                        requested_param = "500"
                    elif tool.id == "image-crop":
                        requested_param = "0,0,100,100"
                    result=engine.convert(tool=tool,safe_inputs=inputs,workspace=workspace,
                        timeout=min(settings.subprocess_timeout,90),max_pdf_pages=settings.max_pdf_pages,
                        param=requested_param,options=smoke.options_for(tool))
                    assertion=independent_oracle(tool.id,original,result.path,fixture)
                    if assertion is None: raise AssertionError("No independent quality assertion assigned")
                    verified[tool.id]=assertion
                    print(f"SEMANTIC PASS {tool.id}: {assertion}",flush=True)
                except Exception as error:
                    failures.append({"id":tool.id,"error":f"{type(error).__name__}: {error}"})
                    print(f"SEMANTIC FAIL {tool.id}: {type(error).__name__}: {error}",flush=True)
        report={"profile":profile,"total":len(TOOLS),"semantic_verified":len(verified),
            "semantic_failures":failures,"unverified":unverified,"verifications":verified,
            "quality_complete":len(verified)==len(TOOLS) and not failures}
        report_path=Path(os.environ.get("IC_SEMANTIC_REPORT","/tmp/semantic-quality-report.json"))
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"SEMANTIC RESULT {len(verified)}/{len(TOOLS)} verified, {len(failures)} failures, {len(unverified)} not yet independently checked",flush=True)
        if failures: raise SystemExit(1)


if __name__=="__main__": run()

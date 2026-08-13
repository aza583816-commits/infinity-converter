import base64
import csv
import hashlib
import io
import json
import os
import re
import secrets
import string
import zipfile
from datetime import datetime, timezone
from difflib import unified_diff

from flask import Flask, request, jsonify, render_template, send_file

import pandas as pd
from PIL import Image
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph as RLParagraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

from pypdf import PdfReader, PdfWriter
import qrcode
import markdown as md_lib

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
except Exception:
    Presentation = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12MB
MAX_FILE_BYTES = 4 * 1024 * 1024  # 4MB

ARABIC_FONT_NAME = "ArabicFont"
_arabic_font_registered = False

def ensure_arabic_font():
    global _arabic_font_registered
    if _arabic_font_registered:
        return ARABIC_FONT_NAME
    
    possible_paths = [
        "static/fonts/NotoNaskhArabic-Regular.ttf",
        "static/NotoNaskhArabic-Regular.ttf",
        "static/Cairo-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, path))
                _arabic_font_registered = True
                return ARABIC_FONT_NAME
            except Exception:
                continue
                
    return "Helvetica"

def shape_arabic(text):
    if not text:
        return text
    if arabic_reshaper and get_display:
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text
    return text

def is_arabic_text(t):
    return bool(re.search(r"[\u0600-\u06FF]", t or ""))

def pdf_font_name(is_arabic):
    if is_arabic:
        return ensure_arabic_font()
    return "Helvetica"

def file_response(data_bytes, mimetype, filename):
    return send_file(io.BytesIO(data_bytes), mimetype=mimetype, as_attachment=True, download_name=filename)

def bad_request(message):
    return jsonify({"error": message}), 400

def get_file_bytes(payload, key="fileBase64"):
    b64 = payload.get(key)
    if not b64:
        return None
    return base64.b64decode(b64)

def parse_csv_text(text):
    text = (text or "").strip()
    return list(csv.reader(io.StringIO(text)))

def escape_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_docx_from_text(text, is_arabic):
    doc = Document()
    for line in (text or "").split("\n"):
        p = doc.add_paragraph()
        if is_arabic:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pPr = p._p.get_or_add_pPr()
            pPr.append(pPr.makeelement(qn("w:bidi"), {}))
        run = p.add_run(line if line else " ")
        if is_arabic:
            rPr = run._r.get_or_add_rPr()
            rPr.append(rPr.makeelement(qn("w:rtl"), {}))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def text_to_pdf_bytes(text, is_arabic, title=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    # ضبط المحاذاة لليمين واتجاه النص العربي للفقرات العادية
    style = ParagraphStyle("Body", fontName=font, fontSize=12, leading=18, alignment=2 if is_arabic else 0)
    story = []
    for line in (text or "").split("\n"):
        content = shape_arabic(line) if is_arabic else line
        story.append(RLParagraph(escape_html(content).replace("\n", "<br/>") or "&nbsp;", style))
        story.append(Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()

def word_to_pdf_structured(docx_doc, is_arabic):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    style = ParagraphStyle("Body", fontName=font, fontSize=12, leading=18, alignment=2 if is_arabic else 0)
    story = []

    for par in docx_doc.paragraphs:
        txt = par.text.strip()
        if txt:
            # معالجة وعكس الحروف للفقرات العادية لتظهر بشكل صحيح وسليم
            content = shape_arabic(txt) if is_arabic else txt
            story.append(RLParagraph(escape_html(content), style))
            story.append(Spacer(1, 6))

    for table_elem in docx_doc.tables:
        table_data = []
        for row in table_elem.rows:
            formatted_row = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                processed = shape_arabic(cell_text) if is_arabic else cell_text
                cell_style = ParagraphStyle('TableCell', fontName=font, fontSize=10, leading=14, alignment=2 if is_arabic else 0)
                formatted_row.append(RLParagraph(escape_html(processed), cell_style))
            table_data.append(formatted_row)
            
        if table_data:
            t = Table(table_data, hAlign="CENTER")
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0ea5e9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(Spacer(1, 10))
            story.append(t)
            story.append(Spacer(1, 10))

    doc.build(story)
    return buf.getvalue()

def csv_to_pdf_bytes(text, is_arabic):
    rows = parse_csv_text(text)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    
    table_data = []
    for row in rows:
        formatted_row = []
        for c in row:
            cell_text = (c or "").strip()
            processed_text = shape_arabic(cell_text) if is_arabic else cell_text
            style_cell = ParagraphStyle('TableCell', fontName=font, fontSize=10, leading=14, alignment=2 if is_arabic else 0)
            formatted_row.append(RLParagraph(escape_html(processed_text), style_cell))
        table_data.append(formatted_row)
        
    if not table_data:
        table_data = [[RLParagraph("", ParagraphStyle('Empty', fontName=font, fontSize=10))]]

    table = Table(table_data, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0ea5e9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    doc.build([table])
    return buf.getvalue()

def handle_word_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if file_bytes:
        try:
            docx_doc = Document(io.BytesIO(file_bytes))
            pdf_bytes = word_to_pdf_structured(docx_doc, is_arabic)
            return file_response(pdf_bytes, "application/pdf", "converted_document.pdf")
        except Exception:
            return bad_request("تعذر قراءة ملف الوورد" if is_arabic else "Could not read the Word file")
            
    text = p.get("text", "")
    pdf_bytes = text_to_pdf_bytes(text, is_arabic)
    return file_response(pdf_bytes, "application/pdf", "converted_document.pdf")

def handle_csv_to_pdf(p):
    pdf_bytes = csv_to_pdf_bytes(p.get("text", ""), p["is_arabic"])
    return file_response(pdf_bytes, "application/pdf", "converted_table.pdf")

def handle_pdf_to_text(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    reader = PdfReader(io.BytesIO(file_bytes))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return jsonify({"result": text.strip()})

def handle_pdf_to_doc(p):
    buf = build_docx_from_text(p.get("text", ""), p["is_arabic"])
    return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.doc")

def handle_pdf_to_docx(p):
    buf = build_docx_from_text(p.get("text", ""), p["is_arabic"])
    return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")

def handle_doc_to_docx(p):
    buf = build_docx_from_text(p.get("text", ""), p["is_arabic"])
    return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")

def handle_pdf_to_excel(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    reader = PdfReader(io.BytesIO(file_bytes))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            rows = [line.split() for line in text.split("\n") if line.strip()]
            if not rows:
                rows = [[""]]
            max_len = max(len(r) for r in rows)
            rows = [r + [""] * (max_len - len(r)) for r in rows]
            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=f"Page {idx + 1}"[:31], index=False, header=False)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "converted.xlsx")

def handle_pdf_to_ppt(p):
    if Presentation is None:
        return bad_request("python-pptx غير مثبّت على السيرفر")
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    reader = PdfReader(io.BytesIO(file_bytes))
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    for idx, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()[:1800]
        slide = prs.slides.add_slide(blank_layout)
        title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.3), Inches(9), Inches(0.8))
        title_box.text_frame.text = f"Page {idx + 1}"
        title_box.text_frame.paragraphs[0].font.size = Pt(20)
        title_box.text_frame.paragraphs[0].font.bold = True
        body_box = slide.shapes.add_textbox(Inches(0.4), Inches(1.2), Inches(9), Inches(5))
        body_box.text_frame.text = text
        body_box.text_frame.word_wrap = True
    buf = io.BytesIO()
    prs.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "converted.pptx")

def handle_merge_pdf(p):
    files = p.get("filesBase64") or ([p.get("fileBase64")] if p.get("fileBase64") else [])
    if len(files) < 2:
        msg = "يرجى رفع ملفين PDF على الأقل للدمج" if p["is_arabic"] else "Please upload at least 2 PDF files to merge"
        return bad_request(msg)
    writer = PdfWriter()
    for b64 in files:
        reader = PdfReader(io.BytesIO(base64.b64decode(b64)))
        for page in reader.pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "merged.pdf")

def handle_split_pdf(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    reader = PdfReader(io.BytesIO(file_bytes))
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            page_buf = io.BytesIO()
            writer.write(page_buf)
            zf.writestr(f"page_{i + 1}.pdf", page_buf.getvalue())
    return file_response(zip_buf.getvalue(), "application/zip", "split_pages.zip")

def handle_csv_to_word(p):
    rows = parse_csv_text(p.get("text", ""))
    is_arabic = p["is_arabic"]
    doc = Document()
    if rows:
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                cell = table.cell(r, c)
                cell.text = (val or "").strip()
                if is_arabic:
                    for par in cell.paragraphs:
                        par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    buf = io.BytesIO()
    doc.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")

def handle_text_to_excel(p):
    rows = [line.split("\t") if "\t" in line else line.split(",") for line in (p.get("text", "")).split("\n")]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False, header=False)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "converted.xlsx")

def handle_json_to_excel(p):
    raw = p.get("json") or p.get("text", "")
    data = json.loads(raw)
    df = pd.DataFrame(data if isinstance(data, list) else [data])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "converted.xlsx")

def handle_excel_to_json(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    df = pd.read_excel(io.BytesIO(file_bytes))
    return jsonify({"result": df.to_json(orient="records", force_ascii=False, indent=2)})

def handle_csv_to_json(p):
    rows = parse_csv_text(p.get("text", ""))
    if not rows:
        return jsonify({"result": "[]"})
    headers = [h.strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        item = {headers[i]: (r[i].strip() if i < len(r) else "") for i in range(len(headers))}
        data.append(item)
    return jsonify({"result": json.dumps(data, ensure_ascii=False, indent=2)})

def handle_text_to_csv(p):
    text = p.get("text", "")
    buf = ("\ufeff" + text).encode("utf-8")
    return file_response(buf, "text/csv", "converted.csv")

def handle_word_to_csv(p):
    return handle_text_to_csv(p)

def handle_compress_image(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70, optimize=True)
    return file_response(buf.getvalue(), "image/jpeg", "compressed.jpg")

def handle_image_to_png(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    img = Image.open(io.BytesIO(file_bytes))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return file_response(buf.getvalue(), "image/png", "converted.png")

def handle_image_to_jpg(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    img = Image.open(io.BytesIO(file_bytes))
    background = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode in ("RGBA", "LA"):
        background.paste(img, mask=img.split()[-1])
    else:
        background.paste(img.convert("RGB"))
    buf = io.BytesIO()
    background.save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "converted.jpg")

def handle_image_to_base64(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    b64 = base64.b64encode(file_bytes).decode("ascii")
    mime = p.get("mimeType") or "image/png"
    return jsonify({"result": f"data:{mime};base64,{b64}"})

def handle_image_to_pdf(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return file_response(buf.getvalue(), "application/pdf", "converted.pdf")

def handle_heic_to_jpg(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    if pillow_heif is None:
        return bad_request("pillow-heif غير مثبّت على السيرفر")
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "converted.jpg")

def handle_base64_tool(p):
    text = p.get("text", "")
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        re_encoded = base64.b64encode(decoded.encode("utf-8")).decode("ascii")
        result = decoded if re_encoded.rstrip("=") == text.strip().rstrip("=") else base64.b64encode(text.encode("utf-8")).decode("ascii")
    except Exception:
        result = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return jsonify({"result": result})

def handle_url_encoder(p):
    from urllib.parse import quote, unquote
    text = p.get("text", "")
    try:
        decoded = unquote(text)
        result = decoded if decoded != text else quote(text)
    except Exception:
        result = quote(text)
    return jsonify({"result": result})

def handle_json_beautifier(p):
    data = json.loads(p.get("text", ""))
    return jsonify({"result": json.dumps(data, ensure_ascii=False, indent=4)})

def handle_css_js_minifier(p):
    text = p.get("text", "")
    no_comments = re.sub(r"/\*[\s\S]*?\*/|//.*", "", text)
    result = re.sub(r"\s+", " ", no_comments).strip()
    return jsonify({"result": result})

def handle_html_entity(p):
    text = p.get("text", "")
    result = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
    return jsonify({"result": result})

def handle_hash_generator(p):
    text = p.get("text", "").encode("utf-8")
    result = f"MD5: {hashlib.md5(text).hexdigest()}\nSHA-1: {hashlib.sha1(text).hexdigest()}\nSHA-256: {hashlib.sha256(text).hexdigest()}\nSHA-512: {hashlib.sha512(text).hexdigest()}"
    return jsonify({"result": result})

def handle_timestamp_converter(p):
    dt = datetime.fromtimestamp(int(p.get("text", "").strip()), tz=timezone.utc)
    return jsonify({"result": dt.strftime("%a, %d %b %Y %H:%M:%S GMT")})

def handle_clean_text(p):
    result = re.sub(r"<[^>]*>?", "", p.get("text", "")).replace("&nbsp;", " ").strip()
    return jsonify({"result": result})

def handle_text_to_qr(p):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(p.get("text", ""))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return jsonify({"resultImage": f"data:image/png;base64,{b64}"})

def handle_password_generator(p):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    return jsonify({"result": "".join(secrets.choice(chars) for _ in range(20))})

def handle_password_strength(p):
    text = p.get("text", "")
    strong = len(text) >= 8 and re.search(r"[A-Z]", text) and re.search(r"[0-9]", text) and re.search(r"[^A-Za-z0-9]", text)
    result = ("🔒 قوية" if p["is_arabic"] else "🔒 STRONG") if strong else ("⚠️ ضعيفة" if p["is_arabic"] else "⚠️ WEAK")
    return jsonify({"result": result})

def handle_text_counter(p):
    text = p.get("text", "")
    return jsonify({"result": f"Chars: {len(text)}\nWords: {len(text.strip().split()) if text.strip() else 0}\nLines: {len(text.split('\n'))}"})

def handle_percentage_calc(p):
    nums = re.findall(r"\d+(?:\.\d+)?", p.get("text", ""))
    if len(nums) < 2:
        return jsonify({"result": "يرجى إدخال رقمين" if p["is_arabic"] else "Please enter two numbers"})
    a, b = float(nums[0]), float(nums[1])
    return jsonify({"result": f"{nums[0]}% of {nums[1]} = {(a / 100) * b}"})

def handle_byte_converter(p):
    cleaned = re.sub(r"[^0-9.]", "", p.get("text", ""))
    b = float(cleaned) if cleaned else 0.0
    return jsonify({"result": f"Bytes: {b}\nKB: {b / 1024:.2f}\nMB: {b / 1024 ** 2:.2f}\nGB: {b / 1024 ** 3:.4f}"})

def handle_unit_converter(p):
    cleaned = re.sub(r"[^0-9.]", "", p.get("text", ""))
    val = float(cleaned) if cleaned else 0.0
    return jsonify({"result": f"Meters: {val} m\nFeet: {val * 3.28084:.2f} ft\nInches: {val * 39.3701:.2f} in\Miles: {val / 1609.34:.4f} mi"})

def handle_markdown_to_html(p):
    return jsonify({"result": md_lib.markdown(p.get("text", ""))})

def handle_text_diff(p):
    lines = p.get("text", "").split("\n")
    mid = len(lines) // 2
    diff = unified_diff(lines[:mid], lines[mid:], lineterm="")
    out_lines = []
    for line in diff:
        if line.startswith(("+++", "---", "@@")):
            continue
        out_lines.append(("+ " if line.startswith("+") else ("- " if line.startswith("-") else "  ")) + line[1:])
    return jsonify({"result": "\n".join(out_lines)})

REGISTRY = {
    "word-to-pdf": handle_word_to_pdf, "csv-to-pdf": handle_csv_to_pdf, "pdf-to-text": handle_pdf_to_text,
    "pdf-to-doc": handle_pdf_to_doc, "pdf-to-docx": handle_pdf_to_docx, "doc-to-docx": handle_doc_to_docx,
    "pdf-to-excel": handle_pdf_to_excel, "pdf-to-ppt": handle_pdf_to_ppt, "merge-pdf": handle_merge_pdf,
    "split-pdf": handle_split_pdf, "csv-to-word": handle_csv_to_word, "text-to-excel": handle_text_to_excel,
    "json-to-excel": handle_json_to_excel, "excel-to-json": handle_excel_to_json, "csv-to-json": handle_csv_to_json,
    "text-to-csv": handle_text_to_csv, "word-to-csv": handle_word_to_csv, "compress-image": handle_compress_image,
    "image-to-png": handle_image_to_png, "image-to-jpg": handle_image_to_jpg, "image-to-base64": handle_image_to_base64,
    "image-to-pdf": handle_image_to_pdf, "heic-to-jpg": handle_heic_to_jpg, "base64-tool": handle_base64_tool,
    "url-encoder": handle_url_encoder, "json-beautifier": handle_json_beautifier, "css-js-minifier": handle_css_js_minifier,
    "html-entity": handle_html_entity, "hash-generator": handle_hash_generator, "timestamp-converter": handle_timestamp_converter,
    "clean-text": handle_clean_text, "text-to-qr": handle_text_to_qr, "password-generator": handle_password_generator,
    "password-strength": handle_password_strength, "text-counter": handle_text_counter, "percentage-calc": handle_percentage_calc,
    "byte-converter": handle_byte_converter, "unit-converter": handle_unit_converter, "markdown-to-html": handle_markdown_to_html,
    "text-diff": handle_text_diff,
}

NEEDS_MULTIPLE_FILES = {"merge-pdf"}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/convert", methods=["POST"])
def convert():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    text = payload.get("text", "") or ""
    lang = payload.get("lang")
    is_arabic = lang == "ar" or is_arabic_text(text)

    files_to_check = payload.get("filesBase64") or [] if action in NEEDS_MULTIPLE_FILES else ([payload.get("fileBase64")] if payload.get("fileBase64") else [])
    for b64 in files_to_check:
        if b64 and (len(b64) * 3 / 4) > MAX_FILE_BYTES:
            msg = "حجم الملف أكبر من الحد المسموح (4MB)" if is_arabic else "File exceeds the allowed size (4MB)"
            return jsonify({"error": msg}), 413

    handler = REGISTRY.get(action)
    if not handler:
        return bad_request(f"Unknown action: {action}")

    ctx = dict(payload)
    ctx["text"] = text
    ctx["is_arabic"] = is_arabic

    try:
        return handler(ctx)
    except Exception as exc:
        app.logger.exception("convert() error")
        return jsonify({"error": str(exc)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

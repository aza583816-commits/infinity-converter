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
import tempfile
import subprocess
import textwrap
import urllib.request
from datetime import datetime, timezone
from difflib import unified_diff

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
from docx.oxml import OxmlElement

from reportlab.lib.pagesizes import A4, landscape
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
    from pdf2docx import Converter
except Exception:
    Converter = None

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
except Exception:
    Presentation = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  
MAX_FILE_BYTES = 4 * 1024 * 1024  

# ==================== إعدادات الحماية ====================
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day", "100 per hour"],
    storage_uri="memory://"
)

@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="تم تجاوز الحد المسموح. يرجى الانتظار قليلاً لحماية السيرفر."), 429
# ==========================================================

ARABIC_FONT_NAME = "ArabicFont"
_arabic_font_registered = False

def ensure_arabic_font():
    global _arabic_font_registered
    if _arabic_font_registered:
        return ARABIC_FONT_NAME
    
    font_path = "/tmp/Cairo-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/googlefonts/cairo/raw/main/fonts/ttf/Cairo-Regular.ttf"
            urllib.request.urlretrieve(url, font_path)
        except Exception as e:
            app.logger.error(f"Failed to download font: {e}")
            
    possible_paths = [
        font_path,
        "static/fonts/NotoNaskhArabic-Regular.ttf",
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

def shape_arabic(text, wrap_width=None):
    if not text:
        return text
    if arabic_reshaper and get_display:
        try:
            reshaped = arabic_reshaper.reshape(text)
            if wrap_width:
                lines = textwrap.wrap(reshaped, wrap_width)
                return "<br/>".join(get_display(line) for line in lines)
            else:
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
    story = []
    
    align = 2 if is_arabic else 0
    p_style = ParagraphStyle('BodyText', fontName=font, fontSize=12, leading=18, alignment=align)

    paragraphs = (text or "").split("\n")
    for para in paragraphs:
        if not para.strip():
             story.append(Spacer(1, 12))
             continue
        shaped_text = shape_arabic(para) if is_arabic else para
        story.append(RLParagraph(escape_html(shaped_text), p_style))
        story.append(Spacer(1, 8))

    doc.build(story)
    return buf.getvalue()

def csv_to_pdf_bytes(text, is_arabic):
    rows = parse_csv_text(text)
    buf = io.BytesIO()
    
    # استخدام العرض الأفقي (Landscape) عشان الجدول ياخذ راحته ويمتلئ بالعرض
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    
    table_data = []
    for row in rows:
        formatted_row = []
        for c in row:
            cell_text = (c or "").strip()
            processed_text = shape_arabic(cell_text, wrap_width=40) if is_arabic else cell_text
            style_cell = ParagraphStyle('TableCell', fontName=font, fontSize=11, leading=16, alignment=1)
            formatted_row.append(RLParagraph(escape_html(processed_text).replace("&lt;br/&gt;", "<br/>"), style_cell))
        
        if is_arabic:
            formatted_row.reverse()
        table_data.append(formatted_row)
        
    if not table_data:
        table_data = [[RLParagraph("", ParagraphStyle('Empty', fontName=font, fontSize=11))]]

    # حساب عرض الأعمدة تلقائياً لتملأ الصفحة بالعرض الكامل
    page_width, _ = landscape(A4)
    available_width = page_width - (30 * mm)
    num_cols = len(table_data[0]) if table_data else 1
    col_widths = [available_width / num_cols] * num_cols

    # مكتبة الألوان الذكية لترويسة الجدول
    color_palette = [
        "#0ea5e9", "#10b981", "#f59e0b", "#6366f1", 
        "#334155", "#ec4899", "#14b8a6", "#ef4444"
    ]
    chosen_bg_color = secrets.choice(color_palette)

    table = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
    
    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(chosen_bg_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]
    
    for i in range(1, len(table_data)):
        bg_color = colors.HexColor("#f8fafc") if i % 2 == 0 else colors.white
        style_commands.append(("BACKGROUND", (0, i), (-1, i), bg_color))

    table.setStyle(TableStyle(style_commands))
    doc.build([table])
    return buf.getvalue()

# ================= الأدوات =================

def handle_word_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if file_bytes:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
                tmp_docx.write(file_bytes)
                tmp_docx_path = tmp_docx.name
            
            out_dir = tempfile.gettempdir()
            cmd = ["libreoffice", "--headless", "--convert-to", "pdf", tmp_docx_path, "--outdir", out_dir]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            base_name = os.path.splitext(os.path.basename(tmp_docx_path))[0]
            pdf_path = os.path.join(out_dir, f"{base_name}.pdf")
            
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            
            os.remove(tmp_docx_path)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                
            return file_response(pdf_bytes, "application/pdf", "converted_document.pdf")
        except Exception as e:
            app.logger.error(f"LibreOffice Error: {e}")
            if 'tmp_docx_path' in locals() and os.path.exists(tmp_docx_path):
                os.remove(tmp_docx_path)
            return bad_request("فشل التحويل. قد يكون السيرفر تحت ضغط، يرجى المحاولة لاحقاً." if is_arabic else "Conversion failed due to server load.")
            
    text = p.get("text", "")
    pdf_bytes = text_to_pdf_bytes(text, is_arabic)
    return file_response(pdf_bytes, "application/pdf", "converted_document.pdf")

def handle_text_to_pdf(p):
    text = p.get("text", "")
    is_arabic = p["is_arabic"]
    if not text.strip():
        return bad_request("يرجى إدخال نص للتحويل" if is_arabic else "Please enter text to convert")
    pdf_bytes = text_to_pdf_bytes(text, is_arabic)
    return file_response(pdf_bytes, "application/pdf", "converted_text.pdf")

def handle_pdf_to_pdf_enhanced(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("يرجى رفع ملف PDF" if is_arabic else "Please upload a PDF file")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        pdf_bytes = text_to_pdf_bytes(extracted_text, is_arabic)
        return file_response(pdf_bytes, "application/pdf", "reformatted_document.pdf")
    except Exception:
        return bad_request("تعذر قراءة ملف الـ PDF" if is_arabic else "Could not read the PDF file")

def handle_csv_to_pdf(p):
    text = p.get("text", "")
    file_bytes = get_file_bytes(p)
    if file_bytes:
        try:
            text = file_bytes.decode("utf-8")
        except Exception:
            text = file_bytes.decode("windows-1256", errors="ignore")
    pdf_bytes = csv_to_pdf_bytes(text, p["is_arabic"])
    return file_response(pdf_bytes, "application/pdf", "converted_table.pdf")

def handle_excel_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("يرجى رفع ملف Excel" if is_arabic else "Please upload an Excel file")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_xlsx:
            tmp_xlsx.write(file_bytes)
            tmp_xlsx_path = tmp_xlsx.name
        
        out_dir = tempfile.gettempdir()
        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", tmp_xlsx_path, "--outdir", out_dir]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        base_name = os.path.splitext(os.path.basename(tmp_xlsx_path))[0]
        pdf_path = os.path.join(out_dir, f"{base_name}.pdf")
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        os.remove(tmp_xlsx_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            
        return file_response(pdf_bytes, "application/pdf", "converted_excel.pdf")
    except Exception as e:
        app.logger.error(f"LibreOffice Excel Error: {e}")
        if 'tmp_xlsx_path' in locals() and os.path.exists(tmp_xlsx_path):
            os.remove(tmp_xlsx_path)
        return bad_request("تعذر تحويل ملف الـ Excel. قد يكون الملف تالفاً أو السيرفر تحت ضغط." if is_arabic else "Could not convert the Excel file")

def handle_pdf_to_text(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    reader = PdfReader(io.BytesIO(file_bytes))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return jsonify({"result": text.strip()})

def handle_pdf_to_csv(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        buf = io.StringIO()
        writer = csv.writer(buf)
        for page in reader.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if line.strip():
                    writer.writerow(line.split())
        output_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        return file_response(output_bytes, "text/csv", "converted.csv")
    except Exception:
         return bad_request("تعذر استخراج الجداول من ملف الـ PDF" if p["is_arabic"] else "Could not extract tables from PDF")

def handle_pdf_to_docx(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        buf = build_docx_from_text(p.get("text", ""), is_arabic)
        return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")
    if Converter is not None:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(file_bytes)
                tmp_pdf_path = tmp_pdf.name
            tmp_docx_path = tmp_pdf_path + ".docx"
            cv = Converter(tmp_pdf_path)
            cv.convert(tmp_docx_path, start=0, end=None)
            cv.close()
            with open(tmp_docx_path, "rb") as f:
                docx_bytes = f.read()
            os.remove(tmp_pdf_path)
            os.remove(tmp_docx_path)
            return file_response(docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")
        except Exception:
            if 'tmp_pdf_path' in locals() and os.path.exists(tmp_pdf_path):
                os.remove(tmp_pdf_path)
            if 'tmp_docx_path' in locals() and os.path.exists(tmp_docx_path):
                os.remove(tmp_docx_path)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        buf = build_docx_from_text(text, is_arabic)
        return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")
    except Exception:
        return bad_request("تعذر قراءة أو تحويل ملف الـ PDF" if is_arabic else "Could not read or convert the PDF file")

def handle_pdf_to_doc(p):
    return handle_pdf_to_docx(p)

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
    text = p.get("text", "")
    file_bytes = get_file_bytes(p)
    if file_bytes:
        try:
            text = file_bytes.decode("utf-8")
        except Exception:
            text = file_bytes.decode("windows-1256", errors="ignore")
    rows = parse_csv_text(text)
    is_arabic = p["is_arabic"]
    doc = Document()
    
    if rows:
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        
        if is_arabic:
            tblPr = table._element.xpath('w:tblPr')
            if tblPr:
                bidiVisual = OxmlElement('w:bidiVisual')
                tblPr[0].append(bidiVisual)
                
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                cell = table.cell(r, c)
                cell.text = (val or "").strip()
                if is_arabic:
                    for par in cell.paragraphs:
                        par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        pPr = par._p.get_or_add_pPr()
                        pPr.append(pPr.makeelement(qn("w:bidi"), {}))
                        
    buf = io.BytesIO()
    doc.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx")

def handle_word_to_csv(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return handle_text_to_csv(p)
    try:
        docx_doc = Document(io.BytesIO(file_bytes))
        buf = io.StringIO()
        writer = csv.writer(buf)
        for table in docx_doc.tables:
            for row in table.rows:
                writer.writerow([cell.text.strip() for cell in row.cells])
        output_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        return file_response(output_bytes, "text/csv", "converted.csv")
    except Exception:
        return bad_request("تعذر استخراج الجداول من ملف الوورد" if p["is_arabic"] else "Could not extract tables from Word")

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
    text = p.get("text", "")
    file_bytes = get_file_bytes(p)
    if file_bytes:
        try:
            text = file_bytes.decode("utf-8")
        except Exception:
            text = file_bytes.decode("windows-1256", errors="ignore")
    rows = parse_csv_text(text)
    if not rows:
        return jsonify({"result": "[]"})
    headers = [h.strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        item = {headers[i]: (r[i].strip() if i < len(r) else "") for i in range(len(headers))}
        data.append(item)
    return jsonify({"result": json.dumps(data, ensure_ascii=False, indent=2)})

def handle_json_to_csv(p):
    text = p.get("text", "")
    file_bytes = get_file_bytes(p)
    if file_bytes:
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
    try:
        data = json.loads(text)
        if isinstance(data, dict): data = [data]
        if not data: return bad_request("Empty JSON")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        output_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        return file_response(output_bytes, "text/csv", "converted.csv")
    except Exception:
        return bad_request("تنسيق JSON غير صحيح" if p["is_arabic"] else "Invalid JSON format")

def handle_text_to_csv(p):
    text = p.get("text", "")
    buf = ("\ufeff" + text).encode("utf-8")
    return file_response(buf, "text/csv", "converted.csv")

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
    chars = len(text)
    words = len(text.strip().split()) if text.strip() else 0
    lines = len(text.splitlines())
    return jsonify({"result": f"Chars: {chars}\nWords: {words}\nLines: {lines}"})

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
    return jsonify({"result": f"Meters: {val} m\nFeet: {val * 3.28084:.2f} ft\nInches: {val * 39.3701:.2f} in\nMiles: {val / 1609.34:.4f} mi"})

def handle_markdown_to_html(p):
    text = p.get("text", "")
    if "<" in text and ">" in text and ("<h" in text or "<b" in text or "<p" in text):
        text = re.sub(r'<h1>(.*?)</h1>', r'# \1\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<h2>(.*?)</h2>', r'## \1\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<h3>(.*?)</h3>', r'### \1\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<strong>(.*?)</strong>|<b>(.*?)</b>', r'**\1\2**', text, flags=re.IGNORECASE)
        text = re.sub(r'<em>(.*?)</em>|<i>(.*?)</i>', r'*\1\2*', text, flags=re.IGNORECASE)
        text = re.sub(r'<a href="(.*?)">(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', r'\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', text, flags=re.IGNORECASE|re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text) 
        return jsonify({"result": text.strip()})
    else:
        return jsonify({"result": md_lib.markdown(text)})

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
    "word-to-pdf": handle_word_to_pdf, 
    "text-to-pdf": handle_text_to_pdf, 
    "pdf-to-pdf": handle_pdf_to_pdf_enhanced, 
    "csv-to-pdf": handle_csv_to_pdf, 
    "excel-to-pdf": handle_excel_to_pdf,
    "pdf-to-text": handle_pdf_to_text,
    "pdf-to-csv": handle_pdf_to_csv,
    "pdf-to-doc": handle_pdf_to_doc, 
    "pdf-to-docx": handle_pdf_to_docx, 
    "doc-to-docx": handle_doc_to_docx,
    "pdf-to-excel": handle_pdf_to_excel, 
    "pdf-to-ppt": handle_pdf_to_ppt, 
    "merge-pdf": handle_merge_pdf,
    "split-pdf": handle_split_pdf, 
    "csv-to-word": handle_csv_to_word, 
    "word-to-csv": handle_word_to_csv,
    "text-to-excel": handle_text_to_excel,
    "json-to-excel": handle_json_to_excel, 
    "excel-to-json": handle_excel_to_json, 
    "csv-to-json": handle_csv_to_json,
    "json-to-csv": handle_json_to_csv,
    "text-to-csv": handle_text_to_csv, 
    "compress-image": handle_compress_image,
    "image-to-png": handle_image_to_png, 
    "image-to-jpg": handle_image_to_jpg, 
    "image-to-base64": handle_image_to_base64,
    "image-to-pdf": handle_image_to_pdf, 
    "heic-to-jpg": handle_heic_to_jpg, 
    "base64-tool": handle_base64_tool,
    "url-encoder": handle_url_encoder, 
    "json-beautifier": handle_json_beautifier, 
    "css-js-minifier": handle_css_js_minifier,
    "html-entity": handle_html_entity, 
    "hash-generator": handle_hash_generator, 
    "timestamp-converter": handle_timestamp_converter,
    "clean-text": handle_clean_text, 
    "text-to-qr": handle_text_to_qr, 
    "password-generator": handle_password_generator,
    "password-strength": handle_password_strength, 
    "text-counter": handle_text_counter, 
    "percentage-calc": handle_percentage_calc,
    "byte-converter": handle_byte_converter, 
    "unit-converter": handle_unit_converter, 
    "markdown-to-html": handle_markdown_to_html,
    "html-to-markdown": handle_markdown_to_html,
    "text-diff": handle_text_diff,
}

NEEDS_MULTIPLE_FILES = {"merge-pdf"}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/convert", methods=["POST"])
@limiter.limit("15 per minute")
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

@app.route('/ads.txt')
def ads_txt():
    return "google.com, pub-4343857922748618, DIRECT, f08c47fec0942fa0", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

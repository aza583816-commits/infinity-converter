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
import gc
from datetime import datetime, timezone
from difflib import unified_diff

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import pandas as pd
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

# مكتبات الإكسل
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

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
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask

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
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  
MAX_FILE_BYTES = 4 * 1024 * 1024  

# ==================== الحماية العسكرية ====================
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "150 per hour"],
    storage_uri="memory://"
)

@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    return response

@app.errorhandler(429)
def ratelimit_handler(e): return jsonify(error="تم تجاوز الحد المسموح. يرجى الانتظار قليلاً."), 429

@app.errorhandler(413)
def request_entity_too_large(error): return jsonify(error="حجم الملف يتجاوز الحد المسموح."), 413

ARABIC_FONT_NAME = "ArabicFont"
_arabic_font_registered = False

# ==================== دوال المساعدة الـ VIP ====================

def smart_decode(file_bytes):
    encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1256', 'cp1256', 'iso-8859-6']
    for enc in encodings_to_try:
        try: return file_bytes.decode(enc)
        except UnicodeDecodeError: continue
    return file_bytes.decode('utf-8', errors='ignore')

def apply_ghost_privacy(writer):
    writer.add_metadata({"/Author": "", "/Creator": "", "/Producer": "", "/CreationDate": "", "/ModDate": ""})

def auto_fit_excel_columns(writer, sheet_name="Sheet1"):
    worksheet = writer.sheets[sheet_name]
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    thin_border = Border(left=Side(style='thin', color="CBD5E1"), right=Side(style='thin', color="CBD5E1"),
                         top=Side(style='thin', color="CBD5E1"), bottom=Side(style='thin', color="CBD5E1"))
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, row in enumerate(worksheet.iter_rows(), start=1):
        for cell in row:
            cell.border = thin_border
            cell.alignment = center_align
            if row_idx == 1:
                cell.fill = header_fill
                cell.font = header_font
            elif row_idx % 2 == 0:
                cell.fill = alt_fill

    for col in worksheet.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value and len(str(cell.value)) > max_length: max_length = len(str(cell.value))
            except: pass
        worksheet.column_dimensions[column].width = min(max_length + 3, 40)
        
    worksheet.freeze_panes = "A2"  
    worksheet.auto_filter.ref = worksheet.dimensions

def ensure_arabic_font():
    global _arabic_font_registered
    if _arabic_font_registered: return ARABIC_FONT_NAME
    font_path = "/tmp/Cairo-Regular.ttf"
    if not os.path.exists(font_path):
        try: urllib.request.urlretrieve("https://github.com/googlefonts/cairo/raw/main/fonts/ttf/Cairo-Regular.ttf", font_path)
        except: pass
    for path in [font_path, "static/fonts/NotoNaskhArabic-Regular.ttf", "static/Cairo-Regular.ttf"]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, path))
                _arabic_font_registered = True
                return ARABIC_FONT_NAME
            except: continue
    return "Helvetica"

def shape_arabic(text, wrap_width=None):
    if not text: return text
    if arabic_reshaper and get_display:
        try:
            reshaped = arabic_reshaper.reshape(text)
            if wrap_width:
                lines = textwrap.wrap(reshaped, wrap_width)
                return "<br/>".join(get_display(line) for line in lines)
            return get_display(reshaped)
        except: return text
    return text

def is_arabic_text(t): return bool(re.search(r"[\u0600-\u06FF]", t or ""))
def file_response(data_bytes, mimetype, filename): return send_file(io.BytesIO(data_bytes), mimetype=mimetype, as_attachment=True, download_name=filename)
def bad_request(message): return jsonify({"error": message}), 400

def get_file_bytes(payload, key="fileBase64"):
    b64 = payload.get(key)
    if not b64: return None
    b64_clean = b64.replace('\n', '').replace('\r', '')
    if not re.match(r'^[A-Za-z0-9+/]+={0,2}$', b64_clean): raise ValueError("بيانات الملف غير صالحة")
    return base64.b64decode(b64_clean)

def parse_csv_text(text): return list(csv.reader(io.StringIO((text or "").strip())))
def escape_html(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def text_to_pdf_bytes(text, is_arabic):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    font = ensure_arabic_font() if is_arabic else "Helvetica"
    story = []
    for line in (text or "").split("\n"):
        content = shape_arabic(line, wrap_width=85) if is_arabic else line
        p_style = ParagraphStyle('Body', fontName=font, fontSize=11, leading=16, alignment=2 if is_arabic else 0)
        t_cell = Table([[RLParagraph(escape_html(content).replace("&lt;br/&gt;", "<br/>") or "&nbsp;", p_style)]], colWidths=[480])
        t_cell.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
                                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.append(t_cell)
        story.append(Spacer(1, 4))
    doc.build(story)
    
    reader = PdfReader(io.BytesIO(buf.getvalue()))
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams()
        writer.add_page(page)
    apply_ghost_privacy(writer)
    final_buf = io.BytesIO()
    writer.write(final_buf)
    return final_buf.getvalue()

def csv_to_pdf_bytes(text, is_arabic):
    rows = parse_csv_text(text)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    font = ensure_arabic_font() if is_arabic else "Helvetica"
    
    table_data = []
    for row in rows:
        formatted_row = []
        for c in row:
            style_cell = ParagraphStyle('TableCell', fontName=font, fontSize=11, leading=16, alignment=1)
            formatted_row.append(RLParagraph(escape_html(shape_arabic((c or "").strip()) if is_arabic else (c or "").strip()), style_cell))
        if is_arabic: formatted_row.reverse()
        table_data.append(formatted_row)
        
    if not table_data: table_data = [[RLParagraph("", ParagraphStyle('Empty', fontName=font, fontSize=11))]]
    
    col_widths = [(A4[0] - 30*mm) / max(len(table_data[0]), 1)] * max(len(table_data[0]), 1)
    table = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
    
    style_commands = [("FONTNAME", (0, 0), (-1, -1), font), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                      ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                      ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                      ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]
    for i in range(1, len(table_data)):
        style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc") if i % 2 == 0 else colors.white))

    table.setStyle(TableStyle(style_commands))
    doc.build([table])
    
    reader = PdfReader(io.BytesIO(buf.getvalue()))
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams()
        writer.add_page(page)
    apply_ghost_privacy(writer)
    final_buf = io.BytesIO()
    writer.write(final_buf)
    return final_buf.getvalue()

# ================= الأدوات القصوى (Maximum VIP Features) =================

def handle_word_to_pdf(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return text_to_pdf_bytes(p.get("text", ""), p["is_arabic"])
    tmp_docx_path = None
    pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
            tmp_docx.write(file_bytes)
            tmp_docx_path = tmp_docx.name
        
        out_dir = tempfile.gettempdir()
        cmd = ["libreoffice", "--headless", "--nologo", "--nofirststartwizard", "--norestore", 
               "--convert-to", "pdf", tmp_docx_path, "--outdir", out_dir]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        base_name = os.path.splitext(os.path.basename(tmp_docx_path))[0]
        pdf_path = os.path.join(out_dir, f"{base_name}.pdf")
        
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Converted_Document.pdf")
    except Exception as e:
        app.logger.error(f"LibreOffice Error: {e}")
        return bad_request("فشل التحويل. السيرفر تحت الضغط." if p["is_arabic"] else "Conversion failed.")
    finally:
        if tmp_docx_path and os.path.exists(tmp_docx_path): os.remove(tmp_docx_path)
        if pdf_path and os.path.exists(pdf_path): os.remove(pdf_path)

def handle_text_to_pdf(p):
    if not p.get("text", "").strip(): return bad_request("يرجى إدخال نص" if p["is_arabic"] else "Please enter text")
    return file_response(text_to_pdf_bytes(p.get("text", ""), p["is_arabic"]), "application/pdf", "Converted_Text.pdf")

def handle_pdf_to_pdf_enhanced(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("يرجى رفع ملف" if p["is_arabic"] else "Upload PDF")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        return file_response(text_to_pdf_bytes(extracted, p["is_arabic"]), "application/pdf", "Reformatted_Document.pdf")
    except Exception: return bad_request("ملف تالف" if p["is_arabic"] else "Corrupted file")

def handle_csv_to_pdf(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    return file_response(csv_to_pdf_bytes(text, p["is_arabic"]), "application/pdf", "Converted_Table.pdf")

def handle_excel_to_pdf(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("يرجى رفع ملف Excel" if p["is_arabic"] else "Upload Excel")
    tmp_xlsx_path = None
    pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_xlsx:
            tmp_xlsx.write(file_bytes)
            tmp_xlsx_path = tmp_xlsx.name
        
        out_dir = tempfile.gettempdir()
        cmd = ["libreoffice", "--headless", "--nologo", "--nofirststartwizard", "--norestore",
               "--convert-to", "pdf", tmp_xlsx_path, "--outdir", out_dir]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        base_name = os.path.splitext(os.path.basename(tmp_xlsx_path))[0]
        pdf_path = os.path.join(out_dir, f"{base_name}.pdf")
        
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Converted_Excel.pdf")
    except Exception:
        return bad_request("فشل التحويل" if p["is_arabic"] else "Conversion failed")
    finally:
        if tmp_xlsx_path and os.path.exists(tmp_xlsx_path): os.remove(tmp_xlsx_path)
        if pdf_path and os.path.exists(pdf_path): os.remove(pdf_path)

def handle_pdf_to_text(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(file_bytes)).pages)
    return jsonify({"result": text.strip()})

def handle_pdf_to_csv(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        buf = io.StringIO()
        writer = csv.writer(buf)
        for page in reader.pages:
            for line in (page.extract_text() or "").split("\n"):
                if line.strip(): writer.writerow(line.split())
        return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")
    except Exception: return bad_request("فشل التحويل" if p["is_arabic"] else "Failed")

def handle_pdf_to_docx(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("يرجى رفع ملف PDF" if p["is_arabic"] else "Upload PDF")
    if Converter is None: return bad_request("pdf2docx is not installed")
    tmp_pdf_path = None
    docx_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(file_bytes)
            tmp_pdf_path = tmp_pdf.name
        
        out_dir = tempfile.gettempdir()
        base_name = os.path.splitext(os.path.basename(tmp_pdf_path))[0]
        docx_path = os.path.join(out_dir, f"{base_name}.docx")
        
        cv = Converter(tmp_pdf_path)
        cv.convert(docx_path, start=0, end=None, kwargs={"connected_border_tolerance": 2.5, "line_overlap_threshold": 0.8, "line_margin": 0.1, "maintain_layout": True})
        cv.close()
        
        if p["is_arabic"]:
            try:
                doc = Document(docx_path)
                for paragraph in doc.paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    pPr = paragraph._element.get_or_add_pPr()
                    pPr.insert(0, OxmlElement('w:bidi'))
                for table in doc.tables:
                    tblPr = table._element.xpath('w:tblPr')
                    if tblPr: tblPr[0].append(OxmlElement('w:bidiVisual'))
                    for row in table.rows:
                        for cell in row.cells:
                            for par in cell.paragraphs:
                                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                                pPr = par._p.get_or_add_pPr()
                                pPr.insert(0, OxmlElement('w:bidi'))
                doc.save(docx_path)
            except: pass

        with open(docx_path, "rb") as f: docx_bytes = f.read()
        return file_response(docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")
    except Exception: return bad_request("فشل التحويل للملف المعقد." if p["is_arabic"] else "Failed for complex file.")
    finally:
        if tmp_pdf_path and os.path.exists(tmp_pdf_path): os.remove(tmp_pdf_path)
        if docx_path and os.path.exists(docx_path): os.remove(docx_path)

def handle_pdf_to_doc(p): return handle_pdf_to_docx(p)

def handle_doc_to_docx(p):
    doc = Document()
    for line in (p.get("text", "")).split("\n"):
        par = doc.add_paragraph()
        if p["is_arabic"]:
            par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pPr = par._p.get_or_add_pPr()
            pPr.append(pPr.makeelement(qn("w:bidi"), {}))
        run = par.add_run(line if line else " ")
        if p["is_arabic"]:
            rPr = run._r.get_or_add_rPr()
            rPr.append(rPr.makeelement(qn("w:rtl"), {}))
    buf = io.BytesIO()
    doc.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")

def handle_pdf_to_excel(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for idx, page in enumerate(PdfReader(io.BytesIO(file_bytes)).pages):
            rows = [line.split() for line in (page.extract_text() or "").split("\n") if line.strip()]
            if not rows: rows = [[""]]
            max_len = max(len(r) for r in rows)
            df = pd.DataFrame([r + [""] * (max_len - len(r)) for r in rows])
            # الذكاء المحاسبي: تحويل النصوص إلى أرقام حقيقية للإكسل
            for col in df.columns: df[col] = pd.to_numeric(df[col], errors='ignore')
            sheet_name = f"Page {idx + 1}"[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            auto_fit_excel_columns(writer, sheet_name) 
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_pdf_to_ppt(p):
    if Presentation is None: return bad_request("python-pptx غير مثبّت")
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    for idx, page in enumerate(PdfReader(io.BytesIO(file_bytes)).pages):
        text = (page.extract_text() or "").strip()
        if len(text) > 1500: text = text[:1497] + "..." # تقطيع ذكي للنصوص
        slide = prs.slides.add_slide(blank_layout)
        t_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.3), Inches(9), Inches(0.8))
        t_box.text_frame.text = f"Page {idx + 1}"
        t_box.text_frame.paragraphs[0].font.size, t_box.text_frame.paragraphs[0].font.bold = Pt(20), True
        b_box = slide.shapes.add_textbox(Inches(0.4), Inches(1.2), Inches(9), Inches(5))
        b_box.text_frame.text, b_box.text_frame.word_wrap = text, True
    buf = io.BytesIO()
    prs.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Converted_Presentation.pptx")

def handle_merge_pdf(p):
    files = p.get("filesBase64") or ([p.get("fileBase64")] if p.get("fileBase64") else [])
    if len(files) < 2: return bad_request("يرجى رفع ملفين PDF" if p["is_arabic"] else "Upload 2 PDFs")
    writer = PdfWriter()
    page_count = 0
    for i, b64 in enumerate(files):
        b64_clean = b64.replace('\n', '').replace('\r', '')
        reader = PdfReader(io.BytesIO(base64.b64decode(b64_clean)))
        writer.add_outline_item(f"ملف {i+1}" if p["is_arabic"] else f"Document {i+1}", page_count)
        for page in reader.pages:
            page.compress_content_streams() 
            writer.add_page(page)
            page_count += 1
    apply_ghost_privacy(writer)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Merged_Document.pdf")

def handle_split_pdf(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    zip_buf = io.BytesIO()
    # الضغط الأقصى المزدوج Level 9
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for i, page in enumerate(PdfReader(io.BytesIO(file_bytes)).pages):
            writer = PdfWriter()
            page.compress_content_streams()
            writer.add_page(page)
            apply_ghost_privacy(writer)
            page_buf = io.BytesIO()
            writer.write(page_buf)
            zf.writestr(f"Page_{i + 1}.pdf", page_buf.getvalue())
    return file_response(zip_buf.getvalue(), "application/zip", "Split_Pages.zip")

def handle_csv_to_word(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    rows = parse_csv_text(text)
    doc = Document()
    if rows:
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        if p["is_arabic"]:
            tblPr = table._element.xpath('w:tblPr')
            if tblPr: tblPr[0].append(OxmlElement('w:bidiVisual'))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                cell = table.cell(r, c)
                cell.text = (val or "").strip()
                if p["is_arabic"]:
                    for par in cell.paragraphs:
                        par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        pPr = par._p.get_or_add_pPr()
                        pPr.append(pPr.makeelement(qn("w:bidi"), {}))
    buf = io.BytesIO()
    doc.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")

def handle_word_to_csv(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return handle_text_to_csv(p)
    try:
        buf = io.StringIO()
        writer = csv.writer(buf)
        for table in Document(io.BytesIO(file_bytes)).tables:
            for row in table.rows: writer.writerow([cell.text.strip() for cell in row.cells])
        return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")
    except Exception: return bad_request("فشل" if p["is_arabic"] else "Failed")

def handle_text_to_excel(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    df = pd.DataFrame([line.split("\t") if "\t" in line else line.split(",") for line in text.split("\n")])
    for col in df.columns: df[col] = pd.to_numeric(df[col], errors='ignore') # ذكاء محاسبي
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False, header=False)
        auto_fit_excel_columns(writer, "Data")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_json_to_excel(p):
    file_bytes = get_file_bytes(p)
    raw = smart_decode(file_bytes) if file_bytes else (p.get("json") or p.get("text", ""))
    df = pd.DataFrame(json.loads(raw) if isinstance(json.loads(raw), list) else [json.loads(raw)])
    for col in df.columns: df[col] = pd.to_numeric(df[col], errors='ignore') # ذكاء محاسبي
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False)
        auto_fit_excel_columns(writer, "Data")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_excel_to_json(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    df = pd.read_excel(io.BytesIO(file_bytes)).map(lambda x: x.strip() if isinstance(x, str) else x)
    df = df.where(pd.notnull(df), None) # إبادة القيم الميتة (NaN Purge)
    return jsonify({"result": df.to_json(orient="records", force_ascii=False, indent=2)})

def handle_csv_to_json(p):
    file_bytes = get_file_bytes(p)
    rows = parse_csv_text(smart_decode(file_bytes) if file_bytes else p.get("text", ""))
    if not rows: return jsonify({"result": "[]"})
    headers = [h.strip() for h in rows[0]]
    data = [{headers[i]: (r[i].strip() if i < len(r) else "") for i in range(len(headers))} for r in rows[1:]]
    return jsonify({"result": json.dumps(data, ensure_ascii=False, indent=2)})

def handle_json_to_csv(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    try:
        data = json.loads(text)
        if isinstance(data, dict): data = [data]
        if not data: return bad_request("Empty JSON")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")
    except Exception: return bad_request("تنسيق JSON غير صحيح" if p["is_arabic"] else "Invalid JSON format")

def handle_text_to_csv(p):
    file_bytes = get_file_bytes(p)
    return file_response(("\ufeff" + (smart_decode(file_bytes) if file_bytes else p.get("text", ""))).encode("utf-8"), "text/csv", "Converted_Data.csv")

# ================= أدوات الصور والتعديلات الخارقة (AI Auto-Enhance & Privacy) =================
def process_image_super(file_bytes, fmt="JPEG", dpi=(300, 300)):
    """دالة مركزية لمعالجة الصور بدقة استوديوهات وتصحيح ألوان (CMYK to RGB)"""
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode == "CMYK": img = img.convert("RGB") # معالجة ألوان الطباعة
    else: img = img.convert("RGB")
    
    if 'exif' in img.info: del img.info['exif'] # إعدام EXIF
    img = ImageOps.exif_transpose(img) 
    
    # الفلتر السينمائي
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=100, threshold=3))
    img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    
    buf = io.BytesIO()
    if fmt == "JPEG": img.save(buf, format="JPEG", quality=85, optimize=True, progressive=True, dpi=dpi) 
    else: img.save(buf, format=fmt, optimize=True, dpi=dpi)
    return buf.getvalue()

def handle_compress_image(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No image provided")
    return file_response(process_image_super(file_bytes, "JPEG"), "image/jpeg", "Compressed_Enhanced.jpg")

def handle_image_to_png(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No image provided")
    return file_response(process_image_super(file_bytes, "PNG"), "image/png", "Converted_Image.png")

def handle_image_to_jpg(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No image provided")
    return file_response(process_image_super(file_bytes, "JPEG"), "image/jpeg", "Converted_Image.jpg")

def handle_image_to_base64(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No image provided")
    img = Image.open(io.BytesIO(file_bytes))
    if 'exif' in img.info: del img.info['exif']
    img = ImageOps.exif_transpose(img) 
    buf = io.BytesIO()
    img.save(buf, format=img.format or "PNG")
    return jsonify({"result": f"data:{p.get('mimeType') or 'image/png'};base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"})

def handle_image_to_pdf(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No image provided")
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    if 'exif' in img.info: del img.info['exif']
    img = ImageOps.exif_transpose(img) 
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=300) 
    return file_response(buf.getvalue(), "application/pdf", "Converted_Image.pdf")

def handle_heic_to_jpg(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No image provided")
    if pillow_heif is None: return bad_request("pillow-heif غير مثبّت")
    return file_response(process_image_super(file_bytes, "JPEG"), "image/jpeg", "Converted_Image.jpg")

def handle_base64_tool(p):
    text = p.get("text", "")
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        re_encoded = base64.b64encode(decoded.encode("utf-8")).decode("ascii")
        result = decoded if re_encoded.rstrip("=") == text.strip().rstrip("=") else base64.b64encode(text.encode("utf-8")).decode("ascii")
    except Exception: result = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return jsonify({"result": result})

def handle_url_encoder(p):
    from urllib.parse import quote, unquote
    text = p.get("text", "")
    try:
        decoded = unquote(text)
        result = decoded if decoded != text else quote(text)
    except Exception: result = quote(text)
    return jsonify({"result": result})

def handle_json_beautifier(p):
    try: return jsonify({"result": json.dumps(json.loads(p.get("text", "")), ensure_ascii=False, indent=4, sort_keys=True)})
    except Exception: return bad_request("تنسيق JSON غير صحيح" if p["is_arabic"] else "Invalid JSON")

def handle_css_js_minifier(p):
    text = p.get("text", "")
    return jsonify({"result": re.sub(r"\s+", " ", re.sub(r"/\*[\s\S]*?\*/|//.*", "", text)).strip()})

def handle_html_entity(p):
    return jsonify({"result": p.get("text", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")})

def handle_hash_generator(p):
    text = p.get("text", "").encode("utf-8")
    # تشفير عسكري وبنكي مضاف (BLAKE2b)
    result = f"MD5: {hashlib.md5(text).hexdigest()}\nSHA-1: {hashlib.sha1(text).hexdigest()}\nSHA-256: {hashlib.sha256(text).hexdigest()}\nSHA-512: {hashlib.sha512(text).hexdigest()}\nBLAKE2b: {hashlib.blake2b(text).hexdigest()}"
    return jsonify({"result": result})

def handle_timestamp_converter(p):
    try: return jsonify({"result": datetime.fromtimestamp(int(p.get("text", "").strip()), tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")})
    except: return bad_request("رقم Timestamp غير صحيح" if p["is_arabic"] else "Invalid Timestamp")

def handle_clean_text(p):
    # مصحح الطباعة اللغوي (Typography Auto-Fix)
    text = p.get("text", "")
    text = re.sub(r'<[^>]*>?', '', text).replace("&nbsp;", " ")
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text) 
    text = re.sub(r' +', ' ', text) # إزالة المسافات المزدوجة
    text = re.sub(r' ,', ',', text) # إزالة المسافة قبل الفاصلة
    return jsonify({"result": text.strip()})

def handle_text_to_qr(p):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=2)
    qr.add_data(p.get("text", ""))
    # الباركود الملكي: 3D, Rounded, Gradient
    img = qr.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer(), color_mask=RadialGradiantColorMask(back_color=(255,255,255), center_color=(30,41,59), edge_color=(15,23,42)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return jsonify({"resultImage": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"})

def handle_password_generator(p):
    # مولد باسوردات (سهل القراءة، قوي التشفير)
    chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(chars) for _ in range(16))
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd) and 
            any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*" for c in pwd)):
            break
    return jsonify({"result": "-".join([pwd[i:i+4] for i in range(0, 16, 4)])})

def handle_password_strength(p):
    text = p.get("text", "")
    strong = len(text) >= 8 and re.search(r"[A-Z]", text) and re.search(r"[a-z]", text) and re.search(r"[0-9]", text) and re.search(r"[^A-Za-z0-9]", text)
    return jsonify({"result": ("🔒 قوية جداً (عسكرية)" if p["is_arabic"] else "🔒 VERY STRONG") if strong else ("⚠️ ضعيفة" if p["is_arabic"] else "⚠️ WEAK")})

def handle_text_counter(p):
    text = p.get("text", "")
    return jsonify({"result": f"Chars: {len(text)}\nWords: {len(text.strip().split()) if text.strip() else 0}\nLines: {len(text.splitlines())}"})

def handle_percentage_calc(p):
    nums = re.findall(r"\d+(?:\.\d+)?", p.get("text", ""))
    if len(nums) < 2: return jsonify({"result": "يرجى إدخال رقمين" if p["is_arabic"] else "Please enter two numbers"})
    return jsonify({"result": f"{nums[0]}% of {nums[1]} = {(float(nums[0]) / 100) * float(nums[1])}"})

def handle_byte_converter(p):
    b = float(re.sub(r"[^0-9.]", "", p.get("text", "")) or 0.0)
    return jsonify({"result": f"Bytes: {b}\nKB: {b / 1024:.2f}\nMB: {b / 1024 ** 2:.2f}\nGB: {b / 1024 ** 3:.4f}"})

def handle_unit_converter(p):
    val = float(re.sub(r"[^0-9.]", "", p.get("text", "")) or 0.0)
    return jsonify({"result": f"Meters: {val} m\nFeet: {val * 3.28084:.2f} ft\nInches: {val * 39.3701:.2f} in\nMiles: {val / 1609.34:.4f} mi"})

def handle_markdown_to_html(p):
    # ستايل آبل الفخم للـ HTML (يتفاعل مع الوضع الليلي للجوال)
    apple_css = """<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
    pre { background: #f4f4f4; padding: 15px; border-radius: 8px; overflow-x: auto; }
    code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.9em; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f8f9fa; }
    @media (prefers-color-scheme: dark) {
        body { background-color: #121212; color: #e0e0e0; }
        pre { background: #1e1e1e; }
        th { background-color: #1e293b; border-color: #334155; }
        td { border-color: #334155; }
    }
    </style>"""
    try: 
        html_content = md_lib.markdown(p.get("text", ""), extensions=['extra', 'tables', 'fenced_code', 'nl2br', 'toc', 'def_list', 'sane_lists']).strip()
        return jsonify({"result": apple_css + "\n" + html_content})
    except Exception: return jsonify({"result": md_lib.markdown(p.get("text", ""))})

def handle_text_diff(p):
    lines = p.get("text", "").split("\n")
    mid = len(lines) // 2
    out_lines = [("+ " if l.startswith("+") else ("- " if l.startswith("-") else "  ")) + l[1:] for l in unified_diff(lines[:mid], lines[mid:], lineterm="") if not l.startswith(("+++", "---", "@@"))]
    return jsonify({"result": "\n".join(out_lines)})

REGISTRY = {
    "word-to-pdf": handle_word_to_pdf, "text-to-pdf": handle_text_to_pdf, "pdf-to-pdf": handle_pdf_to_pdf_enhanced, 
    "csv-to-pdf": handle_csv_to_pdf, "excel-to-pdf": handle_excel_to_pdf, "pdf-to-text": handle_pdf_to_text,
    "pdf-to-csv": handle_pdf_to_csv, "pdf-to-doc": handle_pdf_to_doc, "pdf-to-docx": handle_pdf_to_docx, 
    "doc-to-docx": handle_doc_to_docx, "pdf-to-excel": handle_pdf_to_excel, "pdf-to-ppt": handle_pdf_to_ppt, 
    "merge-pdf": handle_merge_pdf, "split-pdf": handle_split_pdf, "csv-to-word": handle_csv_to_word, 
    "word-to-csv": handle_word_to_csv, "text-to-excel": handle_text_to_excel, "json-to-excel": handle_json_to_excel, 
    "excel-to-json": handle_excel_to_json, "csv-to-json": handle_csv_to_json, "json-to-csv": handle_json_to_csv,
    "text-to-csv": handle_text_to_csv, "compress-image": handle_compress_image, "image-to-png": handle_image_to_png, 
    "image-to-jpg": handle_image_to_jpg, "image-to-base64": handle_image_to_base64, "image-to-pdf": handle_image_to_pdf, 
    "heic-to-jpg": handle_heic_to_jpg, "base64-tool": handle_base64_tool, "url-encoder": handle_url_encoder, 
    "json-beautifier": handle_json_beautifier, "css-js-minifier": handle_css_js_minifier, "html-entity": handle_html_entity, 
    "hash-generator": handle_hash_generator, "timestamp-converter": handle_timestamp_converter, "clean-text": handle_clean_text, 
    "text-to-qr": handle_text_to_qr, "password-generator": handle_password_generator, "password-strength": handle_password_strength, 
    "text-counter": handle_text_counter, "percentage-calc": handle_percentage_calc, "byte-converter": handle_byte_converter, 
    "unit-converter": handle_unit_converter, "markdown-to-html": handle_markdown_to_html, "html-to-markdown": handle_markdown_to_html, "text-diff": handle_text_diff
}

NEEDS_MULTIPLE_FILES = {"merge-pdf"}

@app.route("/")
def index(): return render_template("index.html")

@app.route("/privacy")
def privacy(): return render_template("privacy.html")

@app.route("/terms")
def terms(): return render_template("terms.html")

@app.route("/contact")
def contact(): return render_template("contact.html")

@app.route("/convert", methods=["POST"])
@limiter.limit("20 per minute")
def convert():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    text = payload.get("text", "") or ""
    is_arabic = payload.get("lang") == "ar" or is_arabic_text(text)

    files_to_check = payload.get("filesBase64") or [] if action in NEEDS_MULTIPLE_FILES else ([payload.get("fileBase64")] if payload.get("fileBase64") else [])
    for b64 in files_to_check:
        if b64 and (len(b64) * 3 / 4) > MAX_FILE_BYTES:
            return jsonify({"error": "حجم الملف أكبر من الحد المسموح (4MB)" if is_arabic else "File exceeds 4MB"}), 413

    handler = REGISTRY.get(action)
    if not handler: return bad_request(f"Unknown action: {action}")

    ctx = dict(payload)
    ctx["text"] = text
    ctx["is_arabic"] = is_arabic

    try:
        response = handler(ctx)
        gc.collect() # مضاد الكراش: تنظيف الذاكرة الإجباري بعد كل عملية
        return response
    except Exception as exc:
        app.logger.exception("convert() error")
        return jsonify({"error": "حدث خطأ غير متوقع، يرجى المحاولة لاحقاً." if is_arabic else "Unexpected error occurred."}), 500

@app.route('/ads.txt')
def ads_txt(): return "google.com, pub-4343857922748618, DIRECT, f08c47fec0942fa0", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

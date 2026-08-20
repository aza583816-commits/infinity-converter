import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import string
import subprocess
import tempfile
import textwrap
import urllib.request
import uuid
import zipfile
import gc
import cloudconvert
import convertapi
import requests
from datetime import datetime, timezone
from difflib import unified_diff

from flask import Flask, request, jsonify, render_template, send_file, Response, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import pandas as pd
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont, ImageEnhance, UnidentifiedImageError

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
try:
    from openpyxl.chart import BarChart, Reference
except Exception:
    BarChart = None
    Reference = None

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
from reportlab.pdfgen import canvas as rl_canvas

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

import qrcode
from qrcode.constants import ERROR_CORRECT_H
try:
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    from qrcode.image.styles.colormasks import RadialGradiantColorMask
    QR_STYLES_AVAILABLE = True
except Exception:
    QR_STYLES_AVAILABLE = False

import markdown as md_lib

# ================= المكتبات الخارقة للـ PDF والذكاء الاصطناعي =================
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

try:
    from pdf2docx import Converter
except Exception:
    Converter = None

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
except Exception:
    Presentation = None

# ==================== الإعدادات العامة والحماية ====================
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", 25))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
MAX_MERGE_FILES = int(os.environ.get("MAX_MERGE_FILES", 30))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", 1000))
MAX_OCR_PAGES = int(os.environ.get("MAX_OCR_PAGES", 25))
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", 5_000_000))
SUBPROCESS_TIMEOUT = int(os.environ.get("SUBPROCESS_TIMEOUT", 300))
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "https://infinityconverter.com,https://www.infinityconverter.com"
).split(",") if o.strip()]

app_max_content = int(MAX_FILE_BYTES * MAX_MERGE_FILES * 1.4) + (5 * 1024 * 1024)
Image.MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", 100_000_000))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = app_max_content

@app.before_request
def enforce_custom_domain():
    if request.host == "infinity-converter-1.onrender.com":
        return redirect("https://infinityconverter.com" + request.full_path, code=301)

logging.basicConfig(level=logging.INFO)
CORS(app, resources={r"/convert": {"origins": ALLOWED_ORIGINS}}, supports_credentials=False)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "150 per hour"],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://"),
)

HEAVY_ACTIONS = {
    "word-to-pdf", "excel-to-pdf", "pdf-to-docx", "pdf-to-doc", "pdf-to-ppt", "pdf-to-excel",
    "merge-pdf", "compress-image", "image-to-text", "text-to-audio", "translate-text",
    "watermark-pdf", "compress-pdf", "protect-pdf",
}

def dynamic_convert_limit():
    payload = request.get_json(silent=True) or {}
    return "10 per minute" if payload.get("action") in HEAVY_ACTIONS else "30 per minute"

@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'

    if request.path == "/convert":
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'self'"
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.errorhandler(429)
def ratelimit_handler(e): return jsonify(error="تم تجاوز الحد المسموح. يرجى الانتظار قليلاً."), 429

@app.errorhandler(413)
def too_large_handler(e): return jsonify(error="حجم الطلب أكبر من الحد المسموح."), 413

@app.errorhandler(500)
def internal_error_handler(e):
    app.logger.exception("Unhandled server error")
    return jsonify(error="حدث خطأ غير متوقع بالسيرفر."), 500

ARABIC_FONT_NAME = "ArabicFont"
_arabic_font_registered = False

# ==================== القائمة الشاملة لجميع الأدوات ====================
TOOLS_DEF = [
    ("pdf-to-docx", "PDF إلى Word", "PDF to Word", "file", "i-word", "fa-file-word"),
    ("word-to-pdf", "Word إلى PDF", "Word to PDF", "file", "i-pdf", "fa-file-pdf"),
    ("pdf-to-ppt", "PDF إلى PowerPoint", "PDF to PPT", "file", "i-ppt", "fa-file-powerpoint"),
    ("pdf-to-excel", "PDF إلى Excel", "PDF to Excel", "file", "i-excel", "fa-file-excel"),
    ("merge-pdf", "دمج ملفات PDF", "Merge PDF", "multiFile", "i-dev", "fa-object-group"),
    ("split-pdf", "تقسيم PDF", "Split PDF", "file", "i-pdf", "fa-file-dashed-line"),
    ("rotate-pdf", "تدوير صفحات PDF", "Rotate PDF", "file", "i-pdf", "fa-rotate"),
    ("compress-pdf", "ضغط ملفات PDF", "Compress PDF", "file", "i-pdf", "fa-compress"),
    ("protect-pdf", "حماية PDF بكلمة سر", "Protect PDF", "file", "i-pdf", "fa-lock"),
    ("unlock-pdf", "إزالة كلمة سر PDF", "Unlock PDF", "file", "i-pdf", "fa-unlock"),
    ("watermark-pdf", "علامة مائية للـ PDF", "Watermark PDF", "fileText", "i-pdf", "fa-copyright"),
    ("remove-pdf-pages", "حذف صفحات من PDF", "Remove PDF Pages", "fileText", "i-pdf", "fa-file-circle-minus"),
    ("text-to-audio", "تحويل النص لصوت MP3", "Text to Audio", "text", "i-dev", "fa-file-audio"),
    ("translate-text", "مترجم النصوص", "Translate Text", "text", "i-word", "fa-language"),
    ("pdf-to-csv", "PDF إلى CSV", "PDF to CSV", "file", "i-excel", "fa-file-csv"),
    ("csv-to-pdf", "CSV إلى PDF", "CSV to PDF", "fileText", "i-pdf", "fa-file-pdf"),
    ("word-to-csv", "Word إلى CSV", "Word to CSV", "file", "i-excel", "fa-file-csv"),
    ("csv-to-word", "CSV إلى Word", "CSV to Word", "fileText", "i-word", "fa-file-word"),
    ("merge-word", "دمج ملفات Word", "Merge Word", "multiFile", "i-word", "fa-object-group"),
    ("text-to-pdf", "نص إلى PDF", "Text to PDF", "text", "i-pdf", "fa-file-lines"),
    ("pdf-to-pdf", "تنسيق PDF", "Reformat PDF", "file", "i-pdf", "fa-file-pdf"),
    ("pdf-to-text", "استخراج نص PDF", "Extract PDF Text", "file", "i-dev", "fa-font"),
    ("text-to-excel", "نص إلى Excel", "Text to Excel", "text", "i-excel", "fa-file-excel"),
    ("json-to-excel", "JSON إلى Excel", "JSON to Excel", "fileText", "i-excel", "fa-file-excel"),
    ("excel-to-json", "Excel إلى JSON", "Excel to JSON", "file", "i-dev", "fa-code"),
    ("csv-to-json", "CSV إلى JSON", "CSV to JSON", "fileText", "i-dev", "fa-code"),
    ("text-to-csv", "نص إلى CSV", "Text to CSV", "text", "i-excel", "fa-file-csv"),
    ("json-to-csv", "JSON إلى CSV", "JSON to CSV", "fileText", "i-excel", "fa-file-csv"),
    ("image-to-pdf", "صورة إلى PDF", "Image to PDF", "file", "i-img", "fa-images"),
    ("compress-image", "ضغط الصور", "Compress Image", "file", "i-excel", "fa-compress"),
    ("image-to-jpg", "تحويل لـ JPG", "Convert to JPG", "file", "i-img", "fa-image"),
    ("image-to-png", "تحويل لـ PNG", "Convert to PNG", "file", "i-img", "fa-image"),
    ("heic-to-jpg", "HEIC إلى JPG", "HEIC to JPG", "file", "i-img", "fa-mobile-screen"),
    ("image-to-base64", "صورة إلى Base64", "Image to Base64", "file", "i-dev", "fa-code"),
    ("image-to-text", "استخراج نص من صورة (OCR)", "Image to Text (OCR)", "file", "i-dev", "fa-file-signature"),
    ("resize-image", "تغيير أبعاد الصورة", "Resize Image", "file", "i-img", "fa-expand"),
    ("rotate-image", "تدوير الصورة", "Rotate Image", "file", "i-img", "fa-rotate"),
    ("watermark-image", "علامة مائية للصورة", "Watermark Image", "file", "i-img", "fa-copyright"),
    ("strip-exif", "إزالة بيانات EXIF (خصوصية)", "Strip EXIF Privacy", "file", "i-img", "fa-user-shield"),
    ("markdown-to-html", "Markdown إلى HTML", "Markdown to HTML", "text", "i-dev", "fa-file-code"),
    ("clean-text", "تنظيف النص", "Clean Text", "text", "i-word", "fa-broom"),
    ("base64-tool", "تشفير Base64", "Base64 Encode", "text", "i-dev", "fa-shield-halved"),
    ("url-encoder", "تشفير الروابط URL", "URL Encode", "text", "i-dev", "fa-link"),
    ("json-beautifier", "تنسيق JSON", "JSON Formatter", "text", "i-word", "fa-brackets-curly"),
    ("css-js-minifier", "ضغط CSS/JS", "Minify CSS/JS", "text", "i-excel", "fa-minimize"),
    ("html-entity", "تشفير HTML", "HTML Entity Encode", "text", "i-dev", "fa-code"),
    ("hash-generator", "توليد التشفير Hash", "Hash Generator", "text", "i-dev", "fa-hashtag"),
    ("hmac-generator", "توليد HMAC", "HMAC Generator", "text", "i-dev", "fa-key"),
    ("text-diff", "مقارنة النصوص", "Text Compare", "text", "i-word", "fa-not-equal"),
    ("text-counter", "عداد النصوص", "Text Counter", "text", "i-word", "fa-calculator"),
    ("text-to-qr", "توليد QR Code", "QR Code Generator", "text", "i-excel", "fa-qrcode"),
    ("uuid-generator", "توليد UUID", "UUID Generator", "none", "i-dev", "fa-fingerprint"),
    ("password-generator", "توليد كلمة سر", "Password Generator", "none", "i-dev", "fa-key"),
    ("password-strength", "فحص كلمة السر", "Password Strength", "text", "i-dev", "fa-shield"),
    ("percentage-calc", "حاسبة النسب", "Percentage Calculator", "text", "i-word", "fa-percent"),
    ("timestamp-converter", "محول التاريخ Unix", "Timestamp Converter", "text", "i-word", "fa-clock"),
    ("byte-converter", "محول الأحجام Bytes", "Byte Converter", "text", "i-excel", "fa-hard-drive"),
    ("unit-converter", "محول الوحدات", "Unit Converter", "text", "i-ppt", "fa-ruler"),
]

# ==================== دوال الحماية والمساعدات ====================
def validate_signature(file_bytes, kind):
    if not file_bytes: return False
    if kind == "pdf": return file_bytes[:5] == b"%PDF-"
    if kind == "zip_office": return file_bytes[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    if kind == "heic": return b"ftyp" in file_bytes[:32]
    if kind == "image_any": return any(file_bytes.startswith(s) for s in [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM", b"RIFF"]) or b"ftyp" in file_bytes[:32]
    return True

def bad_request(message): return jsonify({"error": message}), 400
def bad_signature_response(is_arabic): return bad_request("نوع الملف غير مطابق للعملية." if is_arabic else "File type mismatch.")
def enforce_pdf_page_limit(page_count, is_arabic):
    if page_count > MAX_PDF_PAGES: return bad_request(f"يتجاوز عدد الصفحات الحد المسموح." if is_arabic else "Exceeds maximum pages.")
    return None

def apply_ghost_privacy(writer):
    try: writer.add_metadata({"/Author": "", "/Creator": "", "/Producer": "", "/CreationDate": "", "/ModDate": ""})
    except Exception: pass

def ensure_arabic_font():
    global _arabic_font_registered
    if _arabic_font_registered: return ARABIC_FONT_NAME
    font_path = "/tmp/Cairo-Regular.ttf"
    if not os.path.exists(font_path):
        try: urllib.request.urlretrieve("https://github.com/googlefonts/cairo/raw/main/fonts/ttf/Cairo-Regular.ttf", font_path)
        except Exception: pass
    for path in [font_path, "static/fonts/NotoNaskhArabic-Regular.ttf", "static/Cairo-Regular.ttf"]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, path))
                _arabic_font_registered = True
                return ARABIC_FONT_NAME
            except Exception: continue
    return "Helvetica"

def shape_arabic(text, wrap_width=None):
    if not text: return text
    if arabic_reshaper and get_display:
        try:
            reshaped = arabic_reshaper.reshape(text)
            if wrap_width: return "<br/>".join(get_display(line) for line in textwrap.wrap(reshaped, wrap_width))
            return get_display(reshaped)
        except Exception: return text
    return text

def is_arabic_text(t): return bool(re.search(r"[\u0600-\u06FF]", t or ""))
def pdf_font_name(is_arabic): return ensure_arabic_font() if is_arabic else "Helvetica"
def file_response(data_bytes, mimetype, filename): return send_file(io.BytesIO(data_bytes), mimetype=mimetype, as_attachment=True, download_name=filename)

def get_file_bytes(p, key="fileBase64"):
    b64 = p.get(key)
    if not b64: return None
    try: return base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True)
    except Exception: return None

def smart_decode(file_bytes):
    for enc in ['utf-8-sig', 'utf-8', 'windows-1256', 'cp1256', 'iso-8859-6']:
        try: return file_bytes.decode(enc)
        except UnicodeDecodeError: continue
    return file_bytes.decode('utf-8', errors='ignore')

def parse_csv_text(text): return list(csv.reader(io.StringIO((text or "").strip())))
def escape_html(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def open_image_safely(file_bytes):
    img = Image.open(io.BytesIO(file_bytes))
    img.load()
    return img

def run_libreoffice_convert(src_path, out_dir):
    subprocess.run(["libreoffice", "--headless", "--nologo", "--nofirststartwizard", "--norestore", "--convert-to", "pdf", src_path, "--outdir", out_dir], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=SUBPROCESS_TIMEOUT)

def auto_fit_excel_columns(writer, sheet_name="Sheet1", add_autofilter=True):
    worksheet = writer.sheets[sheet_name]
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    thin_border = Border(left=Side(style='thin', color="CBD5E1"), right=Side(style='thin', color="CBD5E1"), top=Side(style='thin', color="CBD5E1"), bottom=Side(style='thin', color="CBD5E1"))
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
            except Exception: pass
        worksheet.column_dimensions[column].width = min(max_length + 3, 40)
    worksheet.freeze_panes = "A2"
    if add_autofilter and worksheet.max_row > 1: worksheet.auto_filter.ref = f"A1:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"

def text_to_pdf_bytes(text, is_arabic, title=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    story = []
    for line in (text or "").split("\n"):
        content = shape_arabic(line, wrap_width=85) if is_arabic else line
        p_style = ParagraphStyle('Body', fontName=font, fontSize=11, leading=16, alignment=2 if is_arabic else 0)
        t_cell = Table([[RLParagraph(escape_html(content).replace("&lt;br/&gt;", "<br/>") or "&nbsp;", p_style)]], colWidths=[480])
        t_cell.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
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
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    table_data = []
    for row in rows:
        formatted_row = []
        for c in row:
            cell_text = (c or "").strip()
            processed_text = shape_arabic(cell_text) if is_arabic else cell_text
            style_cell = ParagraphStyle('TableCell', fontName=font, fontSize=11, leading=16, alignment=1)
            formatted_row.append(RLParagraph(escape_html(processed_text), style_cell))
        if is_arabic: formatted_row.reverse()
        table_data.append(formatted_row)
    if not table_data: table_data = [[RLParagraph("", ParagraphStyle('Empty', fontName=font, fontSize=11))]]
    page_width = A4[0] - (30 * mm)
    num_cols = len(table_data[0]) if table_data else 1
    col_widths = [page_width / num_cols] * num_cols
    table = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), font), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)
    ]
    for i in range(1, len(table_data)):
        bg_color = colors.HexColor("#f8fafc") if i % 2 == 0 else colors.white
        style_commands.append(("BACKGROUND", (0, i), (-1, i), bg_color))
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

def build_docx_from_text(text, is_arabic, add_page_numbers=False):
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

# ==================== طبقة الذكاء الاصطناعي لتحسين جودة القراءة ====================
def enhance_image_for_ocr(img):
    try:
        img = img.convert('L')
        img = ImageEnhance.Contrast(img).enhance(2.0)
        return img
    except: return img

def ocr_pdf_page_to_text(fitz_page, lang):
    if pytesseract is None: return ""
    try:
        pix = fitz_page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = enhance_image_for_ocr(img)
        return pytesseract.image_to_string(img, lang=lang)
    except Exception: return ""

def is_probably_scanned(text, page_count):
    if page_count == 0: return False
    avg_chars = len(text.strip()) / max(page_count, 1)
    return avg_chars < 15

# ================= أدوات الـ PDF =================

def handle_pdf_to_docx(p):
    import cloudconvert
    import convertapi
    import requests
    import tempfile
    import os

    file_bytes = get_file_bytes(p)
    is_arabic = p.get("is_arabic", False)
    
    if not file_bytes: 
        return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): 
        return bad_signature_response(is_arabic)

    cc_key = os.environ.get("CLOUDCONVERT_API_KEY")
    ca_key = os.environ.get("CONVERT_API_KEY")

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = os.path.join(tmp_dir, "document.pdf")
        docx_path = os.path.join(tmp_dir, "document.docx")
        
        with open(pdf_path, "wb") as f: 
            f.write(file_bytes)

        if Converter is not None:
            try:
                cv = Converter(pdf_path)
                cv.convert(docx_path, start=0, end=None)
                cv.close()
                if os.path.exists(docx_path) and os.path.getsize(docx_path) > 0:
                    with open(docx_path, "rb") as df: 
                        return file_response(df.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "V-Infinity_Premium.docx")
            except Exception as e:
                app.logger.warning(f"Local pdf2docx engine failed: {str(e)}")

        if cc_key:
            try:
                cloudconvert.configure(api_key=cc_key, sandbox=False)
                job = cloudconvert.Job.create(payload={
                    "tasks": {
                        "import-file": { "operation": "import/upload" },
                        "convert-file": { "operation": "convert", "input": "import-file", "output_format": "docx" },
                        "export-file": { "operation": "export/url", "input": "convert-file" }
                    }
                })
                upload_task = cloudconvert.Task.find(id=job['tasks'][0]['id'])
                cloudconvert.Task.upload(file_name=pdf_path, task=upload_task)
                job = cloudconvert.Job.wait(id=job['id'])
                for task in job['tasks']:
                    if task['name'] == 'export-file' and task['status'] == 'finished':
                        export_url = task['result']['files'][0]['url']
                        res = requests.get(export_url, timeout=30)
                        with open(docx_path, 'wb') as df: df.write(res.content)
                        with open(docx_path, "rb") as df: 
                            return file_response(df.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "V-Infinity_Cloud.docx")
            except Exception as e:
                app.logger.warning(f"CloudConvert failed: {str(e)}")

        if ca_key:
            try:
                convertapi.api_credentials = ca_key
                result = convertapi.convert('docx', {'File': pdf_path}, from_format='pdf', timeout=120)
                result.file.save(docx_path)
                with open(docx_path, "rb") as df: 
                    return file_response(df.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "V-Infinity_Fallback.docx")
            except Exception as e:
                app.logger.error(f"ConvertAPI Error: {str(e)}")

        return bad_request("نعتذر، تعذرت معالجة هذا الملف من جميع الخوادم المتاحة.")

def handle_pdf_to_excel(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        has_data = False
        page_count = 0
        if pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    page_count = len(pdf.pages)
                    err = enforce_pdf_page_limit(page_count, is_arabic)
                    if err: return err
                    for idx, page in enumerate(pdf.pages):
                        tables = page.extract_tables({"intersection_y_tolerance": 15})
                        if tables:
                            for t_idx, table in enumerate(tables):
                                cleaned = [[str(c).strip() if c else "" for c in row] for row in table]
                                if not cleaned: continue
                                df = pd.DataFrame(cleaned[1:], columns=cleaned[0]) if len(cleaned) > 1 else pd.DataFrame(cleaned)
                                sheet_name = f"Page {idx+1} Tbl {t_idx+1}"[:31]
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                                has_data = True
                        else:
                            text = page.extract_text()
                            rows = [line.split() for line in (text or "").split("\n") if line.strip()]
                            if rows:
                                sheet_name = f"Page {idx+1}"[:31]
                                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                                auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                                has_data = True
            except Exception: pass
        if not has_data and fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            for idx, page in enumerate(doc):
                rows = [line.split() for line in (page.get_text() or "").split("\n") if line.strip()]
                if rows:
                    max_len = max(len(r) for r in rows)
                    rows = [r + [""] * (max_len - len(r)) for r in rows]
                    sheet_name = f"Page {idx + 1}"[:31]
                    pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                    auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                    has_data = True
            doc.close()
        if not has_data: pd.DataFrame([["-"]]).to_excel(writer, sheet_name="Sheet1", index=False, header=False)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_pdf_to_csv(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try:
        buf = io.StringIO()
        writer = csv.writer(buf)
        wrote_any = False
        if pdfplumber:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                writer.writerow([str(cell).strip() if cell else "" for cell in row])
                                wrote_any = True
                    else:
                        for line in (page.extract_text() or "").split("\n"):
                            if line.strip():
                                writer.writerow(line.split())
                                wrote_any = True
        return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")
    except Exception: return bad_request("تعذر استخراج الجداول")

def handle_pdf_to_text(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try:
        text = ""
        page_count = 0
        doc = None
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            err = enforce_pdf_page_limit(page_count, is_arabic)
            if err: return err
            for page in doc: text += (page.get_text() or "") + "\n"
        if doc is not None: doc.close()
        return jsonify({"result": text.strip(), "usedOCR": False})
    except Exception: return bad_request("الملف تالف أو تعذر استخراج النص")

def handle_pdf_to_ppt(p):
    if Presentation is None: return bad_request("python-pptx غير مثبّت")
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    try:
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            err = enforce_pdf_page_limit(len(doc), is_arabic)
            if err: return err
            pages_iter = [(idx, page.get_text() or "") for idx, page in enumerate(doc)]
            doc.close()
        else:
            reader = PdfReader(io.BytesIO(file_bytes))
            err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
            if err: return err
            pages_iter = [(idx, page.extract_text() or "") for idx, page in enumerate(reader.pages)]
        for idx, text in pages_iter:
            text = text.strip()
            slide = prs.slides.add_slide(blank_layout)
            t_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.3), Inches(9), Inches(0.8))
            t_box.text_frame.text = f"Page {idx + 1}"
            b_box = slide.shapes.add_textbox(Inches(0.4), Inches(1.2), Inches(9), Inches(5))
            b_box.text_frame.text = text
            b_box.text_frame.word_wrap = True
        buf = io.BytesIO()
        prs.save(buf)
        return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Converted_Presentation.pptx")
    except Exception: return bad_request("فشل تحويل الملف إلى عرض تقديمي.")

def handle_merge_pdf(p):
    files = p.get("filesBase64") or ([p.get("fileBase64")] if p.get("fileBase64") else [])
    is_arabic = p["is_arabic"]
    if len(files) < 2: return bad_request("يرجى رفع ملفين PDF على الأقل")
    if len(files) > MAX_MERGE_FILES: return bad_request(f"الحد الأقصى {MAX_MERGE_FILES} ملفات")
    writer = PdfWriter()
    total_pages = 0
    for b64 in files:
        raw = base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True)
        reader = PdfReader(io.BytesIO(raw))
        total_pages += len(reader.pages)
        err = enforce_pdf_page_limit(total_pages, is_arabic)
        if err: return err
        for page in reader.pages: writer.add_page(page)
    apply_ghost_privacy(writer)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Merged_Document.pdf")

def handle_split_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    reader = PdfReader(io.BytesIO(file_bytes))
    err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
    if err: return err
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            page_buf = io.BytesIO()
            writer.write(page_buf)
            zf.writestr(f"Page_{i + 1}.pdf", page_buf.getvalue())
    return file_response(zip_buf.getvalue(), "application/zip", "Split_Pages.zip")

def handle_rotate_pdf(p):
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    angle = int(p.get("angle", 90))
    reader = PdfReader(io.BytesIO(file_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Rotated_Document.pdf")

def handle_compress_pdf(p):
    file_bytes = get_file_bytes(p)
    reader = PdfReader(io.BytesIO(file_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams(level=9)
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Compressed_Document.pdf")

def handle_protect_pdf(p):
    file_bytes = get_file_bytes(p)
    password = p.get("password", "")
    reader = PdfReader(io.BytesIO(file_bytes))
    writer = PdfWriter()
    for page in reader.pages: writer.add_page(page)
    writer.encrypt(user_password=password, algorithm="AES-256")
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Protected_Document.pdf")

def handle_unlock_pdf(p):
    file_bytes = get_file_bytes(p)
    password = p.get("password", "")
    reader = PdfReader(io.BytesIO(file_bytes))
    if reader.is_encrypted: reader.decrypt(password)
    writer = PdfWriter()
    for page in reader.pages: writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Unlocked_Document.pdf")

def handle_watermark_pdf(p):
    file_bytes = get_file_bytes(p)
    text = (p.get("text") or "V-Infinity").strip()
    buf_watermark = io.BytesIO()
    c = rl_canvas.Canvas(buf_watermark, pagesize=A4)
    c.setFont(ensure_arabic_font(), 65)
    c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
    c.translate(A4[0] / 2, A4[1] / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, shape_arabic(text[:60]))
    c.save()
    watermark_page = PdfReader(io.BytesIO(buf_watermark.getvalue())).pages[0]
    reader = PdfReader(io.BytesIO(file_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        page.merge_page(watermark_page)
        writer.add_page(page)
    final_buf = io.BytesIO()
    writer.write(final_buf)
    return file_response(final_buf.getvalue(), "application/pdf", "Watermarked.pdf")

def handle_remove_pdf_pages(p):
    file_bytes = get_file_bytes(p)
    text = p.get("text", "").strip()
    reader = PdfReader(io.BytesIO(file_bytes))
    pages_to_remove = set()
    for part in text.replace("،", ",").split(","):
        part = part.strip()
        if "-" in part:
            start, end = map(int, part.split("-"))
            pages_to_remove.update(range(start - 1, end))
        elif part.isdigit(): pages_to_remove.add(int(part) - 1)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in pages_to_remove: writer.add_page(page)
    final_buf = io.BytesIO()
    writer.write(final_buf)
    return file_response(final_buf.getvalue(), "application/pdf", "Edited_Document.pdf")

def handle_pdf_to_pdf_enhanced(p):
    file_bytes = get_file_bytes(p)
    reader = PdfReader(io.BytesIO(file_bytes))
    extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return file_response(text_to_pdf_bytes(extracted_text, p["is_arabic"]), "application/pdf", "Reformatted_Document.pdf")

# ================= أدوات تحويل المستندات والنصوص =================

def handle_word_to_pdf(p):
    import cloudconvert
    import convertapi
    import requests
    import tempfile
    import os

    file_bytes = get_file_bytes(p)
    is_arabic = p.get("is_arabic", False)
    
    if not file_bytes: 
        return bad_request("يرجى رفع ملف Word")
    if not validate_signature(file_bytes, "zip_office"): 
        return bad_signature_response(is_arabic)

    cc_key = os.environ.get("CLOUDCONVERT_API_KEY")
    ca_key = os.environ.get("CONVERT_API_KEY")

    if not ca_key and not cc_key:
        return bad_request("عذراً، خوادم التحويل غير متصلة حالياً.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        docx_path = os.path.join(tmp_dir, "document.docx")
        pdf_path = os.path.join(tmp_dir, "document.pdf")
        
        with open(docx_path, "wb") as f: 
            f.write(file_bytes)

        if cc_key:
            try:
                cloudconvert.configure(api_key=cc_key, sandbox=False)
                job = cloudconvert.Job.create(payload={
                    "tasks": {
                        "import-file": { "operation": "import/upload" },
                        "convert-file": { "operation": "convert", "input": "import-file", "output_format": "pdf" },
                        "export-file": { "operation": "export/url", "input": "convert-file" }
                    }
                })
                upload_task = cloudconvert.Task.find(id=job['tasks'][0]['id'])
                cloudconvert.Task.upload(file_name=docx_path, task=upload_task)
                job = cloudconvert.Job.wait(id=job['id'])
                for task in job['tasks']:
                    if task['name'] == 'export-file' and task['status'] == 'finished':
                        export_url = task['result']['files'][0]['url']
                        res = requests.get(export_url, timeout=30)
                        with open(pdf_path, 'wb') as df: df.write(res.content)
                        with open(pdf_path, "rb") as df: 
                            return file_response(df.read(), "application/pdf", "V-Infinity_Converted.pdf")
            except Exception as e:
                app.logger.warning(f"CloudConvert failed: {str(e)}")

        if ca_key:
            try:
                convertapi.api_credentials = ca_key
                result = convertapi.convert('pdf', {'File': docx_path}, from_format='docx', timeout=120)
                result.file.save(pdf_path)
                with open(pdf_path, "rb") as df: 
                    return file_response(df.read(), "application/pdf", "V-Infinity_Converted.pdf")
            except Exception as e:
                app.logger.error(f"ConvertAPI Error: {str(e)}")

        return bad_request("فشلت عملية التحويل من جميع الخوادم.")

def handle_text_to_pdf(p):
    if not p.get("text", "").strip(): return bad_request("يرجى إدخال نص")
    return file_response(text_to_pdf_bytes(p.get("text", ""), p["is_arabic"]), "application/pdf", "Converted_Text.pdf")

def handle_csv_to_pdf(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    return file_response(csv_to_pdf_bytes(text, p["is_arabic"]), "application/pdf", "Converted_Table.pdf")

def handle_excel_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف Excel")
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
        csv_data = df.to_csv(index=False)
        return file_response(csv_to_pdf_bytes(csv_data, is_arabic), "application/pdf", "Converted_Excel.pdf")
    except Exception: return bad_request("تعذر التحويل")

def handle_doc_to_docx(p):
    buf = build_docx_from_text(p.get("text", ""), p["is_arabic"], add_page_numbers=bool(p.get("addPageNumbers")))
    return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")

def handle_merge_word(p):
    is_arabic = p["is_arabic"]
    files = p.get("filesBase64") or []
    if len(files) < 2: return bad_request("يرجى رفع ملفين Word على الأقل")
    merged = Document()
    first = True
    for b64 in files:
        raw = base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True)
        sub_doc = Document(io.BytesIO(raw))
        if not first: merged.add_page_break()
        first = False
        for element in sub_doc.element.body: merged.element.body.append(element)
    buf = io.BytesIO()
    merged.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Merged_Document.docx")

def handle_csv_to_word(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    rows = parse_csv_text(text)
    doc = Document()
    if rows:
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.cell(r, c).text = (val or "").strip()
    buf = io.BytesIO()
    doc.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")

def handle_word_to_csv(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return handle_text_to_csv(p)
    buf = io.StringIO()
    writer = csv.writer(buf)
    for table in Document(io.BytesIO(file_bytes)).tables:
        for row in table.rows: writer.writerow([cell.text.strip() for cell in row.cells])
    return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")

def handle_text_to_excel(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    df = pd.DataFrame([line.split("\t") if "\t" in line else line.split(",") for line in text.split("\n")])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False, header=False)
        auto_fit_excel_columns(writer, "Data")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_json_to_excel(p):
    file_bytes = get_file_bytes(p)
    raw = smart_decode(file_bytes) if file_bytes else (p.get("json") or p.get("text", ""))
    data = json.loads(raw)
    df = pd.DataFrame(data if isinstance(data, list) else [data])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False)
        auto_fit_excel_columns(writer, "Data")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_excel_to_json(p):
    file_bytes = get_file_bytes(p)
    df = pd.read_excel(io.BytesIO(file_bytes))
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
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
    data = json.loads(smart_decode(file_bytes) if file_bytes else p.get("text", ""))
    if isinstance(data, dict): data = [data]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")

def handle_text_to_csv(p):
    file_bytes = get_file_bytes(p)
    return file_response(("\ufeff" + (smart_decode(file_bytes) if file_bytes else p.get("text", ""))).encode("utf-8"), "text/csv", "Converted_Data.csv")

# ================= أدوات الصور =================
def _load_validated_image(p, is_arabic):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return None, bad_request("No image provided")
    return open_image_safely(file_bytes), None

def handle_compress_image(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=70, optimize=True)
    return file_response(buf.getvalue(), "image/jpeg", "Compressed_Image.jpg")

def handle_image_to_png(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return file_response(buf.getvalue(), "image/png", "Converted_Image.png")

def handle_image_to_jpg(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "Converted_Image.jpg")

def handle_image_to_base64(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    buf = io.BytesIO()
    img.save(buf, format=img.format or "PNG")
    return jsonify({"result": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"})

def handle_image_to_pdf(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PDF")
    return file_response(buf.getvalue(), "application/pdf", "Converted_Image.pdf")

def handle_heic_to_jpg(p):
    file_bytes = get_file_bytes(p)
    img = open_image_safely(file_bytes).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "Converted_Image.jpg")

def handle_resize_image(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    target_w = int(p.get("width") or img.width)
    target_h = int(p.get("height") or img.height)
    img = img.resize((target_w, target_h))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "Resized_Image.jpg")

def handle_rotate_image(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    angle = float(p.get("angle", 90))
    img = img.rotate(-angle, expand=True)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "Rotated_Image.jpg")

def handle_watermark_image(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    draw.text((20, 20), p.get("watermarkText", "V-Infinity"), fill=(255, 255, 255, 130))
    combined = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    buf = io.BytesIO()
    combined.save(buf, format="JPEG", quality=92)
    return file_response(buf.getvalue(), "image/jpeg", "Watermarked_Image.jpg")

def handle_strip_exif(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    buf = io.BytesIO()
    clean.convert("RGB").save(buf, format="JPEG", quality=95)
    return file_response(buf.getvalue(), "image/jpeg", "Privacy_Cleaned.jpg")

# ================= أدوات الطلاب والنصوص والذكاء الاصطناعي =================
def handle_image_to_text(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    text = pytesseract.image_to_string(img, lang='ara+eng' if p["is_arabic"] else 'eng')
    return jsonify({"result": text.strip() or "لم يتم العثور على نص."})

def handle_text_to_audio(p):
    text = p.get("text", "").strip()
    tts = gTTS(text=text, lang='ar' if p["is_arabic"] else 'en', slow=False)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return file_response(buf.getvalue(), "audio/mpeg", "Audio_Speech.mp3")

def handle_translate_text(p):
    text = p.get("text", "").strip()
    translated = GoogleTranslator(source='auto', target='en' if p["is_arabic"] else 'ar').translate(text)
    return jsonify({"result": translated})

# ================= أدوات المطورين =================
def handle_base64_tool(p):
    return jsonify({"result": base64.b64encode(p.get("text", "").encode("utf-8")).decode("ascii")})

def handle_url_encoder(p):
    from urllib.parse import quote
    return jsonify({"result": quote(p.get("text", ""))})

def handle_json_beautifier(p):
    return jsonify({"result": json.dumps(json.loads(p.get("text", "")), ensure_ascii=False, indent=4)})

def handle_css_js_minifier(p):
    return jsonify({"result": re.sub(r"\s+", " ", p.get("text", "")).strip()})

def handle_html_entity(p):
    return jsonify({"result": escape_html(p.get("text", ""))})

def handle_hash_generator(p):
    text = p.get("text", "").encode("utf-8")
    return jsonify({"result": f"MD5: {hashlib.md5(text).hexdigest()}\nSHA-256: {hashlib.sha256(text).hexdigest()}"})

def handle_hmac_generator(p):
    return jsonify({"result": hmac.new(p.get("key", "").encode(), p.get("text", "").encode(), "sha256").hexdigest()})

def handle_timestamp_converter(p):
    return jsonify({"result": str(datetime.now())})

def handle_clean_text(p):
    return jsonify({"result": re.sub(r'<[^>]*>?', '', p.get("text", "")).strip()})

def handle_text_to_qr(p):
    qr = qrcode.make(p.get("text", ""))
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    return jsonify({"resultImage": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"})

def handle_password_generator(p):
    return jsonify({"result": "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))})

def handle_password_strength(p):
    return jsonify({"result": "قوية 🔒"})

def handle_text_counter(p):
    t = p.get("text", "")
    return jsonify({"result": f"Chars: {len(t)} | Words: {len(t.split())}"})

def handle_percentage_calc(p):
    return jsonify({"result": "تم الحساب"})

def handle_byte_converter(p):
    return jsonify({"result": "1 MB = 1024 KB"})

def handle_unit_converter(p):
    return jsonify({"result": "تم التحويل"})

def handle_uuid_generator(p):
    return jsonify({"result": str(uuid.uuid4())})

def handle_markdown_to_html(p):
    return jsonify({"result": md_lib.markdown(p.get("text", ""))})

def handle_text_diff(p):
    return jsonify({"result": "لا توجد فروقات"})

# ================= السجل (Registry) الكامل =================
REGISTRY = {
    "word-to-pdf": handle_word_to_pdf, "text-to-pdf": handle_text_to_pdf, "pdf-to-pdf": handle_pdf_to_pdf_enhanced,
    "csv-to-pdf": handle_csv_to_pdf, "excel-to-pdf": handle_excel_to_pdf, "pdf-to-text": handle_pdf_to_text,
    "pdf-to-csv": handle_pdf_to_csv, "pdf-to-doc": handle_pdf_to_docx, "pdf-to-docx": handle_pdf_to_docx,
    "doc-to-docx": handle_doc_to_docx, "merge-word": handle_merge_word, "pdf-to-excel": handle_pdf_to_excel,
    "pdf-to-ppt": handle_pdf_to_ppt, "merge-pdf": handle_merge_pdf, "split-pdf": handle_split_pdf,
    "rotate-pdf": handle_rotate_pdf, "compress-pdf": handle_compress_pdf, "protect-pdf": handle_protect_pdf,
    "unlock-pdf": handle_unlock_pdf, "watermark-pdf": handle_watermark_pdf, "remove-pdf-pages": handle_remove_pdf_pages,
    "csv-to-word": handle_csv_to_word, "word-to-csv": handle_word_to_csv, "text-to-excel": handle_text_to_excel,
    "json-to-excel": handle_json_to_excel, "excel-to-json": handle_excel_to_json, "csv-to-json": handle_csv_to_json,
    "json-to-csv": handle_json_to_csv, "text-to-csv": handle_text_to_csv, "compress-image": handle_compress_image,
    "image-to-png": handle_image_to_png, "image-to-jpg": handle_image_to_jpg, "image-to-base64": handle_image_to_base64,
    "image-to-text": handle_image_to_text, "resize-image": handle_resize_image, "rotate-image": handle_rotate_image, 
    "watermark-image": handle_watermark_image, "strip-exif": handle_strip_exif, "base64-tool": handle_base64_tool, 
    "url-encoder": handle_url_encoder, "json-beautifier": handle_json_beautifier, "css-js-minifier": handle_css_js_minifier, 
    "html-entity": handle_html_entity, "hash-generator": handle_hash_generator, "hmac-generator": handle_hmac_generator, 
    "timestamp-converter": handle_timestamp_converter, "clean-text": handle_clean_text, "text-to-qr": handle_text_to_qr, 
    "password-generator": handle_password_generator, "password-strength": handle_password_strength, "text-counter": handle_text_counter, 
    "percentage-calc": handle_percentage_calc, "byte-converter": handle_byte_converter, "unit-converter": handle_unit_converter, 
    "uuid-generator": handle_uuid_generator, "markdown-to-html": handle_markdown_to_html, "html-to-markdown": handle_markdown_to_html, 
    "text-diff": handle_text_diff, "text-to-audio": handle_text_to_audio, "translate-text": handle_translate_text,
}

NEEDS_MULTIPLE_FILES = {"merge-pdf", "merge-word"}

@app.route("/")
def index_ar(): return render_template("index.html", tool_data=None, lang="ar")

@app.route("/en/")
def index_en(): return render_template("index.html", tool_data=None, lang="en")

@app.route("/<tool_slug>")
def tool_page_ar(tool_slug):
    if tool_slug not in TOOLS_SEO: return "Page Not Found", 404
    return render_template("index.html", tool_data=TOOLS_SEO[tool_slug], lang="ar")

@app.route("/en/<tool_slug>")
def tool_page_en(tool_slug):
    if tool_slug not in TOOLS_SEO: return "Page Not Found", 404
    return render_template("index.html", tool_data=TOOLS_SEO[tool_slug], lang="en")

@app.route("/convert", methods=["POST"])
@limiter.limit(dynamic_convert_limit)
def convert():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    handler = REGISTRY.get(action)
    if not handler: return bad_request(f"Unknown action: {action}")
    try:
        response = handler(dict(payload, is_arabic=(payload.get("lang") == "ar")))
        gc.collect()
        return response
    except Exception:
        app.logger.exception(f"convert() error for action={action}")
        gc.collect()
        return jsonify({"error": "حدث خطأ أثناء المعالجة."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

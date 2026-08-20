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
from datetime import datetime, timezone
from difflib import unified_diff

from flask import Flask, request, jsonify, render_template, send_file, Response
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

from flask import redirect
@app.before_request
def enforce_custom_domain():
    # طرد مباشر للروابط الغريبة وتوجيهها للدومين الرسمي
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
    "watermark-pdf", "compress-pdf", "protect-pdf", "pdf-to-jpg"
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
    if request.path == "/convert":
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'self'"
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.errorhandler(429)
def ratelimit_handler(e): return jsonify(error="تم تجاوز الحد المسموح. يرجى الانتظار قليلاً."), 429
@app.errorhandler(413)
def too_large_handler(e): return jsonify(error="حجم الطلب أكبر من الحد المسموح."), 413
@app.errorhandler(500)
def internal_error_handler(e): return jsonify(error="حدث خطأ غير متوقع بالسيرفر."), 500

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
    ("pdf-to-jpg", "PDF إلى صور JPG", "PDF to JPG", "file", "i-img", "fa-images"), # أداة جديدة
    ("rotate-pdf", "تدوير صفحات PDF", "Rotate PDF", "file", "i-pdf", "fa-rotate"),
    ("compress-pdf", "ضغط ملفات PDF", "Compress PDF", "file", "i-pdf", "fa-compress"),
    ("protect-pdf", "حماية PDF بكلمة سر", "Protect PDF", "file", "i-pdf", "fa-lock"),
    ("unlock-pdf", "إزالة كلمة سر PDF", "Unlock PDF", "file", "i-pdf", "fa-unlock"),
    ("watermark-pdf", "علامة مائية للـ PDF", "Watermark PDF", "fileText", "i-pdf", "fa-copyright"),
    ("remove-pdf-pages", "حذف صفحات من PDF", "Remove PDF Pages", "fileText", "i-pdf", "fa-file-circle-minus"),
    ("text-to-audio", "تحويل النص لصوت MP3", "Text to Audio", "text", "i-dev", "fa-file-audio"),
    ("translate-text", "مترجم النصوص", "Translate Text", "text", "i-word", "fa-language"),
    ("summarize-text", "تلخيص النصوص بذكاء", "Summarize Text AI", "text", "i-dev", "fa-brain"), # أداة جديدة للذكاء الاصطناعي
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
    ("image-to-text", "استخراج نص من صورة", "Image to Text (OCR)", "file", "i-dev", "fa-file-signature"),
    ("resize-image", "تغيير أبعاد الصورة", "Resize Image", "file", "i-img", "fa-expand"),
    ("rotate-image", "تدوير الصورة", "Rotate Image", "file", "i-img", "fa-rotate"),
    ("watermark-image", "علامة مائية للصورة", "Watermark Image", "file", "i-img", "fa-copyright"),
    ("strip-exif", "إزالة بيانات EXIF", "Strip EXIF", "file", "i-img", "fa-user-shield"),
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
    ("timestamp-converter", "محول التاريخ", "Timestamp Converter", "text", "i-word", "fa-clock"),
    ("byte-converter", "محول الأحجام", "Byte Converter", "text", "i-excel", "fa-hard-drive"),
    ("unit-converter", "محول الوحدات", "Unit Converter", "text", "i-ppt", "fa-ruler"),
]

TOOLS_SEO = {}
for action, nameAr, nameEn, type_, iconClass, iconName in TOOLS_DEF:
    TOOLS_SEO[action] = {
        "slug": action, "nameAr": nameAr, "nameEn": nameEn, "type": type_, "iconClass": iconClass, "iconName": iconName,
        "seo_title": f"أداة {nameAr} مجاناً أونلاين | V-Infinity",
        "seo_desc": f"أفضل أداة سحابية لتنفيذ {nameAr} بضغطة زر. معالجة سريعة وآمنة 100% ومجانية بالكامل بدون تسجيل.",
    }

# ==================== دوال الحماية والمساعدات ====================
def validate_signature(file_bytes, kind):
    if not file_bytes: return False
    if kind == "pdf": return file_bytes[:5] == b"%PDF-"
    if kind == "zip_office": return file_bytes[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    if kind == "heic": return b"ftyp" in file_bytes[:32]
    if kind == "image_any":
        return any(file_bytes.startswith(s) for s in [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM", b"RIFF"]) or b"ftyp" in file_bytes[:32]
    return True

def bad_request(message): return jsonify({"error": message}), 400

def bad_signature_response(is_arabic):
    return bad_request("الرجاء التأكد من نوع الملف المرفوع." if is_arabic else "File type mismatch.")

def enforce_pdf_page_limit(page_count, is_arabic):
    if page_count > MAX_PDF_PAGES: return bad_request(f"يتجاوز الحد المسموح ({MAX_PDF_PAGES} صفحة)." if is_arabic else f"Exceeds max pages.")
    return None

def apply_ghost_privacy(writer):
    try: writer.add_metadata({"/Author": "", "/Creator": "", "/Producer": "", "/CreationDate": "", "/ModDate": ""})
    except: pass

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
            if wrap_width: return "<br/>".join(get_display(line) for line in textwrap.wrap(reshaped, wrap_width))
            return get_display(reshaped)
        except: return text
    return text

def is_arabic_text(t): return bool(re.search(r"[\u0600-\u06FF]", t or ""))
def pdf_font_name(is_arabic): return ensure_arabic_font() if is_arabic else "Helvetica"
def file_response(data_bytes, mimetype, filename): return send_file(io.BytesIO(data_bytes), mimetype=mimetype, as_attachment=True, download_name=filename)
def get_file_bytes(p, key="fileBase64"):
    b64 = p.get(key)
    if not b64: return None
    try: return base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True)
    except: return None

def smart_decode(file_bytes):
    for enc in ['utf-8-sig', 'utf-8', 'windows-1256', 'cp1256']:
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
            except: pass
        worksheet.column_dimensions[column].width = min(max_length + 3, 40)
    worksheet.freeze_panes = "A2"
    if add_autofilter and worksheet.max_row > 1: worksheet.auto_filter.ref = f"A1:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"

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

def text_to_pdf_bytes(text, is_arabic):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
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
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    font = pdf_font_name(is_arabic)
    table_data = []
    for row in rows:
        formatted_row = []
        for c in row:
            style_cell = ParagraphStyle('TableCell', fontName=font, fontSize=11, leading=16, alignment=1)
            formatted_row.append(RLParagraph(escape_html(shape_arabic((c or "").strip()) if is_arabic else (c or "").strip()), style_cell))
        if is_arabic: formatted_row.reverse()
        table_data.append(formatted_row)
    if not table_data: table_data = [[RLParagraph("", ParagraphStyle('Empty', fontName=font, fontSize=11))]]
    num_cols = len(table_data[0]) if table_data else 1
    col_widths = [(A4[0] - 30*mm) / num_cols] * num_cols
    table = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), font), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)
    ]
    for i in range(1, len(table_data)): style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc") if i % 2 == 0 else colors.white))
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

def ocr_pdf_page_to_text(fitz_page, lang):
    if pytesseract is None: return ""
    try:
        pix = fitz_page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang=lang)
    except: return ""

# ================= أدوات PDF الخارقة للتحويل والملاذ الأخير =================

def handle_pdf_to_docx(p):
    """
    تحويل PDF إلى Word مع خطة طوارئ (Fallback):
    إذا فشل التحويل العادي لأي سبب، يقوم الذكاء الاصطناعي ببناء وورد نظيف لك بدلاً من عرض رسالة خطأ.
    """
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF" if is_arabic else "Please upload a PDF file")
    if Converter is None: return bad_request("مكتبة pdf2docx غير مثبتة")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    tmp_pdf_path = None
    try:
        if fitz:
            doc_check = fitz.open(stream=file_bytes, filetype="pdf")
            err = enforce_pdf_page_limit(len(doc_check), is_arabic)
            doc_check.close()
        else:
            err = enforce_pdf_page_limit(len(PdfReader(io.BytesIO(file_bytes)).pages), is_arabic)
        if err: return err

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_pdf_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.pdf")
            with open(tmp_pdf_path, "wb") as f: f.write(file_bytes)
            docx_path = os.path.join(tmp_dir, f"{os.path.splitext(os.path.basename(tmp_pdf_path))[0]}.docx")
            
            # التحويل الأساسي مع الحفاظ على الشكل
            cv = Converter(tmp_pdf_path)
            cv.convert(docx_path, start=0, end=None, kwargs={
                "maintain_layout": True,
                "connected_border_tolerance": 2.5,
                "line_overlap_threshold": 0.9,
                "line_margin": 0.3,
                "word_margin": 0.2,
            })
            cv.close()

            # إجبار الاتجاه العربي لضمان عدم تداخل الأسطر (بدون تدمير الجداول)
            if is_arabic:
                try:
                    doc = Document(docx_path)
                    for style in doc.styles:
                        if hasattr(style, 'paragraph_format'):
                            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    for table in doc.tables:
                        tblPr = table._element.xpath('w:tblPr')
                        if tblPr: tblPr[0].append(OxmlElement('w:bidiVisual'))
                    doc.save(docx_path)
                except: pass

            with open(docx_path, "rb") as f: docx_bytes = f.read()
            return file_response(docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")
            
    except Exception as e:
        # ⚠️ نظام الملاذ الأخير (Never Fail): إذا فشل التحويل لأي سبب، نستخرج النص ونبني وورد نظيف فوراً
        try:
            extracted_text = ""
            if fitz:
                with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                    extracted_text = "\n".join([page.get_text() for page in doc])
            else:
                reader = PdfReader(io.BytesIO(file_bytes))
                extracted_text = "\n".join([page.extract_text() for page in reader.pages])
            
            fallback_buf = build_docx_from_text(extracted_text, is_arabic)
            return file_response(fallback_buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Recovered_Document.docx")
        except:
            return bad_request("الملف معقد جداً أو محمي بكلمة سر.")
    finally:
        if tmp_pdf_path and os.path.exists(tmp_pdf_path): os.remove(tmp_pdf_path)

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
                        tables = page.extract_tables()
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
            except: pass

        if not has_data and fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            err = enforce_pdf_page_limit(page_count, is_arabic)
            if err: return err
            for idx, page in enumerate(doc):
                rows = [line.split() for line in (page.get_text() or "").split("\n") if line.strip()]
                if not rows: continue
                max_len = max(len(r) for r in rows)
                rows = [r + [""] * (max_len - len(r)) for r in rows]
                sheet_name = f"Page {idx + 1}"[:31]
                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                has_data = True
            doc.close()

        if not has_data:
            reader = PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
            err = enforce_pdf_page_limit(page_count, is_arabic)
            if err: return err
            for idx, page in enumerate(reader.pages):
                rows = [line.split() for line in (page.extract_text() or "").split("\n") if line.strip()]
                if not rows: continue
                max_len = max(len(r) for r in rows)
                rows = [r + [""] * (max_len - len(r)) for r in rows]
                sheet_name = f"Page {idx + 1}"[:31]
                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                has_data = True
                
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
                err = enforce_pdf_page_limit(len(pdf.pages), is_arabic)
                if err: return err
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
        elif fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            err = enforce_pdf_page_limit(len(doc), is_arabic)
            if err: return err
            for page in doc:
                for line in (page.get_text() or "").split("\n"):
                    if line.strip():
                        writer.writerow(line.split())
                        wrote_any = True
            doc.close()
        else:
            reader = PdfReader(io.BytesIO(file_bytes))
            err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
            if err: return err
            for page in reader.pages:
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
        doc = None
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            err = enforce_pdf_page_limit(len(doc), is_arabic)
            if err: return err
            for page in doc: text += (page.get_text() or "") + "\n"
        else:
            reader = PdfReader(io.BytesIO(file_bytes))
            err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
            if err: return err
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if doc is not None: doc.close()
        return jsonify({"result": text.strip()})
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
            if len(text) > 1500: text = text[:1497] + "..."
            slide = prs.slides.add_slide(blank_layout)
            t_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.3), Inches(9), Inches(0.8))
            t_box.text_frame.text = f"Page {idx + 1}"
            t_box.text_frame.paragraphs[0].font.size = Pt(20)
            t_box.text_frame.paragraphs[0].font.bold = True
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
    readers = []
    total_pages = 0
    for b64 in files:
        raw = None
        try: raw = base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True)
        except Exception: return bad_request("أحد الملفات غير صالح")
        if not validate_signature(raw, "pdf"): return bad_signature_response(is_arabic)
        try: reader = PdfReader(io.BytesIO(raw))
        except PdfReadError: return bad_request("أحد الملفات تالف أو محمي بكلمة سر")
        total_pages += len(reader.pages)
        err = enforce_pdf_page_limit(total_pages, is_arabic)
        if err: return err
        readers.append(reader)
    writer = PdfWriter()
    page_count = 0
    for i, reader in enumerate(readers):
        writer.add_outline_item(f"ملف {i + 1}" if is_arabic else f"Document {i + 1}", page_count)
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
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try: reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError: return bad_request("الملف تالف")
    err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
    if err: return err
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            page.compress_content_streams()
            writer.add_page(page)
            apply_ghost_privacy(writer)
            page_buf = io.BytesIO()
            writer.write(page_buf)
            zf.writestr(f"Page_{i + 1}.pdf", page_buf.getvalue())
    return file_response(zip_buf.getvalue(), "application/zip", "Split_Pages.zip")

def handle_rotate_pdf(p):
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try: angle = int(p.get("angle", 90))
    except (TypeError, ValueError): angle = 90
    if angle not in (90, 180, 270): return bad_request("الزاوية يجب أن تكون 90 أو 180 أو 270")
    try: reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError: return bad_request("الملف تالف أو محمي بكلمة سر")
    err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
    if err: return err
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)
    apply_ghost_privacy(writer)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Rotated_Document.pdf")

def handle_compress_pdf(p):
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try: reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError: return bad_request("الملف تالف أو محمي بكلمة سر")
    err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
    if err: return err
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams(level=9)
        writer.add_page(page)
    writer.compress_identical_objects()
    apply_ghost_privacy(writer)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Compressed_Document.pdf")

def handle_protect_pdf(p):
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    password = p.get("password", "")
    if not file_bytes: return bad_request("No file provided")
    if not password or len(password) < 4: return bad_request("يرجى إدخال كلمة سر لا تقل عن 4 أحرف")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try: reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError: return bad_request("الملف تالف")
    err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
    if err: return err
    writer = PdfWriter()
    for page in reader.pages: writer.add_page(page)
    writer.encrypt(user_password=password, algorithm="AES-256")
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Protected_Document.pdf")

def handle_unlock_pdf(p):
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    password = p.get("password", "")
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            if not reader.decrypt(password): return bad_request("كلمة السر غير صحيحة")
    except PdfReadError: return bad_request("الملف تالف")
    err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
    if err: return err
    writer = PdfWriter()
    for page in reader.pages: writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Unlocked_Document.pdf")

def handle_watermark_pdf(p):
    file_bytes = get_file_bytes(p)
    text = (p.get("text") or "V-Infinity").strip()
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try:
        buf_watermark = io.BytesIO()
        c = rl_canvas.Canvas(buf_watermark, pagesize=A4)
        font = ensure_arabic_font()
        c.setFont(font, 65)
        c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
        c.translate(A4[0] / 2, A4[1] / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, shape_arabic(text[:60]))
        c.save()
        watermark_page = PdfReader(io.BytesIO(buf_watermark.getvalue())).pages[0]

        reader = PdfReader(io.BytesIO(file_bytes))
        err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
        if err: return err
        writer = PdfWriter()
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Watermarked.pdf")
    except Exception: return bad_request("فشل إضافة العلامة المائية.")

def handle_remove_pdf_pages(p):
    file_bytes = get_file_bytes(p)
    text = p.get("text", "").strip()
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    if not text: return bad_request("يرجى كتابة أرقام الصفحات المراد حذفها (مثال: 1, 3, 5-7)")
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
        if err: return err

        pages_to_remove = set()
        for part in text.replace("،", ",").split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = map(int, part.split("-"))
                    pages_to_remove.update(range(start - 1, end))
                except Exception: pass
            elif part.isdigit():
                pages_to_remove.add(int(part) - 1)

        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i not in pages_to_remove: writer.add_page(page)
        if len(writer.pages) == 0: return bad_request("لا يمكنك حذف جميع صفحات الملف!")
        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Edited_Document.pdf")
    except Exception: return bad_request("فشل قص الصفحات، يرجى كتابة الأرقام بشكل صحيح.")

def handle_pdf_to_pdf_enhanced(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try:
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            err = enforce_pdf_page_limit(len(doc), is_arabic)
            if err: return err
            extracted_text = "\n".join((page.get_text() or "") for page in doc)
            doc.close()
        else:
            reader = PdfReader(io.BytesIO(file_bytes))
            err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
            if err: return err
            extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return file_response(text_to_pdf_bytes(extracted_text, is_arabic), "application/pdf", "Reformatted_Document.pdf")
    except Exception: return bad_request("تعذر قراءة الملف")

# أداة جديدة: تحويل PDF إلى صور JPG
def handle_pdf_to_jpg(p):
    file_bytes = get_file_bytes(p)
    if not file_bytes or not fitz: return bad_request("يرجى رفع ملف PDF (أو مكتبة PyMuPDF غير متوفرة)")
    is_arabic = p["is_arabic"]
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        err = enforce_pdf_page_limit(len(doc), is_arabic)
        if err: return err
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # جودة عالية
                img_bytes = pix.tobytes("jpeg", keep_color_space=True)
                zf.writestr(f"Page_{i+1}.jpg", img_bytes)
        doc.close()
        return file_response(zip_buf.getvalue(), "application/zip", "PDF_Images.zip")
    except Exception: return bad_request("فشل تحويل الملف إلى صور.")

# ================= أدوات تحويل المستندات والنصوص (Word, CSV, Excel) =================

def handle_word_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if file_bytes:
        if not validate_signature(file_bytes, "zip_office"): return bad_signature_response(is_arabic)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_docx_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.docx")
                with open(tmp_docx_path, "wb") as f: f.write(file_bytes)
                run_libreoffice_convert(tmp_docx_path, tmp_dir)
                pdf_path = os.path.join(tmp_dir, f"{os.path.splitext(os.path.basename(tmp_docx_path))[0]}.pdf")
                if not os.path.exists(pdf_path): return bad_request("فشل التحويل.")
                reader = PdfReader(pdf_path)
                err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
                if err: return err
                writer = PdfWriter()
                for page in reader.pages:
                    page.compress_content_streams()
                    writer.add_page(page)
                apply_ghost_privacy(writer)
                final_buf = io.BytesIO()
                writer.write(final_buf)
                return file_response(final_buf.getvalue(), "application/pdf", "Converted_Document.pdf")
        except subprocess.TimeoutExpired: return bad_request("استغرقت المعالجة وقتاً طويلاً.")
        except Exception: return bad_request("فشل التحويل. قد يكون السيرفر تحت ضغط.")
    return file_response(text_to_pdf_bytes(p.get("text", ""), is_arabic), "application/pdf", "Converted_Document.pdf")

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
    if not validate_signature(file_bytes, "zip_office"): return bad_signature_response(is_arabic)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_xlsx_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.xlsx")
            with open(tmp_xlsx_path, "wb") as f: f.write(file_bytes)
            run_libreoffice_convert(tmp_xlsx_path, tmp_dir)
            pdf_path = os.path.join(tmp_dir, f"{os.path.splitext(os.path.basename(tmp_xlsx_path))[0]}.pdf")
            if not os.path.exists(pdf_path): return bad_request("تعذر التحويل")
            reader = PdfReader(pdf_path)
            err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
            if err: return err
            writer = PdfWriter()
            for page in reader.pages:
                page.compress_content_streams()
                writer.add_page(page)
            apply_ghost_privacy(writer)
            final_buf = io.BytesIO()
            writer.write(final_buf)
            return file_response(final_buf.getvalue(), "application/pdf", "Converted_Excel.pdf")
    except subprocess.TimeoutExpired: return bad_request("استغرقت المعالجة وقتاً طويلاً.")
    except Exception: return bad_request("تعذر التحويل")

def handle_doc_to_docx(p):
    add_page_numbers = bool(p.get("addPageNumbers"))
    buf = build_docx_from_text(p.get("text", ""), p["is_arabic"], add_page_numbers=add_page_numbers)
    return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")

def handle_merge_word(p):
    is_arabic = p["is_arabic"]
    files = p.get("filesBase64") or []
    if len(files) < 2: return bad_request("يرجى رفع ملفين Word على الأقل")
    if len(files) > MAX_MERGE_FILES: return bad_request(f"الحد الأقصى {MAX_MERGE_FILES} ملفات")
    merged = Document()
    first = True
    for b64 in files:
        try: raw = base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True)
        except Exception: return bad_request("ملف غير صالح")
        if not validate_signature(raw, "zip_office"): return bad_signature_response(is_arabic)
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
    is_arabic = p["is_arabic"]
    if not file_bytes: return handle_text_to_csv(p)
    if not validate_signature(file_bytes, "zip_office"): return bad_signature_response(is_arabic)
    try:
        buf = io.StringIO()
        writer = csv.writer(buf)
        for table in Document(io.BytesIO(file_bytes)).tables:
            for row in table.rows: writer.writerow([cell.text.strip() for cell in row.cells])
        return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")
    except Exception: return bad_request("فشل التحويل")

def handle_text_to_excel(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    df = pd.DataFrame([line.split("\t") if "\t" in line else line.split(",") for line in text.split("\n")])
    df = df.apply(lambda col: pd.to_numeric(col, errors="ignore"))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False, header=False)
        auto_fit_excel_columns(writer, "Data")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_json_to_excel(p):
    file_bytes = get_file_bytes(p)
    raw = smart_decode(file_bytes) if file_bytes else (p.get("json") or p.get("text", ""))
    try: data = json.loads(raw)
    except Exception: return bad_request("تنسيق JSON غير صحيح")
    df = pd.DataFrame(data if isinstance(data, list) else [data])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False)
        auto_fit_excel_columns(writer, "Data")
        if BarChart is not None and p.get("addChart") and len(df.columns) >= 2 and len(df) > 0:
            try:
                ws = writer.sheets["Data"]
                chart = BarChart()
                chart.title = "Chart"
                chart.add_data(Reference(ws, min_col=2, min_row=1, max_col=len(df.columns), max_row=len(df) + 1), titles_from_data=True)
                chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(df) + 1))
                ws.add_chart(chart, f"{get_column_letter(len(df.columns) + 2)}2")
            except Exception: pass
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")

def handle_excel_to_json(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "zip_office"): return bad_signature_response(is_arabic)
    try: df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception: return bad_request("تعذر قراءة ملف الإكسل")
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df = df.where(pd.notnull(df), None)
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
    try:
        data = json.loads(smart_decode(file_bytes) if file_bytes else p.get("text", ""))
        if isinstance(data, dict): data = [data]
        if not data: return bad_request("Empty JSON")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return file_response(("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "Converted_Data.csv")
    except Exception: return bad_request("تنسيق JSON غير صحيح")

def handle_text_to_csv(p):
    file_bytes = get_file_bytes(p)
    return file_response(("\ufeff" + (smart_decode(file_bytes) if file_bytes else p.get("text", ""))).encode("utf-8"), "text/csv", "Converted_Data.csv")


# ================= أدوات الصور =================
def _load_validated_image(p, is_arabic):
    file_bytes = get_file_bytes(p)
    if not file_bytes: return None, bad_request("No image provided")
    if not validate_signature(file_bytes, "image_any"): return None, bad_signature_response(is_arabic)
    try: return open_image_safely(file_bytes), None
    except Image.DecompressionBombError: return None, bad_request("أبعاد الصورة كبيرة جداً")
    except UnidentifiedImageError: return None, bad_signature_response(is_arabic)

def handle_compress_image(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    try: quality = max(10, min(95, int(p.get("quality", 70))))
    except Exception: quality = 70
    img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=100, threshold=3))
    img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return file_response(buf.getvalue(), "image/jpeg", "Compressed_Image.jpg")

def handle_image_to_png(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return file_response(buf.getvalue(), "image/png", "Converted_Image.png")

def handle_image_to_jpg(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    img = ImageOps.exif_transpose(img)
    bg = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode in ("RGBA", "LA"): bg.paste(img, mask=img.split()[-1])
    else: bg.paste(img.convert("RGB"))
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=92, optimize=True, progressive=True)
    return file_response(buf.getvalue(), "image/jpeg", "Converted_Image.jpg")

def handle_image_to_base64(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format=img.format or "PNG")
    mime = p.get("mimeType") or "image/png"
    if not re.fullmatch(r"image/[a-zA-Z0-9.+-]+", mime): mime = "image/png"
    return jsonify({"result": f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"})

def handle_image_to_pdf(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=300)
    return file_response(buf.getvalue(), "application/pdf", "Converted_Image.pdf")

def handle_heic_to_jpg(p):
    if pillow_heif is None: return bad_request("pillow-heif غير مثبّت")
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No image provided")
    if not validate_signature(file_bytes, "heic"): return bad_signature_response(is_arabic)
    try: img = open_image_safely(file_bytes).convert("RGB")
    except Exception: return bad_request("أبعاد الصورة كبيرة جداً")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True, progressive=True)
    return file_response(buf.getvalue(), "image/jpeg", "Converted_Image.jpg")

def handle_resize_image(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err: return err
    try:
        target_w = int(p.get("width") or 0)
        target_h = int(p.get("height") or 0)
    except: return bad_request("قيم الأبعاد غير صحيحة")
    if target_w <= 0 and target_h <= 0: return bad_request("يرجى تحديد العرض أو الارتفاع")
    if target_w > 8000 or target_h > 8000: return bad_request("الأبعاد المطلوبة كبيرة جداً")
    img = ImageOps.exif_transpose(img)
    if p.get("keepRatio", True):
        orig_w, orig_h = img.size
        if target_w and not target_h: target_h = int(orig_h * (target_w / orig_w))
        elif target_h and not target_w: target_w = int(orig_w * (target_h / orig_h))
        img = img.copy()
        img.thumbnail((target_w, target_h))
    else: img = img.resize((target_w or img.width, target_h or img.height))
    fmt = "PNG" if img.mode in ("RGBA", "LA") else "JPEG"
    if fmt == "JPEG": img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=92, optimize=True)
    return file_response(buf.getvalue(), "image/png" if fmt == "PNG" else "image/jpeg", f"Resized_Image.{'png' if fmt=='PNG' else 'jpg'}")

def handle_rotate_image(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err: return err
    try: angle = float(p.get("angle", 90))
    except: angle = 90
    img = ImageOps.exif_transpose(img)
    rotated = img.rotate(-angle, expand=True, fillcolor=(255, 255, 255) if img.mode == "RGB" else None)
    fmt = "PNG" if rotated.mode in ("RGBA", "LA") else "JPEG"
    if fmt == "JPEG": rotated = rotated.convert("RGB")
    buf = io.BytesIO()
    rotated.save(buf, format=fmt, quality=92, optimize=True)
    return file_response(buf.getvalue(), "image/png" if fmt == "PNG" else "image/jpeg", f"Rotated_Image.{'png' if fmt=='PNG' else 'jpg'}")

def handle_watermark_image(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err: return err
    watermark_text = (p.get("watermarkText") or "V-Infinity").strip()
    img = ImageOps.exif_transpose(img).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(18, img.width // 20)
    try: font = ImageFont.load_default(size=font_size)
    except: font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), watermark_text[:80], font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((img.width - tw) / 2, (img.height - th) / 2), watermark_text[:80], font=font, fill=(255, 255, 255, 130))
    combined = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    combined.save(buf, format="JPEG", quality=92, optimize=True)
    return file_response(buf.getvalue(), "image/jpeg", "Watermarked_Image.jpg")

def handle_strip_exif(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err: return err
    img = ImageOps.exif_transpose(img)
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    fmt = "PNG" if img.mode in ("RGBA", "LA") else "JPEG"
    if fmt == "JPEG": clean = clean.convert("RGB")
    buf = io.BytesIO()
    clean.save(buf, format=fmt, quality=95, optimize=True)
    return file_response(buf.getvalue(), "image/png" if fmt == "PNG" else "image/jpeg", f"Privacy_Cleaned.{'png' if fmt=='PNG' else 'jpg'}")


# ================= أدوات الطلاب والمعلمين والذكاء الاصطناعي =================
def handle_image_to_text(p):
    """أداة OCR معززة بالذكاء الاصطناعي، تصفي الصورة وتوضحها قبل القراءة"""
    if pytesseract is None: return bad_request("مكتبة OCR غير مثبتة بالسيرفر")
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    try:
        # AI PRE-PROCESSING: تنظيف الصورة لرفع دقة الـ OCR
        img = img.convert('L') # تحويل للأبيض والأسود
        img = ImageEnhance.Contrast(img).enhance(1.5) # رفع التباين
        img = img.filter(ImageFilter.SHARPEN) # توضيح الحواف

        lang = 'ara+eng' if p["is_arabic"] else 'eng'
        text = pytesseract.image_to_string(img, lang=lang)
        if not text.strip(): return jsonify({"result": "لم يتم العثور على أي نص واضح في الصورة."})
        return jsonify({"result": text.strip()})
    except Exception: return bad_request("فشل التعرف على النص. يرجى التأكد من تثبيت الحزم.")

def handle_text_to_audio(p):
    if gTTS is None: return bad_request("مكتبة الصوت غير مثبتة.")
    text = p.get("text", "").strip()
    if not text: return bad_request("يرجى إدخال النص.")
    if len(text) > 5000: return bad_request("النص طويل جداً (الحد الأقصى 5000 حرف).")
    try:
        lang_code = 'ar' if p["is_arabic"] else 'en'
        tts = gTTS(text=text, lang=lang_code, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return file_response(buf.getvalue(), "audio/mpeg", "Audio_Speech.mp3")
    except Exception: return bad_request("فشل توليد الصوت.")

def handle_translate_text(p):
    if GoogleTranslator is None: return bad_request("مكتبة الترجمة غير مثبتة.")
    text = p.get("text", "").strip()
    if not text: return bad_request("يرجى إدخال النص.")
    if len(text) > 4500: text = text[:4500] 
    try:
        target_lang = 'en' if p["is_arabic"] else 'ar'
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return jsonify({"result": translated})
    except Exception: return bad_request("فشلت الترجمة، يرجى المحاولة لاحقاً أو بنص أقصر.")

# أداة جديدة: تلخيص النصوص باستخدام خوارزمية ذكية (Extractive AI)
def handle_summarize_text(p):
    text = p.get("text", "").strip()
    if not text: return bad_request("يرجى إدخال النص للتلخيص.")
    try:
        sentences = re.split(r'(?<=[.!?؟]) +|\n+', text)
        if len(sentences) <= 3: return jsonify({"result": text}) # النص قصير أصلاً
        word_freq = {}
        for w in re.findall(r'\w+', text): word_freq[w] = word_freq.get(w, 0) + 1
        max_freq = max(word_freq.values()) if word_freq else 1
        scores = {}
        for i, s in enumerate(sentences):
            for w in re.findall(r'\w+', s):
                scores[i] = scores.get(i, 0) + (word_freq.get(w, 0) / max_freq)
        summary_len = max(3, len(sentences) // 3) # يلخص للثلث
        top_indices = sorted(scores, key=scores.get, reverse=True)[:summary_len]
        summary = "\n\n".join([sentences[i] for i in sorted(top_indices)])
        return jsonify({"result": summary})
    except Exception: return bad_request("فشل تلخيص النص.")


# ================= أدوات المطورين والنصوص =================
def handle_base64_tool(p):
    text = p.get("text", "")
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        re_encoded = base64.b64encode(decoded.encode("utf-8")).decode("ascii")
        res = decoded if re_encoded.rstrip("=") == text.strip().rstrip("=") else base64.b64encode(text.encode("utf-8")).decode("ascii")
    except Exception: res = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return jsonify({"result": res})

def handle_url_encoder(p):
    from urllib.parse import quote, unquote
    text = p.get("text", "")
    try:
        decoded = unquote(text)
        res = decoded if decoded != text else quote(text)
    except Exception: res = quote(text)
    return jsonify({"result": res})

def handle_json_beautifier(p):
    try: return jsonify({"result": json.dumps(json.loads(p.get("text", "")), ensure_ascii=False, indent=4, sort_keys=True)})
    except Exception: return bad_request("تنسيق JSON غير صحيح")

def handle_css_js_minifier(p):
    return jsonify({"result": re.sub(r"\s+", " ", re.sub(r"/\*[\s\S]*?\*/|//.*", "", p.get("text", ""))).strip()})

def handle_html_entity(p):
    return jsonify({"result": p.get("text", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")})

def handle_hash_generator(p):
    text = p.get("text", "").encode("utf-8")
    return jsonify({"result": f"MD5: {hashlib.md5(text).hexdigest()}\nSHA-1: {hashlib.sha1(text).hexdigest()}\nSHA-256: {hashlib.sha256(text).hexdigest()}\nSHA-512: {hashlib.sha512(text).hexdigest()}\nBLAKE2b: {hashlib.blake2b(text).hexdigest()}"})

def handle_hmac_generator(p):
    key, text = p.get("key", ""), p.get("text", "")
    if not key: return bad_request("يرجى إدخال المفتاح السري")
    algo = p.get("algorithm", "sha256")
    if algo not in hashlib.algorithms_available: algo = "sha256"
    return jsonify({"result": f"HMAC-{algo.upper()}: {hmac.new(key.encode('utf-8'), text.encode('utf-8'), algo).hexdigest()}"})

def handle_timestamp_converter(p):
    try: return jsonify({"result": datetime.fromtimestamp(int(p.get("text", "").strip()), tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")})
    except Exception: return bad_request("رقم Timestamp غير صحيح")

def handle_clean_text(p):
    text = p.get("text", "")
    text = re.sub(r'<[^>]*>?', '', text).replace("&nbsp;", " ")
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text) 
    text = re.sub(r' +', ' ', text) 
    text = re.sub(r' ,', ',', text) 
    return jsonify({"result": text.strip()})

def handle_text_to_qr(p):
    text = p.get("text", "")
    if not text.strip(): return bad_request("يرجى إدخال نص أو رابط")
    if len(text) > 2000: return bad_request("النص طويل جداً")

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(text)
    qr.make(fit=True)

    img = None
    if QR_STYLES_AVAILABLE:
        try:
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer(),
                color_mask=RadialGradiantColorMask(back_color=(255, 255, 255), center_color=(30, 41, 59), edge_color=(15, 23, 42))
            ).convert("RGB")
        except Exception: img = None
    if img is None: img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return jsonify({"resultImage": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"})

def handle_password_generator(p):
    try: length = max(8, min(128, int(p.get("length", 20))))
    except Exception: length = 20
    use_symbols = p.get("useSymbols", True)
    chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789" + ("!@#$%^&*_+=" if use_symbols else "")
    pw_chars = [secrets.choice(string.ascii_lowercase.replace('l','')), secrets.choice(string.ascii_uppercase.replace('O','').replace('I','')), secrets.choice(string.digits.replace('0','').replace('1',''))]
    if use_symbols: pw_chars.append(secrets.choice("!@#$%^&*_+="))
    pw_chars += [secrets.choice(chars) for _ in range(length - len(pw_chars))]
    secrets.SystemRandom().shuffle(pw_chars)
    pwd = "".join(pw_chars)
    return jsonify({"result": "-".join([pwd[i:i+4] for i in range(0, len(pwd), 4)])})

def handle_password_strength(p):
    text = p.get("text", "")
    score = sum([len(text) >= 8, len(text) >= 12, bool(re.search(r"[A-Z]", text)), bool(re.search(r"[a-z]", text)), bool(re.search(r"[0-9]", text)), bool(re.search(r"[^A-Za-z0-9]", text))])
    labels = ["ضعيفة جداً ⚠️", "ضعيفة ⚠️", "متوسطة 🟡", "جيدة 🙂", "قوية 🔒", "قوية جداً 🔒🔒", "ممتازة 🛡️"] if p["is_arabic"] else ["Very Weak ⚠️", "Weak ⚠️", "Fair 🟡", "Good 🙂", "Strong 🔒", "Very Strong 🔒🔒", "Excellent 🛡️"]
    return jsonify({"result": f"{labels[min(score, 6)]} ({score}/6)"})

def handle_text_counter(p):
    text = p.get("text", "")
    return jsonify({"result": f"Chars: {len(text)}\nChars (no spaces): {len(text.replace(' ', '').replace(chr(10), ''))}\nWords: {len(text.strip().split()) if text.strip() else 0}\nLines: {len(text.splitlines())}"})

def handle_percentage_calc(p):
    nums = re.findall(r"-?\d+(?:\.\d+)?", p.get("text", ""))
    if len(nums) < 2: return jsonify({"result": "يرجى إدخال رقمين"})
    return jsonify({"result": f"{nums[0]}% of {nums[1]} = {(float(nums[0]) / 100) * float(nums[1])}"})

def handle_byte_converter(p):
    b = float(re.sub(r"[^0-9.]", "", p.get("text", "")) or 0.0)
    return jsonify({"result": f"Bytes: {b}\nKB: {b / 1024:.2f}\nMB: {b / 1024 ** 2:.2f}\nGB: {b / 1024 ** 3:.4f}\nTB: {b / 1024 ** 4:.6f}"})

def handle_unit_converter(p):
    val = float(re.sub(r"[^0-9.]", "", p.get("text", "")) or 0.0)
    return jsonify({"result": f"Meters: {val} m\nFeet: {val * 3.28084:.2f} ft\nInches: {val * 39.3701:.2f} in\nMiles: {val / 1609.34:.4f} mi\nKilometers: {val / 1000:.4f} km"})

def handle_uuid_generator(p):
    try: count = max(1, min(50, int(p.get("count", 1))))
    except Exception: count = 1
    return jsonify({"result": "\n".join(str(uuid.uuid4()) for _ in range(count))})

def handle_markdown_to_html(p):
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

# ================= السجل (Registry) الكامل لجميع الأدوات =================
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
    "image-to-text": handle_image_to_text, "image-to-pdf": handle_image_to_pdf, "heic-to-jpg": handle_heic_to_jpg,
    "resize-image": handle_resize_image, "rotate-image": handle_rotate_image, "watermark-image": handle_watermark_image,
    "strip-exif": handle_strip_exif, "base64-tool": handle_base64_tool, "url-encoder": handle_url_encoder,
    "json-beautifier": handle_json_beautifier, "css-js-minifier": handle_css_js_minifier, "html-entity": handle_html_entity,
    "hash-generator": handle_hash_generator, "hmac-generator": handle_hmac_generator, "timestamp-converter": handle_timestamp_converter,
    "clean-text": handle_clean_text, "text-to-qr": handle_text_to_qr, "password-generator": handle_password_generator,
    "password-strength": handle_password_strength, "text-counter": handle_text_counter, "percentage-calc": handle_percentage_calc,
    "byte-converter": handle_byte_converter, "unit-converter": handle_unit_converter, "uuid-generator": handle_uuid_generator,
    "markdown-to-html": handle_markdown_to_html, "html-to-markdown": handle_markdown_to_html, "text-diff": handle_text_diff,
    "text-to-audio": handle_text_to_audio, "translate-text": handle_translate_text, "pdf-to-jpg": handle_pdf_to_jpg,
    "summarize-text": handle_summarize_text # تسجيل الأداة الجديدة
}

NEEDS_MULTIPLE_FILES = {"merge-pdf", "merge-word"}

# ================= مسارات (Routes) الـ SEO =================
@app.route("/")
@app.route("/<tool_slug>")
def index(tool_slug=None):
    if tool_slug in ("privacy", "terms", "contact"):
        return render_template(f"{tool_slug}.html")
    tool_data = None
    if tool_slug:
        if tool_slug not in TOOLS_SEO:
            return "Page Not Found", 404
        tool_data = TOOLS_SEO[tool_slug]
    return render_template("index.html", tool_data=tool_data)

@app.route('/sitemap.xml')
def sitemap():
    base_url = "https://infinityconverter.com"
    urls = [f"<url><loc>{base_url}/</loc><priority>1.0</priority></url>"]
    for slug in TOOLS_SEO.keys():
        urls.append(f"<url><loc>{base_url}/{slug}</loc><priority>0.8</priority></url>")
    xml_content = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(urls)}</urlset>'
    return Response(xml_content, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return Response("User-agent: *\nAllow: /\n\nSitemap: https://infinityconverter.com/sitemap.xml\n", mimetype='text/plain')

@app.route("/convert", methods=["POST"])
@limiter.limit(dynamic_convert_limit)
def convert():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict): return bad_request("Invalid request body")

    action = payload.get("action")
    if not isinstance(action, str): return bad_request("Unknown action")

    text = payload.get("text", "") or ""
    if not isinstance(text, str): return bad_request("Invalid text field")

    is_arabic = payload.get("lang") == "ar" or is_arabic_text(text)
    files_to_check = payload.get("filesBase64") or [] if action in NEEDS_MULTIPLE_FILES else ([payload.get("fileBase64")] if payload.get("fileBase64") else [])

    if action in NEEDS_MULTIPLE_FILES and len(files_to_check) > MAX_MERGE_FILES:
        return jsonify({"error": f"الحد الأقصى {MAX_MERGE_FILES} ملفات" if is_arabic else f"Maximum {MAX_MERGE_FILES} files"}), 413

    for b64 in files_to_check:
        if b64 and (len(b64) * 3 / 4) > MAX_FILE_BYTES:
            return jsonify({"error": f"حجم الملف أكبر من الحد المسموح ({MAX_FILE_MB}MB)" if is_arabic else f"File exceeds the allowed size ({MAX_FILE_MB}MB)"}), 413

    handler = REGISTRY.get(action)
    if not handler: return bad_request(f"Unknown action: {action}")

    try:
        ctx = dict(payload, text=text, is_arabic=is_arabic)
        response = handler(ctx)
        gc.collect() # تنظيف إجباري للذاكرة
        return response
    except Exception:
        app.logger.exception(f"convert() error for action={action}")
        gc.collect()
        return jsonify({"error": "حدث خطأ أثناء المعالجة. تأكد من صحة الملف وحاول مجدداً."}), 500

@app.route('/ads.txt')
def ads_txt():
    return "google.com, pub-4343857922748618, DIRECT, f08c47fec0942fa0", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

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
from datetime import datetime, timezone
from difflib import unified_diff
from functools import wraps

from flask import Flask, request, jsonify, render_template, send_file
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

# ==================== الإعدادات العامة (قابلة للتحكم عبر متغيرات البيئة) ====================
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", 4))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
MAX_MERGE_FILES = int(os.environ.get("MAX_MERGE_FILES", 15))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", 500))
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", 2_000_000))
SUBPROCESS_TIMEOUT = int(os.environ.get("SUBPROCESS_TIMEOUT", 60))
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "https://infinityconverter.com,https://www.infinityconverter.com"
).split(",") if o.strip()]

# يحسب هذا الحد سقف حجم الطلب الكلي بما يغطي أسوأ الحالات (دمج عدة ملفات PDF)
# مع هامش لتضخم ترميز base64 (~37%) وحمولة JSON الإضافية.
app_max_content = int(MAX_FILE_BYTES * MAX_MERGE_FILES * 1.4) + (2 * 1024 * 1024)

# حماية من هجمات "قنبلة فك الضغط" على الصور (صورة صغيرة الحجم لكنها تتمدد لأبعاد ضخمة بالذاكرة)
Image.MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", 50_000_000))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = app_max_content

logging.basicConfig(level=logging.INFO)

# ==================== الحماية: CORS مقيّد بدل السماح للجميع ====================
CORS(app, resources={r"/convert": {"origins": ALLOWED_ORIGINS}}, supports_credentials=False)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day", "100 per hour"],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://"),
)

# الأدوات الثقيلة على المعالج (LibreOffice / pdf2docx) تأخذ حد أشد لحماية السيرفر من الإغراق
HEAVY_ACTIONS = {
    "word-to-pdf", "excel-to-pdf", "pdf-to-docx", "pdf-to-doc",
    "pdf-to-ppt", "pdf-to-excel", "merge-pdf",
}


def dynamic_convert_limit():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    return "6 per minute" if action in HEAVY_ACTIONS else "20 per minute"


@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'"
    )
    if request.path == "/convert":
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="تم تجاوز الحد المسموح. يرجى الانتظار قليلاً لحماية السيرفر."), 429


@app.errorhandler(413)
def too_large_handler(e):
    return jsonify(error=f"حجم الطلب أكبر من الحد المسموح."), 413


@app.errorhandler(500)
def internal_error_handler(e):
    # لا نكشف تفاصيل الخطأ الداخلي أو أثر التنفيذ (stack trace) للمستخدم أبداً
    app.logger.exception("Unhandled server error")
    return jsonify(error="حدث خطأ غير متوقع بالسيرفر. تم إبلاغ الفريق التقني."), 500
# ==========================================================

ARABIC_FONT_NAME = "ArabicFont"
_arabic_font_registered = False

# ==================== توقيعات الملفات (Magic Bytes) لمنع انتحال نوع الملف ====================
def validate_signature(file_bytes, kind):
    """يتحقق من أن محتوى الملف الفعلي يطابق النوع المُعلن، لمنع رفع ملفات ضارة بامتداد مزيف."""
    if not file_bytes:
        return False
    if kind == "pdf":
        return file_bytes[:5] == b"%PDF-"
    if kind == "zip_office":  # docx / xlsx / pptx كلها أرشيفات ZIP
        return file_bytes[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    if kind == "webp":
        return file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"
    if kind == "heic":
        return b"ftyp" in file_bytes[:32]
    if kind == "image_any":
        sigs = [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM", b"RIFF"]
        return any(file_bytes.startswith(s) for s in sigs) or validate_signature(file_bytes, "heic")
    return True


def bad_signature_response(is_arabic):
    msg = "نوع الملف الفعلي لا يطابق الامتداد المتوقع أو الملف تالف." if is_arabic \
        else "The file's actual content does not match the expected type, or it is corrupted."
    return bad_request(msg)


def enforce_pdf_page_limit(reader, is_arabic):
    if len(reader.pages) > MAX_PDF_PAGES:
        msg = f"عدد صفحات الملف يتجاوز الحد المسموح ({MAX_PDF_PAGES} صفحة)." if is_arabic \
            else f"The file exceeds the maximum allowed pages ({MAX_PDF_PAGES})."
        return bad_request(msg)
    return None
# ==========================================================


def smart_decode(file_bytes):
    """رادار النصوص: يفك تشفير الملفات العربية والإنجليزية بدون أي طلاسم"""
    encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1256', 'cp1256', 'iso-8859-6']
    for enc in encodings_to_try:
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode('utf-8', errors='ignore')


def auto_fit_excel_columns(writer, sheet_name="Sheet1", add_autofilter=True):
    """تنسيق إكسل الماسي: تلوين، توسيط، تجميد، حدود احترافية، وفلترة تلقائية"""
    worksheet = writer.sheets[sheet_name]

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    alt_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    thin_border = Border(left=Side(style='thin', color="CBD5E1"),
                          right=Side(style='thin', color="CBD5E1"),
                          top=Side(style='thin', color="CBD5E1"),
                          bottom=Side(style='thin', color="CBD5E1"))
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    max_row = worksheet.max_row
    max_col = worksheet.max_column

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
                if cell.value and len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except Exception:
                pass
        adjusted_width = min(max_length + 3, 40)
        worksheet.column_dimensions[column].width = adjusted_width

    worksheet.freeze_panes = "A2"

    if add_autofilter and max_row > 1 and max_col > 0:
        worksheet.auto_filter.ref = f"A1:{get_column_letter(max_col)}{max_row}"


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
        font_path, "static/fonts/NotoNaskhArabic-Regular.ttf", "static/Cairo-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
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
    try:
        return base64.b64decode(b64, validate=True)
    except Exception:
        return None


def parse_csv_text(text):
    text = (text or "").strip()
    return list(csv.reader(io.StringIO(text)))


def escape_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def open_image_safely(file_bytes):
    """يفتح الصورة مع الحماية من الملفات التالفة أو قنابل فك الضغط."""
    img = Image.open(io.BytesIO(file_bytes))
    img.load()  # يفعّل الفحص الكامل للبيانات فوراً بدل التحميل الكسول
    return img


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
    if add_page_numbers:
        _add_docx_page_numbers(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _add_docx_page_numbers(doc):
    """يضيف ترقيم صفحات ديناميكي (PAGE field) بتذييل المستند."""
    section = doc.sections[0]
    footer = section.footer
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = "PAGE"
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def text_to_pdf_bytes(text, is_arabic, title=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    story = []
    for line in (text or "").split("\n"):
        content = shape_arabic(line, wrap_width=85) if is_arabic else line
        p_style = ParagraphStyle('Body', fontName=font, fontSize=11, leading=16, alignment=2 if is_arabic else 0)
        t_cell = Table([[RLParagraph(escape_html(content).replace("&lt;br/&gt;", "<br/>") or "&nbsp;", p_style)]], colWidths=[480])
        t_cell.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_cell)
        story.append(Spacer(1, 4))
    doc.build(story)

    reader = PdfReader(io.BytesIO(buf.getvalue()))
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams()
        writer.add_page(page)

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
        if is_arabic:
            formatted_row.reverse()
        table_data.append(formatted_row)

    if not table_data:
        table_data = [[RLParagraph("", ParagraphStyle('Empty', fontName=font, fontSize=11))]]

    page_width = A4[0] - (30 * mm)
    num_cols = len(table_data[0]) if table_data else 1
    col_width = page_width / num_cols
    col_widths = [col_width] * num_cols

    table = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)

    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
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

    final_buf = io.BytesIO()
    writer.write(final_buf)
    return final_buf.getvalue()


def run_libreoffice_convert(src_path, out_dir):
    cmd = ["libreoffice", "--headless", "--nologo", "--nofirststartwizard", "--norestore",
           "--convert-to", "pdf", src_path, "--outdir", out_dir]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=SUBPROCESS_TIMEOUT)


# ================= الأدوات القصوى (Maximum Features) =================

def handle_word_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if file_bytes:
        if not validate_signature(file_bytes, "zip_office"):
            return bad_signature_response(is_arabic)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_docx_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.docx")
                with open(tmp_docx_path, "wb") as f:
                    f.write(file_bytes)

                run_libreoffice_convert(tmp_docx_path, tmp_dir)

                base_name = os.path.splitext(os.path.basename(tmp_docx_path))[0]
                pdf_path = os.path.join(tmp_dir, f"{base_name}.pdf")
                if not os.path.exists(pdf_path):
                    return bad_request("فشل التحويل." if is_arabic else "Conversion failed.")

                reader = PdfReader(pdf_path)
                err = enforce_pdf_page_limit(reader, is_arabic)
                if err:
                    return err
                writer = PdfWriter()
                for page in reader.pages:
                    page.compress_content_streams()
                    writer.add_page(page)

                final_buf = io.BytesIO()
                writer.write(final_buf)
                return file_response(final_buf.getvalue(), "application/pdf", "Converted_Document.pdf")
        except subprocess.TimeoutExpired:
            return bad_request("استغرقت المعالجة وقتاً طويلاً جداً، جرّب ملفاً أصغر." if is_arabic else "Processing took too long; try a smaller file.")
        except Exception as e:
            app.logger.error(f"LibreOffice Error: {e}")
            return bad_request("فشل التحويل. قد يكون السيرفر تحت ضغط، يرجى المحاولة لاحقاً." if is_arabic else "Conversion failed due to server load.")

    text = p.get("text", "")
    pdf_bytes = text_to_pdf_bytes(text, is_arabic)
    return file_response(pdf_bytes, "application/pdf", "Converted_Document.pdf")


def handle_text_to_pdf(p):
    text = p.get("text", "")
    is_arabic = p["is_arabic"]
    if not text.strip():
        return bad_request("يرجى إدخال نص" if is_arabic else "Please enter text")
    pdf_bytes = text_to_pdf_bytes(text, is_arabic)
    return file_response(pdf_bytes, "application/pdf", "Converted_Text.pdf")


def handle_pdf_to_pdf_enhanced(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("يرجى رفع ملف PDF" if is_arabic else "Please upload a PDF")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        err = enforce_pdf_page_limit(reader, is_arabic)
        if err:
            return err
        extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        pdf_bytes = text_to_pdf_bytes(extracted_text, is_arabic)
        return file_response(pdf_bytes, "application/pdf", "Reformatted_Document.pdf")
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "The file is corrupted or password-protected")
    except Exception:
        return bad_request("تعذر قراءة الملف" if is_arabic else "Could not read PDF")


def handle_csv_to_pdf(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    pdf_bytes = csv_to_pdf_bytes(text, p["is_arabic"])
    return file_response(pdf_bytes, "application/pdf", "Converted_Table.pdf")


def handle_excel_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("يرجى رفع ملف Excel" if is_arabic else "Please upload an Excel file")
    if not validate_signature(file_bytes, "zip_office"):
        return bad_signature_response(is_arabic)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_xlsx_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.xlsx")
            with open(tmp_xlsx_path, "wb") as f:
                f.write(file_bytes)

            run_libreoffice_convert(tmp_xlsx_path, tmp_dir)

            base_name = os.path.splitext(os.path.basename(tmp_xlsx_path))[0]
            pdf_path = os.path.join(tmp_dir, f"{base_name}.pdf")
            if not os.path.exists(pdf_path):
                return bad_request("تعذر التحويل" if is_arabic else "Could not convert")

            reader = PdfReader(pdf_path)
            err = enforce_pdf_page_limit(reader, is_arabic)
            if err:
                return err
            writer = PdfWriter()
            for page in reader.pages:
                page.compress_content_streams()
                writer.add_page(page)

            final_buf = io.BytesIO()
            writer.write(final_buf)
            return file_response(final_buf.getvalue(), "application/pdf", "Converted_Excel.pdf")
    except subprocess.TimeoutExpired:
        return bad_request("استغرقت المعالجة وقتاً طويلاً جداً." if is_arabic else "Processing took too long.")
    except Exception as e:
        app.logger.error(f"LibreOffice Excel Error: {e}")
        return bad_request("تعذر التحويل" if is_arabic else "Could not convert")


def handle_pdf_to_text(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        err = enforce_pdf_page_limit(reader, is_arabic)
        if err:
            return err
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return jsonify({"result": text.strip()})
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "The file is corrupted or password-protected")


def handle_pdf_to_csv(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        err = enforce_pdf_page_limit(reader, is_arabic)
        if err:
            return err
        buf = io.StringIO()
        writer = csv.writer(buf)
        for page in reader.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if line.strip():
                    writer.writerow(line.split())
        output_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        return file_response(output_bytes, "text/csv", "Converted_Data.csv")
    except Exception:
        return bad_request("تعذر استخراج الجداول" if is_arabic else "Could not extract tables")


def handle_pdf_to_docx(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("يرجى رفع ملف PDF" if is_arabic else "Please upload a PDF file")
    if Converter is None:
        return bad_request("مكتبة pdf2docx غير مثبتة" if is_arabic else "pdf2docx is not installed")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_pdf_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.pdf")
            with open(tmp_pdf_path, "wb") as f:
                f.write(file_bytes)

            reader_check = PdfReader(tmp_pdf_path)
            err = enforce_pdf_page_limit(reader_check, is_arabic)
            if err:
                return err

            base_name = os.path.splitext(os.path.basename(tmp_pdf_path))[0]
            docx_path = os.path.join(tmp_dir, f"{base_name}.docx")

            cv = Converter(tmp_pdf_path)
            cv.convert(docx_path, start=0, end=None, kwargs={
                "connected_border_tolerance": 2.5, "line_overlap_threshold": 0.8,
                "line_margin": 0.1, "word_margin": 0.1, "maintain_layout": True
            })
            cv.close()

            if is_arabic:
                try:
                    doc = Document(docx_path)
                    for paragraph in doc.paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        pPr = paragraph._element.get_or_add_pPr()
                        pPr.insert(0, OxmlElement('w:bidi'))
                    for table in doc.tables:
                        tblPr = table._element.xpath('w:tblPr')
                        if tblPr:
                            bidiVisual = OxmlElement('w:bidiVisual')
                            tblPr[0].append(bidiVisual)
                        for row in table.rows:
                            for cell in row.cells:
                                for par in cell.paragraphs:
                                    par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                                    pPr = par._p.get_or_add_pPr()
                                    pPr.insert(0, OxmlElement('w:bidi'))
                    doc.save(docx_path)
                except Exception as e:
                    app.logger.warning(f"Post-processing DOCX failed: {e}")

            with open(docx_path, "rb") as f:
                docx_bytes = f.read()

            return file_response(docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")
    except subprocess.TimeoutExpired:
        return bad_request("استغرقت المعالجة وقتاً طويلاً جداً." if is_arabic else "Processing took too long.")
    except Exception as e:
        app.logger.error(f"PDF to DOCX Error: {e}")
        return bad_request("فشل التحويل. قد يكون الملف معقداً جداً." if is_arabic else "Conversion failed.")


def handle_pdf_to_doc(p):
    return handle_pdf_to_docx(p)


def handle_doc_to_docx(p):
    add_page_numbers = bool(p.get("addPageNumbers"))
    buf = build_docx_from_text(p.get("text", ""), p["is_arabic"], add_page_numbers=add_page_numbers)
    return file_response(buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")


def handle_merge_word(p):
    """أداة جديدة: دمج عدة ملفات Word في مستند واحد بالترتيب المرسل."""
    is_arabic = p["is_arabic"]
    files = p.get("filesBase64") or []
    if len(files) < 2:
        return bad_request("يرجى رفع ملفين Word على الأقل للدمج" if is_arabic else "Please upload at least 2 Word files")
    if len(files) > MAX_MERGE_FILES:
        return bad_request(f"الحد الأقصى {MAX_MERGE_FILES} ملفات" if is_arabic else f"Maximum {MAX_MERGE_FILES} files")

    merged = Document()
    first = True
    for b64 in files:
        try:
            raw = base64.b64decode(b64, validate=True)
        except Exception:
            return bad_request("ملف غير صالح" if is_arabic else "Invalid file")
        if not validate_signature(raw, "zip_office"):
            return bad_signature_response(is_arabic)
        sub_doc = Document(io.BytesIO(raw))
        if not first:
            merged.add_page_break()
        first = False
        for element in sub_doc.element.body:
            merged.element.body.append(element)

    buf = io.BytesIO()
    merged.save(buf)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Merged_Document.docx")


def handle_pdf_to_excel(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    reader = PdfReader(io.BytesIO(file_bytes))
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err
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
            sheet_name = f"Page {idx + 1}"[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")


def handle_pdf_to_ppt(p):
    is_arabic = p["is_arabic"]
    if Presentation is None:
        return bad_request("python-pptx غير مثبّت على السيرفر")
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    reader = PdfReader(io.BytesIO(file_bytes))
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err
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
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Converted_Presentation.pptx")


def handle_merge_pdf(p):
    is_arabic = p["is_arabic"]
    files = p.get("filesBase64") or ([p.get("fileBase64")] if p.get("fileBase64") else [])
    if len(files) < 2:
        return bad_request("يرجى رفع ملفين PDF على الأقل للدمج" if is_arabic else "Please upload at least 2 PDFs")
    if len(files) > MAX_MERGE_FILES:
        return bad_request(f"الحد الأقصى {MAX_MERGE_FILES} ملفات لكل عملية دمج" if is_arabic else f"Maximum {MAX_MERGE_FILES} files per merge")

    add_page_numbers = bool(p.get("addPageNumbers"))
    writer = PdfWriter()
    page_count = 0
    total_pages = 0

    decoded_readers = []
    for b64 in files:
        try:
            raw = base64.b64decode(b64, validate=True)
        except Exception:
            return bad_request("أحد الملفات غير صالح" if is_arabic else "One of the files is invalid")
        if not validate_signature(raw, "pdf"):
            return bad_signature_response(is_arabic)
        try:
            reader = PdfReader(io.BytesIO(raw))
        except PdfReadError:
            return bad_request("أحد الملفات تالف أو محمي بكلمة سر" if is_arabic else "One of the files is corrupted or password-protected")
        total_pages += len(reader.pages)
        if total_pages > MAX_PDF_PAGES:
            return bad_request(f"إجمالي الصفحات يتجاوز الحد المسموح ({MAX_PDF_PAGES})" if is_arabic else f"Total pages exceed the limit ({MAX_PDF_PAGES})")
        decoded_readers.append(reader)

    for i, reader in enumerate(decoded_readers):
        writer.add_outline_item(f"ملف {i + 1}" if is_arabic else f"Document {i + 1}", page_count)
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
            page_count += 1

    if add_page_numbers:
        _stamp_page_numbers(writer)

    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Merged_Document.pdf")


def _stamp_page_numbers(writer):
    """يطبع رقم الصفحة أسفل كل صفحة في مستند PDF ناتج."""
    total = len(writer.pages)
    for i, page in enumerate(writer.pages, start=1):
        w = float(page.mediabox.width)
        overlay_buf = io.BytesIO()
        c = rl_canvas.Canvas(overlay_buf, pagesize=(w, float(page.mediabox.height)))
        c.setFont("Helvetica", 9)
        c.drawCentredString(w / 2, 12, f"{i} / {total}")
        c.save()
        overlay_buf.seek(0)
        overlay_reader = PdfReader(overlay_buf)
        page.merge_page(overlay_reader.pages[0])


def handle_split_pdf(p):
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "The file is corrupted or password-protected")
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            page.compress_content_streams()
            writer.add_page(page)
            page_buf = io.BytesIO()
            writer.write(page_buf)
            zf.writestr(f"Page_{i + 1}.pdf", page_buf.getvalue())
    return file_response(zip_buf.getvalue(), "application/zip", "Split_Pages.zip")


def handle_rotate_pdf(p):
    """أداة جديدة: تدوير جميع صفحات PDF بزاوية محددة (90/180/270)."""
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        angle = int(p.get("angle", 90))
    except (TypeError, ValueError):
        angle = 90
    if angle not in (90, 180, 270):
        return bad_request("الزاوية يجب أن تكون 90 أو 180 أو 270" if is_arabic else "Angle must be 90, 180, or 270")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "The file is corrupted or password-protected")
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err

    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Rotated_Document.pdf")


def handle_compress_pdf(p):
    """أداة جديدة: ضغط PDF عبر تقليل محتوى التدفقات (content streams)."""
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "The file is corrupted or password-protected")
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err

    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams(level=9)
        writer.add_page(page)
    writer.compress_identical_objects()

    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Compressed_Document.pdf")


def handle_protect_pdf(p):
    """أداة جديدة: حماية PDF بكلمة سر (تشفير AES-256)."""
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    password = p.get("password", "")
    if not file_bytes:
        return bad_request("No file provided")
    if not password or len(password) < 4:
        return bad_request("يرجى إدخال كلمة سر لا تقل عن 4 أحرف" if is_arabic else "Please provide a password of at least 4 characters")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError:
        return bad_request("الملف تالف" if is_arabic else "The file is corrupted")
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, algorithm="AES-256")

    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Protected_Document.pdf")


def handle_unlock_pdf(p):
    """أداة جديدة: إزالة كلمة سر معروفة من ملف PDF."""
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    password = p.get("password", "")
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            ok = reader.decrypt(password)
            if not ok:
                return bad_request("كلمة السر غير صحيحة" if is_arabic else "Incorrect password")
    except PdfReadError:
        return bad_request("الملف تالف" if is_arabic else "The file is corrupted")
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Unlocked_Document.pdf")


def handle_watermark_pdf(p):
    """أداة جديدة: إضافة علامة مائية نصية لكل صفحات PDF."""
    is_arabic = p["is_arabic"]
    file_bytes = get_file_bytes(p)
    watermark_text = (p.get("watermarkText") or "").strip()
    if not file_bytes:
        return bad_request("No file provided")
    if not watermark_text:
        return bad_request("يرجى إدخال نص العلامة المائية" if is_arabic else "Please provide watermark text")
    if not validate_signature(file_bytes, "pdf"):
        return bad_signature_response(is_arabic)
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "The file is corrupted or password-protected")
    err = enforce_pdf_page_limit(reader, is_arabic)
    if err:
        return err

    writer = PdfWriter()
    for page in reader.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        overlay_buf = io.BytesIO()
        c = rl_canvas.Canvas(overlay_buf, pagesize=(w, h))
        c.saveState()
        c.translate(w / 2, h / 2)
        c.rotate(45)
        c.setFont("Helvetica-Bold", 40)
        c.setFillColor(colors.Color(0.6, 0.6, 0.6, alpha=0.35))
        c.drawCentredString(0, 0, watermark_text[:60])
        c.restoreState()
        c.save()
        overlay_buf.seek(0)
        overlay_reader = PdfReader(overlay_buf)
        page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return file_response(buf.getvalue(), "application/pdf", "Watermarked_Document.pdf")


def handle_csv_to_word(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
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
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Converted_Document.docx")


def handle_word_to_csv(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return handle_text_to_csv(p)
    if not validate_signature(file_bytes, "zip_office"):
        return bad_signature_response(is_arabic)
    try:
        docx_doc = Document(io.BytesIO(file_bytes))
        buf = io.StringIO()
        writer = csv.writer(buf)
        for table in docx_doc.tables:
            for row in table.rows:
                writer.writerow([cell.text.strip() for cell in row.cells])
        output_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        return file_response(output_bytes, "text/csv", "Converted_Data.csv")
    except Exception:
        return bad_request("تعذر استخراج الجداول من ملف الوورد" if is_arabic else "Could not extract tables from Word")


def handle_text_to_excel(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    rows = [line.split("\t") if "\t" in line else line.split(",") for line in text.split("\n")]
    df = pd.DataFrame(rows)
    # تحويل الأعمدة الرقمية تلقائياً بدل تركها كنص، لتسهيل الحسابات في إكسل
    df = df.apply(lambda col: pd.to_numeric(col, errors="ignore"))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data", index=False, header=False)
        auto_fit_excel_columns(writer, "Data")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")


def handle_json_to_excel(p):
    file_bytes = get_file_bytes(p)
    raw = smart_decode(file_bytes) if file_bytes else (p.get("json") or p.get("text", ""))
    try:
        data = json.loads(raw)
    except Exception:
        return bad_request("تنسيق JSON غير صحيح" if p["is_arabic"] else "Invalid JSON format")
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
                data_ref = Reference(ws, min_col=2, min_row=1, max_col=len(df.columns), max_row=len(df) + 1)
                cats_ref = Reference(ws, min_col=1, min_row=2, max_row=len(df) + 1)
                chart.add_data(data_ref, titles_from_data=True)
                chart.set_categories(cats_ref)
                ws.add_chart(chart, f"{get_column_letter(len(df.columns) + 2)}2")
            except Exception as e:
                app.logger.warning(f"Chart generation skipped: {e}")
    return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Converted_Excel.xlsx")


def handle_excel_to_json(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes:
        return bad_request("No file provided")
    if not validate_signature(file_bytes, "zip_office"):
        return bad_signature_response(is_arabic)
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception:
        return bad_request("تعذر قراءة ملف الإكسل" if is_arabic else "Could not read the Excel file")
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x).fillna("")
    return jsonify({"result": df.to_json(orient="records", force_ascii=False, indent=2)})


def handle_csv_to_json(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
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
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = [data]
        if not data:
            return bad_request("Empty JSON")
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        output_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        return file_response(output_bytes, "text/csv", "Converted_Data.csv")
    except Exception:
        return bad_request("تنسيق JSON غير صحيح" if p["is_arabic"] else "Invalid JSON format")


def handle_text_to_csv(p):
    file_bytes = get_file_bytes(p)
    text = smart_decode(file_bytes) if file_bytes else p.get("text", "")
    buf = ("\ufeff" + text).encode("utf-8")
    return file_response(buf, "text/csv", "Converted_Data.csv")


# ================= أدوات الصور والتعديلات الخارقة =================
def _load_validated_image(p, is_arabic):
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return None, bad_request("No image provided")
    if not validate_signature(file_bytes, "image_any"):
        return None, bad_signature_response(is_arabic)
    try:
        img = open_image_safely(file_bytes)
    except Image.DecompressionBombError:
        return None, bad_request("أبعاد الصورة كبيرة جداً وغير آمنة للمعالجة" if is_arabic else "Image dimensions are unsafely large")
    except UnidentifiedImageError:
        return None, bad_signature_response(is_arabic)
    return img, None


def handle_compress_image(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    quality = p.get("quality", 70)
    try:
        quality = max(10, min(95, int(quality)))
    except (TypeError, ValueError):
        quality = 70

    img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=100, threshold=3))
    img.thumbnail((1600, 1600))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return file_response(buf.getvalue(), "image/jpeg", "Compressed_Image.jpg")


def handle_image_to_png(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return file_response(buf.getvalue(), "image/png", "Converted_Image.png")


def handle_image_to_jpg(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    img = ImageOps.exif_transpose(img)
    background = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode in ("RGBA", "LA"):
        background.paste(img, mask=img.split()[-1])
    else:
        background.paste(img.convert("RGB"))
    buf = io.BytesIO()
    background.save(buf, format="JPEG", quality=92, optimize=True, progressive=True)
    return file_response(buf.getvalue(), "image/jpeg", "Converted_Image.jpg")


def handle_image_to_base64(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format=img.format or "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = p.get("mimeType") or "image/png"
    if not re.fullmatch(r"image/[a-zA-Z0-9.+-]+", mime or ""):
        mime = "image/png"
    return jsonify({"result": f"data:{mime};base64,{b64}"})


def handle_image_to_pdf(p):
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    img = img.convert("RGB")
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=100)
    return file_response(buf.getvalue(), "application/pdf", "Converted_Image.pdf")


def handle_heic_to_jpg(p):
    is_arabic = p["is_arabic"]
    if pillow_heif is None:
        return bad_request("pillow-heif غير مثبّت على السيرفر")
    file_bytes = get_file_bytes(p)
    if not file_bytes:
        return bad_request("No image provided")
    if not validate_signature(file_bytes, "heic"):
        return bad_signature_response(is_arabic)
    try:
        img = open_image_safely(file_bytes).convert("RGB")
    except Image.DecompressionBombError:
        return bad_request("أبعاد الصورة كبيرة جداً وغير آمنة للمعالجة" if is_arabic else "Image dimensions are unsafely large")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True, progressive=True)
    return file_response(buf.getvalue(), "image/jpeg", "Converted_Image.jpg")


def handle_resize_image(p):
    """أداة جديدة: تغيير أبعاد الصورة مع خيار الحفاظ على النسبة."""
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    try:
        target_w = int(p.get("width") or 0)
        target_h = int(p.get("height") or 0)
    except (TypeError, ValueError):
        return bad_request("قيم الأبعاد غير صحيحة" if is_arabic else "Invalid dimensions")
    if target_w <= 0 and target_h <= 0:
        return bad_request("يرجى تحديد العرض أو الارتفاع" if is_arabic else "Please specify width or height")
    if target_w > 8000 or target_h > 8000:
        return bad_request("الأبعاد المطلوبة كبيرة جداً" if is_arabic else "Requested dimensions are too large")

    img = ImageOps.exif_transpose(img)
    keep_ratio = p.get("keepRatio", True)
    if keep_ratio:
        orig_w, orig_h = img.size
        if target_w and not target_h:
            target_h = int(orig_h * (target_w / orig_w))
        elif target_h and not target_w:
            target_w = int(orig_w * (target_h / orig_h))
        img = img.copy()
        img.thumbnail((target_w, target_h))
    else:
        img = img.resize((target_w or img.width, target_h or img.height))

    buf = io.BytesIO()
    fmt = "PNG" if img.mode in ("RGBA", "LA") else "JPEG"
    if fmt == "JPEG":
        img = img.convert("RGB")
    img.save(buf, format=fmt, quality=92, optimize=True)
    mimetype = "image/png" if fmt == "PNG" else "image/jpeg"
    ext = "png" if fmt == "PNG" else "jpg"
    return file_response(buf.getvalue(), mimetype, f"Resized_Image.{ext}")


def handle_rotate_image(p):
    """أداة جديدة: تدوير الصورة بزاوية مخصصة."""
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    try:
        angle = float(p.get("angle", 90))
    except (TypeError, ValueError):
        angle = 90
    img = ImageOps.exif_transpose(img)
    rotated = img.rotate(-angle, expand=True, fillcolor=(255, 255, 255) if img.mode == "RGB" else None)
    buf = io.BytesIO()
    fmt = "PNG" if rotated.mode in ("RGBA", "LA") else "JPEG"
    if fmt == "JPEG":
        rotated = rotated.convert("RGB")
    rotated.save(buf, format=fmt, quality=92, optimize=True)
    mimetype = "image/png" if fmt == "PNG" else "image/jpeg"
    ext = "png" if fmt == "PNG" else "jpg"
    return file_response(buf.getvalue(), mimetype, f"Rotated_Image.{ext}")


def handle_watermark_image(p):
    """أداة جديدة: إضافة علامة مائية نصية على الصورة."""
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    watermark_text = (p.get("watermarkText") or "").strip()
    if not watermark_text:
        return bad_request("يرجى إدخال نص العلامة المائية" if is_arabic else "Please provide watermark text")

    img = ImageOps.exif_transpose(img).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(18, img.width // 20)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()
    text = watermark_text[:80]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (img.width - tw) / 2, (img.height - th) / 2
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 130))
    combined = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    combined.save(buf, format="JPEG", quality=92, optimize=True)
    return file_response(buf.getvalue(), "image/jpeg", "Watermarked_Image.jpg")


def handle_strip_exif(p):
    """أداة جديدة: إزالة بيانات EXIF (الموقع الجغرافي وغيره) من الصورة لحماية الخصوصية."""
    is_arabic = p["is_arabic"]
    img, err = _load_validated_image(p, is_arabic)
    if err:
        return err
    img = ImageOps.exif_transpose(img)
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    buf = io.BytesIO()
    fmt = "PNG" if img.mode in ("RGBA", "LA") else "JPEG"
    if fmt == "JPEG":
        clean = clean.convert("RGB")
    clean.save(buf, format=fmt, quality=95, optimize=True)
    mimetype = "image/png" if fmt == "PNG" else "image/jpeg"
    ext = "png" if fmt == "PNG" else "jpg"
    return file_response(buf.getvalue(), mimetype, f"Privacy_Cleaned.{ext}")


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
    try:
        data = json.loads(p.get("text", ""))
        return jsonify({"result": json.dumps(data, ensure_ascii=False, indent=4, sort_keys=True)})
    except Exception:
        return bad_request("تنسيق JSON غير صحيح" if p["is_arabic"] else "Invalid JSON")


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
    result = (
        f"MD5: {hashlib.md5(text).hexdigest()}\n"
        f"SHA-1: {hashlib.sha1(text).hexdigest()}\n"
        f"SHA-256: {hashlib.sha256(text).hexdigest()}\n"
        f"SHA-512: {hashlib.sha512(text).hexdigest()}\n"
        f"BLAKE2b: {hashlib.blake2b(text).hexdigest()}\n"
        f"SHA3-256: {hashlib.sha3_256(text).hexdigest()}"
    )
    return jsonify({"result": result})


def handle_hmac_generator(p):
    """أداة جديدة: توليد HMAC باستخدام مفتاح سري."""
    is_arabic = p["is_arabic"]
    text = p.get("text", "")
    key = p.get("key", "")
    if not key:
        return bad_request("يرجى إدخال المفتاح السري" if is_arabic else "Please provide a secret key")
    algo = p.get("algorithm", "sha256")
    if algo not in hashlib.algorithms_available:
        algo = "sha256"
    digest = hmac.new(key.encode("utf-8"), text.encode("utf-8"), algo).hexdigest()
    return jsonify({"result": f"HMAC-{algo.upper()}: {digest}"})


def handle_timestamp_converter(p):
    try:
        dt = datetime.fromtimestamp(int(p.get("text", "").strip()), tz=timezone.utc)
        return jsonify({"result": dt.strftime("%a, %d %b %Y %H:%M:%S GMT")})
    except Exception:
        return bad_request("رقم Timestamp غير صحيح" if p["is_arabic"] else "Invalid Timestamp")


def handle_clean_text(p):
    result = re.sub(r"<[^>]*>?", "", p.get("text", "")).replace("&nbsp;", " ").strip()
    return jsonify({"result": result})


def handle_text_to_qr(p):
    """يدعم الآن أيضاً تضمين شعار صغير داخل رمز QR (اختياري)."""
    text = p.get("text", "")
    if not text.strip():
        return bad_request("يرجى إدخال نص أو رابط" if p["is_arabic"] else "Please enter text or a link")
    if len(text) > 2000:
        return bad_request("النص طويل جداً لرمز QR" if p["is_arabic"] else "Text is too long for a QR code")

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color=p.get("fillColor", "black"), back_color=p.get("backColor", "white")).convert("RGB")

    logo_b64 = p.get("logoBase64")
    if logo_b64:
        try:
            logo_bytes = base64.b64decode(logo_b64, validate=True)
            if validate_signature(logo_bytes, "image_any"):
                logo = open_image_safely(logo_bytes).convert("RGBA")
                logo_size = img.size[0] // 4
                logo.thumbnail((logo_size, logo_size))
                pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
                img.paste(logo, pos, mask=logo)
        except Exception:
            pass  # نتجاهل مشكلة الشعار ونكمل بإصدار QR بدونه بدل فشل الطلب بالكامل

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return jsonify({"resultImage": f"data:image/png;base64,{b64}"})


def handle_password_generator(p):
    """يدعم الآن التحكم بالطول ونوع الرموز المستخدمة."""
    try:
        length = int(p.get("length", 20))
    except (TypeError, ValueError):
        length = 20
    length = max(8, min(128, length))

    use_symbols = p.get("useSymbols", True)
    base_chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    symbol_chars = "!@#$%^&*_+="
    chars = base_chars + (symbol_chars if use_symbols else "")

    # نضمن ظهور كل الفئات المطلوبة على الأقل مرة واحدة
    password_chars = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]
    if use_symbols:
        password_chars.append(secrets.choice(symbol_chars))
    password_chars += [secrets.choice(chars) for _ in range(length - len(password_chars))]
    secrets.SystemRandom().shuffle(password_chars)
    return jsonify({"result": "".join(password_chars)})


def handle_password_strength(p):
    text = p.get("text", "")
    is_arabic = p["is_arabic"]
    score = 0
    if len(text) >= 8:
        score += 1
    if len(text) >= 12:
        score += 1
    if re.search(r"[A-Z]", text):
        score += 1
    if re.search(r"[a-z]", text):
        score += 1
    if re.search(r"[0-9]", text):
        score += 1
    if re.search(r"[^A-Za-z0-9]", text):
        score += 1

    labels_ar = ["ضعيفة جداً ⚠️", "ضعيفة ⚠️", "متوسطة 🟡", "جيدة 🙂", "قوية 🔒", "قوية جداً 🔒🔒", "ممتازة 🛡️"]
    labels_en = ["Very Weak ⚠️", "Weak ⚠️", "Fair 🟡", "Good 🙂", "Strong 🔒", "Very Strong 🔒🔒", "Excellent 🛡️"]
    label = (labels_ar if is_arabic else labels_en)[min(score, 6)]
    return jsonify({"result": f"{label} ({score}/6)"})


def handle_text_counter(p):
    text = p.get("text", "")
    chars = len(text)
    chars_no_spaces = len(text.replace(" ", "").replace("\n", ""))
    words = len(text.strip().split()) if text.strip() else 0
    lines = len(text.splitlines())
    return jsonify({"result": f"Chars: {chars}\nChars (no spaces): {chars_no_spaces}\nWords: {words}\nLines: {lines}"})


def handle_percentage_calc(p):
    nums = re.findall(r"-?\d+(?:\.\d+)?", p.get("text", ""))
    if len(nums) < 2:
        return jsonify({"result": "يرجى إدخال رقمين" if p["is_arabic"] else "Please enter two numbers"})
    a, b = float(nums[0]), float(nums[1])
    return jsonify({"result": f"{nums[0]}% of {nums[1]} = {(a / 100) * b}"})


def handle_byte_converter(p):
    cleaned = re.sub(r"[^0-9.]", "", p.get("text", ""))
    b = float(cleaned) if cleaned else 0.0
    return jsonify({"result": f"Bytes: {b}\nKB: {b / 1024:.2f}\nMB: {b / 1024 ** 2:.2f}\nGB: {b / 1024 ** 3:.4f}\nTB: {b / 1024 ** 4:.6f}"})


def handle_unit_converter(p):
    cleaned = re.sub(r"[^0-9.]", "", p.get("text", ""))
    val = float(cleaned) if cleaned else 0.0
    return jsonify({"result": f"Meters: {val} m\nFeet: {val * 3.28084:.2f} ft\nInches: {val * 39.3701:.2f} in\nMiles: {val / 1609.34:.4f} mi\nKilometers: {val / 1000:.4f} km"})


def handle_uuid_generator(p):
    """أداة جديدة: توليد معرفات UUID فريدة."""
    try:
        count = int(p.get("count", 1))
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(50, count))
    return jsonify({"result": "\n".join(str(uuid.uuid4()) for _ in range(count))})


def handle_markdown_to_html(p):
    text = p.get("text", "")
    try:
        html_result = md_lib.markdown(text, extensions=[
            'extra', 'tables', 'fenced_code', 'nl2br', 'toc', 'def_list', 'abbr', 'attr_list', 'admonition', 'sane_lists'
        ])
        return jsonify({"result": html_result.strip()})
    except Exception:
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
    "merge-word": handle_merge_word,
    "pdf-to-excel": handle_pdf_to_excel,
    "pdf-to-ppt": handle_pdf_to_ppt,
    "merge-pdf": handle_merge_pdf,
    "split-pdf": handle_split_pdf,
    "rotate-pdf": handle_rotate_pdf,
    "compress-pdf": handle_compress_pdf,
    "protect-pdf": handle_protect_pdf,
    "unlock-pdf": handle_unlock_pdf,
    "watermark-pdf": handle_watermark_pdf,
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
    "resize-image": handle_resize_image,
    "rotate-image": handle_rotate_image,
    "watermark-image": handle_watermark_image,
    "strip-exif": handle_strip_exif,
    "base64-tool": handle_base64_tool,
    "url-encoder": handle_url_encoder,
    "json-beautifier": handle_json_beautifier,
    "css-js-minifier": handle_css_js_minifier,
    "html-entity": handle_html_entity,
    "hash-generator": handle_hash_generator,
    "hmac-generator": handle_hmac_generator,
    "timestamp-converter": handle_timestamp_converter,
    "clean-text": handle_clean_text,
    "text-to-qr": handle_text_to_qr,
    "password-generator": handle_password_generator,
    "password-strength": handle_password_strength,
    "text-counter": handle_text_counter,
    "percentage-calc": handle_percentage_calc,
    "byte-converter": handle_byte_converter,
    "unit-converter": handle_unit_converter,
    "uuid-generator": handle_uuid_generator,
    "markdown-to-html": handle_markdown_to_html,
    "html-to-markdown": handle_markdown_to_html,
    "text-diff": handle_text_diff,
}

NEEDS_MULTIPLE_FILES = {"merge-pdf", "merge-word"}


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
@limiter.limit(dynamic_convert_limit)
def convert():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return bad_request("Invalid request body")

    action = payload.get("action")
    if not isinstance(action, str):
        return bad_request("Unknown action")

    text = payload.get("text", "") or ""
    if not isinstance(text, str):
        return bad_request("Invalid text field")
    if len(text) > MAX_TEXT_CHARS:
        return bad_request(f"النص يتجاوز الحد المسموح ({MAX_TEXT_CHARS} حرف)")

    lang = payload.get("lang")
    is_arabic = lang == "ar" or is_arabic_text(text)

    files_to_check = payload.get("filesBase64") or [] if action in NEEDS_MULTIPLE_FILES else \
        ([payload.get("fileBase64")] if payload.get("fileBase64") else [])

    if action in NEEDS_MULTIPLE_FILES and len(files_to_check) > MAX_MERGE_FILES:
        msg = f"الحد الأقصى {MAX_MERGE_FILES} ملفات" if is_arabic else f"Maximum {MAX_MERGE_FILES} files"
        return jsonify({"error": msg}), 413

    for b64 in files_to_check:
        if b64 and (len(b64) * 3 / 4) > MAX_FILE_BYTES:
            msg = f"حجم الملف أكبر من الحد المسموح ({MAX_FILE_MB}MB)" if is_arabic else f"File exceeds the allowed size ({MAX_FILE_MB}MB)"
            return jsonify({"error": msg}), 413

    handler = REGISTRY.get(action)
    if not handler:
        return bad_request(f"Unknown action: {action}")

    ctx = dict(payload)
    ctx["text"] = text
    ctx["is_arabic"] = is_arabic

    try:
        return handler(ctx)
    except Exception:
        app.logger.exception(f"convert() error for action={action}")
        msg = "حدث خطأ أثناء المعالجة. تأكد من صحة الملف وحاول مجدداً." if is_arabic \
            else "An error occurred while processing. Please check the file and try again."
        return jsonify({"error": msg}), 500


@app.route('/ads.txt')
def ads_txt():
    return "google.com, pub-4343857922748618, DIRECT, f08c47fec0942fa0", 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

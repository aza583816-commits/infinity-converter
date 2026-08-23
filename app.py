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
import threading
import queue
import time
import gzip
import cloudconvert
import convertapi
import requests
import concurrent.futures
from datetime import datetime, timezone
from difflib import unified_diff

CLOUDCONVERT_WAIT_TIMEOUT = int(os.environ.get("CLOUDCONVERT_WAIT_TIMEOUT", 90))

def cloudconvert_wait_with_timeout(job_id, timeout_seconds=CLOUDCONVERT_WAIT_TIMEOUT):
    # cloudconvert.Job.wait() ما عنده مهلة زمنية داخلية، فلو تعلقت الخدمة السحابية
    # الطلب يفضل معلّق. هذا الغلاف يجبره يفشل بسرعة وينتقل لخط الدفاع التالي (ConvertAPI)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(cloudconvert.Job.wait, id=job_id)
        return future.result(timeout=timeout_seconds)

# ================= ضبط متغيرات النوى وحماية المعالج (CPU Throttling) =================
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

try:
    import resource
    MAX_VIRTUAL_MEM = 1536 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (MAX_VIRTUAL_MEM, MAX_VIRTUAL_MEM))
except Exception:
    pass

from flask import Flask, request, jsonify, render_template, send_file, send_from_directory, Response, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    from flask_compress import Compress
except Exception:
    Compress = None

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
    import tabula
except Exception:
    tabula = None

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

# ==================== تحسينات الذاكرة الفائقة والسيرفر (RAM Disk / tmpfs) ====================
if os.path.exists("/dev/shm"):
    tempfile.tempdir = "/dev/shm"

MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", 25))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
MAX_MERGE_FILES = int(os.environ.get("MAX_MERGE_FILES", 30))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", 1000))
MAX_OCR_PAGES = int(os.environ.get("MAX_OCR_PAGES", 25))
MAX_TEXT_CHARS = int(os.environ.get("MAX_TEXT_CHARS", 5_000_000))
SUBPROCESS_TIMEOUT = int(os.environ.get("SUBPROCESS_TIMEOUT", 180))
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "https://infinityconverter.com,https://www.infinityconverter.com"
).split(",") if o.strip()]

app_max_content = int(MAX_FILE_BYTES * MAX_MERGE_FILES * 1.4) + (5 * 1024 * 1024)
Image.MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", 100_000_000))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = app_max_content
app.config["COMPRESS_MIMETYPES"] = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript']
app.config["COMPRESS_LEVEL"] = 6
app.config["COMPRESS_MIN_SIZE"] = 500
app.config["COMPRESS_ALGORITHM"] = ['br', 'gzip']

if Compress:
    Compress(app)

SERVER_START_TIME = time.time()
TOTAL_REQUESTS_PROCESSED = 0
# قفل عام يمنع تعارض عدة نسخ LibreOffice headless على نفس ملف الـ profile
# عند وصول طلبات متزامنة (خصوصاً تحت ضغط عالي على Railway Pro)
LIBREOFFICE_LOCK = threading.Lock()

@app.before_request
def enforce_custom_domain():
    global TOTAL_REQUESTS_PROCESSED
    TOTAL_REQUESTS_PROCESSED += 1
    
    if request.path in ("/healthz", "/metrics", "/manifest.json", "/sw.js", "/robots.txt", "/sitemap.xml", "/.well-known/assetlinks.json") or request.path.startswith("/api/") or request.path.startswith("/static/"):
        return
    
    parsed_host = request.host.split(':')[0]
    if parsed_host == "infinity-converter-1.onrender.com":
        return redirect("https://infinityconverter.com" + request.full_path, code=301)

    # ملاحظة: تم حذف فرض HTTPS يدويًا من هنا لأن Render يفرضه تلقائيًا لأي دومين
    # مخصص مربوط ومُفعّل عنده. وجود فرض إضافي هنا كان سبب حلقة إعادة التوجيه اللانهائية سابقًا.

logging.basicConfig(level=logging.INFO)
CORS(app, resources={
    r"/convert": {"origins": ALLOWED_ORIGINS},
    r"/convert-async": {"origins": ALLOWED_ORIGINS},
    r"/task-status/*": {"origins": ALLOWED_ORIGINS},
    r"/pdf-preview": {"origins": ALLOWED_ORIGINS},
    r"/create-share-link": {"origins": ALLOWED_ORIGINS},
    r"/download/*": {"origins": ALLOWED_ORIGINS},
    r"/api/telegram-webhook": {"origins": "*"}
}, supports_credentials=False)

def advanced_fingerprint_key():
    remote_ip = get_remote_address()
    user_agent = request.headers.get("User-Agent", "generic")
    ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
    return f"{remote_ip}_{ua_hash}"

limiter = Limiter(
    advanced_fingerprint_key,
    app=app,
    default_limits=["1000 per day", "150 per hour"],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://"),
)

HEAVY_ACTIONS = {
    "word-to-pdf", "excel-to-pdf", "pdf-to-docx", "pdf-to-doc", "pdf-to-ppt", "pdf-to-excel",
    "merge-pdf", "compress-image", "image-to-text", "text-to-audio", "translate-text",
    "watermark-pdf", "compress-pdf", "protect-pdf", "clean-study-sheet", "summarize-doc",
    "pdf-page-number", "ink-saver-pdf", "sign-pdf", "remove-blank-pages", "generate-quiz",
    "redact-pdf", "pdf-compare", "reorder-pdf", "compress-pdf-target", "pdf-to-images",
    "extract-pdf-images", "arabic-proofreader", "ppt-to-images"
}

def dynamic_convert_limit():
    payload = request.get_json(silent=True) or request.form or {}
    return "10 per minute" if payload.get("action") in HEAVY_ACTIONS else "30 per minute"

@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'

    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif request.path in ("/convert", "/convert-async", "/pdf-preview", "/create-share-link"):
        response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' https:; frame-ancestors 'self'"
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

@app.errorhandler(404)
def not_found_custom(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource not found"}), 404
    if request.path in ("/", "/en", "/en/"):
        return render_template("index.html", tool_data=None, lang="en" if request.path.startswith("/en") else "ar", is_404=False)
    return render_template("index.html", tool_data=None, lang="ar", is_404=True), 404

ARABIC_FONT_NAME = "ArabicFont"
_arabic_font_registered = False

# ==================== إدارة المهام والتنظيف ====================
conversion_queue = queue.Queue()
async_task_results = {}
temporary_share_store = {}
dedup_conversion_cache = {}
TASK_TTL_SECONDS = 1800
SHARE_TTL_SECONDS = 86400
DEDUP_CACHE_TTL = 21600

def cache_cleanup_worker():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            expired_tasks = [k for k, v in async_task_results.items() if now - v.get("timestamp", now) > TASK_TTL_SECONDS]
            for k in expired_tasks:
                async_task_results.pop(k, None)
            
            expired_shares = [k for k, v in temporary_share_store.items() if now - v.get("timestamp", now) > SHARE_TTL_SECONDS]
            for k in expired_shares:
                temporary_share_store.pop(k, None)
                
            expired_dedup = [k for k, v in dedup_conversion_cache.items() if now - v.get("timestamp", now) > DEDUP_CACHE_TTL]
            for k in expired_dedup:
                dedup_conversion_cache.pop(k, None)
                
            gc.collect()
        except Exception:
            pass

threading.Thread(target=cache_cleanup_worker, daemon=True).start()

def background_worker():
    while True:
        try:
            task_id, task_func, args, callback = conversion_queue.get()
            if task_func is None: break
            if task_id:
                async_task_results[task_id] = {"status": "processing", "progress": 25, "timestamp": time.time()}
            try:
                res = task_func(*args)
                if task_id:
                    async_task_results[task_id] = {"status": "completed", "progress": 100, "result": res, "timestamp": time.time()}
                if callback: callback(res, None)
            except Exception as e:
                if task_id:
                    async_task_results[task_id] = {"status": "failed", "progress": 100, "error": str(e), "timestamp": time.time()}
                if callback: callback(None, str(e))
            finally:
                conversion_queue.task_done()
        except Exception: pass

worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

def ai_smart_ocr_extraction(image_bytes, is_arabic=True, lang_code=None):
    if pytesseract is None: return "OCR Library not available."
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        img = ImageEnhance.Contrast(img).enhance(2.2)
        lang = lang_code if lang_code else ('ara+eng' if is_arabic else 'eng')
        text = pytesseract.image_to_string(img, lang=lang)
        return re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text).strip()
    except Exception as e:
        return f"AI OCR Error: {str(e)}"

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
    ("remove-pdf-pages", "حذف صفحات من PDF", "Remove PDF Pages", "fileText", "i-pdf", "fa-circle-minus"),
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
    ("json-to-csv", "JSON إلى CSV", "JSON to CSV", "fileText", "i-dev", "fa-csv"),
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
    ("clean-study-sheet", "تنقية الملازم والكتب للطباعة", "Clean Study Sheets", "file", "i-img", "fa-wand-magic-sparkles"),
    ("pdf-page-number", "ترقيم صفحات PDF", "Number PDF Pages", "fileText", "i-pdf", "fa-list-ol"),
    ("ink-saver-pdf", "توفير حبر الطباعة (رمادي)", "Ink Saver PDF", "file", "i-pdf", "fa-print"),
    ("summarize-doc", "تلخيص المستندات والنصوص", "Summarize Text/Doc", "text", "i-word", "fa-brain"),
    ("citation-generator", "مولد التوثيق الأكاديمي (APA/MLA)", "Citation Generator", "text", "i-word", "fa-book-bookmark"),
    ("sign-pdf", "توقيع ملفات PDF إلكترونياً", "Sign PDF Online", "fileText", "i-pdf", "fa-signature"),
    ("remove-blank-pages", "حذف الصفحات الفارغة من PDF", "Remove Blank Pages", "file", "i-pdf", "fa-file-circle-xmark"),
    ("generate-quiz", "توليد أسئلة واختبارات من ملف", "Quiz & Flashcard Generator", "fileText", "i-word", "fa-spell-check"),
    ("redact-pdf", "طمس البيانات الحساسة من PDF", "Redact PDF", "fileText", "i-pdf", "fa-user-secret"),
    ("pdf-compare", "مقارنة نسختين من PDF", "Compare Two PDFs", "multiFile", "i-pdf", "fa-code-compare"),
    ("reorder-pdf", "إعادة ترتيب صفحات PDF", "Reorder PDF Pages", "fileText", "i-pdf", "fa-arrow-down-1-9"),
    ("compress-pdf-target", "ضغط PDF إلى حجم محدد (KB)", "Compress PDF to Target Size", "fileText", "i-pdf", "fa-gauge-high"),
    ("pdf-to-images", "PDF إلى صور JPG/PNG (ZIP)", "PDF to Images (ZIP)", "file", "i-img", "fa-file-zipper"),
    ("extract-pdf-images", "استخراج الصور المضمنة من PDF", "Extract Images from PDF", "file", "i-img", "fa-image"),
    ("arabic-proofreader", "المصحح والمدقق اللغوي العربي", "Arabic Proofreader", "text", "i-word", "fa-spell-check"),
    ("ppt-to-images", "شرائح PowerPoint إلى صور", "PPT to Images", "file", "i-ppt", "fa-file-powerpoint")
]

TOOLS_SEO = {}
for action, nameAr, nameEn, type_, iconClass, iconName in TOOLS_DEF:
    TOOLS_SEO[action] = {
        "slug": action, "nameAr": nameAr, "nameEn": nameEn, "type": type_, "iconClass": iconClass, "iconName": iconName,
        "seo_title_ar": f"أداة {nameAr} مجاناً أونلاين وبدقة عالية | V-Infinity",
        "seo_title_en": f"Free {nameEn} Online Tool | V-Infinity",
        "seo_desc_ar": f"أفضل أداة سحابية لتنفيذ {nameAr} بضغطة زر. معالجة سريعة وآمنة 100% ومجانية بالكامل بدون تخزين للملفات.",
        "seo_desc_en": f"Best cloud tool for {nameEn} with one click. Fast, secure, and 100% free with no file storage.",
        "h1_ar": nameAr, "h1_en": nameEn,
        "short_desc_ar": f"قم بإنجاز {nameAr} بسهولة وبدون تعقيد عبر تقنياتنا المتطورة.",
        "short_desc_en": f"Easily perform {nameEn} without complexity using our advanced tools.",
        "long_desc_ar": f"منصة V-Infinity تقدم لك أداة '{nameAr}' المجانية بالكامل. تم تصميم هذه الأداة لتكون سريعة جداً وتعمل بالذكاء الاصطناعي لضمان أعلى جودة ممكنة. أمان ملفاتك هو أولويتنا القصوى، حيث نقوم بمعالجة البيانات سحابياً وحذفها تلقائياً بمجرد انتهاء العملية دون الاحتفاظ بأي نسخ.",
        "long_desc_en": f"V-Infinity platform offers the completely free '{nameEn}' tool. This tool is designed to be extremely fast and uses advanced AI to ensure the highest quality possible. Your file security is our top priority; we process data in the cloud and automatically delete it once the operation is complete.",
        "faq_ar": [
            {"q": f"هل استخدام أداة {nameAr} مجاني؟", "a": "نعم، الأداة مجانية بالكامل ولا تتطلب أي تسجيل أو رسوم مخفية."},
            {"q": "هل ملفاتي آمنة عند الرفع؟", "a": "بالتأكيد! تتم المعالجة بشكل مشفر، وتُحذف جميع الملفات من خوادمنا تلقائياً فور انتهائك."}
        ],
        "faq_en": [
            {"q": f"Is the {nameEn} tool free to use?", "a": "Yes, the tool is completely free with no hidden fees or registration required."},
            {"q": "Are my uploaded files secure?", "a": "Absolutely! Processing is encrypted, and all files are automatically deleted from our servers immediately after you finish."}
        ]
    }

COMPARISON_PAGES = {
    "ilovepdf-alternative": {
        "slug": "ilovepdf-alternative", "nameAr": "أفضل بديل مجاني لـ iLovePDF", "nameEn": "Best Free iLovePDF Alternative",
        "type": "none", "iconClass": "i-pdf", "iconName": "fa-trophy",
        "seo_title_ar": "أفضل بديل مجاني لـ iLovePDF بدون حدود للملفات | V-Infinity",
        "seo_title_en": "Best Free iLovePDF Alternative without limits | V-Infinity",
        "seo_desc_ar": "هل تبحث عن بديل مجاني وسريع لـ iLovePDF؟ منصة V-Infinity تتيح تحويل وتعديل ملفات PDF بدون اشتراكات أو حدود يومية مع دعم فائق للعربية.",
        "seo_desc_en": "Looking for a free and fast alternative to iLovePDF? V-Infinity offers unlimited PDF conversion and editing with zero fees.",
        "h1_ar": "أفضل بديل مجاني لـ iLovePDF لعام 2026", "h1_en": "The #1 Free iLovePDF Alternative in 2026",
        "short_desc_ar": "جميع أدوات الـ PDF والمستندات مجانية 100% وبدون قيود أو حدود يومية.",
        "short_desc_en": "All PDF and document tools 100% free with no daily limits.",
        "long_desc_ar": "تعتبر V-Infinity البديل الأمثل لمنصة iLovePDF، حيث توفر معالجة سحابية فائقة السرعة مدعومة بالذكاء الاصطناعي لحل مشاكل الخطوط العربية المعكوسة وتنسيق الجداول، دون فرض أي رسوم أو قيود على عدد الملفات.",
        "long_desc_en": "V-Infinity is the ultimate alternative to iLovePDF, offering AI-powered cloud document processing without restrictions or fees.",
        "faq_ar": [{"q": "ما الفرق بين V-Infinity و iLovePDF؟", "a": "V-Infinity مجانية بالكامل، لا تفرض قيوداً يومية، وتوفر دعماً فائقاً لمعالجة النصوص العربية بدقة 100%."}],
        "faq_en": [{"q": "Why choose V-Infinity over iLovePDF?", "a": "V-Infinity is completely free with no limits and advanced AI accuracy for complex documents."}]
    },
    "smallpdf-alternative": {
        "slug": "smallpdf-alternative", "nameAr": "بديل Smallpdf المجاني", "nameEn": "Free Smallpdf Alternative",
        "type": "none", "iconClass": "i-pdf", "iconName": "fa-bolt",
        "seo_title_ar": "بديل Smallpdf المجاني بدون تسجيل | V-Infinity",
        "seo_title_en": "Free Smallpdf Alternative No Sign-up | V-Infinity",
        "seo_desc_ar": "حول واضغط ملفات PDF مجاناً دون الحاجة لاشتراك Smallpdf. معالجة آمنة وفورية للمستندات والصور.",
        "seo_desc_en": "Convert and compress PDFs for free without a Smallpdf subscription. Instant and secure cloud tools.",
        "h1_ar": "بديل Smallpdf المجاني والآمن بالكامل", "h1_en": "Free & Secure Smallpdf Alternative",
        "short_desc_ar": "معالجة سحابية مشفرة وفورية لجميع ملفاتك دون الحاجة لتسجيل حساب.",
        "short_desc_en": "Encrypted cloud processing for all your files without registration.",
        "long_desc_ar": "استمتع بكافة أدوات تحويل وضغط الـ PDF والصور مجاناً دون الانتظار أو الحاجة لدفع اشتراك شهري مثل Smallpdf.",
        "long_desc_en": "Enjoy all PDF conversion and compression features for free without monthly fees.",
        "faq_ar": [{"q": "هل يتطلب الموقع إنشاء حساب؟", "a": "لا، يمكنك استخدام كافة الأدوات مباشرة بدون تسجيل."}],
        "faq_en": [{"q": "Is account registration required?", "a": "No, all tools are instantly accessible without signing up."}]
    }
}
TOOLS_SEO.update(COMPARISON_PAGES)

# ==================== محتوى فريد ومكتوب يدويًا لأهم الأدوات (دفعة 1 من 3) ====================
# كل أداة عندها وصف، خطوات استخدام، مميزات، وأسئلة شائعة مختلفة فعليًا - مو قالب مكرر
UNIQUE_TOOL_CONTENT = {
    "pdf-to-docx": {
        "long_desc_ar": "تحويل PDF إلى Word ليس مجرد نسخ للنص — التحدي الحقيقي هو الحفاظ على الجداول والخطوط والتنسيق كما هي. تستخدم أداتنا محرك تحويل ثلاثي الطبقات: يبدأ بمحرك محلي فائق السرعة، وإذا كان الملف معقداً (جداول متداخلة، تنسيق عربي RTL، خطوط مدمجة)، ينتقل تلقائياً لمحركات سحابية متقدمة أدق لضمان نتيجة قابلة للتعديل الفوري في Word دون كسر أي عنصر.",
        "long_desc_en": "Converting PDF to Word isn't just text extraction — the real challenge is preserving tables, fonts, and layout exactly. Our tool uses a three-layer conversion engine: it starts with a fast local engine, and for complex files (nested tables, RTL Arabic formatting, embedded fonts) it automatically escalates to more precise cloud engines so the result opens in Word fully editable without broken formatting.",
        "how_to_ar": ["ارفع ملف PDF (حتى 25 ميجابايت) بالسحب والإفلات أو باختيار الملف.", "اضغط زر التحويل وانتظر ثوانٍ — الملفات المعقدة تأخذ وقتاً أطول قليلاً لضمان الدقة.", "حمّل ملف Word (.docx) الجاهز للتعديل الفوري."],
        "how_to_en": ["Upload your PDF file (up to 25MB) via drag-and-drop or file picker.", "Click Convert and wait a few seconds — complex files take slightly longer for accuracy.", "Download the ready-to-edit Word (.docx) file."],
        "features_ar": ["حفظ الجداول المدمجة والمتداخلة كما هي دون تفكك", "دعم كامل لاتجاه النص العربي (RTL) بدون انعكاس الحروف", "لا حد أقصى لعدد مرات الاستخدام يومياً", "معالجة الملف وحذفه تلقائياً بعد التحويل"],
        "features_en": ["Preserves merged and nested tables without breaking structure", "Full Arabic RTL text direction support with correct letter shaping", "No daily usage limit", "Files are processed and automatically deleted after conversion"],
        "faq_ar": [
            {"q": "هل يحافظ التحويل على الجداول المعقدة؟", "a": "نعم، نستخدم محرك متعدد الطبقات ينتقل تلقائياً لمعالجة أدق لو اكتشف جداول متداخلة أو تنسيقاً معقداً بالملف."},
            {"q": "ماذا لو كان ملفي بالعربي؟", "a": "الأداة مبنية خصيصاً لدعم اتجاه النص العربي (RTL) ومنع انعكاس أو تقطع الحروف، بعكس أغلب الأدوات المجانية الأخرى."},
            {"q": "كم يأخذ التحويل من وقت؟", "a": "الملفات البسيطة تتحول خلال ثوانٍ. الملفات المعقدة (جداول متداخلة، خطوط كثيرة) قد تأخذ حتى دقيقة لضمان الدقة."},
            {"q": "هل يوجد حد لعدد الصفحات؟", "a": "يمكنك تحويل ملفات تصل حتى 1000 صفحة طالما الحجم الإجمالي أقل من 25 ميجابايت."},
            {"q": "هل ملفاتي تُحفظ عندكم؟", "a": "لا، تتم معالجة الملف مؤقتاً في الذاكرة ويُحذف تلقائياً فور اكتمال التحويل أو انتهاء الجلسة."}
        ],
        "faq_en": [
            {"q": "Does the conversion preserve complex tables?", "a": "Yes — we use a multi-layer engine that automatically escalates to more precise processing when it detects nested tables or complex formatting."},
            {"q": "What if my file is in Arabic?", "a": "The tool is specifically built to support Arabic RTL text direction and prevent reversed or disconnected letters, unlike most free alternatives."},
            {"q": "How long does conversion take?", "a": "Simple files convert in seconds. Complex files (nested tables, many fonts) may take up to a minute for accuracy."},
            {"q": "Is there a page limit?", "a": "You can convert files up to 1000 pages as long as the total size is under 25MB."},
            {"q": "Are my files stored on your servers?", "a": "No — files are processed temporarily in memory and deleted automatically once conversion completes or the session ends."}
        ]
    },
    "word-to-pdf": {
        "long_desc_ar": "عكس عملية PDF إلى Word تبدو بسيطة، لكن المشكلة الشائعة هي اختلاف الخطوط بين جهازك والسيرفر مما يكسر التنسيق. نعالج هذا باستخدام محرك LibreOffice الكامل مع خطوط عربية وإنجليزية مثبتة مسبقاً بالسيرفر، فتحصل على PDF مطابق تماماً لما تراه في Word، بما فيه الصور والجداول والترويسات.",
        "long_desc_en": "Reversing PDF to Word sounds simple, but the common issue is font mismatches between your device and the server breaking the layout. We solve this using a full LibreOffice engine with pre-installed Arabic and English fonts on our servers, so you get a PDF that matches exactly what you see in Word — including images, tables, and headers.",
        "how_to_ar": ["ارفع ملف Word (.docx أو .doc).", "اضغط تحويل — تتم المعالجة بمحرك LibreOffice الكامل.", "حمّل ملف PDF جاهز للطباعة أو المشاركة فوراً."],
        "how_to_en": ["Upload your Word file (.docx or .doc).", "Click Convert — processing runs through a full LibreOffice engine.", "Download a print-ready, shareable PDF instantly."],
        "features_ar": ["يحافظ على الخطوط والترويسات والتذييل كما هي بالضبط", "يدعم ملفات .doc القديمة و.docx الحديثة", "معالجة متزامنة محمية تمنع تعارض الملفات وقت الازدحام", "بدون علامة مائية أو إضافات على الملف الناتج"],
        "features_en": ["Preserves fonts, headers, and footers exactly", "Supports both legacy .doc and modern .docx", "Concurrency-safe processing prevents file conflicts under load", "No watermark or branding added to the output"],
        "faq_ar": [
            {"q": "هل يدعم ملفات .doc القديمة؟", "a": "نعم، يدعم كلا الصيغتين .doc القديمة و.docx الحديثة من Word."},
            {"q": "هل الصور والجداول تنتقل بنفس مكانها؟", "a": "نعم، نستخدم محرك LibreOffice الكامل الذي يحافظ على التخطيط الأصلي بدقة عالية."},
            {"q": "هل يضيف الموقع أي علامة مائية على ملفي؟", "a": "لا إطلاقاً، الملف الناتج نظيف تماماً بدون أي إضافات من الموقع."},
            {"q": "ماذا لو الملف يحتوي خطوطاً غير شائعة؟", "a": "السيرفر مزوّد بمجموعة واسعة من الخطوط العربية والإنجليزية؛ لو خط معين غير متوفر، يُستبدل تلقائياً بأقرب خط مشابه للحفاظ على القراءة."},
            {"q": "هل يمكن تحويل عدة ملفات Word دفعة واحدة؟", "a": "حالياً الأداة تعالج ملفاً واحداً بكل عملية لضمان أعلى دقة ممكنة في النتيجة."}
        ],
        "faq_en": [
            {"q": "Does it support legacy .doc files?", "a": "Yes, both legacy .doc and modern .docx Word formats are supported."},
            {"q": "Do images and tables stay in the same position?", "a": "Yes — we use a full LibreOffice engine that preserves the original layout with high fidelity."},
            {"q": "Does the site add a watermark to my file?", "a": "No, the output file is completely clean with no branding added."},
            {"q": "What if my file uses uncommon fonts?", "a": "The server includes a wide range of Arabic and English fonts; if a specific font is unavailable, it's automatically substituted with the closest match to preserve readability."},
            {"q": "Can I convert multiple Word files at once?", "a": "Currently the tool processes one file per operation to guarantee the highest possible accuracy in the result."}
        ]
    },
    "merge-pdf": {
        "long_desc_ar": "دمج ملفات PDF قد يبدو عملية بسيطة، لكن الفرق الحقيقي بين أداة جيدة وأخرى ضعيفة يظهر عند التعامل مع ملفات كبيرة العدد أو المحمية بكلمة سر. أداتنا تسمح بدمج حتى 30 ملف PDF دفعة واحدة، مع الحفاظ على ترتيبك بالضبط كما رفعته، وبدون ضغط أو فقدان جودة الصفحات الأصلية.",
        "long_desc_en": "Merging PDF files may sound simple, but the real difference between a good tool and a weak one shows when handling many files at once. Our tool lets you merge up to 30 PDF files in a single batch, preserving your exact upload order, without compressing or degrading the original page quality.",
        "how_to_ar": ["ارفع كل ملفات PDF اللي تبي تدمجها (حتى 30 ملف).", "رتّب الملفات بالسحب حسب الترتيب النهائي اللي تبيه.", "اضغط دمج وحمّل ملف PDF واحد يجمعهم كلهم."],
        "how_to_en": ["Upload all the PDF files you want to merge (up to 30 files).", "Drag to reorder files into your final desired sequence.", "Click Merge and download one combined PDF file."],
        "features_ar": ["دمج حتى 30 ملف PDF بعملية واحدة", "إعادة ترتيب الملفات بالسحب قبل الدمج", "لا فقدان بجودة الصفحات الأصلية", "الحد الأقصى لحجم كل ملف 25 ميجابايت"],
        "features_en": ["Merge up to 30 PDF files in one operation", "Drag-to-reorder files before merging", "No quality loss on original pages", "25MB maximum size per individual file"],
        "faq_ar": [
            {"q": "كم أقصى عدد ملفات أقدر أدمجها؟", "a": "يمكنك دمج حتى 30 ملف PDF بعملية واحدة."},
            {"q": "هل ترتيب الصفحات يبقى كما رفعته؟", "a": "نعم، تماماً بنفس الترتيب اللي رفعت فيه الملفات (أو رتبته يدوياً قبل الدمج)."},
            {"q": "هل يقل حجم أو جودة الصفحات بعد الدمج؟", "a": "لا، الدمج لا يضغط أو يغيّر جودة الصفحات الأصلية إطلاقاً."},
            {"q": "هل يعمل مع ملفات محمية بكلمة سر؟", "a": "لازم تزيل كلمة السر أولاً باستخدام أداة 'إزالة كلمة سر PDF' قبل الدمج."},
            {"q": "هل يوجد حد أقصى لحجم كل ملف؟", "a": "نعم، الحد الأقصى لكل ملف على حدة هو 25 ميجابايت."}
        ],
        "faq_en": [
            {"q": "What's the maximum number of files I can merge?", "a": "You can merge up to 30 PDF files in a single operation."},
            {"q": "Does the page order stay as I uploaded it?", "a": "Yes, exactly in the order you uploaded (or manually reordered before merging)."},
            {"q": "Does merging reduce page quality or size?", "a": "No, merging never compresses or alters the original page quality."},
            {"q": "Does it work with password-protected files?", "a": "You'll need to remove the password first using the 'Unlock PDF' tool before merging."},
            {"q": "Is there a size limit per file?", "a": "Yes, the maximum size per individual file is 25MB."}
        ]
    },
    "split-pdf": {
        "long_desc_ar": "تقسيم PDF يستخدمه الطلاب والمعلمون كثيراً لفصل فصول كتاب أو أوراق امتحان عن بعضها. أداتنا تسمح بتحديد نطاقات صفحات دقيقة (مثل 1-5، 8، 10-12) واستخراجها كملف PDF منفصل جديد، مع تنبيه فوري لو كتبت رقم صفحة غير موجود بدل ما تحصل على نتيجة فارغة أو خاطئة بصمت.",
        "long_desc_en": "Splitting PDFs is heavily used by students and teachers to separate book chapters or exam sheets. Our tool lets you specify exact page ranges (like 1-5, 8, 10-12) and extract them as a new separate PDF, with an immediate clear warning if you enter a page number that doesn't exist — instead of silently returning an empty or wrong result.",
        "how_to_ar": ["ارفع ملف PDF اللي تبي تقسمه.", "اكتب أرقام أو نطاقات الصفحات اللي تبي تستخرجها (مثال: 1-5, 8).", "حمّل ملف PDF جديد يحتوي فقط الصفحات المحددة."],
        "how_to_en": ["Upload the PDF file you want to split.", "Type the page numbers or ranges you want to extract (e.g. 1-5, 8).", "Download a new PDF containing only the selected pages."],
        "features_ar": ["تحديد نطاقات صفحات متعددة بعملية واحدة (مثل 1-3, 7, 10-12)", "رسالة خطأ واضحة فوراً لو رقم صفحة غير موجود بالملف", "يدعم ملفات تصل حتى 1000 صفحة", "لا حاجة لتثبيت أي برنامج"],
        "features_en": ["Specify multiple page ranges in one go (e.g. 1-3, 7, 10-12)", "Clear instant error if a page number doesn't exist in the file", "Supports files up to 1000 pages", "No software installation required"],
        "faq_ar": [
            {"q": "كيف أكتب نطاق الصفحات؟", "a": "افصل بينها بفاصلة، واستخدم شرطة للنطاقات المتصلة، مثل: 1-5, 8, 10-12."},
            {"q": "ماذا لو كتبت رقم صفحة غير موجود؟", "a": "الأداة تنبهك فوراً برسالة خطأ واضحة توضح الصفحات غير الصحيحة بدل ما تعطيك نتيجة فارغة."},
            {"q": "هل أقدر أستخرج أكثر من نطاق بنفس الوقت؟", "a": "نعم، مثال: 1-3, 7, 10-12 يستخرج كل هذي الصفحات بملف واحد."},
            {"q": "هل يؤثر التقسيم على جودة الصفحات؟", "a": "لا، الصفحات المستخرجة بنفس الجودة الأصلية تماماً بدون أي ضغط."},
            {"q": "كم أقصى عدد صفحات يدعمه الملف الأصلي؟", "a": "حتى 1000 صفحة، طالما الحجم الإجمالي أقل من 25 ميجابايت."}
        ],
        "faq_en": [
            {"q": "How do I write the page range?", "a": "Separate with commas, and use a dash for continuous ranges, e.g.: 1-5, 8, 10-12."},
            {"q": "What if I enter a page number that doesn't exist?", "a": "The tool immediately warns you with a clear error message specifying the invalid pages, instead of returning an empty result."},
            {"q": "Can I extract multiple ranges at once?", "a": "Yes, for example: 1-3, 7, 10-12 extracts all of these pages into one file."},
            {"q": "Does splitting affect page quality?", "a": "No, extracted pages keep the exact original quality with no compression."},
            {"q": "What's the maximum page count for the source file?", "a": "Up to 1000 pages, as long as the total size is under 25MB."}
        ]
    },
    "compress-pdf": {
        "long_desc_ar": "ضغط PDF عندنا تكيفي فعلياً، مو إعداد ثابت واحد للجميع. الأداة تجرب أول مستوى ضغط متوازن (جودة عالية)، وإذا كان الملف مليء بالصور عالية الدقة والتخفيض بالحجم كان ضعيفاً، تنتقل تلقائياً لمستوى ضغط أقوى وتختار لك أصغر نتيجة ممكنة دون كسر جودة النصوص القابلة للقراءة.",
        "long_desc_en": "Our PDF compression is genuinely adaptive, not a single fixed setting for everyone. The tool first tries a balanced high-quality compression level, and if the file is image-heavy and the size reduction is weak, it automatically escalates to a stronger compression level and picks the smallest possible result without breaking readable text quality.",
        "how_to_ar": ["ارفع ملف PDF اللي تبي تصغّر حجمه.", "اضغط ضغط — الأداة تجرب أكثر من مستوى تلقائياً وتختار الأفضل.", "حمّل النسخة المضغوطة بحجم أصغر بشكل ملحوظ."],
        "how_to_en": ["Upload the PDF file you want to shrink.", "Click Compress — the tool automatically tries multiple levels and picks the best.", "Download the compressed version with a noticeably smaller size."],
        "features_ar": ["ضغط تكيفي حقيقي يتصاعد تلقائياً للملفات الغنية بالصور", "يحافظ على وضوح النصوص القابلة للقراءة", "مناسب لإرسال الملفات عبر البريد الإلكتروني بحدوده المعتادة", "معالجة سريعة حتى للملفات كبيرة الحجم"],
        "features_en": ["Genuinely adaptive compression that auto-escalates for image-heavy files", "Preserves readable text clarity", "Great for fitting typical email attachment size limits", "Fast processing even for large files"],
        "faq_ar": [
            {"q": "هل الضغط يقلل جودة النص؟", "a": "لا، الضغط يستهدف الصور بشكل أساسي، بينما النصوص تبقى واضحة وقابلة للقراءة بالكامل."},
            {"q": "كم نسبة التخفيض المتوقعة بالحجم؟", "a": "تختلف حسب محتوى الملف؛ الملفات الغنية بالصور عالية الدقة تشوف أكبر تخفيض، بينما الملفات النصية البحتة أصلاً صغيرة الحجم."},
            {"q": "هل يوجد مستوى ضغط أقوى لو الأول ما كفى؟", "a": "نعم، الأداة تكتشف تلقائياً لو التخفيض كان ضعيفاً وتنتقل لمستوى ضغط أقوى بنفس الطلب."},
            {"q": "هل يعمل مع ملفات ممسوحة ضوئياً (سكانر)؟", "a": "نعم، ويكون التأثير أوضح لأن ملفات السكانر عادة صور عالية الدقة يستفيد الضغط منها كثيراً."},
            {"q": "هل أقدر أحدد حجم مستهدف بالضبط؟", "a": "نعم، عندنا أداة منفصلة 'ضغط PDF إلى حجم محدد' لو تبي تتحكم بالحجم النهائي بالكيلوبايت بالضبط."}
        ],
        "faq_en": [
            {"q": "Does compression reduce text quality?", "a": "No, compression primarily targets images while text remains fully clear and readable."},
            {"q": "What size reduction should I expect?", "a": "It varies by content — image-heavy files see the biggest reduction, while text-only files are already small."},
            {"q": "Is there a stronger level if the first isn't enough?", "a": "Yes, the tool automatically detects a weak reduction and escalates to a stronger compression level in the same request."},
            {"q": "Does it work on scanned documents?", "a": "Yes, and the effect is even more noticeable since scanned pages are usually high-resolution images that benefit greatly from compression."},
            {"q": "Can I target an exact file size?", "a": "Yes, we have a separate 'Compress PDF to Target Size' tool if you need precise control over the final size in KB."}
        ]
    },
    "pdf-to-excel": {
        "long_desc_ar": "استخراج الجداول من PDF لملف Excel قابل للتعديل هو من أصعب التحويلات تقنياً، لأن الجداول تختلف بين مسطّرة بخطوط واضحة وأخرى بدون حدود مرئية. لهذا ندمج أكثر من محرك استخراج (Tabula للجداول المسطّرة، pdfplumber للجداول بدون حدود)، ونضيف OCR تلقائي للملفات الممسوحة ضوئياً، لضمان أعلى دقة ممكنة بغض النظر عن نوع الجدول.",
        "long_desc_en": "Extracting tables from PDF into an editable Excel file is one of the most technically difficult conversions, because tables vary between clearly ruled ones and borderless ones. That's why we combine multiple extraction engines (Tabula for ruled tables, pdfplumber for borderless ones), plus automatic OCR for scanned documents, to ensure the highest possible accuracy regardless of table type.",
        "how_to_ar": ["ارفع ملف PDF يحتوي على جدول أو أكثر.", "اضغط تحويل — الأداة تجرب عدة محركات استخراج تلقائياً.", "حمّل ملف Excel (.xlsx) بكل جدول بورقة منفصلة."],
        "how_to_en": ["Upload a PDF containing one or more tables.", "Click Convert — the tool automatically tries multiple extraction engines.", "Download an Excel (.xlsx) file with each table on its own sheet."],
        "features_ar": ["يدعم الجداول المسطّرة (بحدود واضحة) والجداول بدون حدود مرئية", "استخراج تلقائي بالـ OCR للملفات الممسوحة ضوئياً", "كل جدول ينزل بورقة Excel منفصلة لسهولة التعديل", "تعديل عرض الأعمدة تلقائياً حسب المحتوى"],
        "features_en": ["Supports both ruled (bordered) tables and borderless tables", "Automatic OCR extraction for scanned documents", "Each table lands on its own Excel sheet for easy editing", "Automatic column width adjustment based on content"],
        "faq_ar": [
            {"q": "هل يعمل مع جداول بدون حدود واضحة؟", "a": "نعم، نستخدم محرك pdfplumber المتخصص بالجداول اللي ما فيها خطوط فاصلة واضحة، بجانب Tabula للجداول المسطّرة."},
            {"q": "ماذا لو ملفي عبارة عن صورة ممسوحة ضوئياً؟", "a": "الأداة تكتشف هذا تلقائياً وتستخدم تقنية OCR لاستخراج بيانات الجدول من الصورة."},
            {"q": "هل كل جدول ينزل بورقة منفصلة؟", "a": "نعم، كل جدول مكتشف بالملف يوضع بورقة Excel مستقلة لسهولة التعديل والتنظيم."},
            {"q": "هل الأرقام تبقى كأرقام قابلة للحساب في Excel؟", "a": "نعم، البيانات الرقمية تُستخرج كقيم رقمية قابلة لعمل معادلات عليها مباشرة، مو كنص فقط."},
            {"q": "ماذا لو الملف فيه أكثر من جدول بصفحات مختلفة؟", "a": "الأداة تفحص كل صفحات الملف وتستخرج كل الجداول الموجودة تلقائياً بدون ما تحدد صفحة معينة."}
        ],
        "faq_en": [
            {"q": "Does it work with borderless tables?", "a": "Yes, we use the pdfplumber engine specialized for tables without visible separating lines, alongside Tabula for ruled tables."},
            {"q": "What if my file is a scanned image?", "a": "The tool automatically detects this and uses OCR technology to extract table data from the image."},
            {"q": "Does each table land on a separate sheet?", "a": "Yes, every detected table in the file is placed on its own Excel sheet for easy editing and organization."},
            {"q": "Do numbers stay as calculable numeric values in Excel?", "a": "Yes, numeric data is extracted as actual numeric values you can use directly in formulas, not just as text."},
            {"q": "What if the file has multiple tables across different pages?", "a": "The tool scans every page in the file and automatically extracts all tables found, without needing you to specify a page."}
        ]
    }
}
for slug, content in UNIQUE_TOOL_CONTENT.items():
    if slug in TOOLS_SEO:
        TOOLS_SEO[slug].update(content)

# ==================== دفعة 2 من 3 ====================
UNIQUE_TOOL_CONTENT_BATCH2 = {
    "pdf-to-images": {
        "long_desc_ar": "أحياناً تحتاج صفحات PDF كصور منفصلة — لعرضها بموقع، أو رفعها بمنصة تعليمية، أو مشاركتها بسرعة عبر واتساب بدون ما يحتاج المستلم يفتح ملف PDF كامل. أداتنا تحوّل كل صفحة لصورة JPG أو PNG عالية الدقة، وتجمعها كلها بملف ZIP واحد جاهز للتحميل بدل ما تنزّل كل صورة لحالها.",
        "long_desc_en": "Sometimes you need PDF pages as separate images — for a website, an LMS upload, or quick WhatsApp sharing without the recipient opening a full PDF. Our tool converts each page into a high-resolution JPG or PNG and packages them all into a single ZIP file ready to download, instead of downloading each image separately.",
        "how_to_ar": ["ارفع ملف PDF اللي تبي تحوّله لصور.", "اختر صيغة الصورة (JPG أو PNG).", "حمّل ملف ZIP يحتوي كل صفحة كصورة منفصلة."],
        "how_to_en": ["Upload the PDF file you want converted to images.", "Choose the image format (JPG or PNG).", "Download a ZIP file with every page as a separate image."],
        "features_ar": ["تحويل كل صفحات الملف دفعة واحدة داخل ZIP واحد", "دعم صيغتي JPG وPNG حسب حاجتك", "دقة صورة عالية تحافظ على وضوح النص والتفاصيل", "لا حاجة لتحميل كل صورة يدوياً"],
        "features_en": ["Converts all pages in one batch inside a single ZIP", "Supports both JPG and PNG based on your need", "High image resolution preserving text and detail clarity", "No need to download each image manually"],
        "faq_ar": [
            {"q": "هل يحول كل صفحات الملف أم صفحة وحدة؟", "a": "يحول كل الصفحات دفعة واحدة ويجمعها بملف ZIP واحد لتحميلها كلها بضغطة واحدة."},
            {"q": "وش الفرق بين JPG وPNG هنا؟", "a": "JPG أصغر حجماً ومناسب للمشاركة السريعة، بينما PNG أعلى جودة ومناسب لو الصفحة فيها نص دقيق أو رسومات."},
            {"q": "هل جودة الصور تكفي للطباعة؟", "a": "نعم، الصور تُصدّر بدقة عالية تكفي للعرض الرقمي والطباعة العادية."},
            {"q": "هل أقدر أحول صفحة واحدة بس؟", "a": "حالياً الأداة تحول كل صفحات الملف؛ لو تبي صفحة معينة بس، استخدم أداة 'تقسيم PDF' أول لاستخراجها ثم حوّلها."},
            {"q": "كم يأخذ وقت التحويل لملف كبير؟", "a": "يعتمد على عدد الصفحات، لكن غالباً يأخذ ثوانٍ معدودة حتى لملفات تحتوي عشرات الصفحات."}
        ],
        "faq_en": [
            {"q": "Does it convert all pages or just one?", "a": "It converts all pages at once and bundles them into a single ZIP file for one-click download."},
            {"q": "What's the difference between JPG and PNG here?", "a": "JPG is smaller and great for quick sharing, while PNG is higher quality and better for pages with fine text or graphics."},
            {"q": "Is the image quality good enough for printing?", "a": "Yes, images export at high resolution suitable for digital display and regular printing."},
            {"q": "Can I convert just one page?", "a": "Currently the tool converts all pages; if you need just one, use 'Split PDF' first to extract it, then convert."},
            {"q": "How long does conversion take for a large file?", "a": "It depends on page count, but it usually takes just a few seconds even for files with dozens of pages."}
        ]
    },
    "protect-pdf": {
        "long_desc_ar": "حماية ملف PDF بكلمة سر تستخدم تشفير AES-256 (نفس معيار التشفير المستخدم بالبنوك)، مما يمنع أي شخص من فتح الملف دون كلمة السر اللي تحددها. كما تقوم الأداة بمسح أي بيانات وصفية مخفية بالملف (مثل اسم منشئ الملف أو تاريخ التعديل) لحماية خصوصيتك بشكل كامل، مو بس تشفير المحتوى.",
        "long_desc_en": "Protecting a PDF with a password uses AES-256 encryption (the same standard used by banks), preventing anyone from opening the file without the password you set. The tool also strips any hidden metadata from the file (like the creator's name or last-modified date) for complete privacy, not just content encryption.",
        "how_to_ar": ["ارفع ملف PDF اللي تبي تحميه.", "اكتب كلمة السر اللي تبيها.", "حمّل الملف المحمي — ما أحد يقدر يفتحه بدون كلمة السر."],
        "how_to_en": ["Upload the PDF file you want to protect.", "Enter your chosen password.", "Download the protected file — no one can open it without the password."],
        "features_ar": ["تشفير AES-256 بمعيار بنكي فعلي", "مسح بيانات المؤلف والتاريخ من الملف تلقائياً", "لا يحتاج برنامج خارجي، كله من المتصفح", "الملف الأصلي عندك ما يتأثر إطلاقاً"],
        "features_en": ["Real bank-grade AES-256 encryption", "Automatically strips author and date metadata from the file", "No external software needed, everything from the browser", "Your original file remains completely unaffected"],
        "faq_ar": [
            {"q": "أي نوع تشفير تستخدمون؟", "a": "نستخدم تشفير AES-256، وهو نفس المعيار المستخدم في القطاع المصرفي والحكومي لحماية البيانات الحساسة."},
            {"q": "لو نسيت كلمة السر، أقدر أستردها؟", "a": "لا، احنا ما نحتفظ بأي نسخة من كلمة السر، فاحفظها بمكان آمن لأنه لا يمكن استعادتها."},
            {"q": "هل يمسح بيانات المؤلف من الملف؟", "a": "نعم، بالإضافة للتشفير، نمسح أي بيانات وصفية مخفية (اسم المنشئ، تاريخ التعديل) لحماية خصوصيتك بشكل كامل."},
            {"q": "هل يمكن حماية ملف محمي مسبقاً؟", "a": "لازم تزيل الحماية الحالية أولاً باستخدام أداة 'إزالة كلمة سر PDF' قبل إضافة كلمة سر جديدة."},
            {"q": "هل الحماية تمنع الطباعة أو النسخ أيضاً؟", "a": "الحماية الحالية تمنع فتح الملف بدون كلمة السر؛ للتحكم بصلاحيات الطباعة والنسخ تحديداً، تواصل معنا لطلب مخصص."}
        ],
        "faq_en": [
            {"q": "What kind of encryption do you use?", "a": "We use AES-256 encryption, the same standard used in banking and government sectors for sensitive data protection."},
            {"q": "If I forget the password, can I recover it?", "a": "No, we don't keep any copy of your password, so store it somewhere safe as it cannot be recovered."},
            {"q": "Does it strip author metadata from the file?", "a": "Yes, in addition to encryption, we remove any hidden metadata (creator name, modification date) for complete privacy."},
            {"q": "Can I protect an already-protected file?", "a": "You'll need to remove the current protection first using 'Unlock PDF' before adding a new password."},
            {"q": "Does protection also block printing or copying?", "a": "Current protection prevents opening the file without the password; for specific print/copy permission controls, contact us for a custom request."}
        ]
    },
    "unlock-pdf": {
        "long_desc_ar": "إزالة كلمة سر PDF مخصصة للملفات اللي تعرف كلمة سرها بنفسك وتحتاج تزيلها لتسهيل الوصول لاحقاً (مثل ملف رفعته أنت وحميته، أو ملف مشترك بينك وبين فريقك). الأداة تزيل الحماية وتنظف الملف من البيانات الوصفية المرتبطة بالتشفير السابق، بحيث تحصل على نسخة مفتوحة نظيفة تماماً.",
        "long_desc_en": "Removing a PDF password is meant for files whose password you already know and need removed for easier future access (like a file you uploaded and protected yourself, or one shared within your team). The tool removes the protection and cleans the file of metadata tied to the previous encryption, giving you a completely clean, open copy.",
        "how_to_ar": ["ارفع ملف PDF المحمي بكلمة سر.", "اكتب كلمة السر الصحيحة للملف.", "حمّل نسخة مفتوحة بدون أي حماية."],
        "how_to_en": ["Upload the password-protected PDF file.", "Enter the file's correct password.", "Download an open copy with no protection."],
        "features_ar": ["يزيل الحماية بشكل كامل ونهائي من الملف", "ينظف الملف من بيانات وصفية مرتبطة بالتشفير القديم", "سريع — النتيجة جاهزة خلال ثوانٍ", "الملف الأصلي المحمي عندك يبقى كما هو"],
        "features_en": ["Completely and permanently removes protection from the file", "Cleans the file of metadata tied to the old encryption", "Fast — result ready within seconds", "Your original protected file remains unchanged"],
        "faq_ar": [
            {"q": "هل أحتاج أعرف كلمة السر الحالية؟", "a": "نعم، الأداة تحتاج كلمة السر الصحيحة لفتح الملف وإزالة الحماية منه؛ لا يمكن كسر حماية ملف بدون معرفة كلمة السر."},
            {"q": "هل يبقى الملف الأصلي المحمي محفوظ؟", "a": "نعم، الأداة تنشئ نسخة جديدة مفتوحة ولا تلمس ملفك الأصلي المحمي."},
            {"q": "لماذا أزيل كلمة السر بدل ما أستخدم الملف مباشرة؟", "a": "مفيد لو تبي تشارك الملف بمجموعة ما تبي تكتب لهم كلمة السر كل مرة، أو تدمجه مع ملفات ثانية."},
            {"q": "هل تُحذف البيانات الوصفية أيضاً بعد إزالة الحماية؟", "a": "نعم، ننظف الملف من أي بيانات وصفية مرتبطة بالتشفير السابق لضمان نسخة نظيفة تماماً."},
            {"q": "هل تعملون هذا لأي ملف حتى لو مو ملفي؟", "a": "الأداة مخصصة للملفات اللي تملك صلاحية الوصول لها ومعرفة كلمة سرها، ونوصي باستخدامها فقط لملفاتك الخاصة."}
        ],
        "faq_en": [
            {"q": "Do I need to know the current password?", "a": "Yes, the tool needs the correct password to open the file and remove its protection; a file's protection cannot be bypassed without knowing the password."},
            {"q": "Does the original protected file remain intact?", "a": "Yes, the tool creates a new open copy and doesn't touch your original protected file."},
            {"q": "Why remove the password instead of just using the file directly?", "a": "Useful if you want to share the file with a group without giving out the password each time, or merge it with other files."},
            {"q": "Is metadata also cleaned after removing protection?", "a": "Yes, we clean the file of any metadata tied to the previous encryption to ensure a completely clean copy."},
            {"q": "Will this work on any file even if it's not mine?", "a": "The tool is intended for files you have rightful access to and know the password for; we recommend using it only for your own files."}
        ]
    },
    "image-to-pdf": {
        "long_desc_ar": "تجميع عدة صور بملف PDF واحد مفيد جداً لأرشفة إيصالات، رفع واجبات مصورة، أو إرسال مجموعة صور بملف منظم واحد بدل عشرات المرفقات. الأداة ترتب الصور بالترتيب اللي تحدده، وتضبط كل صورة تلقائياً لتملأ صفحة PDF بشكل متناسق دون تشويه أو قص غير مرغوب.",
        "long_desc_en": "Combining several images into one PDF is great for archiving receipts, submitting photographed assignments, or sending a group of images as one organized file instead of dozens of attachments. The tool arranges images in your chosen order and automatically fits each one to a PDF page cleanly, without distortion or unwanted cropping.",
        "how_to_ar": ["ارفع الصور اللي تبي تجمعها (JPG أو PNG).", "رتّبها بالسحب حسب الترتيب اللي تبيه بالملف النهائي.", "حمّل ملف PDF واحد يحتوي كل الصور مرتبة."],
        "how_to_en": ["Upload the images you want to combine (JPG or PNG).", "Drag to arrange them in your desired final order.", "Download one PDF file containing all images in order."],
        "features_ar": ["يدعم رفع عدة صور دفعة واحدة", "إعادة ترتيب الصور بالسحب قبل الإنشاء", "كل صورة تُضبط تلقائياً لتناسب صفحة PDF كاملة", "يدعم صيغ JPG وPNG وHEIC"],
        "features_en": ["Supports uploading multiple images at once", "Drag-to-reorder images before generating", "Each image auto-fits a full PDF page", "Supports JPG, PNG, and HEIC formats"],
        "faq_ar": [
            {"q": "كم صورة أقدر أضيف بملف واحد؟", "a": "تقدر تضيف عدد كبير من الصور بعملية واحدة طالما الحجم الإجمالي ضمن الحد المسموح."},
            {"q": "هل الصور تنقص جودتها بعد التحويل؟", "a": "لا، الصور تُدرج بدقتها الأصلية داخل صفحات PDF بدون ضغط يؤثر على الوضوح."},
            {"q": "هل يدعم صور HEIC من الآيفون؟", "a": "نعم، يمكنك رفع صور HEIC مباشرة وتُحوّل تلقائياً ضمن عملية الدمج."},
            {"q": "هل أقدر أغيّر ترتيب الصور قبل الإنشاء؟", "a": "نعم، تقدر تسحب الصور وترتبها بالترتيب اللي تبيه قبل ما تضغط إنشاء الملف."},
            {"q": "هل كل صورة تاخذ صفحة منفصلة؟", "a": "نعم، كل صورة تُوضع بصفحة PDF خاصة بها للحفاظ على وضوحها الكامل."}
        ],
        "faq_en": [
            {"q": "How many images can I add to one file?", "a": "You can add a large number of images in one operation as long as the total size stays within the allowed limit."},
            {"q": "Does image quality drop after conversion?", "a": "No, images are inserted at their original resolution into PDF pages without quality-degrading compression."},
            {"q": "Does it support HEIC images from iPhone?", "a": "Yes, you can upload HEIC images directly and they're automatically converted as part of the merge process."},
            {"q": "Can I change the image order before generating?", "a": "Yes, you can drag and arrange images in your preferred order before clicking generate."},
            {"q": "Does each image get its own page?", "a": "Yes, each image is placed on its own PDF page to preserve its full clarity."}
        ]
    },
    "heic-to-jpg": {
        "long_desc_ar": "صيغة HEIC هي الصيغة الافتراضية لصور آيفون، لكنها غير مدعومة بشكل واسع خارج منظومة أبل — تفتح بمشاكل على أجهزة أندرويد أو ويندوز أو عند رفعها لمواقع كثيرة. أداتنا تحول صور HEIC إلى JPG المدعوم عالمياً بضغطة واحدة، مع الحفاظ على الجودة الأصلية للصورة بدون أي فقدان ملحوظ.",
        "long_desc_en": "HEIC is the default format for iPhone photos, but it's not widely supported outside Apple's ecosystem — causing issues opening it on Android, Windows, or when uploading to many websites. Our tool converts HEIC images to universally supported JPG in one click, preserving the original image quality with no noticeable loss.",
        "how_to_ar": ["ارفع صورة أو أكثر بصيغة HEIC.", "اضغط تحويل — العملية فورية.", "حمّل صور JPG تفتح على أي جهاز أو موقع."],
        "how_to_en": ["Upload one or more HEIC images.", "Click Convert — it's instant.", "Download JPG images that open on any device or website."],
        "features_ar": ["تحويل فوري بدون فقدان ملحوظ بالجودة", "يدعم تحويل عدة صور HEIC دفعة واحدة", "النتيجة JPG متوافقة مع كل الأجهزة والمواقع", "لا حاجة لتطبيق آيفون أو برنامج إضافي"],
        "features_en": ["Instant conversion with no noticeable quality loss", "Supports converting multiple HEIC images at once", "The resulting JPG is compatible with all devices and websites", "No iPhone app or extra software needed"],
        "faq_ar": [
            {"q": "لماذا صور آيفون تنحفظ بصيغة HEIC أصلاً؟", "a": "أبل تستخدم HEIC لأنها تحفظ نفس الجودة بحجم ملف أصغر من JPG، لكنها أقل توافقاً خارج أجهزة أبل."},
            {"q": "هل تنقص جودة الصورة بعد التحويل لـJPG؟", "a": "الفرق غير ملحوظ عملياً؛ نحافظ على أعلى جودة ممكنة أثناء التحويل."},
            {"q": "هل أقدر أحول أكثر من صورة بنفس الوقت؟", "a": "نعم، يمكنك رفع عدة صور HEIC وتحويلها كلها دفعة واحدة."},
            {"q": "هل يعمل مع فيديوهات Live Photos أيضاً؟", "a": "لا، الأداة مخصصة لتحويل الصور الثابتة HEIC فقط، وليس مقاطع Live Photos المتحركة."},
            {"q": "هل الصورة الناتجة تحتفظ ببيانات الموقع (GPS)؟", "a": "لأسباب خصوصية، نقوم بمسح البيانات الوصفية الحساسة مثل الموقع الجغرافي من الصورة الناتجة."}
        ],
        "faq_en": [
            {"q": "Why do iPhone photos save as HEIC in the first place?", "a": "Apple uses HEIC because it preserves the same quality at a smaller file size than JPG, but it's less compatible outside Apple devices."},
            {"q": "Does quality drop after converting to JPG?", "a": "The difference is practically unnoticeable; we preserve the highest possible quality during conversion."},
            {"q": "Can I convert multiple images at once?", "a": "Yes, you can upload several HEIC images and convert them all in a single batch."},
            {"q": "Does it work with Live Photos videos too?", "a": "No, the tool is designed for converting still HEIC images only, not the moving Live Photos clips."},
            {"q": "Does the resulting image keep location (GPS) data?", "a": "For privacy reasons, we strip sensitive metadata such as geolocation from the resulting image."}
        ]
    }
}
for slug, content in UNIQUE_TOOL_CONTENT_BATCH2.items():
    if slug in TOOLS_SEO:
        TOOLS_SEO[slug].update(content)

# ==================== محتوى أصلي وفريد لأهم 15 أداة (لا يعتمد على قالب مكرر) ====================
# هذا القسم يستبدل المحتوى العام المولّد تلقائياً بمحتوى مكتوب خصيصاً لكل أداة،
# لمعالجة ملاحظة جوجل بخصوص "المحتوى القليل أو المتكرر آلياً" قبل إعادة التقديم لـ AdSense
RICH_TOOL_CONTENT = {
    "pdf-to-docx": {
        "long_desc_ar": "يعتمد محول PDF إلى Word في V-Infinity على نظام دفاع ثلاثي: أولاً محرك محلي سريع (pdf2docx) للملفات البسيطة، ثم في حال احتوى الملف على جداول متداخلة أو رموز مرفوعة (superscript) ينتقل تلقائياً لمحركات سحابية أدق (CloudConvert وConvertAPI) لضمان الحفاظ على التنسيق الأصلي، الجداول، والخطوط العربية دون تشوه.",
        "long_desc_en": "Our PDF to Word converter uses a triple-layer engine: a fast local pdf2docx pass for simple files, and automatic escalation to cloud-grade engines (CloudConvert, ConvertAPI) whenever the PDF contains nested tables or superscript/subscript text — ensuring formatting, tables, and Arabic typography stay intact.",
        "faq_ar": [
            {"q": "هل يحافظ التحويل على الجداول المعقدة؟", "a": "نعم، نستخدم محركات متعددة، ولو كان الجدول متداخلاً ننتقل تلقائياً لمحرك أدق لضمان عدم كسر الهيكل."},
            {"q": "هل يدعم النصوص العربية والاتجاه من اليمين لليسار؟", "a": "نعم، الأداة مصممة خصيصاً لدعم تشكيل الحروف العربية واتجاه RTL دون تقطيع."},
            {"q": "هل يوجد حد لحجم ملف PDF؟", "a": "الحد الأقصى 25 ميجابايت لكل ملف لضمان سرعة المعالجة لجميع المستخدمين."},
            {"q": "ماذا يحدث لو كان الملف PDF ممسوحاً ضوئياً (صورة)؟", "a": "يتم اكتشاف ذلك تلقائياً وتفعيل تقنية التعرف الضوئي (OCR) لاستخراج النص قبل التحويل."},
            {"q": "هل الملف الناتج قابل للتعديل الكامل في Word؟", "a": "نعم، الناتج ملف .docx قياسي قابل للتعديل الكامل فور فتحه."}
        ],
        "faq_en": [
            {"q": "Does the conversion preserve complex tables?", "a": "Yes — if a table is nested, we automatically escalate to a more precise cloud engine to avoid breaking the structure."},
            {"q": "Does it support Arabic and RTL text?", "a": "Yes, the tool is specifically built to preserve Arabic letter shaping and right-to-left direction."},
            {"q": "Is there a file size limit?", "a": "Yes, 25MB per file to keep processing fast for everyone."},
            {"q": "What if my PDF is a scanned image?", "a": "It's automatically detected and OCR is triggered to extract the text before conversion."},
            {"q": "Is the resulting Word file fully editable?", "a": "Yes, you get a standard .docx file, fully editable the moment you open it."}
        ]
    },
    "word-to-pdf": {
        "long_desc_ar": "يحوّل مستندات Word (.docx) إلى PDF عبر محرك LibreOffice المدمج بالسيرفر، مع الحفاظ على الخطوط، الصور، وتنسيق الفقرات كما هي بالضبط. في حال فشل التحويل المحلي لأي سبب، يوجد خط دفاع سحابي احتياطي يضمن نجاح العملية تقريباً في كل الحالات.",
        "long_desc_en": "Converts Word documents (.docx) to PDF using a server-side LibreOffice engine, preserving fonts, images, and paragraph formatting exactly as they appear in the original. A cloud fallback engine kicks in automatically if local conversion fails for any reason.",
        "faq_ar": [
            {"q": "هل تتغير الخطوط عند التحويل؟", "a": "لا، يتم الحفاظ على الخطوط المستخدمة أو استبدالها بأقرب خط متوافق بصرياً لو غير متوفر بالسيرفر."},
            {"q": "هل يدعم الملفات القديمة .doc؟", "a": "الدعم الرئيسي لملفات .docx؛ لملفات .doc القديمة استخدم أداة \"Doc to Docx\" أولاً."},
            {"q": "هل الصور داخل المستند تنتقل بنفس الجودة؟", "a": "نعم، تنتقل الصور بدقتها الأصلية دون ضغط إضافي."},
            {"q": "كم يستغرق التحويل؟", "a": "عادة ثوانٍ معدودة لمعظم المستندات، ويعتمد على عدد الصفحات وحجم الصور."},
            {"q": "هل يمكن تحويل عدة ملفات Word دفعة واحدة؟", "a": "كل عملية تحويل واحدة لملف واحد؛ لدمج عدة ملفات استخدم أداة \"دمج Word\" أولاً."}
        ],
        "faq_en": [
            {"q": "Do fonts change during conversion?", "a": "No, original fonts are preserved, or substituted with the closest visual match if unavailable on the server."},
            {"q": "Does it support old .doc files?", "a": ".docx is the primary format; for old .doc files, use the \"Doc to Docx\" tool first."},
            {"q": "Do embedded images keep their quality?", "a": "Yes, images are carried over at their original resolution without extra compression."},
            {"q": "How long does conversion take?", "a": "Usually a few seconds for most documents, depending on page count and image size."},
            {"q": "Can I convert multiple Word files at once?", "a": "Each conversion handles one file; use \"Merge Word\" first if you need to combine files."}
        ]
    },
    "merge-pdf": {
        "long_desc_ar": "يدمج حتى 30 ملف PDF في ملف واحد مرتب بنفس ترتيب رفعك للملفات، دون أي فقدان بالجودة أو التنسيق. مثالي للطلاب لدمج فصول كتاب، أو للموظفين لتجميع عدة تقارير في مستند واحد جاهز للأرشفة أو الإرسال.",
        "long_desc_en": "Merge up to 30 PDF files into a single document, preserving your upload order with zero quality or formatting loss. Perfect for students combining book chapters or professionals compiling multiple reports into one archive-ready file.",
        "faq_ar": [
            {"q": "ما أقصى عدد ملفات يمكن دمجها؟", "a": "يمكنك دمج حتى 30 ملف PDF في عملية واحدة."},
            {"q": "هل يحافظ الدمج على ترتيب الصفحات الأصلي لكل ملف؟", "a": "نعم، كل ملف يحتفظ بترتيب صفحاته الداخلي، والدمج يكون حسب ترتيب رفعك للملفات."},
            {"q": "هل تقل جودة الملفات بعد الدمج؟", "a": "لا، الدمج لا يعيد ضغط المحتوى، فتبقى الجودة الأصلية كما هي."},
            {"q": "هل يمكنني إعادة ترتيب الملفات قبل الدمج؟", "a": "نعم، رتب الملفات بالترتيب المطلوب قبل الرفع أو أثناء الاختيار."},
            {"q": "هل الملفات المحمية بكلمة سر تدعم الدمج؟", "a": "يفضل إزالة الحماية أولاً عبر أداة \"إزالة كلمة سر PDF\" قبل الدمج."}
        ],
        "faq_en": [
            {"q": "What's the maximum number of files I can merge?", "a": "Up to 30 PDF files in a single operation."},
            {"q": "Does merging preserve each file's internal page order?", "a": "Yes, each file keeps its internal page order, and files are merged in the order you upload them."},
            {"q": "Does quality drop after merging?", "a": "No, merging doesn't recompress content, so original quality is preserved."},
            {"q": "Can I reorder files before merging?", "a": "Yes, arrange them in your desired order before or during upload."},
            {"q": "Do password-protected files work?", "a": "Remove protection first using the \"Unlock PDF\" tool, then merge."}
        ]
    },
    "split-pdf": {
        "long_desc_ar": "يقسّم ملف PDF واحد إلى ملفات منفصلة، صفحة بصفحة أو حسب نطاق تحدده أنت. مفيد جداً لفصل فاتورة عن أخرى داخل ملف مجمّع، أو استخراج فصل واحد فقط من كتاب طويل دون التعامل مع الملف كاملاً.",
        "long_desc_en": "Split a single PDF into separate files — page by page, or by a custom range you define. Ideal for separating individual invoices from a batch file, or extracting just one chapter from a long book without handling the whole document.",
        "faq_ar": [
            {"q": "هل أقدر أحدد صفحات معينة للتقسيم؟", "a": "نعم، تقدر تكتب أرقام أو نطاقات محددة (مثل 1، 3، 5-7)."},
            {"q": "ماذا يحدث لو كتبت رقم صفحة غير موجود؟", "a": "الأداة تنبهك فوراً برسالة خطأ واضحة توضح عدد صفحات الملف الفعلي بدل تجاهل الخطأ."},
            {"q": "هل يمكن تقسيم الملف لكل صفحة على حدة تلقائياً؟", "a": "نعم، اختر خيار التقسيم الكامل ليصير كل صفحة ملف PDF منفصل."},
            {"q": "هل الناتج ملف واحد أم عدة ملفات؟", "a": "يعتمد على اختيارك؛ يمكن استلام عدة ملفات مضغوطة في ZIP."},
            {"q": "هل يدعم ملفات PDF الكبيرة؟", "a": "نعم حتى الحد الأقصى المسموح به (25 ميجابايت وحتى 1000 صفحة)."}
        ],
        "faq_en": [
            {"q": "Can I choose specific pages to split?", "a": "Yes, enter specific numbers or ranges (e.g. 1, 3, 5-7)."},
            {"q": "What happens if I enter a page number that doesn't exist?", "a": "You'll get a clear error message stating the actual page count instead of a silent failure."},
            {"q": "Can it split every page automatically into its own file?", "a": "Yes, choose the full-split option to get one PDF per page."},
            {"q": "Is the output one file or several?", "a": "Depends on your choice; you can receive multiple files bundled in a ZIP."},
            {"q": "Does it support large PDFs?", "a": "Yes, up to the platform limit (25MB and up to 1000 pages)."}
        ]
    },
    "compress-pdf": {
        "long_desc_ar": "يقلل حجم ملف PDF بذكاء دون التضحية بوضوح النص. يبدأ بمستوى ضغط متوازن، وإذا كان الملف يحتوي على صور عالية الدقة ولم يتحسن الحجم كثيراً، يصعّد تلقائياً لمستوى ضغط أقوى ويختار أفضل نتيجة، مثالي لإرسال الملفات عبر البريد الإلكتروني بحد أقصى للحجم.",
        "long_desc_en": "Intelligently shrinks PDF file size without sacrificing text clarity. It starts with a balanced compression level, and if the file is image-heavy and doesn't shrink much, it automatically escalates to a stronger setting and keeps whichever result is smallest — ideal for emailing files under size limits.",
        "faq_ar": [
            {"q": "كم نسبة التخفيض المتوقعة بالحجم؟", "a": "تختلف حسب المحتوى، لكن الملفات المليئة بالصور عادة تنخفض بنسبة أكبر بكثير من الملفات النصية فقط."},
            {"q": "هل يؤثر الضغط على وضوح النص؟", "a": "لا، الضغط يستهدف الصور والبيانات الزائدة أساساً، والنص يبقى حاداً وواضحاً."},
            {"q": "هل يمكنني اختيار مستوى ضغط معين؟", "a": "الأداة تختار تلقائياً أفضل توازن بين الحجم والجودة؛ لو تحتاج حجم دقيق استخدم أداة \"ضغط PDF لحجم محدد\"."},
            {"q": "هل يعمل مع الملفات الممسوحة ضوئياً؟", "a": "نعم، وغالباً هذي الملفات تستفيد أكثر من الضغط لأنها تحتوي صور عالية الدقة."},
            {"q": "هل تُحذف بيانات التعريف (Metadata) أثناء الضغط؟", "a": "نعم، تُمسح بيانات المؤلف والتاريخ تلقائياً حفاظاً على خصوصيتك."}
        ],
        "faq_en": [
            {"q": "How much size reduction can I expect?", "a": "It varies by content, but image-heavy files typically shrink far more than text-only files."},
            {"q": "Does compression affect text clarity?", "a": "No, compression mainly targets images and redundant data — text stays sharp and readable."},
            {"q": "Can I pick a specific compression level?", "a": "The tool automatically picks the best size/quality balance; for an exact target size, use \"Compress PDF to Target Size.\""},
            {"q": "Does it work on scanned documents?", "a": "Yes, and they often benefit the most since they contain high-resolution images."},
            {"q": "Is metadata removed during compression?", "a": "Yes, author and date metadata is automatically stripped for your privacy."}
        ]
    },
    "protect-pdf": {
        "long_desc_ar": "يضيف كلمة سر قوية بمعيار تشفير AES-256 لملف PDF، فلا يقدر أي شخص يفتحه إلا بمعرفة كلمة السر. يُستخدم بكثرة لحماية العقود، الفواتير، والمستندات الرسمية قبل إرسالها عبر البريد الإلكتروني.",
        "long_desc_en": "Adds a strong AES-256 encrypted password to your PDF, so only someone who knows the password can open it. Widely used to protect contracts, invoices, and official documents before emailing them.",
        "faq_ar": [
            {"q": "ما نوع التشفير المستخدم؟", "a": "تشفير AES-256، أحد أقوى معايير التشفير المعتمدة عالمياً."},
            {"q": "هل تُحذف بياناتي الشخصية من الملف أيضاً؟", "a": "نعم، بالإضافة للحماية بكلمة سر، يتم مسح بيانات المؤلف والتعريف تلقائياً."},
            {"q": "ماذا لو نسيت كلمة السر بعد الحماية؟", "a": "للأسف لا يمكننا استرجاعها، فالتشفير حقيقي وليس شكلياً؛ احتفظ بنسخة من كلمة السر بمكان آمن."},
            {"q": "هل يمكنني إزالة الحماية لاحقاً؟", "a": "نعم، عبر أداة \"إزالة كلمة سر PDF\" إذا كنت تعرف كلمة السر الحالية."},
            {"q": "هل يعمل مع الملفات الكبيرة؟", "a": "نعم، حتى الحد الأقصى المسموح لحجم الملفات."}
        ],
        "faq_en": [
            {"q": "What encryption is used?", "a": "AES-256 encryption, one of the strongest globally recognized standards."},
            {"q": "Is my personal metadata also removed?", "a": "Yes, in addition to password protection, author/creation metadata is automatically stripped."},
            {"q": "What if I forget the password afterward?", "a": "Unfortunately it can't be recovered — the encryption is real, not cosmetic. Keep your password somewhere safe."},
            {"q": "Can I remove protection later?", "a": "Yes, using the \"Unlock PDF\" tool if you know the current password."},
            {"q": "Does it work with large files?", "a": "Yes, up to the platform's maximum file size limit."}
        ]
    },
    "unlock-pdf": {
        "long_desc_ar": "يزيل كلمة السر من ملف PDF محمي بشرط معرفتك للكلمة الحالية، ليصير الملف قابلاً للفتح والتعديل بحرية دون طلب كلمة سر في كل مرة. لا يُستخدم لكسر حماية ملفات لا تملكها.",
        "long_desc_en": "Removes the password from a protected PDF, provided you know the current password, so the file opens freely without prompting each time. Not intended for bypassing protection on files you don't own.",
        "faq_ar": [
            {"q": "هل يمكن إزالة الحماية بدون معرفة كلمة السر؟", "a": "لا، الأداة مصممة لإزالة الحماية من ملفاتك الخاصة فقط بمعرفة كلمة السر الصحيحة."},
            {"q": "هل تُمسح بيانات التعريف بعد الإزالة؟", "a": "نعم، تُمسح بيانات المؤلف والتاريخ تلقائياً حفاظاً على خصوصيتك."},
            {"q": "هل يتغير محتوى الملف بعد الإزالة؟", "a": "لا، فقط طبقة الحماية تُزال، والمحتوى يبقى كما هو تماماً."},
            {"q": "هل يدعم كل أنواع حماية PDF؟", "a": "يدعم الحماية القياسية بكلمة مرور المستخدم (User Password)."},
            {"q": "هل الملف الناتج آمن للمشاركة؟", "a": "بما أنه بدون حماية، تأكد من مشاركته فقط مع من تثق به."}
        ],
        "faq_en": [
            {"q": "Can protection be removed without knowing the password?", "a": "No, the tool only removes protection from your own files when you provide the correct password."},
            {"q": "Is metadata cleared after removal?", "a": "Yes, author and date metadata is automatically stripped for your privacy."},
            {"q": "Does the content change after unlocking?", "a": "No, only the protection layer is removed — content stays exactly the same."},
            {"q": "Does it support all PDF protection types?", "a": "It supports standard user-password encryption."},
            {"q": "Is the unlocked file safe to share?", "a": "Since it's no longer protected, only share it with people you trust."}
        ]
    },
    "sign-pdf": {
        "long_desc_ar": "يتيح لك رسم توقيعك بالماوس أو بإصبعك على الجوال وإضافته مباشرة على أي صفحة من ملف PDF، دون طباعة أو مسح ضوئي. مثالي للتوقيع السريع على العقود والموافقات دون الحاجة لأدوات خارجية.",
        "long_desc_en": "Draw your signature with a mouse or your finger on mobile and place it directly on any page of a PDF — no printing or scanning required. Perfect for quickly signing contracts and approvals without external tools.",
        "faq_ar": [
            {"q": "هل التوقيع الإلكتروني له نفس القيمة القانونية للتوقيع اليدوي؟", "a": "يعتمد على قوانين بلدك ونوع المستند؛ للمستندات الرسمية الحساسة يُنصح بمراجعة الجهة المعنية."},
            {"q": "هل يمكن تحديد مكان التوقيع بدقة على الصفحة؟", "a": "نعم، يمكنك وضع التوقيع بالمكان اللي تختاره بالضبط."},
            {"q": "هل يدعم التوقيع على الجوال؟", "a": "نعم، يمكنك الرسم بإصبعك مباشرة على شاشة الجوال."},
            {"q": "هل يمكن التوقيع في أكثر من مكان بنفس الملف؟", "a": "كل عملية تضيف توقيعاً واحداً؛ كرر العملية لإضافة توقيعات متعددة."},
            {"q": "هل التوقيع قابل للحذف أو التعديل لاحقاً؟", "a": "يصبح جزءاً من محتوى الصفحة بعد الحفظ، فلا يمكن فصله تلقائياً."}
        ],
        "faq_en": [
            {"q": "Does an e-signature carry the same legal weight as a handwritten one?", "a": "It depends on your country's laws and document type; consult a relevant authority for sensitive official documents."},
            {"q": "Can I position the signature precisely on the page?", "a": "Yes, you can place it exactly where you want."},
            {"q": "Does it work on mobile?", "a": "Yes, you can draw directly with your finger on your phone screen."},
            {"q": "Can I sign in multiple places in the same file?", "a": "Each run adds one signature; repeat the process to add multiple signatures."},
            {"q": "Can the signature be removed or edited later?", "a": "It becomes part of the page content once saved, so it can't be automatically separated."}
        ]
    },
    "pdf-to-excel": {
        "long_desc_ar": "يستخرج الجداول من ملفات PDF ويحوّلها لملف Excel منظم بأعمدة وصفوف صحيحة. يستخدم عدة محركات استخراج (Tabula للجداول المسطرة، pdfplumber للجداول غير المخططة) بالتتابع لضمان أعلى دقة ممكنة حتى مع الجداول المعقدة.",
        "long_desc_en": "Extracts tables from PDF files into a properly structured Excel spreadsheet with correct rows and columns. It runs multiple extraction engines (Tabula for ruled tables, pdfplumber for borderless tables) in sequence to ensure the highest possible accuracy, even with complex tables.",
        "faq_ar": [
            {"q": "هل يستخرج كل الجداول في ملف متعدد الصفحات؟", "a": "نعم، يمسح كل الصفحات ويضع كل جدول بورقة عمل (Sheet) منفصلة."},
            {"q": "ماذا لو كان الملف صورة ممسوحة ضوئياً؟", "a": "يتم تفعيل تقنية OCR تلقائياً لاستخراج البيانات من الجداول الممسوحة."},
            {"q": "هل يحافظ على تنسيق الأرقام والعملات؟", "a": "نعم، تُستخرج القيم كما هي بالنص الأصلي للحفاظ على دقتها."},
            {"q": "هل يدعم الجداول بدون خطوط فاصلة واضحة؟", "a": "نعم، هذا بالضبط سبب استخدامنا لعدة محركات استخراج مختلفة."},
            {"q": "ماذا لو فشل استخراج جدول معين؟", "a": "النظام ينتقل تلقائياً لمحرك استخراج آخر أدق قبل التسليم."}
        ],
        "faq_en": [
            {"q": "Does it extract every table across a multi-page file?", "a": "Yes, it scans all pages and places each table in a separate worksheet."},
            {"q": "What if the file is a scanned image?", "a": "OCR is automatically triggered to extract data from scanned tables."},
            {"q": "Does it preserve number and currency formatting?", "a": "Yes, values are extracted as-is from the original text to preserve accuracy."},
            {"q": "Does it support borderless tables?", "a": "Yes, that's exactly why we chain multiple extraction engines."},
            {"q": "What happens if one extraction attempt fails on a table?", "a": "The system automatically falls back to a more precise engine before delivering results."}
        ]
    },
    "image-to-pdf": {
        "long_desc_ar": "يحوّل صورة أو عدة صور (JPG، PNG) إلى ملف PDF واحد مرتب، بصفحة لكل صورة. مثالي لتجميع صور مستندات ملتقطة بالجوال (فواتير، إيصالات، واجبات) في ملف PDF واحد منظم وجاهز للإرسال أو الأرشفة.",
        "long_desc_en": "Converts one or more images (JPG, PNG) into a single organized PDF, with one page per image. Perfect for bundling document photos taken with your phone (receipts, invoices, homework) into one clean, shareable, archive-ready PDF.",
        "faq_ar": [
            {"q": "هل يمكن تحويل عدة صور لملف PDF واحد؟", "a": "نعم، كل صورة تصير صفحة منفصلة بنفس ترتيب رفعك لها."},
            {"q": "هل تحافظ الصورة على جودتها الأصلية؟", "a": "نعم، تُدرج الصورة بدقتها الأصلية دون ضغط إضافي."},
            {"q": "هل يدعم صيغة HEIC من آيفون؟", "a": "استخدم أداة \"HEIC إلى JPG\" أولاً ثم حوّل الناتج إلى PDF."},
            {"q": "هل حجم صفحة PDF يتماشى تلقائياً مع أبعاد الصورة؟", "a": "نعم، يتم ضبط مقاس الصفحة تلقائياً بما يتناسب مع أبعاد كل صورة."},
            {"q": "كم أقصى عدد صور يمكن دمجها بملف واحد؟", "a": "حتى 30 صورة بالعملية الواحدة."}
        ],
        "faq_en": [
            {"q": "Can I convert multiple images into one PDF?", "a": "Yes, each image becomes a separate page in your upload order."},
            {"q": "Does the image keep its original quality?", "a": "Yes, images are embedded at their original resolution without extra compression."},
            {"q": "Does it support iPhone's HEIC format?", "a": "Use the \"HEIC to JPG\" tool first, then convert the result to PDF."},
            {"q": "Does the PDF page size automatically match the image dimensions?", "a": "Yes, page size is automatically adjusted to fit each image's dimensions."},
            {"q": "What's the maximum number of images I can combine?", "a": "Up to 30 images in a single operation."}
        ]
    },
    "compress-image": {
        "long_desc_ar": "يقلل حجم ملف الصورة (JPG/PNG) بشكل كبير مع الحفاظ على جودة بصرية عالية، مثالي لتسريع رفع الصور على المواقع أو تقليل حجمها قبل الإرسال عبر تطبيقات المراسلة اللي تضغط الصور تلقائياً بجودة أقل.",
        "long_desc_en": "Significantly reduces image file size (JPG/PNG) while maintaining high visual quality — ideal for faster website uploads or shrinking images before sending them through messaging apps that auto-compress at lower quality.",
        "faq_ar": [
            {"q": "كم نسبة التخفيض بالحجم المتوقعة؟", "a": "تختلف حسب محتوى الصورة، لكن غالباً بين 40% إلى 80% دون فرق ملحوظ بالعين المجردة."},
            {"q": "هل تتأثر أبعاد الصورة (الطول والعرض)؟", "a": "لا، الضغط يقلل حجم الملف بالبايت فقط دون تغيير أبعاد الصورة."},
            {"q": "هل يدعم صيغة PNG الشفافة؟", "a": "نعم، وتبقى الشفافية محفوظة بعد الضغط."},
            {"q": "هل يمكن ضغط عدة صور دفعة واحدة؟", "a": "كل عملية تعالج صورة واحدة لأفضل تحكم بالجودة."},
            {"q": "هل الضغط يحذف بيانات EXIF (الموقع، الجهاز)؟", "a": "استخدم أداة \"إزالة بيانات EXIF\" بشكل منفصل لضمان حذفها بالكامل."}
        ],
        "faq_en": [
            {"q": "What size reduction can I expect?", "a": "It varies by image content, but typically 40-80% with no noticeable visual difference."},
            {"q": "Does it affect image dimensions (width/height)?", "a": "No, compression only reduces file size in bytes without changing dimensions."},
            {"q": "Does it support transparent PNGs?", "a": "Yes, and transparency is preserved after compression."},
            {"q": "Can I compress multiple images at once?", "a": "Each run processes one image for the best quality control."},
            {"q": "Does compression remove EXIF data (location, device)?", "a": "Use the separate \"Strip EXIF\" tool to ensure it's fully removed."}
        ]
    },
    "heic-to-jpg": {
        "long_desc_ar": "يحوّل صور iPhone بصيغة HEIC (غير مدعومة بمعظم المواقع وأجهزة ويندوز) إلى صيغة JPG المتوافقة عالمياً مع كل الأجهزة والمواقع، مباشرة من متصفحك دون تطبيقات إضافية.",
        "long_desc_en": "Converts iPhone HEIC photos (unsupported by most websites and Windows devices) into universally compatible JPG format, directly from your browser with no extra apps needed.",
        "faq_ar": [
            {"q": "لماذا صور آيفون بصيغة HEIC ولا تفتح على بعض الأجهزة؟", "a": "HEIC صيغة حديثة موفرة للمساحة، لكنها غير مدعومة افتراضياً على ويندوز والمواقع القديمة."},
            {"q": "هل تقل جودة الصورة بعد التحويل لـ JPG؟", "a": "الفرق ضئيل جداً وغير ملحوظ بصرياً في أغلب الحالات."},
            {"q": "هل يمكن تحويل عدة صور HEIC دفعة واحدة؟", "a": "كل عملية تعالج صورة واحدة."},
            {"q": "هل تُحفظ بيانات الموقع والتاريخ بعد التحويل؟", "a": "نعم إلا إذا استخدمت أداة \"إزالة بيانات EXIF\" بعدها."},
            {"q": "هل الأداة تعمل على أجهزة أندرويد وويندوز أيضاً؟", "a": "نعم، تعمل من أي متصفح بغض النظر عن نظام التشغيل."}
        ],
        "faq_en": [
            {"q": "Why don't iPhone HEIC photos open on some devices?", "a": "HEIC is a modern space-saving format, but it's not natively supported by default on Windows and many older websites."},
            {"q": "Does image quality drop after converting to JPG?", "a": "The difference is minimal and rarely noticeable visually."},
            {"q": "Can I convert multiple HEIC images at once?", "a": "Each run processes one image."},
            {"q": "Is location/date metadata preserved after conversion?", "a": "Yes, unless you also run it through the \"Strip EXIF\" tool afterward."},
            {"q": "Does it work on Android and Windows too?", "a": "Yes, it works from any browser regardless of your operating system."}
        ]
    },
    "json-to-excel": {
        "long_desc_ar": "يحوّل بيانات JSON المنظمة (Objects أو Arrays) إلى جدول Excel بأعمدة وصفوف واضحة تلقائياً، بدون كتابة أي كود. مفيد جداً للمطورين والمحللين اللي يحتاجون يفحصوا استجابة API بشكل جدولي سريع.",
        "long_desc_en": "Converts structured JSON data (objects or arrays) into a clean Excel table with automatically detected columns and rows — no code required. Great for developers and analysts who need to quickly inspect an API response in tabular form.",
        "faq_ar": [
            {"q": "هل يدعم JSON المتداخل (Nested Objects)؟", "a": "يدعم التسطيح الأساسي للبيانات؛ الهياكل شديدة التعقيد قد تحتاج تبسيط يدوي أولاً."},
            {"q": "ماذا لو كان الـ JSON غير صالح (Invalid)؟", "a": "تظهر رسالة خطأ واضحة تحدد مكان المشكلة بدل فشل صامت."},
            {"q": "هل يدعم المصفوفات (Arrays) المباشرة؟", "a": "نعم، أي مصفوفة من الكائنات تتحول تلقائياً لصفوف بجدول واحد."},
            {"q": "هل يحافظ على ترتيب الحقول الأصلي؟", "a": "نعم، ترتيب الأعمدة يطابق ترتيب الحقول بالكائن الأول."},
            {"q": "هل يوجد حد لحجم بيانات JSON؟", "a": "نعم، حسب الحد الأقصى المسموح لحجم النص المدخل بالمنصة."}
        ],
        "faq_en": [
            {"q": "Does it support nested JSON objects?", "a": "Basic flattening is supported; deeply nested structures may need manual simplification first."},
            {"q": "What if my JSON is invalid?", "a": "You'll get a clear error pointing to the issue instead of a silent failure."},
            {"q": "Does it support direct arrays?", "a": "Yes, any array of objects automatically becomes rows in a single table."},
            {"q": "Does it preserve the original field order?", "a": "Yes, column order matches the field order in the first object."},
            {"q": "Is there a size limit for JSON input?", "a": "Yes, based on the platform's maximum input text size."}
        ]
    },
    "excel-to-json": {
        "long_desc_ar": "يحوّل ورقة عمل Excel إلى مصفوفة JSON منظمة، بحيث يصير كل صف كائن (Object) بمفاتيح تطابق أسماء الأعمدة في الصف الأول. أداة أساسية للمطورين اللي يحتاجون يغذّوا بيانات جدولية لتطبيق أو API.",
        "long_desc_en": "Converts an Excel worksheet into a clean JSON array, where each row becomes an object with keys matching the first row's column headers. An essential tool for developers who need to feed tabular data into an app or API.",
        "faq_ar": [
            {"q": "هل يدعم أكثر من ورقة عمل (Sheet) بنفس الملف؟", "a": "يعالج ورقة العمل الأولى (النشطة) حالياً؛ افصل الأوراق لملفات منفصلة عند الحاجة."},
            {"q": "هل الصف الأول يجب أن يكون عناوين الأعمدة؟", "a": "نعم، الصف الأول يُستخدم كأسماء المفاتيح (keys) في كل كائن JSON."},
            {"q": "ماذا يحدث للخلايا الفارغة؟", "a": "تُدرج كقيمة فارغة أو null بدل حذف الحقل بالكامل."},
            {"q": "هل يدعم ملفات .xlsx و .xls معاً؟", "a": "نعم، الصيغتين مدعومتين."},
            {"q": "هل الناتج JSON منسّق (Formatted) وسهل القراءة؟", "a": "نعم، يخرج بتنسيق واضح ومسافات بادئة (indentation) لسهولة المراجعة."}
        ],
        "faq_en": [
            {"q": "Does it support multiple sheets in one file?", "a": "It currently processes the first (active) sheet; split sheets into separate files if needed."},
            {"q": "Must the first row be column headers?", "a": "Yes, the first row is used as the key names in each JSON object."},
            {"q": "What happens to empty cells?", "a": "They're included as an empty value or null instead of dropping the field entirely."},
            {"q": "Does it support both .xlsx and .xls?", "a": "Yes, both formats are supported."},
            {"q": "Is the output JSON nicely formatted?", "a": "Yes, it's output with clear indentation for easy review."}
        ]
    },
    "csv-to-json": {
        "long_desc_ar": "يحوّل ملف CSV (بيانات مفصولة بفواصل) إلى مصفوفة JSON بسرعة، بحيث يصير كل سطر كائن منفصل. أداة سريعة لمن يحتاج يجهّز بيانات جدولية بسيطة (من Excel أو Google Sheets مُصدّرة كـ CSV) للاستخدام مباشرة بكود برمجي.",
        "long_desc_en": "Quickly converts a CSV file (comma-separated data) into a JSON array, with each row becoming a separate object. A fast tool for anyone who needs simple tabular data (exported from Excel or Google Sheets as CSV) ready to use directly in code.",
        "faq_ar": [
            {"q": "هل يكتشف الفاصل المستخدم تلقائياً (فاصلة أو فاصلة منقوطة)؟", "a": "نعم، يتعرف على الفواصل الشائعة تلقائياً عند القراءة."},
            {"q": "ماذا لو كان أول سطر بيانات وليس عناوين؟", "a": "يُفترض إن السطر الأول عناوين الأعمدة؛ تأكد من ترتيب ملفك قبل الرفع."},
            {"q": "هل يدعم النصوص العربية داخل CSV؟", "a": "نعم، بشرط أن يكون الملف مرمّز بـ UTF-8 لتفادي ظهور رموز غريبة."},
            {"q": "هل يدعم القيم اللي فيها فواصل داخل نص محاط بعلامات اقتباس؟", "a": "نعم، يتبع معيار CSV القياسي في التعامل مع النصوص المقتبسة."},
            {"q": "هل يوجد حد لعدد الصفوف؟", "a": "نعم، حسب الحد الأقصى المسموح لحجم النص المدخل."}
        ],
        "faq_en": [
            {"q": "Does it auto-detect the delimiter (comma or semicolon)?", "a": "Yes, common delimiters are automatically recognized when reading the file."},
            {"q": "What if my first row is data, not headers?", "a": "The first row is assumed to be column headers — make sure your file is arranged correctly before uploading."},
            {"q": "Does it support Arabic text inside CSV?", "a": "Yes, provided the file is UTF-8 encoded to avoid garbled characters."},
            {"q": "Does it handle quoted values containing commas?", "a": "Yes, it follows the standard CSV convention for quoted text."},
            {"q": "Is there a row limit?", "a": "Yes, based on the platform's maximum input text size."}
        ]
    },
}
for slug, content in RICH_TOOL_CONTENT.items():
    if slug in TOOLS_SEO:
        TOOLS_SEO[slug].update(content)

# ==================== دوال الحماية والمساعدات المتقدمة ====================
def sanitize_file_content(file_bytes):
    if not file_bytes: return False
    danger_patterns = [b"<?php", b"<script", b"eval(", b"/bin/sh", b"/bin/bash", b"powershell", b"WScript.Shell"]
    for p in danger_patterns:
        if p in file_bytes[:2048]: return False
    return True

def validate_zip_bomb(file_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            total_uncompressed = 0
            for file_info in zf.infolist():
                total_uncompressed += file_info.file_size
                if total_uncompressed > 100 * 1024 * 1024:
                    return False
            if len(file_bytes) > 0 and (total_uncompressed / len(file_bytes)) > 15:
                return False
        return True
    except Exception:
        return True

def validate_signature(file_bytes, kind):
    if not file_bytes: return False
    if not sanitize_file_content(file_bytes): return False
    if kind == "pdf": return file_bytes[:5] == b"%PDF-"
    if kind == "zip_office": 
        is_zip = file_bytes[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
        return is_zip and validate_zip_bomb(file_bytes)
    if kind == "heic": return b"ftyp" in file_bytes[:32]
    if kind == "image_any": return any(file_bytes.startswith(s) for s in [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM", b"RIFF"]) or b"ftyp" in file_bytes[:32]
    return True

def bad_request(message): return jsonify({"error": message}), 400
def bad_signature_response(is_arabic): return bad_request("نوع الملف غير مطابق للعملية أو يحتوي على بنية غير آمنة." if is_arabic else "File type mismatch or unsafe content.")
def enforce_pdf_page_limit(page_count, is_arabic):
    if page_count > MAX_PDF_PAGES: return bad_request(f"يتجاوز عدد الصفحات الحد المسموح." if is_arabic else "Exceeds maximum pages.")
    return None

def apply_ghost_privacy(writer):
    try: writer.add_metadata({"/Author": "", "/Creator": "", "/Producer": "", "/CreationDate": "", "/ModDate": ""})
    except Exception: pass

def ensure_arabic_font():
    global _arabic_font_registered
    if _arabic_font_registered: return ARABIC_FONT_NAME
    import glob
    # الأولوية لخطوط عربية مثبتة فعليًا على السيرفر (عبر Dockerfile: fonts-noto-core/extra)
    # بدل الاعتماد على تحميل من الإنترنت وقت الطلب، اللي يفشل بصمت لو تعطّل GitHub
    candidate_paths = [
        "static/fonts/NotoNaskhArabic-Regular.ttf",
        "static/Cairo-Regular.ttf",
    ]
    for pattern in ["/usr/share/fonts/**/NotoNaskhArabic*.ttf", "/usr/share/fonts/**/NotoSansArabic*.ttf",
                     "/usr/share/fonts/**/NotoKufiArabic*.ttf", "/usr/share/fonts/**/Amiri*.ttf"]:
        candidate_paths.extend(sorted(glob.glob(pattern, recursive=True)))

    for path in candidate_paths:
        if path and os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, path))
                _arabic_font_registered = True
                return ARABIC_FONT_NAME
            except Exception:
                continue

    # شبكة أمان أخيرة فقط: تنزيل خط Cairo من GitHub لو ما لقينا أي خط عربي مثبت بالسيرفر
    font_path = "/tmp/Cairo-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            urllib.request.urlretrieve("https://github.com/googlefonts/cairo/raw/main/fonts/ttf/Cairo-Regular.ttf", font_path)
        except Exception:
            pass
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, font_path))
            _arabic_font_registered = True
            return ARABIC_FONT_NAME
        except Exception:
            pass

    app.logger.warning("لا يوجد خط عربي متاح على السيرفر — النصوص العربية ستفشل بخط Helvetica.")
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

def normalize_bidi_text(text):
    if not text or not is_arabic_text(text): return text
    if arabic_reshaper and get_display:
        try:
            return get_display(arabic_reshaper.reshape(str(text)))
        except Exception:
            return text
    return text

def is_arabic_text(t): return bool(re.search(r"[\u0600-\u06FF]", str(t or "")))
def pdf_font_name(is_arabic): return ensure_arabic_font() if is_arabic else "Helvetica"
def file_response(data_bytes, mimetype, filename): 
    return send_file(io.BytesIO(data_bytes), mimetype=mimetype, as_attachment=True, download_name=filename)

def get_file_bytes(p, key="fileBase64"):
    if "_file_bytes" in p and p["_file_bytes"]:
        return p["_file_bytes"]
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
    cmd = ["nice", "-n", "10", "libreoffice", "--headless", "--nologo", "--nofirststartwizard", "--norestore", "--convert-to", "pdf", src_path, "--outdir", out_dir]
    with LIBREOFFICE_LOCK:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=SUBPROCESS_TIMEOUT)

def normalize_and_pad_grid(grid):
    if not grid: return []
    max_cols = max(len(row) for row in grid) if grid else 0
    aligned = []
    for row in grid:
        cleaned_row = [str(c).strip() if c is not None else "" for c in row]
        if len(cleaned_row) < max_cols:
            cleaned_row.extend([""] * (max_cols - len(cleaned_row)))
        aligned.append(cleaned_row)
    return aligned

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
    col_count = max((len(r) for r in rows), default=1) or 1
    max_len_per_col = [1] * col_count
    for row in rows:
        for idx in range(col_count):
            cell_val = row[idx] if idx < len(row) else ""
            cell_len = len(str(cell_val or "").strip())
            if cell_len > max_len_per_col[idx]: max_len_per_col[idx] = cell_len
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
    if num_cols == len(max_len_per_col) and num_cols > 0:
        weights = max_len_per_col[::-1] if is_arabic else max_len_per_col
        total_weight = sum(weights) or num_cols
        min_width = page_width * 0.06
        raw_widths = [max((w / total_weight) * page_width, min_width) for w in weights]
        scale = page_width / sum(raw_widths)
        col_widths = [w * scale for w in raw_widths]
    else:
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

# ================= طبقة الذكاء الاصطناعي لتحسين جودة القراءة =================
def enhance_image_for_ocr(img):
    try:
        img = img.convert('L')
        img = ImageEnhance.Contrast(img).enhance(2.0)
        return img
    except Exception:
        return img

def ocr_pdf_page_to_text(fitz_page, lang):
    if pytesseract is None: return ""
    try:
        pix = fitz_page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = enhance_image_for_ocr(img)
        return pytesseract.image_to_string(img, lang=lang)
    except Exception:
        return ""

def is_probably_scanned(text, page_count):
    if page_count == 0: return False
    avg_chars = len(text.strip()) / max(page_count, 1)
    return avg_chars < 15

# ================= أدوات الـ PDF =================

def handle_pdf_to_docx(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p.get("is_arabic", False)
    
    if not file_bytes: 
        return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): 
        return bad_signature_response(is_arabic)

    cc_key = os.environ.get("CLOUDCONVERT_API_KEY")
    ca_key = os.environ.get("CONVERT_API_KEY")

    with tempfile.TemporaryDirectory() as tmp_dir:
        unique_id = uuid.uuid4().hex
        pdf_path = os.path.join(tmp_dir, f"{unique_id}.pdf")
        docx_path = os.path.join(tmp_dir, f"{unique_id}.docx")
        
        with open(pdf_path, "wb") as f: 
            f.write(file_bytes)

        if Converter is not None:
            try:
                cv = Converter(pdf_path)
                cv.convert(docx_path, start=0, end=None)
                cv.close()
                
                if os.path.exists(docx_path) and os.path.getsize(docx_path) > 0:
                    with open(docx_path, "rb") as df: 
                        return file_response(df.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Infinity_Converted.docx")
            except Exception as e:
                app.logger.warning(f"Local pdf2docx engine failed: {str(e)}")

        if cc_key:
            try:
                cloudconvert.configure(api_key=cc_key, sandbox=False)
                job = cloudconvert.Job.create(payload={
                    "tasks": {
                        "import-file": { "operation": "import/upload" },
                        "convert-file": { 
                            "operation": "convert", 
                            "input": "import-file", 
                            "output_format": "docx"
                        },
                        "export-file": { "operation": "export/url", "input": "convert-file" }
                    }
                })
                
                upload_task = cloudconvert.Task.find(id=job['tasks'][0]['id'])
                cloudconvert.Task.upload(file_name=pdf_path, task=upload_task)
                job = cloudconvert_wait_with_timeout(job['id'])
                
                for task in job['tasks']:
                    if task['name'] == 'export-file' and task['status'] == 'finished':
                        export_url = task['result']['files'][0]['url']
                        res = requests.get(export_url, timeout=30)
                        with open(docx_path, 'wb') as df:
                            df.write(res.content)
                        with open(docx_path, "rb") as df: 
                            return file_response(df.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Infinity_Cloud.docx")
            except Exception as e:
                app.logger.warning(f"CloudConvert failed: {str(e)}")

        if ca_key:
            try:
                convertapi.api_credentials = ca_key
                result = convertapi.convert('docx', {'File': pdf_path}, from_format='pdf', timeout=120)
                result.file.save(docx_path)
                with open(docx_path, "rb") as df: 
                    return file_response(df.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Infinity_Fallback.docx")
            except Exception as e:
                app.logger.error(f"ConvertAPI Fallback Error: {str(e)}")

        return bad_request("نعتذر، تعذرت معالجة هذا الملف المعقد من جميع الخوادم المتاحة.")

def handle_pdf_to_excel(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("No file provided")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        has_data = False
        page_count = 0
        
        if tabula:
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tf:
                    tf.write(file_bytes)
                    tf.flush()
                    dfs = tabula.read_pdf(tf.name, pages='all', multiple_tables=True)
                    for i, table_df in enumerate(dfs):
                        if not table_df.empty:
                            sheet_name = f"Table {i+1}"[:31]
                            table_df.to_excel(writer, sheet_name=sheet_name, index=False)
                            auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                            has_data = True
            except Exception as tabula_err:
                app.logger.warning(f"Tabula extraction skipped: {str(tabula_err)}")

        if not has_data and pdfplumber:
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    page_count = len(pdf.pages)
                    err = enforce_pdf_page_limit(page_count, is_arabic)
                    if err: return err
                    for idx, page in enumerate(pdf.pages):
                        tables = page.extract_tables({"intersection_y_tolerance": 15})
                        if tables:
                            for t_idx, table in enumerate(tables):
                                aligned_table = normalize_and_pad_grid(table)
                                if not aligned_table: continue
                                df = pd.DataFrame(aligned_table[1:], columns=aligned_table[0]) if len(aligned_table) > 1 else pd.DataFrame(aligned_table)
                                sheet_name = f"Page {idx+1} Tbl {t_idx+1}"[:31]
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                                has_data = True
                        else:
                            text = page.extract_text()
                            raw_rows = [line.split() for line in (text or "").split("\n") if line.strip()]
                            aligned_rows = normalize_and_pad_grid(raw_rows)
                            if aligned_rows:
                                sheet_name = f"Page {idx+1}"[:31]
                                pd.DataFrame(aligned_rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                                auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                                has_data = True
            except Exception: pass

        if not has_data and fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            for idx, page in enumerate(doc):
                raw_rows = [line.split() for line in (page.get_text() or "").split("\n") if line.strip()]
                aligned_rows = normalize_and_pad_grid(raw_rows)
                if aligned_rows:
                    sheet_name = f"Page {idx + 1}"[:31]
                    pd.DataFrame(aligned_rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                    auto_fit_excel_columns(writer, sheet_name, add_autofilter=False)
                    has_data = True
            doc.close()

        if not has_data and fitz and pytesseract and page_count <= MAX_OCR_PAGES:
            lang = p.get("ocr_lang") or ('ara+eng' if is_arabic else 'eng')
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for idx, page in enumerate(doc):
                ocr_text = ocr_pdf_page_to_text(page, lang)
                raw_rows = [line.split() for line in ocr_text.split("\n") if line.strip()]
                aligned_rows = normalize_and_pad_grid(raw_rows)
                if aligned_rows:
                    sheet_name = f"OCR Page {idx + 1}"[:31]
                    pd.DataFrame(aligned_rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
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
        page_count = 0
        if pdfplumber:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                page_count = len(pdf.pages)
                err = enforce_pdf_page_limit(page_count, is_arabic)
                if err: return err
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            aligned = normalize_and_pad_grid(table)
                            for row in aligned:
                                writer.writerow([normalize_bidi_text(cell) for cell in row])
                                wrote_any = True
                    else:
                        for line in (page.extract_text() or "").split("\n"):
                            if line.strip():
                                writer.writerow([normalize_bidi_text(item) for item in line.split()])
                                wrote_any = True
        elif fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            err = enforce_pdf_page_limit(page_count, is_arabic)
            if err: return err
            for page in doc:
                for line in (page.get_text() or "").split("\n"):
                    if line.strip():
                        writer.writerow([normalize_bidi_text(item) for item in line.split()])
                        wrote_any = True
            doc.close()
        if not wrote_any and fitz and pytesseract and page_count <= MAX_OCR_PAGES:
            lang = p.get("ocr_lang") or ('ara+eng' if is_arabic else 'eng')
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                for line in ocr_pdf_page_to_text(page, lang).split("\n"):
                    if line.strip(): writer.writerow([normalize_bidi_text(item) for item in line.split()])
            doc.close()
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
        else:
            reader = PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
            err = enforce_pdf_page_limit(page_count, is_arabic)
            if err: return err
            text = "\n".join((page.extract_text() or "") for page in reader.pages)

        used_ocr = False
        if is_probably_scanned(text, page_count) and fitz and pytesseract and doc is not None and page_count <= MAX_OCR_PAGES:
            lang = p.get("ocr_lang") or ('ara+eng' if is_arabic else 'eng')
            ocr_text = "".join(ocr_pdf_page_to_text(page, lang) + "\n" for page in doc)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                used_ocr = True
        if doc is not None: doc.close()
        return jsonify({"result": text.strip(), "usedOCR": used_ocr})
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
            font_size = 20 if len(text) < 500 else 14
            if len(text) > 1800: text = text[:1797] + "..."
            slide = prs.slides.add_slide(blank_layout)
            t_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.3), Inches(9), Inches(0.8))
            t_box.text_frame.text = f"Page {idx + 1}"
            t_box.text_frame.paragraphs[0].font.size = Pt(24)
            t_box.text_frame.paragraphs[0].font.bold = True
            b_box = slide.shapes.add_textbox(Inches(0.4), Inches(1.2), Inches(9), Inches(5))
            b_box.text_frame.text = text
            b_box.text_frame.word_wrap = True
            for paragraph in b_box.text_frame.paragraphs: paragraph.font.size = Pt(font_size)
        buf = io.BytesIO()
        prs.save(buf)
        return file_response(buf.getvalue(), "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Converted_Presentation.pptx")
    except Exception: return bad_request("فشل تحويل الملف إلى عرض تقديمي.")

def handle_merge_pdf(p):
    files = p.get("_files_raw") or []
    if not files:
        b64_list = p.get("filesBase64") or ([p.get("fileBase64")] if p.get("fileBase64") else [])
        for b64 in b64_list:
            try: files.append(base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True))
            except Exception: return bad_request("أحد الملفات غير صالح")

    is_arabic = p["is_arabic"]
    if len(files) < 2: return bad_request("يرجى رفع ملفين PDF على الأقل")
    if len(files) > MAX_MERGE_FILES: return bad_request(f"الحد الأقصى {MAX_MERGE_FILES} ملفات")
    readers = []
    total_pages = 0
    for raw in files:
        if not validate_signature(raw, "pdf"): return bad_signature_response(is_arabic)
        try: reader = PdfReader(io.BytesIO(raw))
        except PdfReadError: return bad_request("أحد الملفات تالف أو محمي")
        total_pages += len(reader.pages)
        err = enforce_pdf_page_limit(total_pages, is_arabic)
        if err: return err
        readers.append(reader)
    writer = PdfWriter()
    page_count = 0
    for i, reader in enumerate(readers):
        writer.add_outline_item(f"ملف {i + 1}", page_count)
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

    original_size = len(file_bytes)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            unique_id = uuid.uuid4().hex
            in_pdf = os.path.join(tmp_dir, f"{unique_id}_in.pdf")
            with open(in_pdf, "wb") as f: f.write(file_bytes)

            def run_gs(preset, out_path):
                gs_cmd = [
                    "nice", "-n", "10", "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                    f"-dPDFSETTINGS={preset}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                    "-dDetectDuplicateImages=true", "-dCompressFonts=true",
                    f"-sOutputFile={out_path}", in_pdf
                ]
                res = subprocess.run(gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=SUBPROCESS_TIMEOUT)
                if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    return os.path.getsize(out_path)
                return None

            best_path, best_size = None, None
            ebook_path = os.path.join(tmp_dir, f"{unique_id}_ebook.pdf")
            size = run_gs("/ebook", ebook_path)
            if size:
                best_path, best_size = ebook_path, size

            # ضغط تكيفي: لو الملف غالبًا صور عالية الدقة والتخفيض كان ضعيف (أقل من 15%)
            # نجرب مستوى ضغط أقوى /screen ونأخذ الأصغر بين النتيجتين
            if best_size is None or (original_size and best_size / original_size > 0.85):
                screen_path = os.path.join(tmp_dir, f"{unique_id}_screen.pdf")
                size2 = run_gs("/screen", screen_path)
                if size2 and (best_size is None or size2 < best_size):
                    best_path, best_size = screen_path, size2

            if best_path and (not original_size or best_size < original_size):
                with open(best_path, "rb") as comp_f:
                    return file_response(comp_f.read(), "application/pdf", "Compressed_Document.pdf")
    except Exception as gs_err:
        app.logger.warning(f"Ghostscript compression fallback: {str(gs_err)}")

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
    apply_ghost_privacy(writer)
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
    apply_ghost_privacy(writer)
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
        reader = PdfReader(io.BytesIO(file_bytes))
        err = enforce_pdf_page_limit(len(reader.pages), is_arabic)
        if err: return err

        font = ensure_arabic_font()
        shaped_text = shape_arabic(text[:60])
        # نبني علامة مائية لكل مقاس صفحة مختلف نصادفه (A4, Letter, Landscape...)
        # بدل قياس ثابت، ونخزنها بذاكرة مؤقتة (cache) لتفادي إعادة الرسم لكل صفحة
        watermark_cache = {}

        def build_watermark_page(width, height):
            key = (round(width, 1), round(height, 1))
            if key in watermark_cache:
                return watermark_cache[key]
            buf_watermark = io.BytesIO()
            c = rl_canvas.Canvas(buf_watermark, pagesize=(width, height))
            font_size = max(24, min(width, height) / 8)
            c.setFont(font, font_size)
            c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
            c.translate(width / 2, height / 2)
            c.rotate(45)
            c.drawCentredString(0, 0, shaped_text)
            c.save()
            wm_page = PdfReader(io.BytesIO(buf_watermark.getvalue())).pages[0]
            watermark_cache[key] = wm_page
            return wm_page

        writer = PdfWriter()
        for page in reader.pages:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            wm_page = build_watermark_page(page_width, page_height)
            page.merge_page(wm_page)
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
        total_pages = len(reader.pages)
        err = enforce_pdf_page_limit(total_pages, is_arabic)
        if err: return err

        pages_to_remove = set()
        invalid_tokens = []
        for part in text.replace("،", ",").split(","):
            part = part.strip()
            if not part: continue
            if "-" in part:
                bounds = part.split("-")
                if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                    start, end = int(bounds[0]), int(bounds[1])
                    if start > end: start, end = end, start
                    if start < 1 or end > total_pages:
                        invalid_tokens.append(part)
                    else:
                        pages_to_remove.update(range(start - 1, end))
                else:
                    invalid_tokens.append(part)
            elif part.isdigit():
                n = int(part)
                if n < 1 or n > total_pages:
                    invalid_tokens.append(part)
                else:
                    pages_to_remove.add(n - 1)
            else:
                invalid_tokens.append(part)

        if invalid_tokens:
            bad_list = ", ".join(invalid_tokens)
            msg = (f"أرقام صفحات غير صالحة أو خارج نطاق المستند ({total_pages} صفحة): {bad_list}"
                   if is_arabic else
                   f"Invalid or out-of-range page numbers (document has {total_pages} pages): {bad_list}")
            return bad_request(msg)

        if not pages_to_remove:
            return bad_request("لم يتم تحديد أي صفحة صالحة للحذف." if is_arabic else "No valid pages were specified for removal.")

        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i not in pages_to_remove: writer.add_page(page)
        if len(writer.pages) == 0: return bad_request("لا يمكنك حذف جميع صفحات الملف!")
        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Edited_Document.pdf")
    except PdfReadError:
        return bad_request("الملف تالف أو محمي بكلمة سر" if is_arabic else "File is corrupted or password protected")
    except Exception: return bad_request("فشل قص الصفحات، يرجى كتابة أرقام الصفحات بشكل صحيح.")

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

# ================= أدوات تحويل المستندات والنصوص (Word, CSV, Excel) =================
def handle_word_to_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p.get("is_arabic", False)
    
    if not file_bytes: 
        return bad_request("يرجى رفع ملف Word")
    if not validate_signature(file_bytes, "zip_office"): 
        return bad_signature_response(is_arabic)

    cc_key = os.environ.get("CLOUDCONVERT_API_KEY")
    ca_key = os.environ.get("CONVERT_API_KEY")

    with tempfile.TemporaryDirectory() as tmp_dir:
        unique_id = uuid.uuid4().hex
        docx_path = os.path.join(tmp_dir, f"{unique_id}.docx")
        pdf_path = os.path.join(tmp_dir, f"{unique_id}.pdf")
        
        with open(docx_path, "wb") as f: 
            f.write(file_bytes)

        try:
            run_libreoffice_convert(docx_path, tmp_dir)
            auto_pdf = os.path.join(tmp_dir, f"{unique_id}.pdf")
            if os.path.exists(auto_pdf) and os.path.getsize(auto_pdf) > 0:
                with open(auto_pdf, "rb") as df:
                    return file_response(df.read(), "application/pdf", "V-Infinity_Converted.pdf")
        except Exception as local_err:
            app.logger.warning(f"Local LibreOffice Word-to-PDF failed: {str(local_err)}")

        if cc_key:
            try:
                cloudconvert.configure(api_key=cc_key, sandbox=False)
                job = cloudconvert.Job.create(payload={
                    "tasks": {
                        "import-file": { "operation": "import/upload" },
                        "convert-file": { 
                            "operation": "convert", 
                            "input": "import-file", 
                            "output_format": "pdf"
                        },
                        "export-file": { "operation": "export/url", "input": "convert-file" }
                    }
                })
                
                upload_task = cloudconvert.Task.find(id=job['tasks'][0]['id'])
                cloudconvert.Task.upload(file_name=docx_path, task=upload_task)
                job = cloudconvert_wait_with_timeout(job['id'])
                
                for task in job['tasks']:
                    if task['name'] == 'export-file' and task['status'] == 'finished':
                        export_url = task['result']['files'][0]['url']
                        res = requests.get(export_url, timeout=30)
                        with open(pdf_path, 'wb') as df:
                            df.write(res.content)
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
    files = p.get("_files_raw") or []
    if not files:
        b64_list = p.get("filesBase64") or []
        for b64 in b64_list:
            try: files.append(base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True))
            except Exception: return bad_request("ملف غير صالح")

    if len(files) < 2: return bad_request("يرجى رفع ملفين Word على الأقل")
    if len(files) > MAX_MERGE_FILES: return bad_request(f"الحد الأقصى {MAX_MERGE_FILES} ملفات")
    merged = Document()
    first = True
    for raw in files:
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
    rows = normalize_and_pad_grid(parse_csv_text(text))
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
                cell.text = normalize_bidi_text(val or "")
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
            for row in table.rows: 
                writer.writerow([normalize_bidi_text(cell.text.strip()) for cell in row.cells])
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
    except Image.DecompressionBombError: return None, bad_request("أبعاد الصورة كبيرة جداً وغير آمنة للمعالجة")
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
    except (TypeError, ValueError): return bad_request("قيم الأبعاد غير صحيحة")
    if target_w <= 0 and target_h <= 0: return bad_request("يرجى تحديد العرض أو الارتفاع")
    if target_w > 8000 or target_h > 8000: return bad_request("الأبعاد المطلوبة كبيرة جداً")

    img = ImageOps.exif_transpose(img)
    if p.get("keepRatio", True):
        orig_w, orig_h = img.size
        if target_w and not target_h: target_h = int(orig_h * (target_w / orig_w))
        elif target_h and not target_w: target_w = int(orig_w * (target_h / orig_w))
        img = img.copy()
        img.thumbnail((target_w, target_h))
    else:
        img = img.resize((target_w or img.width, target_h or img.height))

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
    except (TypeError, ValueError): angle = 90
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
    watermark_text = (p.get("watermarkText") or "").strip()
    if not watermark_text: return bad_request("يرجى إدخال نص العلامة المائية")
    img = ImageOps.exif_transpose(img).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(18, img.width // 20)
    try: font = ImageFont.load_default(size=font_size)
    except TypeError: font = ImageFont.load_default()
    text = watermark_text[:80]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((img.width - tw) / 2, (img.height - th) / 2), text, font=font, fill=(255, 255, 255, 130))
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

# ================= أدوات الطلاب والمعلمين والتوقيع والذكاء الاصطناعي والميزات الجديدة =================
def handle_clean_study_sheet(p):
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    try:
        gray = img.convert('L')
        contrast = ImageEnhance.Contrast(gray).enhance(2.8)
        brightness = ImageEnhance.Brightness(contrast).enhance(1.15)
        cleaned = brightness.point(lambda x: 0 if x < 120 else (255 if x > 190 else x))
        buf = io.BytesIO()
        cleaned.save(buf, format="PDF", resolution=300)
        return file_response(buf.getvalue(), "application/pdf", "Cleaned_Study_Sheet.pdf")
    except Exception:
        return bad_request("تعذرت تنقية وتجهيز صورة الملزمة.")

def handle_pdf_page_number(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        total_pages = len(reader.pages)
        err = enforce_pdf_page_limit(total_pages, is_arabic)
        if err: return err

        writer = PdfWriter()
        font = ensure_arabic_font()

        for idx, page in enumerate(reader.pages):
            page_w = float(page.mediabox.width)
            page_h = float(page.mediabox.height)

            num_buf = io.BytesIO()
            c = rl_canvas.Canvas(num_buf, pagesize=(page_w, page_h))
            c.setFont(font, 10)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            
            num_str = f"صفحة {idx + 1} من {total_pages}" if is_arabic else f"Page {idx + 1} of {total_pages}"
            c.drawCentredString(page_w / 2, 20, shape_arabic(num_str) if is_arabic else num_str)
            c.save()

            num_page = PdfReader(io.BytesIO(num_buf.getvalue())).pages[0]
            page.merge_page(num_page)
            writer.add_page(page)

        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Numbered_Document.pdf")
    except Exception:
        return bad_request("فشل ترقيم صفحات المستند.")

def handle_ink_saver_pdf(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        out_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(colorspace=fitz.csGRAY)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img = ImageEnhance.Contrast(img).enhance(1.4)
            img_buf = io.BytesIO()
            img.save(img_buf, format="PDF")
            temp_pdf = fitz.open(stream=img_buf.getvalue(), filetype="pdf")
            out_doc.insert_pdf(temp_pdf)
        
        final_bytes = out_doc.tobytes(deflate=True)
        doc.close()
        out_doc.close()
        return file_response(final_bytes, "application/pdf", "Ink_Saver_Document.pdf")
    except Exception:
        return bad_request("تعذر تطبيق وضع توفير الحبر.")

def handle_summarize_doc(p):
    text = (p.get("text") or "").strip()
    file_bytes = get_file_bytes(p)
    if not text and file_bytes:
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join((page.get_text() or "") for page in doc)
            doc.close()

    if not text: return bad_request("يرجى كتابة نص أو رفع ملف للتلخيص.")

    sentences = [s.strip() for s in re.split(r'[.\n!؟?]', text) if len(s.strip()) > 20]
    if not sentences: return jsonify({"result": "النص قصير جداً للتلخيص."})

    words = re.findall(r'\w+', text.lower())
    freq = {}
    for w in words:
        if len(w) > 3: freq[w] = freq.get(w, 0) + 1
    
    scored = []
    for s in sentences:
        score = sum(freq.get(w, 0) for w in re.findall(r'\w+', s.lower()))
        scored.append((score, s))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    top_points = [item[1] for item in scored[:min(5, len(scored))]]
    summary_text = "📌 ملخص النقاط الرئيسية:\n\n• " + "\n• ".join(top_points)

    return jsonify({"result": summary_text})

def handle_citation_generator(p):
    title = (p.get("title") or p.get("text") or "عنوان البحث / المستند").strip()
    author = (p.get("author") or "اسم الكاتب / الباحث").strip()
    year = str(p.get("year") or datetime.now().year)

    apa = f"{author} ({year}). {title}."
    mla = f'{author}. "{title}." ({year}).'
    chicago = f'{author}. "{title}." {year}.'

    res = f"📑 التوثيق الأكاديمي المعتمد:\n\n1. APA:\n{apa}\n\n2. MLA:\n{mla}\n\n3. Chicago:\n{chicago}"
    return jsonify({"result": res})

def handle_sign_pdf(p):
    file_bytes = get_file_bytes(p)
    sig_b64 = p.get("signatureBase64")
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not sig_b64: return bad_request("يرجى رسم التوقيع أولاً")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    try:
        sig_data = base64.b64decode(sig_b64.split(",")[-1])
        sig_img = Image.open(io.BytesIO(sig_data)).convert("RGBA")
        
        reader = PdfReader(io.BytesIO(file_bytes))
        writer = PdfWriter()
        total_pages = len(reader.pages)
        
        last_page = reader.pages[-1]
        pw = float(last_page.mediabox.width)
        ph = float(last_page.mediabox.height)

        sig_pdf_buf = io.BytesIO()
        c = rl_canvas.Canvas(sig_pdf_buf, pagesize=(pw, ph))
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as temp_sig:
            sig_img.save(temp_sig.name, format="PNG")
            c.drawImage(temp_sig.name, pw - 220, 40, width=180, height=80, mask='auto')
        c.save()

        sig_overlay = PdfReader(io.BytesIO(sig_pdf_buf.getvalue())).pages[0]
        
        for i, page in enumerate(reader.pages):
            if i == total_pages - 1:
                page.merge_page(sig_overlay)
            writer.add_page(page)

        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Signed_Document.pdf")
    except Exception:
        return bad_request("تعذر إضافة التوقيع إلى المستند.")

def handle_remove_blank_pages(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        out_doc = fitz.open()
        removed_count = 0

        for page in doc:
            text = (page.get_text() or "").strip()
            if len(text) == 0 and len(page.get_images()) == 0:
                removed_count += 1
                continue
            out_doc.insert_pdf(doc, from_page=page.number, to_page=page.number)

        if len(out_doc) == 0:
            out_doc.insert_pdf(doc, from_page=0, to_page=0)

        final_bytes = out_doc.tobytes(deflate=True)
        doc.close()
        out_doc.close()
        return file_response(final_bytes, "application/pdf", "Cleaned_No_Blanks.pdf")
    except Exception:
        return bad_request("تعذر فحص وحذف الصفحات الفارغة.")

def handle_generate_quiz(p):
    text = (p.get("text") or "").strip()
    file_bytes = get_file_bytes(p)
    if not text and file_bytes and fitz:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join((page.get_text() or "") for page in doc)
        doc.close()

    if not text: return bad_request("يرجى إدخال محتوى أو رفع ملف لتوليد الاختبار.")

    sentences = [s.strip() for s in re.split(r'[.\n!؟?]', text) if len(s.strip().split()) >= 6]
    if not sentences: return jsonify({"result": "المحتوى قصير جداً لتوليد أسئلة."})

    quiz_items = []
    for i, s in enumerate(sentences[:min(5, len(sentences))]):
        words = [w for w in re.findall(r'\w+', s) if len(w) > 4]
        if words:
            target_word = words[0]
            masked_sentence = s.replace(target_word, " [ ...... ] ")
            quiz_items.append(f"س{i+1}: أكمل الفراغ في الجملة التالية:\n« {masked_sentence} »\n( الإجابة الصحيحة: {target_word} )")
        else:
            quiz_items.append(f"س{i+1}: وضح الفكرة التالية:\n« {s} »")

    final_quiz = "🧠 بنك الأسئلة والبطاقات الذكية:\n\n" + "\n\n".join(quiz_items)
    return jsonify({"result": final_quiz})

def handle_redact_pdf(p):
    file_bytes = get_file_bytes(p)
    words_to_hide = (p.get("text") or "").split(",")
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not words_to_hide or not words_to_hide[0].strip(): return bad_request("يرجى كتابة الكلمات الحساسة المراد طمسها مفصولة بفاصلة")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            for w in words_to_hide:
                w = w.strip()
                if not w: continue
                rects = page.search_for(w)
                for r in rects:
                    page.add_redact_annot(r, fill=(0, 0, 0))
            page.apply_redactions()
        
        final_bytes = doc.tobytes(deflate=True)
        doc.close()
        return file_response(final_bytes, "application/pdf", "Redacted_Document.pdf")
    except Exception:
        return bad_request("تعذر طمس البيانات من المستند.")

def handle_pdf_compare(p):
    files = p.get("_files_raw") or []
    if not files:
        b64_list = p.get("filesBase64") or []
        for b64 in b64_list:
            try: files.append(base64.b64decode(b64.replace('\n', '').replace('\r', ''), validate=True))
            except Exception: return bad_request("أحد الملفات غير صالح")

    if len(files) < 2: return bad_request("يرجى رفع نسختين من PDF للمقارنة")

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc1 = fitz.open(stream=files[0], filetype="pdf")
        doc2 = fitz.open(stream=files[1], filetype="pdf")

        text1 = "\n".join(page.get_text() for page in doc1)
        text2 = "\n".join(page.get_text() for page in doc2)

        doc1.close()
        doc2.close()

        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        diff = list(unified_diff(lines1, lines2, fromfile="الملف_الأصلي", tofile="الملف_المعدل", lineterm=""))
        if not diff:
            return jsonify({"result": "✅ لا توجد أي فروقات بين الملفين، النسختان متطابقتان تماماً."})

        diff_result = "🔍 تقرير مقارنة وتعديلات المستندين:\n\n" + "\n".join(diff[:150])
        return jsonify({"result": diff_result})
    except Exception:
        return bad_request("تعذرت مقارنة الملفين.")

def handle_reorder_pdf(p):
    file_bytes = get_file_bytes(p)
    order_str = (p.get("text") or "").strip()
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not order_str: return bad_request("يرجى كتابة ترتيب الصفحات (مثال: 3,1,2)")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    try:
        order = [int(x.strip()) - 1 for x in order_str.replace("،", ",").split(",") if x.strip().isdigit()]
        reader = PdfReader(io.BytesIO(file_bytes))
        total = len(reader.pages)
        
        writer = PdfWriter()
        for idx in order:
            if 0 <= idx < total:
                writer.add_page(reader.pages[idx])

        if len(writer.pages) == 0:
            return bad_request("أرقام الصفحات المدخلة غير صحيحة.")

        apply_ghost_privacy(writer)
        final_buf = io.BytesIO()
        writer.write(final_buf)
        return file_response(final_buf.getvalue(), "application/pdf", "Reordered_Document.pdf")
    except Exception:
        return bad_request("تعذر إعادة ترتيب صفحات المستند.")

def handle_compress_pdf_target(p):
    file_bytes = get_file_bytes(p)
    target_kb = int(re.sub(r'[^0-9]', '', p.get("text") or "500") or 500)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        dpi_scale = 1.0 if target_kb > 1000 else (0.7 if target_kb > 400 else 0.5)
        
        out_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=int(72 * dpi_scale))
            img = Image.open(io.BytesIO(pix.tobytes("jpeg")))
            img_buf = io.BytesIO()
            img.save(img_buf, format="JPEG", quality=60, optimize=True)
            img_pdf = fitz.open(stream=img_buf.getvalue(), filetype="pdf")
            out_doc.insert_pdf(img_pdf)

        final_bytes = out_doc.tobytes(deflate=True, garbage=4)
        doc.close()
        out_doc.close()
        return file_response(final_bytes, "application/pdf", f"Compressed_{target_kb}KB.pdf")
    except Exception:
        return bad_request("تعذر ضغط المستند للحجم المحدد.")

def handle_pdf_to_images(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=150)
                zf.writestr(f"Page_{i+1}.jpg", pix.tobytes("jpeg"))
        doc.close()
        return file_response(zip_buf.getvalue(), "application/zip", "PDF_Images.zip")
    except Exception:
        return bad_request("تعذر استخراج صفحات المستند كصور.")

def handle_extract_pdf_images(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PDF")
    if not validate_signature(file_bytes, "pdf"): return bad_signature_response(is_arabic)

    if not fitz: return bad_request("PyMuPDF غير متوفر")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        zip_buf = io.BytesIO()
        img_count = 0
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for page in doc:
                for img_info in page.get_images():
                    xref = img_info[0]
                    base_img = doc.extract_image(xref)
                    img_bytes = base_img["image"]
                    img_ext = base_img["ext"]
                    img_count += 1
                    zf.writestr(f"Embedded_Image_{img_count}.{img_ext}", img_bytes)
        doc.close()
        if img_count == 0:
            return jsonify({"result": "لم يتم العثور على أي صور مضمنة داخل هذا الملف."})
        return file_response(zip_buf.getvalue(), "application/zip", "Extracted_Embedded_Images.zip")
    except Exception:
        return bad_request("تعذر استخراج الصور المضمنة.")

def handle_arabic_proofreader(p):
    text = (p.get("text") or "").strip()
    if not text: return bad_request("يرجى كتابة أو لصق النص للتدقيق.")

    corrected = text
    corrected = re.sub(r'\bاذا\b', 'إذا', corrected)
    corrected = re.sub(r'\bان\b', 'أن', corrected)
    corrected = re.sub(r'\bاو\b', 'أو', corrected)
    corrected = re.sub(r'\bالى\b', 'إلى', corrected)
    corrected = re.sub(r'\bهذة\b', 'هذه', corrected)
    corrected = re.sub(r'\s+([،,.؟?!])', r'\1', corrected)
    corrected = re.sub(r'([،,.؟?!])(?=[^\s])', r'\1 ', corrected)

    return jsonify({"result": corrected})

def handle_ppt_to_images(p):
    file_bytes = get_file_bytes(p)
    is_arabic = p["is_arabic"]
    if not file_bytes: return bad_request("يرجى رفع ملف PowerPoint")
    if not validate_signature(file_bytes, "zip_office"): return bad_signature_response(is_arabic)

    if Presentation is None: return bad_request("python-pptx غير متوفر")
    try:
        prs = Presentation(io.BytesIO(file_bytes))
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for idx, slide in enumerate(prs.slides):
                slide_img = Image.new("RGB", (1280, 720), (255, 255, 255))
                draw = ImageDraw.Draw(slide_img)
                text_content = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        text_content.append(shape.text_frame.text)
                draw.text((60, 60), f"Slide {idx+1}\n\n" + "\n".join(text_content[:6]), fill=(30, 41, 59))
                s_buf = io.BytesIO()
                slide_img.save(s_buf, format="JPEG", quality=90)
                zf.writestr(f"Slide_{idx+1}.jpg", s_buf.getvalue())
        return file_response(zip_buf.getvalue(), "application/zip", "PowerPoint_Slides.zip")
    except Exception:
        return bad_request("تعذر تحويل شرائح العرض إلى صور.")

def handle_image_to_text(p):
    if pytesseract is None: return bad_request("مكتبة OCR غير مثبتة بالسيرفر")
    img, err = _load_validated_image(p, p["is_arabic"])
    if err: return err
    try:
        img = enhance_image_for_ocr(img)
        lang = p.get("ocr_lang") or ('ara+eng' if p["is_arabic"] else 'eng')
        text = pytesseract.image_to_string(img, lang=lang)
        if not text.strip(): return jsonify({"result": "لم يتم العثور على أي نص واضح في الصورة."})
        return jsonify({"result": text.strip()})
    except Exception: return bad_request("فشل التعرف على النص.")

def handle_text_to_audio(p):
    if gTTS is None: return bad_request("مكتبة الصوت غير مثبتة.")
    text = p.get("text", "").strip()
    if not text: return bad_request("يرجى إدخال النص.")
    if len(text) > 5000: return bad_request("النص طويل جداً (الحد الأقصى 5000 حرف).")
    try:
        tts = gTTS(text=text, lang='ar' if p["is_arabic"] else 'en', slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return file_response(buf.getvalue(), "audio/mpeg", "Audio_Speech.mp3")
    except Exception: return bad_request("فشل توليد الصوت. تأكد من الاتصال بالإنترنت من السيرفر.")

def handle_translate_text(p):
    if GoogleTranslator is None: return bad_request("مكتبة الترجمة غير مثبتة.")
    text = p.get("text", "").strip()
    if not text: return bad_request("يرجى إدخال النص.")
    if len(text) > 4500: text = text[:4500] 
    try:
        target_lang = p.get("target_lang") or ('en' if p["is_arabic"] else 'ar')
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return jsonify({"result": translated})
    except Exception: return bad_request("فشلت الترجمة، يرجى المحاولة لاحقاً أو بنص أقصر.")

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
    return jsonify({"result": (f"MD5: {hashlib.md5(text).hexdigest()}\nSHA-1: {hashlib.sha1(text).hexdigest()}\nSHA-256: {hashlib.sha256(text).hexdigest()}\nSHA-512: {hashlib.sha512(text).hexdigest()}\nBLAKE2b: {hashlib.blake2b(text).hexdigest()}")})

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
                image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer(),
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
    pw_chars = [
        secrets.choice(string.ascii_lowercase.replace('l', '')),
        secrets.choice(string.ascii_uppercase.replace('O', '').replace('I', '')),
        secrets.choice(string.digits.replace('0', '').replace('1', '')),
    ]
    if use_symbols: pw_chars.append(secrets.choice("!@#$%^&*_+="))
    pw_chars += [secrets.choice(chars) for _ in range(length - len(pw_chars))]
    secrets.SystemRandom().shuffle(pw_chars)
    pwd = "".join(pw_chars)
    return jsonify({"result": "-".join([pwd[i:i + 4] for i in range(0, len(pwd), 4)])})

def handle_password_strength(p):
    text = p.get("text", "")
    score = sum([len(text) >= 8, len(text) >= 12, bool(re.search(r"[A-Z]", text)), bool(re.search(r"[a-z]", text)), bool(re.search(r"[0-9]", text)), bool(re.search(r"[^A-Za-z0-9]", text))])
    labels = (["ضعيفة جداً ⚠️", "ضعيفة ⚠️", "متوسطة 🟡", "جيدة 🙂", "قوية 🔒", "قوية جداً 🔒🔒", "ممتازة 🛡️"] if p["is_arabic"] else ["Very Weak ⚠️", "Weak ⚠️", "Fair 🟡", "Good 🙂", "Strong 🔒", "Very Strong 🔒🔒", "Excellent 🛡️"])
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
    out_lines = [("+ " if l.startswith("+") else ("- " if l.startswith("-") else "  ")) + l[1:]
                 for l in unified_diff(lines[:mid], lines[mid:], lineterm="") if not l.startswith(("+++", "---", "@@"))]
    return jsonify({"result": "\n".join(out_lines)})

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
    "clean-study-sheet": handle_clean_study_sheet, "pdf-page-number": handle_pdf_page_number,
    "ink-saver-pdf": handle_ink_saver_pdf, "summarize-doc": handle_summarize_doc, "citation-generator": handle_citation_generator,
    "sign-pdf": handle_sign_pdf, "remove-blank-pages": handle_remove_blank_pages, "generate-quiz": handle_generate_quiz,
    "redact-pdf": handle_redact_pdf, "pdf-compare": handle_pdf_compare, "reorder-pdf": handle_reorder_pdf,
    "compress-pdf-target": handle_compress_pdf_target, "pdf-to-images": handle_pdf_to_images,
    "extract-pdf-images": handle_extract_pdf_images, "arabic-proofreader": handle_arabic_proofreader,
    "ppt-to-images": handle_ppt_to_images
}

NEEDS_MULTIPLE_FILES = {"merge-pdf", "merge-word", "pdf-compare"}

# ================= مسارات (Routes) الـ SEO والـ PWA والمراقبة والمقاييس التنبؤية =================

@app.route("/healthz")
def health_check():
    return jsonify({
        "status": "healthy",
        "uptime_seconds": int(time.time() - SERVER_START_TIME),
        "active_queue_tasks": conversion_queue.qsize(),
        "total_requests": TOTAL_REQUESTS_PROCESSED
    }), 200

@app.route("/metrics")
def metrics():
    return jsonify({
        "server": "V-Infinity Cloud Engine",
        "status": "running",
        "cached_dedup_count": len(dedup_conversion_cache),
        "active_shares": len(temporary_share_store),
        "queue_size": conversion_queue.qsize(),
        "total_requests_served": TOTAL_REQUESTS_PROCESSED
    }), 200

@app.route("/api/telegram-webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "clean-study-sheet")
    handler = REGISTRY.get(action)
    if not handler: return jsonify({"error": "Unknown action"}), 400
    try:
        response = handler(data)
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/manifest.json")
def manifest():
    manifest_data = {
        "name": "V-Infinity Converter",
        "short_name": "V-Infinity",
        "start_url": "/",
        "id": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#090d16",
        "theme_color": "#6366f1",
        "description": "The Infinite SaaS Conversion Suite — Word, PDF, Excel, images, and developer tools.",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}
        ]
    }
    return jsonify(manifest_data)

@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.root_path, 'sw.js', mimetype='application/javascript')

@app.route('/.well-known/assetlinks.json')
def assetlinks():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'assetlinks.json', mimetype='application/json')

@app.route("/")
def index_ar():
    return render_template("index.html", tool_data=None, lang="ar", is_404=False)

@app.route("/en")
@app.route("/en/")
def index_en():
    return render_template("index.html", tool_data=None, lang="en", is_404=False)

@app.route("/<tool_slug>")
def tool_page_ar(tool_slug):
    if tool_slug in ("privacy", "terms", "contact", "about"): return render_template(f"{tool_slug}.html", lang="ar")
    if tool_slug not in TOOLS_SEO: 
        return render_template("index.html", tool_data=None, lang="ar", is_404=True), 404
    return render_template("index.html", tool_data=TOOLS_SEO[tool_slug], lang="ar", is_404=False)

@app.route("/en/<tool_slug>")
def tool_page_en(tool_slug):
    if tool_slug in ("privacy", "terms", "contact", "about"): return render_template(f"{tool_slug}.html", lang="en")
    if tool_slug not in TOOLS_SEO: 
        return render_template("index.html", tool_data=None, lang="en", is_404=True), 404
    return render_template("index.html", tool_data=TOOLS_SEO[tool_slug], lang="en", is_404=False)

@app.route('/sitemap.xml')
def sitemap():
    base_url = "https://infinityconverter.com"
    urls = [
        f"<url><loc>{base_url}/</loc><priority>1.0</priority></url>",
        f"<url><loc>{base_url}/en/</loc><priority>1.0</priority></url>",
        f"<url><loc>{base_url}/about</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/en/about</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/privacy</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/en/privacy</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/terms</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/en/terms</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/contact</loc><priority>0.8</priority></url>",
        f"<url><loc>{base_url}/en/contact</loc><priority>0.8</priority></url>"
    ]
    for slug in TOOLS_SEO.keys(): 
        urls.append(f"<url><loc>{base_url}/{slug}</loc><priority>0.8</priority></url>")
        urls.append(f"<url><loc>{base_url}/en/{slug}</loc><priority>0.8</priority></url>")
    xml_content = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(urls)}</urlset>'
    return Response(xml_content, mimetype='application/xml')

@app.route('/robots.txt')
def robots(): return Response("User-agent: *\nAllow: /\n\nSitemap: https://infinityconverter.com/sitemap.xml\n", mimetype='text/plain')

@app.route("/pdf-preview", methods=["POST"])
@limiter.limit("20 per minute")
def get_pdf_preview():
    file_bytes = None
    if request.files.get("file"):
        file_bytes = request.files["file"].read()
    elif request.json and request.json.get("fileBase64"):
        file_bytes = base64.b64decode(request.json["fileBase64"])

    if not file_bytes or not validate_signature(file_bytes, "pdf"):
        return bad_request("Invalid PDF file")

    if not fitz:
        return bad_request("PyMuPDF required for preview")

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        thumbnails = []
        max_preview_pages = min(len(doc), 15)
        for i in range(max_preview_pages):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
            b64_thumb = base64.b64encode(pix.tobytes("png")).decode("ascii")
            thumbnails.append({"page": i + 1, "image": f"data:image/png;base64,{b64_thumb}"})
        doc.close()
        return jsonify({"totalPages": len(doc), "previews": thumbnails})
    except Exception as e:
        return bad_request(f"Error generating preview: {str(e)}")

@app.route("/create-share-link", methods=["POST"])
@limiter.limit("30 per minute")
def create_share_link():
    data = request.get_json(silent=True) or {}
    b64 = data.get("fileBase64")
    filename = data.get("filename", "Converted_Document.pdf")
    if not b64: return bad_request("No file data provided")
    
    share_id = secrets.token_urlsafe(16)
    temporary_share_store[share_id] = {
        "file_bytes": base64.b64decode(b64),
        "filename": filename,
        "timestamp": time.time()
    }
    share_url = request.host_url.rstrip("/") + f"/download/{share_id}"
    return jsonify({"share_url": share_url, "expires_in_hours": 24})

@app.route("/download/<share_id>")
def download_shared_file(share_id):
    item = temporary_share_store.get(share_id)
    if not item:
        return "الرابط منتهي الصلاحية أو غير موجود.", 404
    return file_response(item["file_bytes"], "application/octet-stream", item["filename"])

@app.route("/convert-async", methods=["POST"])
@limiter.limit(dynamic_convert_limit)
def convert_async():
    is_form = request.content_type and "multipart/form-data" in request.content_type
    if is_form:
        payload = request.form.to_dict()
        files = request.files.getlist("files") or ([request.files.get("file")] if request.files.get("file") else [])
        payload["_files_raw"] = [f.read() for f in files if f and f.filename]
        payload["_file_bytes"] = payload["_files_raw"][0] if payload["_files_raw"] else None
    else:
        payload = request.get_json(silent=True) or {}

    action = payload.get("action")
    handler = REGISTRY.get(action)
    if not handler: return bad_request(f"Unknown action: {action}")

    task_id = str(uuid.uuid4())
    text = payload.get("text", "") or ""
    is_arabic = payload.get("lang") == "ar" or is_arabic_text(text)
    ctx = dict(payload, text=text, is_arabic=is_arabic)

    async_task_results[task_id] = {"status": "queued", "progress": 5, "timestamp": time.time()}
    conversion_queue.put((task_id, handler, [ctx], None))

    return jsonify({"task_id": task_id, "status": "queued"})

@app.route("/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    task = async_task_results.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)

@app.route("/convert", methods=["POST"])
@limiter.limit(dynamic_convert_limit)
def convert():
    if request.headers.get("Sec-Fetch-Mode") and request.headers.get("Sec-Fetch-Mode") not in ("cors", "same-origin", "navigate"):
        return jsonify({"error": "Forbidden request origin"}), 403

    is_form = request.content_type and "multipart/form-data" in request.content_type
    if is_form:
        payload = request.form.to_dict()
        files = request.files.getlist("files") or ([request.files.get("file")] if request.files.get("file") else [])
        payload["_files_raw"] = [f.read() for f in files if f and f.filename]
        payload["_file_bytes"] = payload["_files_raw"][0] if payload["_files_raw"] else None
    else:
        payload = request.get_json(silent=True) or {}

    if not isinstance(payload, dict): return bad_request("Invalid request body")
    action = payload.get("action")
    if not isinstance(action, str): return bad_request("Unknown action")
    text = payload.get("text", "") or ""
    if not isinstance(text, str): return bad_request("Invalid text field")
    if len(text) > MAX_TEXT_CHARS: return bad_request(f"النص يتجاوز الحد المسموح")

    is_arabic = payload.get("lang") == "ar" or is_arabic_text(text)
    
    if payload.get("_files_raw"):
        if action in NEEDS_MULTIPLE_FILES and len(payload["_files_raw"]) > MAX_MERGE_FILES:
            return jsonify({"error": f"الحد الأقصى {MAX_MERGE_FILES} ملفات"}), 413
        for raw in payload["_files_raw"]:
            if len(raw) > MAX_FILE_BYTES:
                return jsonify({"error": f"حجم الملف أكبر من الحد المسموح"}), 413
    else:
        files_to_check = payload.get("filesBase64") or [] if action in NEEDS_MULTIPLE_FILES else ([payload.get("fileBase64")] if payload.get("fileBase64") else [])
        if action in NEEDS_MULTIPLE_FILES and len(files_to_check) > MAX_MERGE_FILES:
            return jsonify({"error": f"الحد الأقصى {MAX_MERGE_FILES} ملفات"}), 413
        for b64 in files_to_check:
            if b64 and (len(b64) * 3 / 4) > MAX_FILE_BYTES:
                return jsonify({"error": f"حجم الملف أكبر من الحد المسموح"}), 413

    handler = REGISTRY.get(action)
    if not handler: return bad_request(f"Unknown action: {action}")

    gc_was_enabled = gc.isenabled()
    if action in HEAVY_ACTIONS and gc_was_enabled:
        gc.disable()

    try:
        ctx = dict(payload, text=text, is_arabic=is_arabic)
        response = handler(ctx)
        return response
    except Exception:
        app.logger.exception(f"convert() error for action={action}")
        return jsonify({"error": "حدث خطأ أثناء المعالجة. يرجى التأكد من الملف والمحاولة مجدداً."}), 500
    finally:
        if gc_was_enabled:
            gc.enable()
            gc.collect()

@app.route('/ads.txt')
def ads_txt(): return "google.com, pub-4343857922748618, DIRECT, f08c47fec0942fa0", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

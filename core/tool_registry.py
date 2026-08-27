from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Tool:
    id: str
    name_ar: str
    name_en: str
    description_ar: str
    description_en: str
    category: str
    category_ar: str
    category_en: str
    icon: str
    input_ext: tuple[str, ...]
    output_ext: str
    max_files: int
    local: bool = True
    # When True, each uploaded file is processed independently (a single
    # failure does not abort the batch) and results are zipped together.
    batch: bool = False
    # Optional single extra text field shown on the tool page (e.g. page range).
    param_field: str = ""
    param_label_ar: str = ""
    param_label_en: str = ""
    param_placeholder_ar: str = ""
    param_placeholder_en: str = ""
    param_default: str = ""

TOOLS = {
    # --- PDF tools ---
    "pdf-merge": Tool(
        "pdf-merge", "دمج ملفات PDF", "Merge PDF", "اجمع عدة ملفات PDF في ملف واحد مرتب.", "Combine multiple PDF files into one organized document.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 20, True
    ),
    "pdf-split": Tool(
        "pdf-split", "تقسيم PDF", "Split PDF", "قسّم ملف PDF إلى ملف مستقل لكل صفحة وحمّلها كأرشيف ZIP.", "Split a PDF into one file per page, delivered as a ZIP archive.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".zip", 1
    ),
    "pdf-extract-pages": Tool(
        "pdf-extract-pages", "استخراج صفحات PDF", "Extract PDF Pages", "استخرج نطاق صفحات محددًا من ملف PDF إلى ملف جديد.", "Extract a specific page range from a PDF into a new file.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 1,
        param_field="param", param_label_ar="نطاق الصفحات (اختياري)", param_label_en="Page range (optional)",
        param_placeholder_ar="مثال: 1-3,5", param_placeholder_en="e.g. 1-3,5",
    ),
    "pdf-delete-pages": Tool(
        "pdf-delete-pages", "حذف صفحات PDF", "Delete PDF Pages", "احذف صفحات محددة من ملف PDF مع الحفاظ على الباقي.", "Remove specific pages from a PDF while keeping the rest.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 1,
        param_field="param", param_label_ar="الصفحات المطلوب حذفها", param_label_en="Pages to delete",
        param_placeholder_ar="مثال: 2,4-5", param_placeholder_en="e.g. 2,4-5",
    ),
    "pdf-rotate": Tool(
        "pdf-rotate", "تدوير صفحات PDF", "Rotate PDF", "دوّر جميع صفحات ملف PDF بزاوية محددة.", "Rotate every page of a PDF by a chosen angle.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 5, True,
        param_field="param", param_label_ar="زاوية الدوران", param_label_en="Rotation angle",
        param_placeholder_ar="90 أو 180 أو 270", param_placeholder_en="90, 180, or 270", param_default="90",
    ),
    "pdf-compress": Tool(
        "pdf-compress", "ضغط PDF", "Compress PDF", "قلّل حجم ملف PDF دون فقدان جودة المحتوى.", "Shrink a PDF's file size without degrading content quality.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 10, True
    ),
    "pdf-to-jpg": Tool(
        "pdf-to-jpg", "تحويل PDF إلى JPG", "PDF to JPG", "حوّل كل صفحة من PDF إلى صورة JPG.", "Convert every PDF page into a JPG image.", "pdf", "PDF", "PDF", "IMG", (".pdf",), ".zip", 5, True
    ),
    "pdf-to-png": Tool(
        "pdf-to-png", "تحويل PDF إلى PNG", "PDF to PNG", "حوّل كل صفحة من PDF إلى صورة PNG.", "Convert every PDF page into a PNG image.", "pdf", "PDF", "PDF", "IMG", (".pdf",), ".zip", 5, True
    ),
    "image-to-pdf": Tool(
        "image-to-pdf", "تحويل الصور إلى PDF", "Images to PDF", "اجمع صور JPG أو PNG أو WebP في ملف PDF واحد.", "Combine JPG, PNG, or WebP images into a single PDF.", "pdf", "PDF", "PDF", "IMG", (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"), ".pdf", 20
    ),
    "pdf-to-text": Tool(
        "pdf-to-text", "استخراج نص PDF", "PDF to Text", "استخرج النص الكامل من ملف PDF إلى ملف نصي.", "Extract the full text of a PDF into a plain text file.", "pdf", "PDF", "PDF", "TXT", (".pdf",), ".txt", 10, True
    ),
    "pdf-to-html": Tool(
        "pdf-to-html", "تحويل PDF إلى HTML", "PDF to HTML", "حوّل محتوى PDF إلى صفحة HTML قابلة للتصفح.", "Convert PDF content into a browsable HTML page.", "pdf", "PDF", "PDF", "WEB", (".pdf",), ".html", 5, True
    ),
    "pdf-metadata": Tool(
        "pdf-metadata", "بيانات PDF الوصفية", "PDF Metadata", "اعرض بيانات PDF الوصفية وعدد الصفحات في تقرير JSON.", "View a PDF's metadata and page count as a JSON report.", "pdf", "PDF", "PDF", "INF", (".pdf",), ".json", 10, True
    ),
    "pdf-ocr": Tool(
        "pdf-ocr", "استخراج نص PDF بالـ OCR", "PDF OCR", "استخرج النص من ملفات PDF الممسوحة ضوئيًا بالعربية والإنجليزية.", "Extract text from scanned PDFs in Arabic and English.", "ocr", "OCR", "OCR", "OCR", (".pdf",), ".txt", 5, True,
        param_field="param", param_label_ar="لغة النص", param_label_en="Text language",
        param_placeholder_ar="ar أو en أو ar+en", param_placeholder_en="ar, en, or ar+en", param_default="ar+en",
    ),

    # --- Image tools ---
    "image-to-jpg": Tool(
        "image-to-jpg", "تحويل الصور إلى JPG", "Image to JPG", "حوّل الصور الشائعة إلى JPG بجودة مناسبة.", "Convert common image formats to JPG with practical quality.", "images", "الصور", "Images", "IMG",
        (".png", ".webp", ".jpeg", ".jpg", ".bmp", ".tiff"), ".jpg", 20, True, batch=True
    ),
    "image-to-png": Tool(
        "image-to-png", "تحويل الصور إلى PNG", "Image to PNG", "حوّل الصور إلى PNG مع الحفاظ على الشفافية عند الإمكان.", "Convert images to PNG while preserving transparency when possible.", "images", "الصور", "Images", "IMG",
        (".jpg", ".jpeg", ".webp", ".bmp", ".tiff"), ".png", 20, True, batch=True
    ),
    "image-to-webp": Tool(
        "image-to-webp", "تحويل الصور إلى WebP", "Image to WebP", "حوّل الصور إلى WebP لتقليل الحجم مع جودة جيدة.", "Convert images to WebP for a smaller size with good quality.", "images", "الصور", "Images", "IMG",
        (".jpg", ".jpeg", ".png", ".bmp", ".tiff"), ".webp", 20, True, batch=True
    ),
    "image-resize": Tool(
        "image-resize", "تغيير أبعاد الصورة", "Resize Image", "قلّل أبعاد الصورة إلى حد أقصى مع الحفاظ على النسبة.", "Shrink an image to a maximum dimension while keeping its aspect ratio.", "images", "الصور", "Images", "IMG",
        (".jpg", ".jpeg", ".png", ".webp"), ".jpg", 20, True, batch=True,
        param_field="param", param_label_ar="أقصى عرض/ارتفاع (بكسل)", param_label_en="Max width/height (px)",
        param_placeholder_ar="1600", param_placeholder_en="1600", param_default="1600",
    ),
    "image-compress": Tool(
        "image-compress", "ضغط الصورة", "Compress Image", "قلّل حجم الصورة بضبط مستوى الجودة.", "Reduce an image's file size by adjusting the quality level.", "images", "الصور", "Images", "IMG",
        (".jpg", ".jpeg", ".png", ".webp"), ".jpg", 20, True, batch=True,
        param_field="param", param_label_ar="مستوى الجودة (10-95)", param_label_en="Quality level (10-95)",
        param_placeholder_ar="70", param_placeholder_en="70", param_default="70",
    ),
    "image-rotate": Tool(
        "image-rotate", "تدوير الصورة", "Rotate Image", "دوّر الصورة بزاوية محددة.", "Rotate an image by a chosen angle.", "images", "الصور", "Images", "IMG",
        (".jpg", ".jpeg", ".png", ".webp"), ".jpg", 20, True, batch=True,
        param_field="param", param_label_ar="زاوية الدوران", param_label_en="Rotation angle",
        param_placeholder_ar="90 أو 180 أو 270", param_placeholder_en="90, 180, or 270", param_default="90",
    ),
    "image-ocr": Tool(
        "image-ocr", "استخراج نص من صورة", "Image OCR", "استخرج النص من الصور بالعربية والإنجليزية.", "Extract text from images in Arabic and English.", "ocr", "OCR", "OCR", "OCR",
        (".jpg", ".jpeg", ".png", ".webp"), ".txt", 10, True, batch=True,
        param_field="param", param_label_ar="لغة النص", param_label_en="Text language",
        param_placeholder_ar="ar أو en أو ar+en", param_placeholder_en="ar, en, or ar+en", param_default="ar+en",
    ),

    # --- Document tools ---
    "word-to-pdf": Tool(
        "word-to-pdf", "تحويل Word إلى PDF", "Word to PDF", "حوّل مستندات Word إلى PDF عبر LibreOffice.", "Convert Word documents to PDF using LibreOffice.", "office", "المستندات", "Documents", "DOC", (".docx",), ".pdf", 10, True, batch=True
    ),
    "excel-to-pdf": Tool(
        "excel-to-pdf", "تحويل Excel إلى PDF", "Excel to PDF", "حوّل جداول Excel إلى ملفات PDF قابلة للمشاركة.", "Convert Excel workbooks into shareable PDF files.", "office", "Excel", "Excel", "XLS", (".xlsx",), ".pdf", 10, True, batch=True
    ),
    "ppt-to-pdf": Tool(
        "ppt-to-pdf", "تحويل PowerPoint إلى PDF", "PowerPoint to PDF", "حوّل عروض PowerPoint إلى PDF مع الحفاظ على ترتيب الشرائح.", "Convert PowerPoint presentations to PDF while preserving slide order.", "office", "PowerPoint", "PowerPoint", "PPT", (".pptx",), ".pdf", 10, True, batch=True
    ),
    "txt-to-pdf": Tool(
        "txt-to-pdf", "تحويل TXT إلى PDF", "TXT to PDF", "حوّل الملفات النصية البسيطة إلى PDF.", "Convert plain text files into PDF.", "office", "المستندات", "Documents", "TXT", (".txt",), ".pdf", 10, True, batch=True
    ),
    "html-to-pdf": Tool(
        "html-to-pdf", "تحويل HTML إلى PDF", "HTML to PDF", "حوّل صفحات HTML إلى مستند PDF.", "Convert HTML pages into a PDF document.", "office", "المستندات", "Documents", "WEB", (".html", ".htm"), ".pdf", 10, True, batch=True
    ),
    "markdown-to-html": Tool(
        "markdown-to-html", "تحويل Markdown إلى HTML", "Markdown to HTML", "حوّل ملفات Markdown إلى صفحة HTML منسقة.", "Convert Markdown files into a formatted HTML page.", "office", "المستندات", "Documents", "MD", (".md",), ".html", 10, True, batch=True
    ),
    "markdown-to-pdf": Tool(
        "markdown-to-pdf", "تحويل Markdown إلى PDF", "Markdown to PDF", "حوّل ملفات Markdown إلى مستند PDF منسق.", "Convert Markdown files into a formatted PDF document.", "office", "المستندات", "Documents", "MD", (".md",), ".pdf", 10, True, batch=True
    ),
    "csv-to-xlsx": Tool(
        "csv-to-xlsx", "تحويل CSV إلى Excel", "CSV to Excel", "حوّل ملفات CSV إلى جداول Excel (XLSX).", "Convert CSV files into Excel (XLSX) spreadsheets.", "office", "Excel", "Excel", "XLS", (".csv",), ".xlsx", 10, True, batch=True
    ),
    "csv-to-pdf": Tool(
        "csv-to-pdf", "تحويل CSV إلى PDF", "CSV to PDF", "حوّل بيانات CSV إلى مستند PDF قابل للطباعة.", "Convert CSV data into a printable PDF document.", "office", "المستندات", "Documents", "TXT", (".csv",), ".pdf", 10, True, batch=True
    ),

    # --- Archive tools ---
    "zip-create": Tool(
        "zip-create", "إنشاء أرشيف ZIP", "Create ZIP", "اجمع عدة ملفات في أرشيف ZIP واحد.", "Bundle multiple files into a single ZIP archive.", "archive", "الأرشيف", "Archive", "ZIP",
        (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".md", ".html", ".htm"), ".zip", 20
    ),
    "zip-extract": Tool(
        "zip-extract", "استخراج أرشيف ZIP", "Extract ZIP", "استخرج محتويات أرشيف ZIP بأمان مع حماية من ملفات الضغط الخبيثة.", "Safely extract a ZIP archive's contents, protected against zip bombs.", "archive", "الأرشيف", "Archive", "ZIP", (".zip",), ".zip", 1
    ),

    # --- Utility tools ---
    "file-hash": Tool(
        "file-hash", "توليد بصمة الملف", "File Hash Generator", "احسب بصمة SHA-256 وMD5 لأي ملف للتحقق من سلامته.", "Compute SHA-256 and MD5 hashes of any file to verify its integrity.", "utilities", "الأدوات المساعدة", "Utilities", "HASH",
        (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".md", ".html", ".htm", ".zip"), ".json", 10, True, batch=True
    ),
    "file-info": Tool(
        "file-info", "معلومات الملف", "File Info Analyzer", "اعرض حجم الملف ونوعه وتفاصيله في تقرير JSON.", "View a file's size, type, and details as a JSON report.", "utilities", "الأدوات المساعدة", "Utilities", "INF",
        (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".md", ".html", ".htm", ".zip"), ".json", 10, True, batch=True
    ),
}

TOOL_META = {
    "pdf-merge": {"slug": "merge-pdf", "keywords": "اجمع دمج ملفات pdf combine merge", "popular": True, "sort": 1},
    "pdf-split": {"slug": "split-pdf", "keywords": "قسم تقسيم ملف pdf split pages", "popular": True, "sort": 2},
    "pdf-extract-pages": {"slug": "extract-pdf-pages", "keywords": "استخراج صفحات pdf extract pages", "popular": False, "sort": 3},
    "pdf-delete-pages": {"slug": "delete-pdf-pages", "keywords": "حذف صفحات pdf delete pages remove", "popular": False, "sort": 4},
    "pdf-rotate": {"slug": "rotate-pdf", "keywords": "تدوير pdf rotate", "popular": False, "sort": 5},
    "pdf-compress": {"slug": "compress-pdf", "keywords": "ضغط تصغير pdf compress reduce size", "popular": True, "sort": 6},
    "pdf-to-jpg": {"slug": "pdf-to-jpg", "keywords": "pdf jpg صورة تحويل convert image", "popular": True, "sort": 7},
    "pdf-to-png": {"slug": "pdf-to-png", "keywords": "pdf png صورة تحويل convert image", "popular": False, "sort": 8},
    "image-to-pdf": {"slug": "jpg-to-pdf", "keywords": "jpg png webp pdf صورة تحويل image to pdf", "popular": True, "sort": 9},
    "pdf-to-text": {"slug": "pdf-to-text", "keywords": "pdf نص استخراج text extract", "popular": False, "sort": 10},
    "pdf-to-html": {"slug": "pdf-to-html", "keywords": "pdf html تحويل convert", "popular": False, "sort": 11},
    "pdf-metadata": {"slug": "pdf-metadata", "keywords": "pdf بيانات وصفية metadata info", "popular": False, "sort": 12},
    "pdf-ocr": {"slug": "pdf-ocr", "keywords": "pdf ocr نص استخراج ممسوح scanned", "popular": True, "sort": 13},
    "image-to-jpg": {"slug": "image-to-jpg", "keywords": "صورة jpg تحويل image convert", "popular": False, "sort": 14},
    "image-to-png": {"slug": "image-to-png", "keywords": "صورة png تحويل image convert", "popular": True, "sort": 15},
    "image-to-webp": {"slug": "image-to-webp", "keywords": "صورة webp تحويل image convert", "popular": False, "sort": 16},
    "image-resize": {"slug": "resize-image", "keywords": "تغيير حجم أبعاد صورة resize image dimensions", "popular": False, "sort": 17},
    "image-compress": {"slug": "compress-image", "keywords": "ضغط تصغير صورة compress image size", "popular": True, "sort": 18},
    "image-rotate": {"slug": "rotate-image", "keywords": "تدوير صورة rotate image", "popular": False, "sort": 19},
    "image-ocr": {"slug": "image-ocr", "keywords": "صورة ocr نص استخراج image text", "popular": False, "sort": 20},
    "word-to-pdf": {"slug": "word-to-pdf", "keywords": "وورد word مستند pdf تحويل", "popular": True, "sort": 21},
    "excel-to-pdf": {"slug": "excel-to-pdf", "keywords": "اكسل excel جدول pdf تحويل", "popular": False, "sort": 22},
    "ppt-to-pdf": {"slug": "powerpoint-to-pdf", "keywords": "باوربوينت powerpoint عرض شرائح pdf تحويل", "popular": False, "sort": 23},
    "txt-to-pdf": {"slug": "txt-to-pdf", "keywords": "نص txt pdf تحويل text", "popular": False, "sort": 24},
    "html-to-pdf": {"slug": "html-to-pdf", "keywords": "html pdf تحويل صفحة", "popular": False, "sort": 25},
    "markdown-to-html": {"slug": "markdown-to-html", "keywords": "ماركداون markdown html تحويل", "popular": False, "sort": 26},
    "markdown-to-pdf": {"slug": "markdown-to-pdf", "keywords": "ماركداون markdown pdf تحويل", "popular": False, "sort": 27},
    "csv-to-xlsx": {"slug": "csv-to-excel", "keywords": "csv اكسل excel جدول تحويل", "popular": False, "sort": 28},
    "csv-to-pdf": {"slug": "csv-to-pdf", "keywords": "csv pdf جدول تحويل", "popular": False, "sort": 29},
    "zip-create": {"slug": "create-zip", "keywords": "ضغط أرشيف zip إنشاء archive create", "popular": False, "sort": 30},
    "zip-extract": {"slug": "extract-zip", "keywords": "فك ضغط أرشيف zip استخراج archive extract", "popular": False, "sort": 31},
    "file-hash": {"slug": "file-hash", "keywords": "بصمة hash sha256 md5 تحقق", "popular": False, "sort": 32},
    "file-info": {"slug": "file-info", "keywords": "معلومات ملف تحليل info analyzer", "popular": False, "sort": 33},
}

def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)

def list_tools():
    return [
        {**asdict(tool), **TOOL_META[tool.id]}
        for tool in sorted(TOOLS.values(), key=lambda item: TOOL_META[item.id]["sort"])
    ]


def tool_url(tool: Tool) -> str:
    return f"/tools/{TOOL_META[tool.id]['slug']}"


# Curated "smart next step" suggestions shown on a tool's page, e.g. after
# converting Word to PDF a user likely wants to compress, OCR, merge, or split it.
RELATED_OVERRIDES = {
    "word-to-pdf": ("pdf-compress", "pdf-ocr", "pdf-merge", "pdf-split"),
    "excel-to-pdf": ("pdf-compress", "pdf-merge", "csv-to-xlsx"),
    "ppt-to-pdf": ("pdf-compress", "pdf-to-jpg", "pdf-merge"),
    "pdf-to-jpg": ("image-compress", "image-resize", "pdf-compress"),
    "pdf-to-png": ("image-compress", "image-resize", "pdf-compress"),
    "image-to-pdf": ("pdf-compress", "pdf-merge", "pdf-to-jpg"),
    "pdf-merge": ("pdf-compress", "pdf-split", "pdf-rotate"),
    "pdf-split": ("pdf-merge", "pdf-extract-pages", "pdf-compress"),
    "pdf-compress": ("pdf-merge", "pdf-split", "pdf-to-jpg"),
    "pdf-ocr": ("pdf-to-text", "pdf-compress", "pdf-merge"),
    "image-ocr": ("image-compress", "image-to-pdf"),
    "image-compress": ("image-resize", "image-to-pdf", "image-to-webp"),
    "image-resize": ("image-compress", "image-to-webp"),
    "zip-extract": ("file-info", "file-hash"),
    "zip-create": ("zip-extract",),
}


def related_tools(tool_id: str, limit: int = 6) -> list[dict]:
    tool = TOOLS.get(tool_id)
    if not tool:
        return []
    ordered_ids = list(RELATED_OVERRIDES.get(tool_id, ()))
    for other_id, other in TOOLS.items():
        if other_id != tool_id and other.category == tool.category and other_id not in ordered_ids:
            ordered_ids.append(other_id)
    all_tools = list_tools()
    by_id = {item["id"]: item for item in all_tools}
    return [by_id[i] for i in ordered_ids if i in by_id][:limit]

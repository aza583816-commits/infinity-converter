from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class FormField:
    id: str
    type: str
    label_ar: str
    label_en: str
    required: bool = False
    placeholder_ar: str = ""
    placeholder_en: str = ""
    default: str = ""
    choices: tuple[tuple[str, str, str], ...] = ()

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
    input_required: bool = True
    fields: tuple[FormField, ...] = ()

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
    "pdf-booklet": Tool(
        "pdf-booklet", "صانع كتيب PDF", "PDF Booklet Maker", "رتّب صفحات PDF على ورقة واحدة للطباعة ككتيب، بخيار صفحتين أو أربع صفحات.", "Tile PDF pages two-up or four-up into a print-ready PDF.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 1, True,
        fields=(FormField("layout", "select", "تخطيط الصفحات", "Page layout", True, default="2", choices=(("2", "صفحتان في الورقة", "2 pages per sheet"), ("4", "أربع صفحات في الورقة", "4 pages per sheet"))),),
    ),
    "lms-pdf-size-optimizer": Tool(
        "lms-pdf-size-optimizer", "محسن حجم PDF للمنصات التعليمية", "LMS PDF Size Optimizer", "أنشئ PDF أخف للرفع إلى المنصات التعليمية. الهدف تقديري وليس حجمًا مضمونًا.", "Create a smaller PDF for LMS uploads. The chosen target is a best-effort profile, not a guaranteed final size.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 1, True,
        fields=(FormField("target", "select", "هدف الحجم التقريبي", "Approximate size target", True, default="medium", choices=(("small", "صغير (نحو 1MB)", "Small (about 1 MB)"), ("medium", "متوسط (نحو 5MB)", "Medium (about 5 MB)"), ("large", "كبير (نحو 10MB)", "Large (about 10 MB)"))),),
    ),
    "assignment-cover-page": Tool(
        "assignment-cover-page", "إنشاء صفحة غلاف للواجب", "Assignment Cover Page PDF", "أنشئ صفحة غلاف PDF منظمة للواجب. تُدعَم الكتابة الإنجليزية لضمان خط PDF موثوق.", "Create a structured assignment cover-page PDF. English field content is supported for dependable PDF font rendering.", "pdf", "PDF", "PDF", "PDF", (), ".pdf", 0, True, input_required=False,
        fields=(FormField("course", "text", "المقرر", "Course", True, "CS101", "CS101"), FormField("assignment", "text", "عنوان الواجب", "Assignment title", True, "Project 1", "Project 1"), FormField("student", "text", "اسم الطالب", "Student name", True, "Alex Morgan", "Alex Morgan"), FormField("instructor", "text", "اسم المدرس", "Instructor", False, "Dr. Taylor", "Dr. Taylor"), FormField("due_date", "date", "تاريخ التسليم", "Due date")),
    ),
    "omr-bubble-sheet": Tool(
        "omr-bubble-sheet", "إنشاء ورقة إجابة OMR", "OMR Bubble Sheet Generator", "أنشئ ورقة إجابة قابلة للطباعة تضم 20 أو 50 أو 100 سؤال.", "Create a print-ready blank answer sheet with 20, 50, or 100 questions.", "pdf", "PDF", "PDF", "PDF", (), ".pdf", 0, True, input_required=False,
        fields=(FormField("questions", "select", "عدد الأسئلة", "Question count", True, default="50", choices=(("20", "20 سؤالًا", "20 questions"), ("50", "50 سؤالًا", "50 questions"), ("100", "100 سؤال", "100 questions"))),),
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
    "social-media-image-resizer": Tool(
        "social-media-image-resizer", "تغيير حجم صورة للسوشيال ميديا", "Social Media Image Resizer", "جهّز صورة PNG لمقاس منشور أو قصة مع القص أو الحواف مع الحفاظ على النسبة.", "Create a PNG for a social post or story, using sensible cropping or padding while preserving aspect ratio.", "images", "الصور", "Images", "IMG", (".jpg", ".jpeg", ".png", ".webp"), ".png", 1, True,
        fields=(
            FormField("preset", "select", "المقاس", "Preset", True, default="instagram-post", choices=(("instagram-post", "منشور إنستغرام 1080x1080", "Instagram post 1080x1080"), ("instagram-story", "قصة إنستغرام 1080x1920", "Instagram story 1080x1920"), ("linkedin", "منشور LinkedIn 1200x627", "LinkedIn post 1200x627"), ("x", "منشور X 1600x900", "X post 1600x900"))),
            FormField("fit", "select", "طريقة الملاءمة", "Fit method", True, default="crop", choices=(("crop", "قص من المنتصف", "Center crop"), ("pad", "إضافة حواف بيضاء", "White padding"))),
        ),
    ),
    "quote-social-graphic": Tool(
        "quote-social-graphic", "اقتباس كصورة اجتماعية", "Quote to Social Graphic", "أنشئ صورة PNG لاقتباس قصير باللغة الإنجليزية مع التفاف نص مضبوط.", "Create a PNG graphic for a short English quote with robust text wrapping.", "images", "الصور", "Images", "IMG", (), ".png", 0, True, input_required=False,
        fields=(
            FormField("quote", "textarea", "الاقتباس", "Quote", True, "Keep it short.", "Keep it short."),
            FormField("author", "text", "صاحب الاقتباس", "Attribution", False, "Name", "Name"),
            FormField("preset", "select", "المقاس", "Preset", True, default="square", choices=(("square", "مربع 1080x1080", "Square 1080x1080"), ("portrait", "عمودي 1080x1350", "Portrait 1080x1350"))),
            FormField("theme", "select", "النمط", "Theme", True, default="ink", choices=(("ink", "حبر", "Ink"), ("paper", "ورق", "Paper"), ("ocean", "بحر", "Ocean"))),
        ),
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
    "bulk-certificate-maker": Tool(
        "bulk-certificate-maker", "إنشاء شهادات جماعية", "Bulk Certificate Maker", "حوّل CSV يحتوي على عمود name إلى أرشيف ZIP من شهادات PDF. محتوى CSV الإنجليزي هو المدعوم لضمان خط موثوق.", "Turn a CSV with a name column into a ZIP of certificate PDFs. English CSV content is supported for dependable font rendering.", "office", "المستندات", "Documents", "PDF", (".csv",), ".zip", 1, True,
        fields=(FormField("title", "text", "عنوان الشهادة", "Certificate title", True, "Certificate of Completion", "Certificate of Completion"), FormField("issuer", "text", "الجهة المانحة", "Issued by", False, "Infinity Academy", "Infinity Academy")),
    ),
    "csv-merge-deduplicate": Tool(
        "csv-merge-deduplicate", "دمج CSV وحذف التكرار", "CSV Merger & Deduplicator", "ادمج ملفات CSV ذات الأعمدة المتطابقة واحذف الصفوف المكررة.", "Merge CSV files with matching headers and remove duplicate rows.", "office", "المستندات", "Documents", "CSV", (".csv",), ".csv", 20, True
    ),
    "lms-question-bank-formatter": Tool(
        "lms-question-bank-formatter", "منسق بنك أسئلة LMS", "LMS Question Bank Formatter", "حوّل نص UTF-8 إلى GIFT. استخدم كتلًا مفصولة بسطر فارغ: Q: السؤال ثم A: الإجابة.", "Convert UTF-8 text to GIFT. Use blank-line-separated blocks: Q: question followed by A: answer.", "office", "المستندات", "Documents", "TXT", (".txt",), ".txt", 1, True
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
    "pdf-booklet": {"slug": "pdf-booklet-maker", "keywords": "pdf كتيب booklet 2-up 4-up طباعة", "popular": False, "sort": 14},
    "lms-pdf-size-optimizer": {"slug": "lms-pdf-size-optimizer", "keywords": "lms pdf ضغط حجم رفع منصة تعليمية", "popular": False, "sort": 15},
    "assignment-cover-page": {"slug": "assignment-cover-page", "keywords": "واجب غلاف assignment cover page pdf", "popular": False, "sort": 16},
    "omr-bubble-sheet": {"slug": "omr-bubble-sheet", "keywords": "omr bubble answer sheet ورقة إجابة", "popular": False, "sort": 17},
    "image-to-jpg": {"slug": "image-to-jpg", "keywords": "صورة jpg تحويل image convert", "popular": False, "sort": 14},
    "image-to-png": {"slug": "image-to-png", "keywords": "صورة png تحويل image convert", "popular": True, "sort": 15},
    "image-to-webp": {"slug": "image-to-webp", "keywords": "صورة webp تحويل image convert", "popular": False, "sort": 16},
    "image-resize": {"slug": "resize-image", "keywords": "تغيير حجم أبعاد صورة resize image dimensions", "popular": False, "sort": 17},
    "image-compress": {"slug": "compress-image", "keywords": "ضغط تصغير صورة compress image size", "popular": True, "sort": 18},
    "image-rotate": {"slug": "rotate-image", "keywords": "تدوير صورة rotate image", "popular": False, "sort": 19},
    "image-ocr": {"slug": "image-ocr", "keywords": "صورة ocr نص استخراج image text", "popular": False, "sort": 20},
    "social-media-image-resizer": {"slug": "social-media-image-resizer", "keywords": "social media instagram linkedin image resize صورة سوشيال", "popular": False, "sort": 21},
    "quote-social-graphic": {"slug": "quote-to-social-graphic", "keywords": "quote اقتباس social graphic صورة", "popular": False, "sort": 22},
    "word-to-pdf": {"slug": "word-to-pdf", "keywords": "وورد word مستند pdf تحويل", "popular": True, "sort": 21},
    "excel-to-pdf": {"slug": "excel-to-pdf", "keywords": "اكسل excel جدول pdf تحويل", "popular": False, "sort": 22},
    "ppt-to-pdf": {"slug": "powerpoint-to-pdf", "keywords": "باوربوينت powerpoint عرض شرائح pdf تحويل", "popular": False, "sort": 23},
    "txt-to-pdf": {"slug": "txt-to-pdf", "keywords": "نص txt pdf تحويل text", "popular": False, "sort": 24},
    "html-to-pdf": {"slug": "html-to-pdf", "keywords": "html pdf تحويل صفحة", "popular": False, "sort": 25},
    "markdown-to-html": {"slug": "markdown-to-html", "keywords": "ماركداون markdown html تحويل", "popular": False, "sort": 26},
    "markdown-to-pdf": {"slug": "markdown-to-pdf", "keywords": "ماركداون markdown pdf تحويل", "popular": False, "sort": 27},
    "csv-to-xlsx": {"slug": "csv-to-excel", "keywords": "csv اكسل excel جدول تحويل", "popular": False, "sort": 28},
    "csv-to-pdf": {"slug": "csv-to-pdf", "keywords": "csv pdf جدول تحويل", "popular": False, "sort": 29},
    "bulk-certificate-maker": {"slug": "bulk-certificate-maker", "keywords": "شهادات certificates csv pdf zip جماعية", "popular": False, "sort": 30},
    "csv-merge-deduplicate": {"slug": "csv-merge-deduplicate", "keywords": "csv merge دمج حذف تكرار deduplicate", "popular": False, "sort": 31},
    "lms-question-bank-formatter": {"slug": "lms-question-bank-formatter", "keywords": "lms gift question bank أسئلة بنك", "popular": False, "sort": 32},
    "zip-create": {"slug": "create-zip", "keywords": "ضغط أرشيف zip إنشاء archive create", "popular": False, "sort": 30},
    "zip-extract": {"slug": "extract-zip", "keywords": "فك ضغط أرشيف zip استخراج archive extract", "popular": False, "sort": 31},
    "file-hash": {"slug": "file-hash", "keywords": "بصمة hash sha256 md5 تحقق", "popular": False, "sort": 33},
    "file-info": {"slug": "file-info", "keywords": "معلومات ملف تحليل info analyzer", "popular": False, "sort": 34},
}

AUDIENCE_COLLECTIONS = {
    "students": {
        "title_ar": "للطلاب", "title_en": "For Students",
        "description_ar": "رتب محاضراتك وواجباتك وملفاتك الدراسية بسرعة.",
        "description_en": "Organize lecture notes, assignments, and study files quickly.",
        "tool_ids": ("pdf-merge", "pdf-split", "pdf-compress", "pdf-to-text", "pdf-ocr", "image-to-pdf", "word-to-pdf", "ppt-to-pdf", "assignment-cover-page", "lms-pdf-size-optimizer", "omr-bubble-sheet", "lms-question-bank-formatter"),
    },
    "educators": {
        "title_ar": "للمعلمين والدكاترة", "title_en": "For Educators",
        "description_ar": "جهز موادك التعليمية وشارك المستندات بوضوح.",
        "description_en": "Prepare teaching materials and share documents with clarity.",
        "tool_ids": ("pdf-merge", "pdf-extract-pages", "pdf-delete-pages", "pdf-ocr", "word-to-pdf", "ppt-to-pdf", "image-to-pdf", "zip-create", "bulk-certificate-maker", "omr-bubble-sheet", "lms-question-bank-formatter"),
    },
    "developers": {
        "title_ar": "للمطورين", "title_en": "For Developers",
        "description_ar": "أدوات ملفات عملية للمواصفات والتوثيق والتحقق.",
        "description_en": "Practical file tools for documentation, data, and verification.",
        "tool_ids": ("markdown-to-html", "html-to-pdf", "csv-to-xlsx", "file-hash", "file-info", "zip-create", "zip-extract", "pdf-to-text", "csv-merge-deduplicate"),
    },
    "business": {
        "title_ar": "للأعمال", "title_en": "For Business",
        "description_ar": "حوّل وشارك المستندات والفواتير والملفات اليومية.",
        "description_en": "Convert and share documents, invoices, and everyday files.",
        "tool_ids": ("excel-to-pdf", "csv-to-xlsx", "csv-to-pdf", "pdf-compress", "pdf-merge", "image-to-pdf", "zip-create", "file-info", "bulk-certificate-maker", "csv-merge-deduplicate"),
    },
    "everyday": {
        "title_ar": "للاستخدام اليومي", "title_en": "Everyday Tools",
        "description_ar": "أدوات سريعة للصور وملفات PDF والمهام اليومية.",
        "description_en": "Fast tools for images, PDFs, and everyday tasks.",
        "tool_ids": ("image-to-jpg", "image-to-png", "image-to-webp", "image-resize", "image-compress", "image-rotate", "image-to-pdf", "pdf-compress", "social-media-image-resizer", "quote-social-graphic", "pdf-booklet"),
    },
}

DEVELOPER_TOOLS = {
    "json-formatter": {"name_ar": "منسق JSON", "name_en": "JSON Formatter", "description_ar": "نسّق وتحقق من JSON محليًا في متصفحك.", "description_en": "Format and validate JSON locally in your browser.", "icon": "{}"},
    "base64": {"name_ar": "Base64 تشفير وفك", "name_en": "Base64 Encode / Decode", "description_ar": "شفّر النص أو فك Base64 دون إرسال المحتوى.", "description_en": "Encode text or decode Base64 without sending its contents.", "icon": "64"},
    "url-encoder": {"name_ar": "تشفير URL", "name_en": "URL Encoder", "description_ar": "شفّر أو فك مكونات الروابط محليًا.", "description_en": "Encode or decode URL components locally.", "icon": "URL"},
    "uuid-generator": {"name_ar": "مولد UUID", "name_en": "UUID Generator", "description_ar": "ولّد UUID v4 عشوائيًا محليًا.", "description_en": "Generate random UUID v4 values locally.", "icon": "ID"},
    "hash-generator": {"name_ar": "مولد SHA-256", "name_en": "SHA-256 Generator", "description_ar": "احسب بصمة SHA-256 للنص محليًا.", "description_en": "Calculate a SHA-256 text hash locally.", "icon": "SHA"},
    "timestamp-converter": {"name_ar": "محول التوقيت", "name_en": "Timestamp Converter", "description_ar": "حوّل Unix timestamp إلى تاريخ عالمي والعكس.", "description_en": "Convert Unix timestamps to global dates and back.", "icon": "UTC"},
}

PREMIUM_TOOL_IDS = frozenset({
    "pdf-booklet", "lms-pdf-size-optimizer", "assignment-cover-page",
    "omr-bubble-sheet", "bulk-certificate-maker", "social-media-image-resizer",
    "quote-social-graphic", "csv-merge-deduplicate", "lms-question-bank-formatter",
})


def plan_required_for_tool(tool_id: str) -> str:
    return "pro" if tool_id in PREMIUM_TOOL_IDS else "free"

def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)

def list_tools():
    return [
        {**asdict(tool), **TOOL_META[tool.id], "plan_required": plan_required_for_tool(tool.id)}
        for tool in sorted(TOOLS.values(), key=lambda item: TOOL_META[item.id]["sort"])
    ]


def popular_tools(limit: int = 10) -> list[dict]:
    return [tool for tool in list_tools() if tool["popular"]][:limit]


def collection_tools(collection_id: str) -> tuple[dict, list[dict]] | None:
    collection = AUDIENCE_COLLECTIONS.get(collection_id)
    if not collection:
        return None
    by_id = {tool["id"]: tool for tool in list_tools()}
    return collection, [by_id[tool_id] for tool_id in collection["tool_ids"] if tool_id in by_id]


def get_developer_tool(tool_id: str) -> dict | None:
    return DEVELOPER_TOOLS.get(tool_id)


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

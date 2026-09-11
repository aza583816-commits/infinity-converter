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
        "word-to-pdf", "تحويل Word إلى PDF", "Word to PDF", "حوّل ملفات Word بصيغتي DOC وDOCX إلى PDF عبر LibreOffice.", "Convert legacy DOC and modern DOCX Word documents to PDF using LibreOffice.", "office", "المستندات", "Documents", "DOC/DOCX", (".doc", ".docx"), ".pdf", 10, True, batch=True
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


def _new_tool(id_, name_ar, name_en, desc_ar, desc_en, category, category_ar, category_en, icon,
               input_ext, output_ext, max_files=1, *, batch=False, param_field='', param_label_ar='',
               param_label_en='', param_placeholder_ar='', param_placeholder_en='', param_default='',
               input_required=True, fields=()):
    return Tool(id_, name_ar, name_en, desc_ar, desc_en, category, category_ar, category_en, icon,
                tuple(input_ext), output_ext, max_files, True, batch, param_field, param_label_ar,
                param_label_en, param_placeholder_ar, param_placeholder_en, param_default, input_required, tuple(fields))


TOOLS.update({
    # --- 10 additional PDF tools ---
    'pdf-reorder-pages': _new_tool('pdf-reorder-pages','إعادة ترتيب صفحات PDF','Reorder PDF Pages','غيّر ترتيب صفحات PDF بسهولة بكتابة الترتيب المطلوب.','Reorder PDF pages by entering the exact page order.','pdf','PDF','PDF','SORT',('.pdf',),'.pdf',1,param_field='param',param_label_ar='ترتيب الصفحات',param_label_en='Page order',param_placeholder_ar='3,1,2,4',param_placeholder_en='3,1,2,4'),
    'pdf-rotate-selected': _new_tool('pdf-rotate-selected','تدوير صفحات محددة في PDF','Rotate Selected PDF Pages','دوّر صفحات معينة فقط داخل ملف PDF بزاوية 90 أو 180 أو 270 درجة.','Rotate only selected pages inside a PDF by 90, 180, or 270 degrees.','pdf','PDF','PDF','ROT',('.pdf',),'.pdf',1,param_field='param',param_label_ar='الصفحات المطلوب تدويرها',param_label_en='Pages to rotate',param_placeholder_ar='مثال: 2-4',param_placeholder_en='e.g. 2-4',param_default='1',fields=(FormField('angle','select','زاوية الدوران','Rotation angle',True,default='90',choices=(('90','90°','90°'),('180','180°','180°'),('270','270°','270°'))),)),
    'pdf-page-numbers': _new_tool('pdf-page-numbers','إضافة أرقام الصفحات إلى PDF','Add PDF Page Numbers','أضف أرقامًا واضحة إلى أعلى أو أسفل صفحات المستند.','Add clean page numbers to the top or bottom of every page.','pdf','PDF','PDF','123',('.pdf',),'.pdf',1,fields=(FormField('position','select','موضع الرقم','Number position',True,default='bottom-center',choices=(('bottom-center','أسفل في المنتصف','Bottom center'),('bottom-right','أسفل يمين','Bottom right'),('top-center','أعلى في المنتصف','Top center'),('top-right','أعلى يمين','Top right'))),)),
    'pdf-watermark-text': _new_tool('pdf-watermark-text','علامة مائية نصية لـ PDF','PDF Text Watermark','أضف علامة مائية نصية مائلة لحماية المستند قبل مشاركته.','Add a diagonal text watermark to a PDF before sharing it.','pdf','PDF','PDF','WM',('.pdf',),'.pdf',1,fields=(FormField('text','text','نص العلامة المائية','Watermark text',True,'سري','CONFIDENTIAL'),)),
    'pdf-grayscale': _new_tool('pdf-grayscale','تحويل PDF إلى أبيض وأسود','Grayscale PDF','حوّل صفحات PDF إلى تدرج رمادي لتقليل الألوان وتجهيز الطباعة.','Convert PDF pages to grayscale for cleaner monochrome printing.','pdf','PDF','PDF','GRAY',('.pdf',),'.pdf',1),
    'pdf-remove-blank-pages': _new_tool('pdf-remove-blank-pages','حذف الصفحات الفارغة من PDF','Remove Blank PDF Pages','اكتشف الصفحات الفارغة واحذفها تلقائيًا.','Detect and remove blank PDF pages automatically.','pdf','PDF','PDF','CLEAN',('.pdf',),'.pdf',1),
    'pdf-crop-margins': _new_tool('pdf-crop-margins','قص هوامش PDF','Crop PDF Margins','قلّل الهوامش الخارجية لكل صفحات PDF بمقدار موحد.','Crop the outer margins of every PDF page by a chosen amount.','pdf','PDF','PDF','CROP',('.pdf',),'.pdf',1,param_field='param',param_label_ar='الهامش بالنقاط',param_label_en='Margin in points',param_placeholder_ar='18',param_placeholder_en='18',param_default='18'),
    'pdf-poster-split': _new_tool('pdf-poster-split','تقسيم PDF إلى بلاطات للطباعة','PDF Poster Tiler','قسّم كل صفحة إلى شبكة بلاطات مناسبة لطباعة الملصقات الكبيرة.','Tile each page into smaller print-ready poster sheets.','pdf','PDF','PDF','POST',('.pdf',),'.pdf',1,fields=(FormField('columns','select','الأعمدة','Columns',True,default='2',choices=(('2','2','2'),('3','3','3'),('4','4','4'))),FormField('rows','select','الصفوف','Rows',True,default='2',choices=(('2','2','2'),('3','3','3'),('4','4','4'))))),
    'pdf-contact-sheet': _new_tool('pdf-contact-sheet','إنشاء ورقة معاينة PDF','PDF Contact Sheet','أنشئ ورقة واحدة تجمع صورًا مصغرة لصفحات PDF مع أرقامها.','Create a thumbnail overview of PDF pages with page numbers.','pdf','PDF','PDF','GRID',('.pdf',),'.pdf',1,fields=(FormField('columns','select','عدد الأعمدة','Columns',True,default='2',choices=(('2','2','2'),('3','3','3'),('4','4','4'))),)),
    'pdf-password-protect': _new_tool('pdf-password-protect','حماية PDF بكلمة مرور','Password Protect PDF','أنشئ نسخة مشفّرة من PDF تتطلب كلمة مرور لفتحها.','Create a password-protected encrypted copy of a PDF.','pdf','PDF','PDF','LOCK',('.pdf',),'.pdf',1,fields=(FormField('password','password','كلمة المرور','Password',True,'كلمة مرور قوية','Strong password'),)),

    # --- 10 additional image tools ---
    'image-crop': _new_tool('image-crop','قص الصورة بإحداثيات دقيقة','Crop Image','اقصص الصورة بإحداثيات دقيقة بدون تغيير الدقة غير الضروري.','Crop an image precisely using pixel coordinates.','images','الصور','Images','CROP',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.png',20,batch=True,param_field='param',param_label_ar='left,top,right,bottom (px)',param_label_en='left,top,right,bottom',param_placeholder_ar='0,0,1200,800',param_placeholder_en='0,0,1200,800'),
    'image-flip': _new_tool('image-flip','قلب الصورة','Flip Image','اقلب الصورة أفقيًا أو رأسيًا بسرعة.','Flip an image horizontally or vertically.','images','الصور','Images','FLIP',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.png',20,batch=True,fields=(FormField('direction','select','الاتجاه','Direction',True,default='horizontal',choices=(('horizontal','أفقي','Horizontal'),('vertical','رأسي','Vertical'))),)),
    'image-grayscale': _new_tool('image-grayscale','تحويل الصورة إلى تدرج رمادي','Grayscale Image','حوّل الصور إلى أبيض وأسود بشكل نظيف.','Convert images to clean grayscale.','images','الصور','Images','GRAY',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.png',20,batch=True),
    'image-sharpen': _new_tool('image-sharpen','زيادة حدة الصورة','Sharpen Image','حسّن حدة التفاصيل في الصور بثلاث درجات بسيطة.','Enhance image detail with three practical sharpening levels.','images','الصور','Images','SHARP',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.png',20,batch=True,fields=(FormField('strength','select','الحدة','Strength',True,default='2',choices=(('1','خفيفة','Light'),('2','متوسطة','Medium'),('3','قوية','Strong'))),)),
    'image-auto-contrast': _new_tool('image-auto-contrast','تحسين تباين الصورة تلقائيًا','Auto Contrast Image','اضبط التباين تلقائيًا لتحسين وضوح الصورة.','Automatically improve image contrast for clearer results.','images','الصور','Images','AUTO',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.jpg',20,batch=True),
    'image-sepia': _new_tool('image-sepia','تأثير سيبيا للصورة','Sepia Image','طبّق مظهر سيبيا أنيق على الصورة.','Apply a warm sepia look to an image.','images','الصور','Images','SEPIA',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.jpg',20,batch=True),
    'image-strip-metadata': _new_tool('image-strip-metadata','إزالة بيانات الصورة الوصفية','Remove Image Metadata','أنشئ نسخة من الصورة بدون EXIF والبيانات الوصفية الشائعة.','Create a copy without common EXIF metadata.','images','الصور','Images','META',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.png',20,batch=True),
    'image-favicon-pack': _new_tool('image-favicon-pack','حزمة Favicon كاملة','Favicon Pack Generator','أنشئ مجموعة Favicon ومقاسات المواقع الشائعة داخل ZIP واحد.','Generate common favicon and web icon sizes in one ZIP archive.','images','الصور','Images','ICON',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.zip',1),
    'image-contact-sheet': _new_tool('image-contact-sheet','ورقة معاينة للصورة','Image Contact Sheet','أنشئ لوحة معاينة جاهزة للمشاركة من صورة واحدة.','Create a polished preview sheet from an image.','images','الصور','Images','SHEET',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.jpg',20,batch=True),
    'image-set-dpi': _new_tool('image-set-dpi','تعيين دقة DPI للصورة','Set Image DPI','غيّر بيانات DPI للصورة للطباعة بدون تغيير عدد البكسلات.','Set image DPI metadata for print workflows without resampling pixels.','images','الصور','Images','DPI',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.png',20,batch=True,param_field='param',param_label_ar='DPI',param_label_en='DPI',param_placeholder_ar='144',param_placeholder_en='144',param_default='144'),

    # --- 10 additional document/data tools ---
    'docx-to-text': _new_tool('docx-to-text','تحويل Word إلى TXT','Word to Text','استخرج الفقرات والجداول من Word إلى ملف نصي واضح.','Extract Word paragraphs and tables into plain text.','office','المستندات','Documents','DOC',('.docx',),'.txt',10,batch=True),
    'docx-to-html': _new_tool('docx-to-html','تحويل Word إلى HTML','Word to HTML','حوّل محتوى Word إلى HTML بسيط وقابل للتصفح.','Convert Word content into simple browsable HTML.','office','المستندات','Documents','WEB',('.docx',),'.html',10,batch=True),
    'xlsx-to-csv': _new_tool('xlsx-to-csv','تحويل Excel إلى CSV','Excel to CSV','حوّل أول ورقة في Excel إلى CSV نظيف.','Convert the first Excel worksheet into clean CSV.','office','Excel','Excel','CSV',('.xlsx',),'.csv',10,batch=True),
    'xlsx-to-json': _new_tool('xlsx-to-json','تحويل Excel إلى JSON','Excel to JSON','حوّل أوراق Excel إلى JSON منظم بحسب أسماء الأعمدة.','Convert Excel worksheets into structured JSON keyed by headers.','office','Excel','Excel','JSON',('.xlsx',),'.json',10,batch=True),
    'pptx-to-text': _new_tool('pptx-to-text','تحويل PowerPoint إلى TXT','PowerPoint to Text','استخرج النصوص من شرائح PowerPoint مع أرقام الشرائح.','Extract PowerPoint slide text with slide numbers.','office','المستندات','Documents','PPT',('.pptx',),'.txt',10,batch=True),
    'csv-to-json': _new_tool('csv-to-json','تحويل CSV إلى JSON','CSV to JSON','حوّل جدول CSV إلى قائمة JSON منظمة.','Convert CSV rows into structured JSON objects.','office','البيانات','Data','JSON',('.csv',),'.json',20,batch=True),
    'json-to-csv': _new_tool('json-to-csv','تحويل JSON إلى CSV','JSON to CSV','حوّل قائمة كائنات JSON إلى ملف CSV.','Convert a JSON array of objects into CSV.','office','البيانات','Data','CSV',('.json',),'.csv',10,batch=True),
    'json-to-xlsx': _new_tool('json-to-xlsx','تحويل JSON إلى Excel','JSON to Excel','حوّل قائمة JSON إلى جدول Excel مرتب.','Convert a JSON array into a clean Excel worksheet.','office','البيانات','Data','XLS',('.json',),'.xlsx',10,batch=True),
    'xml-to-json': _new_tool('xml-to-json','تحويل XML إلى JSON','XML to JSON','حوّل XML إلى JSON هرمي قابل للمعالجة.','Convert XML into structured hierarchical JSON.','office','البيانات','Data','XML',('.xml',),'.json',10,batch=True),
    'text-to-json': _new_tool('text-to-json','تحويل TXT إلى JSON','Text to JSON','حوّل الملف النصي إلى JSON يحافظ على ترتيب الأسطر.','Convert a text file into JSON while preserving line order.','office','المستندات','Documents','TXT',('.txt',),'.json',10,batch=True),

    # --- 10 additional OCR tools ---
    'ocr-image-to-pdf': _new_tool('ocr-image-to-pdf','صورة إلى PDF قابل للبحث','OCR Image to Searchable PDF','حوّل صورة إلى PDF مع طبقة نص قابلة للبحث.','Turn an image into a searchable PDF with an OCR text layer.','ocr','OCR','OCR','OCR',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.pdf',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-pdf-to-searchable': _new_tool('ocr-pdf-to-searchable','PDF ممسوح إلى PDF قابل للبحث','OCR PDF to Searchable PDF','أعد بناء PDF الممسوح مع طبقة نص OCR قابلة للبحث.','Rebuild scanned PDFs with a searchable OCR text layer.','ocr','OCR','OCR','OCR',('.pdf',),'.pdf',1,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-image-to-json': _new_tool('ocr-image-to-json','OCR الصورة إلى JSON','OCR Image to JSON','استخرج النص ومربعات الكلمات ودرجات الثقة إلى JSON.','Extract OCR text, word boxes, and confidence into JSON.','ocr','OCR','OCR','JSON',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.json',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-pdf-to-json': _new_tool('ocr-pdf-to-json','OCR PDF إلى JSON','OCR PDF to JSON','استخرج نص كل صفحة إلى JSON منظم.','Extract OCR text page by page into structured JSON.','ocr','OCR','OCR','JSON',('.pdf',),'.json',1,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-pdf-page-texts': _new_tool('ocr-pdf-page-texts','نصوص صفحات PDF عبر OCR','OCR PDF Pages to Texts','استخرج ملف TXT مستقل لكل صفحة في ملف PDF الممسوح.','Create one OCR text file per scanned PDF page.','ocr','OCR','OCR','TXT',('.pdf',),'.zip',1,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-image-numbers': _new_tool('ocr-image-numbers','استخراج الأرقام من الصورة عبر OCR','OCR Number Extractor','استخرج الأرقام والنسب التي يقرأها OCR من الصورة.','Extract numbers and percentages recognized by OCR.','ocr','OCR','OCR','123',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.txt',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-image-emails': _new_tool('ocr-image-emails','استخراج البريد الإلكتروني من الصورة','OCR Email Extractor','استخرج عناوين البريد التي تظهر داخل الصورة.','Extract email addresses visible in an image.','ocr','OCR','OCR','@',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.txt',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-image-urls': _new_tool('ocr-image-urls','استخراج الروابط من الصورة','OCR URL Extractor','استخرج الروابط المكتوبة داخل لقطة الشاشة أو الصورة.','Extract URLs visible in a screenshot or image.','ocr','OCR','OCR','URL',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.txt',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-image-table-csv': _new_tool('ocr-image-table-csv','تحويل جدول الصورة إلى CSV','OCR Table to CSV','حوّل الأسطر التي يتعرف عليها OCR إلى CSV سريع قابل للتحرير.','Turn OCR-detected rows into an editable CSV.','ocr','OCR','OCR','CSV',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.csv',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),
    'ocr-image-clean-text': _new_tool('ocr-image-clean-text','OCR وتنظيف النص','OCR Clean Text','استخرج النص من الصورة ونظّف المسافات والأسطر تلقائيًا.','OCR an image and normalize spacing and lines automatically.','ocr','OCR','OCR','TXT',('.jpg','.jpeg','.png','.webp','.bmp','.tiff'),'.txt',5,batch=True,fields=(FormField('language','select','لغة OCR','OCR language',True,default='ar+en',choices=(('ar','العربية','Arabic'),('en','English','English'),('ar+en','عربي + English','Arabic + English'))),)),

    # --- 10 additional archive tools ---
    'tar-create': _new_tool('tar-create','إنشاء TAR','Create TAR Archive','اجمع الملفات في أرشيف TAR بسيط ومناسب للأرشفة.','Bundle files into a standard TAR archive.','archive','الأرشيف','Archive','TAR',('.pdf','.jpg','.jpeg','.png','.webp','.docx','.xlsx','.pptx','.txt','.csv','.md','.html','.htm','.json','.xml'),'.tar',20),
    'tar-extract': _new_tool('tar-extract','استخراج TAR','Extract TAR Archive','استخرج ملفات TAR بأمان مع فحص للمسارات والملفات الخاصة.','Safely extract TAR archives with traversal and special-file checks.','archive','الأرشيف','Archive','TAR',('.tar',),'.zip',1),
    'gzip-compress': _new_tool('gzip-compress','ضغط GZIP','GZIP Compress','اضغط ملفًا واحدًا بتنسيق GZIP عالي الضغط.','Compress one file using GZIP.','archive','الأرشيف','Archive','GZ',('.txt','.csv','.json','.xml','.html','.htm','.md'),'.gz',1),
    'gzip-decompress': _new_tool('gzip-decompress','فك ضغط GZIP كنص','GZIP Decompress to Text','فك ضغط GZIP النصي إلى TXT بشكل آمن.','Decompress a text-based GZIP payload into TXT.','archive','الأرشيف','Archive','GZ',('.gz',),'.txt',1),
    'zip-list': _new_tool('zip-list','قائمة محتويات ZIP','ZIP Contents Report','أنشئ تقرير JSON بأسماء عناصر ZIP وأحجامها.','Create a JSON report of ZIP entries and sizes.','archive','الأرشيف','Archive','LIST',('.zip',),'.json',1),
    'zip-integrity': _new_tool('zip-integrity','فحص سلامة ZIP','ZIP Integrity Check','اختبر سلامة عناصر ZIP وأنشئ تقريرًا بالنتيجة.','Test ZIP integrity and produce a machine-readable report.','archive','الأرشيف','Archive','CHECK',('.zip',),'.json',1),
    'zip-flatten': _new_tool('zip-flatten','تبسيط بنية ZIP','Flatten ZIP','أنشئ ZIP جديدًا يزيل المجلدات الداخلية ويمنع تعارض الأسماء.','Create a flat ZIP without nested directory paths.','archive','الأرشيف','Archive','FLAT',('.zip',),'.zip',1),
    'tar-list': _new_tool('tar-list','قائمة محتويات TAR','TAR Contents Report','أنشئ تقرير JSON لمحتويات TAR وأحجامها.','Create a JSON report of TAR members and sizes.','archive','الأرشيف','Archive','LIST',('.tar',),'.json',1),
    'gzip-info': _new_tool('gzip-info','معلومات GZIP','GZIP Information','اعرض حجم GZIP والحجم بعد فك الضغط ونسبة الضغط.','Report compressed size, uncompressed size, and ratio for GZIP.','archive','الأرشيف','Archive','INFO',('.gz',),'.json',1),
    'zip-to-tar': _new_tool('zip-to-tar','تحويل ZIP إلى TAR','ZIP to TAR','حوّل أرشيف ZIP إلى TAR مع تسطيح المسارات الداخلية.','Convert ZIP archives into TAR with safe flattened member names.','archive','الأرشيف','Archive','→TAR',('.zip',),'.tar',1),

    # --- 10 additional utility tools ---
    'file-mime-report': _new_tool('file-mime-report','كاشف نوع الملف','File MIME Report','اعرض امتداد الملف وتخمين MIME وبصمة البداية السداسية.','Report extension, MIME guess, and initial file signature bytes.','utilities','الأدوات المساعدة','Utilities','MIME',('.pdf','.jpg','.jpeg','.png','.webp','.bmp','.tiff','.docx','.xlsx','.pptx','.txt','.csv','.md','.html','.htm','.json','.xml','.zip','.tar','.gz'),'.json',10,batch=True),
    'text-statistics': _new_tool('text-statistics','إحصائيات النص','Text Statistics','احسب الكلمات والأسطر والفقرات والأحرف في ملف نصي.','Count words, lines, paragraphs, characters, and UTF-8 bytes.','utilities','الأدوات المساعدة','Utilities','STAT',('.txt','.md','.csv','.html','.htm'),'.json',20,batch=True),
    'text-clean': _new_tool('text-clean','تنظيف النص','Text Cleaner','وحّد المسافات والأسطر ونظّف النص بسرعة.','Normalize whitespace and clean text lines quickly.','utilities','الأدوات المساعدة','Utilities','CLEAN',('.txt','.md'),'.txt',20,batch=True),
    'text-deduplicate': _new_tool('text-deduplicate','حذف الأسطر المكررة','Text Line Deduplicator','احذف الأسطر المكررة مع الحفاظ على أول ظهور لها.','Remove duplicate lines while keeping first occurrence order.','utilities','الأدوات المساعدة','Utilities','DEDUP',('.txt','.md','.csv'),'.txt',20,batch=True),
    'text-sort': _new_tool('text-sort','ترتيب أسطر النص','Text Line Sorter','رتّب أسطر النص أبجديًا تصاعديًا أو تنازليًا.','Sort text lines ascending or descending.','utilities','الأدوات المساعدة','Utilities','SORT',('.txt','.md','.csv'),'.txt',20,batch=True,fields=(FormField('descending','select','الاتجاه','Direction',True,default='0',choices=(('0','تصاعدي','Ascending'),('1','تنازلي','Descending'))),)),
    'filename-normalizer': _new_tool('filename-normalizer','تنظيف اسم الملف','Filename Normalizer','اقترح اسم ملف نظيفًا وآمنًا ومناسبًا للمشاركة.','Suggest a clean, normalized, share-friendly filename.','utilities','الأدوات المساعدة','Utilities','NAME',('.pdf','.jpg','.jpeg','.png','.webp','.docx','.xlsx','.pptx','.txt','.csv','.md','.html','.json','.xml','.zip','.tar','.gz'),'.json',20,batch=True),
    'csv-validator': _new_tool('csv-validator','مدقق CSV','CSV Validator','تحقق من تساوي عدد الأعمدة في صفوف CSV وأنشئ تقريرًا بالأخطاء.','Validate CSV row widths and report structural errors.','utilities','الأدوات المساعدة','Utilities','CSV',('.csv',),'.json',10,batch=True),
    'json-validator': _new_tool('json-validator','مدقق JSON','JSON Validator','تحقق من JSON واعرف موضع الخطأ عند وجوده.','Validate JSON and report the error location when invalid.','utilities','الأدوات المساعدة','Utilities','JSON',('.json',),'.json',10,batch=True),
    'number-list-analyzer': _new_tool('number-list-analyzer','محلل قائمة الأرقام','Number List Analyzer','احسب المتوسط والوسيط والمجموع وأقصى وأدنى قيمة.','Calculate count, sum, mean, median, minimum, and maximum.','utilities','الأدوات المساعدة','Utilities','123',('.txt',),'.json',20,batch=True),
    'text-to-base64': _new_tool('text-to-base64','ترميز TXT إلى Base64','Text to Base64','حوّل محتوى ملف TXT إلى Base64 داخل ملف نصي.','Encode a UTF-8 text file as Base64.','utilities','الأدوات المساعدة','Utilities','64',('.txt',),'.txt',10,batch=True),
})

# New tools deliberately inherit the free/public state.  Their plan metadata is kept
# separate so future Pro gating can be enabled without rewriting the registry.

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
        "tool_ids": ("pdf-merge", "pdf-split", "pdf-compress", "pdf-to-text", "pdf-ocr", "pdf-to-docx", "pdf-to-markdown", "image-to-pdf", "image-upscale", "word-to-pdf", "ppt-to-pdf", "assignment-cover-page", "lms-pdf-size-optimizer", "omr-bubble-sheet", "ocr-pdf-to-markdown", "lms-question-bank-formatter"),
    },
    "educators": {
        "title_ar": "للمعلمين والدكاترة", "title_en": "For Educators",
        "description_ar": "جهز موادك التعليمية وشارك المستندات بوضوح.",
        "description_en": "Prepare teaching materials and share documents with clarity.",
        "tool_ids": ("pdf-merge", "pdf-extract-pages", "pdf-delete-pages", "pdf-redact", "pdf-ocr", "pdf-to-docx", "word-to-pdf", "ppt-to-pdf", "image-to-pdf", "image-watermark", "zip-create", "bulk-certificate-maker", "omr-bubble-sheet", "lms-question-bank-formatter"),
    },
    "developers": {
        "title_ar": "للمطورين", "title_en": "For Developers",
        "description_ar": "أدوات ملفات عملية للمواصفات والتوثيق والتحقق.",
        "description_en": "Practical file tools for documentation, data, and verification.",
        "tool_ids": ("markdown-to-html", "html-to-pdf", "csv-to-xlsx", "file-hash", "file-info", "json-minify", "text-diff", "checksum-compare", "zip-create", "zip-extract", "pdf-to-text", "csv-merge-deduplicate"),
    },
    "business": {
        "title_ar": "للأعمال", "title_en": "For Business",
        "description_ar": "حوّل وشارك المستندات والفواتير والملفات اليومية.",
        "description_en": "Convert and share documents, invoices, and everyday files.",
        "tool_ids": ("excel-to-pdf", "csv-to-xlsx", "csv-to-pdf", "xlsx-to-html", "csv-statistics", "pdf-compress", "pdf-merge", "pdf-redact", "image-to-pdf", "image-watermark", "zip-create", "file-info", "bulk-certificate-maker", "csv-merge-deduplicate"),
    },
    "everyday": {
        "title_ar": "للاستخدام اليومي", "title_en": "Everyday Tools",
        "description_ar": "أدوات سريعة للصور وملفات PDF والمهام اليومية.",
        "description_en": "Fast tools for images, PDFs, and everyday tasks.",
        "tool_ids": ("image-to-jpg", "image-to-png", "image-to-webp", "image-resize", "image-compress", "image-upscale", "image-background-cleaner", "image-rotate", "image-to-pdf", "pdf-compress", "social-media-image-resizer", "quote-social-graphic", "pdf-booklet"),
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

def _meta_for(tool: Tool) -> dict:
    existing = TOOL_META.get(tool.id)
    if existing:
        return existing
    # New tools inherit a deterministic, SEO-friendly slug and conservative metadata.
    return {
        "slug": tool.id,
        "keywords": f"{tool.name_ar} {tool.name_en} {tool.category_ar} {tool.category_en}",
        "popular": False,
        "sort": 1000 + list(TOOLS).index(tool.id),
    }

def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)

def list_tools():
    return [
        {**asdict(tool), **_meta_for(tool), "plan_required": plan_required_for_tool(tool.id)}
        for tool in sorted(TOOLS.values(), key=lambda item: _meta_for(item)["sort"])
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
    return f"/tools/{_meta_for(tool)['slug']}"


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
    "pdf-compress": ("pdf-merge", "pdf-split", "pdf-to-jpg", "pdf-remove-blank-pages", "pdf-grayscale"),
    "pdf-reorder-pages": ("pdf-rotate-selected", "pdf-extract-pages", "pdf-delete-pages"),
    "pdf-password-protect": ("pdf-watermark-text", "pdf-metadata", "pdf-compress"),
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

# --- Infinity 6.0 high-value expansion: 60 production-oriented tools ---
# Kept data-driven so future feature flags, pricing, search, and analytics can
# reason about every tool consistently without duplicating view logic.
from converters.mega_tools import PDF_IDS, IMAGE_IDS, OFFICE_IDS, OCR_IDS, ARCHIVE_IDS, UTILITY_IDS


def _mega_tool(id_, ar, en, dar, den, category, arcat, encat, icon, ins, out, max_files=1, *, fields=(), param_field="", param_label_ar="", param_label_en="", param_placeholder_ar="", param_placeholder_en="", param_default="", input_required=True, batch=False):
    return Tool(id_, ar, en, dar, den, category, arcat, encat, icon, tuple(ins), out, max_files, True, batch, param_field, param_label_ar, param_label_en, param_placeholder_ar, param_placeholder_en, param_default, input_required, tuple(fields))

MegaFormField = FormField
_MEGA = [
    # PDF
    _mega_tool("pdf-to-docx","PDF إلى Word","PDF to Word","حوّل نص PDF إلى مستند Word قابل للتحرير.","Turn extractable PDF text into an editable Word document.","pdf","PDF","PDF","DOCX",(".pdf",),".docx"),
    _mega_tool("pdf-to-markdown","PDF إلى Markdown","PDF to Markdown","حوّل نص PDF إلى Markdown منظم حسب الصفحات.","Convert PDF text into page-structured Markdown.","pdf","PDF","PDF","MD",(".pdf",),".md"),
    _mega_tool("pdf-compare","مقارنة ملفي PDF","Compare PDFs","قارن نص ملفي PDF وأخرج تقرير الفروقات.","Compare two PDFs and produce a readable diff report.","pdf","PDF","PDF","Δ",(".pdf",),".txt",2),
    _mega_tool("pdf-repair","إصلاح PDF","Repair PDF","أعد بناء ملف PDF وحاول تنظيف بنيته مع الحفاظ على المحتوى.","Rewrite a PDF with PyMuPDF garbage collection and deflation.","pdf","PDF","PDF","FIX",(".pdf",),".pdf"),
    _mega_tool("pdf-image-extract","استخراج صور PDF","Extract PDF Images","استخرج الصور المضمّنة داخل PDF كأرشيف ZIP.","Extract embedded raster images from a PDF into a ZIP archive.","pdf","PDF","PDF","IMG",(".pdf",),".zip"),
    _mega_tool("pdf-links-report","تقرير روابط PDF","PDF Link Report","استخرج جميع الروابط والعناوين المرتبطة من ملف PDF.","Export PDF links and destinations as JSON.","pdf","PDF","PDF","URL",(".pdf",),".json"),
    _mega_tool("pdf-annotations-report","تقرير تعليقات PDF","PDF Annotation Report","حلّل التعليقات والملاحظات الموجودة داخل PDF.","Export PDF annotations and comments as JSON.","pdf","PDF","PDF","ANN",(".pdf",),".json"),
    _mega_tool("pdf-page-size-report","مقاسات صفحات PDF","PDF Page Size Report","أظهر مقاس كل صفحة بالـ points والميليمتر.","Report every PDF page size in points and millimeters.","pdf","PDF","PDF","MM",(".pdf",),".json"),
    _mega_tool("pdf-redact","تنقيح PDF","Redact PDF","احذف النصوص الحساسة بإضافة تنقيحات سوداء حقيقية على الكلمات المحددة.","Apply real PDF redactions to matching text terms.","pdf","PDF","PDF","RED",(".pdf",),".pdf",param_field="param",param_label_ar="النصوص المطلوب تنقيحها",param_label_en="Terms to redact",param_placeholder_ar="سر، رقم، بريد",param_placeholder_en="secret, ID, email"),
    _mega_tool("pdf-unlock","إزالة كلمة مرور PDF","Unlock PDF","أزل حماية كلمة المرور عن PDF عندما تملك كلمة المرور.","Remove PDF encryption when the correct password is supplied.","pdf","PDF","PDF","KEY",(".pdf",),".pdf",fields=(MegaFormField("password","password","كلمة المرور","Password",True),)),
    # Images
    _mega_tool("image-upscale","تكبير الصورة","Upscale Image","كبّر الصورة حتى 4× باستخدام إعادة أخذ عينات عالية الجودة.","Upscale images up to 4× with high-quality resampling.","images","الصور","Images","2X",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="عامل التكبير (2-4)",param_label_en="Scale factor (2-4)",param_placeholder_ar="2",param_placeholder_en="2",param_default="2"),
    _mega_tool("image-blur","تمويه الصورة","Blur Image","طبّق تمويهًا قابلًا للتحكم على الصورة.","Apply a configurable Gaussian blur.","images","الصور","Images","BLR",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="قوة التمويه",param_label_en="Blur radius",param_placeholder_ar="3",param_placeholder_en="3",param_default="3"),
    _mega_tool("image-pixelate","بكسلة الصورة","Pixelate Image","حوّل الصورة إلى نمط بكسلات مناسب للمعاينات والإخفاء البصري.","Pixelate an image for stylized previews or visual masking.","images","الصور","Images","PIX",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="حجم البكسلات",param_label_en="Pixel block size",param_placeholder_ar="32",param_placeholder_en="32",param_default="32"),
    _mega_tool("image-invert","عكس ألوان الصورة","Invert Colors","اعكس ألوان الصورة مع الحفاظ على الشفافية.","Invert image colors while preserving alpha.","images","الصور","Images","INV",(".jpg",".jpeg",".png",".webp"),".png",batch=True),
    _mega_tool("image-posterize","تسطيح ألوان الصورة","Posterize Image","قلّل مستويات الألوان لإنشاء مظهر رسومي واضح.","Reduce color levels for a posterized graphic look.","images","الصور","Images","PST",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="مستويات اللون",param_label_en="Color bits",param_placeholder_ar="4",param_placeholder_en="4",param_default="4"),
    _mega_tool("image-color-palette","استخراج لوحة الألوان","Color Palette Extractor","استخرج أكثر الألوان حضورًا مع قيم HEX وRGB.","Extract dominant colors with HEX and RGB values.","images","الصور","Images","PAL",(".jpg",".jpeg",".png",".webp"),".json",batch=True,param_field="param",param_label_ar="عدد الألوان",param_label_en="Color count",param_placeholder_ar="8",param_placeholder_en="8",param_default="8"),
    _mega_tool("image-watermark","علامة مائية للصورة","Image Watermark","أضف علامة مائية أنيقة داخل الصورة.","Add a subtle watermark overlay to the image.","images","الصور","Images","WM",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="نص العلامة المائية",param_label_en="Watermark text",param_placeholder_ar="INFINITY",param_placeholder_en="INFINITY",param_default="INFINITY"),
    _mega_tool("image-background-cleaner","تنظيف الخلفية البيضاء","White Background Cleaner","اجعل الخلفية القريبة من الأبيض شفافة بسرعة.","Remove near-white backgrounds with a conservative alpha threshold.","images","الصور","Images","BG",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="درجة التحمل",param_label_en="Tolerance",param_placeholder_ar="24",param_placeholder_en="24",param_default="24"),
    _mega_tool("image-auto-orient","تصحيح اتجاه الصورة","Auto Orient Image","صحّح اتجاه الصور اعتمادًا على بيانات EXIF.","Apply EXIF-aware orientation automatically.","images","الصور","Images","↻",(".jpg",".jpeg",".png",".webp"),".png",batch=True),
    _mega_tool("image-round-corners","زوايا دائرية للصورة","Round Image Corners","أنشئ صورة PNG بزوايا مستديرة وشفافية.","Create a transparent PNG with rounded corners.","images","الصور","Images","RAD",(".jpg",".jpeg",".png",".webp"),".png",batch=True,param_field="param",param_label_ar="نصف قطر الزاوية",param_label_en="Corner radius",param_placeholder_ar="40",param_placeholder_en="40",param_default="40"),
    # Office / Documents / Data
    _mega_tool("docx-to-markdown","Word إلى Markdown","DOCX to Markdown","حوّل فقرات Word وعناوينه إلى Markdown.","Convert Word paragraphs and headings to Markdown.","office","المستندات والبيانات","Office & Data","MD",(".docx",),".md"),
    _mega_tool("docx-table-to-csv","جداول Word إلى CSV","DOCX Tables to CSV","استخرج أول جداول Word إلى CSV.","Export Word tables into a CSV file.","office","المستندات والبيانات","Office & Data","CSV",(".docx",),".csv"),
    _mega_tool("xlsx-to-html","Excel إلى HTML","Excel to HTML","حوّل أوراق Excel إلى جدول HTML قابل للنشر.","Convert Excel worksheets into publishable HTML tables.","office","المستندات والبيانات","Office & Data","WEB",(".xlsx",),".html"),
    _mega_tool("xlsx-summary","ملخص ملف Excel","Excel Summary","أنشئ تقريرًا عن الأوراق وعدد الصفوف والأعمدة.","Summarize workbook sheets, rows, and columns.","office","المستندات والبيانات","Office & Data","Σ",(".xlsx",),".json"),
    _mega_tool("csv-to-markdown","CSV إلى Markdown","CSV to Markdown","حوّل CSV إلى جدول Markdown جاهز للتوثيق.","Convert CSV data into a Markdown table.","office","المستندات والبيانات","Office & Data","MD",(".csv",),".md"),
    _mega_tool("csv-statistics","إحصائيات CSV","CSV Statistics","حلّل أعمدة CSV الرقمية والنصية وأخرج تقريرًا.","Profile CSV columns with row counts, uniqueness, and numeric stats.","office","المستندات والبيانات","Office & Data","Σ",(".csv",),".json"),
    _mega_tool("json-to-html","JSON إلى HTML","JSON to HTML","حوّل JSON إلى صفحة HTML سهلة القراءة.","Render JSON as a readable HTML document.","office","المستندات والبيانات","Office & Data","JS",(".json",),".html"),
    _mega_tool("html-to-text","HTML إلى نص","HTML to Text","استخرج النص الظاهر من صفحة HTML.","Extract visible text from HTML.","office","المستندات والبيانات","Office & Data","TXT",(".html",".htm"),".txt"),
    _mega_tool("markdown-to-text","Markdown إلى نص","Markdown to Text","نظف Markdown إلى نص عادي.","Strip Markdown syntax into plain text.","office","المستندات والبيانات","Office & Data","TXT",(".md",".markdown"),".txt"),
    _mega_tool("pptx-to-markdown","PowerPoint إلى Markdown","PPTX to Markdown","حوّل نص الشرائح إلى Markdown منظم حسب الشرائح.","Convert slide text into structured Markdown.","office","المستندات والبيانات","Office & Data","SLD",(".pptx",),".md"),
    # OCR
    _mega_tool("ocr-image-to-html","OCR الصورة إلى HTML","OCR Image to HTML","استخرج النص من صورة وضعه في HTML آمن.","OCR an image and export the text as safe HTML.","ocr","OCR","OCR","WEB",(".jpg",".jpeg",".png",".webp",".tiff"),".html",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-image-to-markdown","OCR الصورة إلى Markdown","OCR Image to Markdown","حوّل صورة مستند إلى Markdown قابل للتعديل.","OCR a document image into editable Markdown.","ocr","OCR","OCR","MD",(".jpg",".jpeg",".png",".webp",".tiff"),".md",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-pdf-to-markdown","OCR PDF إلى Markdown","OCR PDF to Markdown","حوّل صفحات PDF المصورة إلى Markdown.","OCR scanned PDF pages into Markdown.","ocr","OCR","OCR","MD",(".pdf",),".md",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-pdf-to-csv","OCR PDF إلى CSV","OCR PDF to CSV","استخرج نص كل صفحة في CSV منظم.","Export OCR text per PDF page as CSV.","ocr","OCR","OCR","CSV",(".pdf",),".csv",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-image-to-csv","OCR الصورة إلى CSV","OCR Image to CSV","حوّل كل سطر مقروء من الصورة إلى صف CSV.","Export each OCR text line to a CSV row.","ocr","OCR","OCR","CSV",(".jpg",".jpeg",".png",".webp",".tiff"),".csv",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-receipt-fields","استخراج حقول الإيصال","Receipt OCR Fields","استخرج البريد والهاتف والتاريخ والمبالغ المحتملة من صورة إيصال.","Extract likely emails, phones, dates, and money values from receipt images.","ocr","OCR","OCR","REC",(".jpg",".jpeg",".png",".webp",".tiff"),".json",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-invoice-fields","حقول الفاتورة بالـOCR","Invoice OCR Fields","استخرج رقم الفاتورة والإجمالي والنص الخام كتقرير JSON.","Extract likely invoice number, total, and raw OCR text.","ocr","OCR","OCR","INV",(".jpg",".jpeg",".png",".webp",".tiff"),".json",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-text-deduplicate","تنظيف تكرار OCR","OCR Deduplicator","احذف الأسطر المكررة أو المتطابقة بعد OCR.","Deduplicate repeated OCR lines.","ocr","OCR","OCR","DED",(".jpg",".jpeg",".png",".webp",".tiff"),".txt",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-entities","كيانات OCR","OCR Entities","استخرج الروابط والبريد والهاتف والتواريخ من صورة المستند.","Extract URLs, emails, phone numbers, and dates from OCR.","ocr","OCR","OCR","ENT",(".jpg",".jpeg",".png",".webp",".tiff"),".json",param_field="param",param_label_ar="اللغة",param_label_en="Language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    _mega_tool("ocr-language-report","تقرير لغة OCR","OCR Language Report","قدّر نسبة العربية والإنجليزية في النص المقروء.","Estimate Arabic and English character ratios in OCR text.","ocr","OCR","OCR","LANG",(".jpg",".jpeg",".png",".webp",".tiff"),".json",param_field="param",param_label_ar="لغة OCR",param_label_en="OCR language",param_placeholder_ar="ar+en",param_placeholder_en="ar+eng",param_default="ar+en"),
    # Archive
    _mega_tool("bzip2-compress","ضغط BZIP2","BZIP2 Compress","اضغط ملفًا باستخدام BZIP2 بأقصى مستوى ضغط.","Compress a file using BZIP2 at the highest level.","archive","الأرشيف","Archive","BZ2",(".txt",".csv",".json",".xml",".log",".md"),".bz2"),
    _mega_tool("bzip2-decompress","فك BZIP2","BZIP2 Decompress","فك ضغط ملف BZIP2 إلى المحتوى الأصلي.","Decompress a BZIP2 payload back to its original bytes.","archive","الأرشيف","Archive","BZ2",(".bz2",),".txt"),
    _mega_tool("xz-compress","ضغط XZ","XZ Compress","اضغط الملفات باستخدام XZ.","Compress a file using XZ/LZMA.","archive","الأرشيف","Archive","XZ",(".txt",".csv",".json",".xml",".log",".md"),".xz"),
    _mega_tool("xz-decompress","فك XZ","XZ Decompress","فك ضغط XZ إلى المحتوى الأصلي.","Decompress XZ files.","archive","الأرشيف","Archive","XZ",(".xz",),".txt"),
    _mega_tool("tar-gzip-create","إنشاء TAR.GZ","Create TAR.GZ","اجمع عدة ملفات في أرشيف TAR.GZ.","Create a TAR.GZ archive from multiple files.","archive","الأرشيف","Archive","TGZ",(".*",),".tar.gz",20),
    _mega_tool("tar-gzip-extract","فك TAR.GZ","Extract TAR.GZ","فك أرشيف TAR.GZ مع حماية من المسارات الخطرة.","Safely extract TAR.GZ archives.","archive","الأرشيف","Archive","TGZ",(".gz",".tgz"),".zip"),
    _mega_tool("zip-duplicate-report","تكرار ملفات ZIP","ZIP Duplicate Report","اكتشف أسماء الإدخالات المتكررة داخل ZIP.","Detect duplicate entry names inside a ZIP archive.","archive","الأرشيف","Archive","DUP",(".zip",),".json"),
    _mega_tool("tar-integrity","سلامة TAR","TAR Integrity Report","تحقق من قابلية فتح TAR ومن المسارات الخطرة.","Validate TAR structure and path safety.","archive","الأرشيف","Archive","OK",(".tar",".tgz",".gz",".bz2"),".json"),
    _mega_tool("tar-bzip2-create","إنشاء TAR.BZ2","Create TAR.BZ2","اجمع عدة ملفات في TAR.BZ2.","Create a TAR.BZ2 archive from multiple files.","archive","الأرشيف","Archive","TBZ",(".*",),".tar.bz2",20),
    _mega_tool("tar-bzip2-extract","فك TAR.BZ2","Extract TAR.BZ2","فك TAR.BZ2 بأمان إلى أرشيف ZIP سهل التنزيل.","Safely extract TAR.BZ2 archives into a ZIP download.","archive","الأرشيف","Archive","TBZ",(".bz2",".tbz2"),".zip"),
    # Utilities
    _mega_tool("base64-decode","فك Base64","Base64 Decode","فك محتوى Base64 إلى ملف ثنائي.","Decode Base64 text back into bytes.","utilities","الأدوات المساعدة","Utilities","64",(".txt",),".bin"),
    _mega_tool("url-encode","ترميز URL","URL Encode","شفّر النص كجزء URL آمن.","Percent-encode text for URL use.","utilities","الأدوات المساعدة","Utilities","URL",(".txt",),".txt"),
    _mega_tool("url-decode","فك ترميز URL","URL Decode","فك ترميز نص URL.","Decode percent-encoded URL text.","utilities","الأدوات المساعدة","Utilities","URL",(".txt",),".txt"),
    _mega_tool("json-minify","تصغير JSON","JSON Minify","تحقق من JSON ثم أزله المسافات الزائدة.","Validate JSON and minify it.","utilities","الأدوات المساعدة","Utilities","{}",(".json",),".json"),
    _mega_tool("text-diff","مقارنة نصين","Text Diff","قارن ملفي نص وأخرج الفروقات بصيغة Unified Diff.","Compare two UTF-8 text files as a unified diff.","utilities","الأدوات المساعدة","Utilities","Δ",(".txt",".md",".csv",".json",".xml"),".txt",2),
    _mega_tool("checksum-compare","مقارنة البصمة","Checksum Compare","قارن SHA-256 لملفين بسرعة.","Compare SHA-256 checksums for two files.","utilities","الأدوات المساعدة","Utilities","SHA",(".*",),".json",2),
    _mega_tool("uuid-list-generator","مولد UUID دفعة واحدة","UUID Batch Generator","ولّد حتى 500 UUID v4 عشوائيًا.","Generate up to 500 random UUID v4 values.","utilities","الأدوات المساعدة","Utilities","ID",(),".txt",0,input_required=False,param_field="param",param_label_ar="عدد UUID",param_label_en="UUID count",param_placeholder_ar="10",param_placeholder_en="10",param_default="10"),
    _mega_tool("regex-extract","استخراج Regex","Regex Extractor","استخرج التطابقات الفريدة من ملف نصي باستخدام Regular Expression.","Extract unique regex matches from a text file.","utilities","الأدوات المساعدة","Utilities",".*",(".txt",".md",".csv",".json"),".txt",param_field="param",param_label_ar="التعبير المنتظم",param_label_en="Regular expression",param_placeholder_ar=r"\\b\\w+\\b",param_placeholder_en=r"\\b\\w+\\b",param_default=r"\\b\\w+\\b"),
    _mega_tool("file-extension-report","تقرير امتداد الملف","File Extension Report","حلّل اسم الملف وامتداده ونوع MIME المتوقع.","Report filename, extension, stem, and MIME guess.","utilities","الأدوات المساعدة","Utilities","EXT",(".*",),".json"),
    _mega_tool("hex-encode","ترميز HEX","Hex Encode","حوّل بيانات الملف إلى تمثيل HEX.","Encode file bytes as hexadecimal text.","utilities","الأدوات المساعدة","Utilities","HEX",(".*",),".txt"),
]
for _tool in _MEGA:
    TOOLS[_tool.id] = _tool

# Ensure all expanded tools have stable, SEO-friendly metadata.
for _tool in _MEGA:
    TOOL_META.setdefault(_tool.id, {
        "slug": _tool.id,
        "keywords": f"{_tool.name_ar} {_tool.name_en} {_tool.category_ar} {_tool.category_en}",
        "popular": _tool.id in {"pdf-to-docx","pdf-compare","pdf-redact","image-upscale","image-watermark","xlsx-to-html","ocr-image-to-markdown","tar-gzip-create","json-minify","text-diff"},
        "sort": 500 + len(TOOL_META),
    })

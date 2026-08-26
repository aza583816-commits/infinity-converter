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

TOOLS = {
    "pdf-merge": Tool(
        "pdf-merge", "دمج ملفات PDF", "Merge PDF", "اجمع عدة ملفات PDF في ملف واحد مرتب.", "Combine multiple PDF files into one organized document.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 20, True
    ),
    "pdf-split": Tool(
        "pdf-split", "تقسيم PDF", "Split PDF", "استخرج الصفحة الأولى من ملف PDF في ملف مستقل.", "Extract the first page of a PDF into a separate file.", "pdf", "PDF", "PDF", "PDF", (".pdf",), ".pdf", 1, True
    ),
    "image-to-jpg": Tool(
        "image-to-jpg", "تحويل الصور إلى JPG", "Image to JPG", "حوّل الصور الشائعة إلى JPG بجودة مناسبة.", "Convert common image formats to JPG with practical quality.", "images", "الصور", "Images", "IMG",
        (".png", ".webp", ".jpeg", ".jpg", ".bmp", ".tiff"), ".jpg", 1, True
    ),
    "image-to-png": Tool(
        "image-to-png", "تحويل الصور إلى PNG", "Image to PNG", "حوّل الصور إلى PNG مع الحفاظ على الشفافية عند الإمكان.", "Convert images to PNG while preserving transparency when possible.", "images", "الصور", "Images", "IMG",
        (".jpg", ".jpeg", ".webp", ".bmp", ".tiff"), ".png", 1, True
    ),
    "word-to-pdf": Tool(
        "word-to-pdf", "تحويل Word إلى PDF", "Word to PDF", "حوّل مستندات Word إلى PDF عبر LibreOffice.", "Convert Word documents to PDF using LibreOffice.", "office", "المستندات", "Documents", "DOC", (".docx",), ".pdf", 1, True
    ),
    "excel-to-pdf": Tool(
        "excel-to-pdf", "تحويل Excel إلى PDF", "Excel to PDF", "حوّل جداول Excel إلى ملفات PDF قابلة للمشاركة.", "Convert Excel workbooks into shareable PDF files.", "office", "Excel", "Excel", "XLS", (".xlsx",), ".pdf", 1, True
    ),
    "ppt-to-pdf": Tool(
        "ppt-to-pdf", "تحويل PowerPoint إلى PDF", "PowerPoint to PDF", "حوّل عروض PowerPoint إلى PDF مع الحفاظ على ترتيب الشرائح.", "Convert PowerPoint presentations to PDF while preserving slide order.", "office", "PowerPoint", "PowerPoint", "PPT", (".pptx",), ".pdf", 1, True
    ),
}

def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)

def list_tools():
    return [asdict(tool) for tool in TOOLS.values()]

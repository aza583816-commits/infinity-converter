from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Tool:
    id: str
    name_ar: str
    name_en: str
    category: str
    input_ext: tuple[str, ...]
    output_ext: str
    max_files: int
    local: bool = True

TOOLS = {
    "pdf-merge": Tool(
        "pdf-merge", "دمج ملفات PDF", "Merge PDF", "pdf", (".pdf",), ".pdf", 20, True
    ),
    "pdf-split": Tool(
        "pdf-split", "تقسيم PDF", "Split PDF", "pdf", (".pdf",), ".pdf", 1, True
    ),
    "image-to-jpg": Tool(
        "image-to-jpg", "تحويل الصور إلى JPG", "Image to JPG", "images",
        (".png", ".webp", ".jpeg", ".jpg", ".bmp", ".tiff"), ".jpg", 1, True
    ),
    "image-to-png": Tool(
        "image-to-png", "تحويل الصور إلى PNG", "Image to PNG", "images",
        (".jpg", ".jpeg", ".webp", ".bmp", ".tiff"), ".png", 1, True
    ),
    "word-to-pdf": Tool(
        "word-to-pdf", "Word إلى PDF", "Word to PDF", "office", (".docx",), ".pdf", 1, True
    ),
    "excel-to-pdf": Tool(
        "excel-to-pdf", "Excel إلى PDF", "Excel to PDF", "office", (".xlsx",), ".pdf", 1, True
    ),
    "ppt-to-pdf": Tool(
        "ppt-to-pdf", "PowerPoint إلى PDF", "PowerPoint to PDF", "office", (".pptx",), ".pdf", 1, True
    ),
}

def get_tool(tool_id: str) -> Tool | None:
    return TOOLS.get(tool_id)

def list_tools():
    return [asdict(tool) for tool in TOOLS.values()]

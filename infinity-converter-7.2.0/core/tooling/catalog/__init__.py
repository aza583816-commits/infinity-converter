from core.tooling.catalog.pdf import TOOLS as PDF_TOOLS
from core.tooling.catalog.images import TOOLS as IMAGE_TOOLS
from core.tooling.catalog.office import TOOLS as OFFICE_TOOLS
from core.tooling.catalog.ocr import TOOLS as OCR_TOOLS
from core.tooling.catalog.archive import TOOLS as ARCHIVE_TOOLS
from core.tooling.catalog.utilities import TOOLS as UTILITY_TOOLS

TOOLS = {}
for _catalog in (PDF_TOOLS, IMAGE_TOOLS, OFFICE_TOOLS, OCR_TOOLS, ARCHIVE_TOOLS, UTILITY_TOOLS):
    overlap = set(TOOLS) & set(_catalog)
    if overlap:
        raise RuntimeError(f"Duplicate tool IDs across catalogs: {sorted(overlap)}")
    TOOLS.update(_catalog)

__all__ = [
    "TOOLS", "PDF_TOOLS", "IMAGE_TOOLS", "OFFICE_TOOLS",
    "OCR_TOOLS", "ARCHIVE_TOOLS", "UTILITY_TOOLS",
]

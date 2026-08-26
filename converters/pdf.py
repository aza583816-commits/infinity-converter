from pathlib import Path
from pypdf import PdfReader, PdfWriter

def merge_pdfs(paths: list[Path], output: Path):
    writer = PdfWriter()
    for path in paths:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    with output.open("wb") as fh:
        writer.write(fh)

def split_pdf(path: Path, output: Path, max_pages: int):
    reader = PdfReader(str(path))
    if len(reader.pages) > max_pages:
        raise ValueError("عدد صفحات PDF يتجاوز الحد الآمن.")
    writer = PdfWriter()
    # V2 foundation: first page output. Page-range API is coming with the next tool layer.
    if reader.pages:
        writer.add_page(reader.pages[0])
    with output.open("wb") as fh:
        writer.write(fh)

from pathlib import Path

from converters.pdf import merge_pdfs, split_pdf
from converters.images import convert_image
from converters.office import office_to_pdf

def convert(*, tool, safe_inputs, workspace, timeout, max_pdf_pages):
    paths = [item["path"] for item in safe_inputs]

    if tool.id == "pdf-merge":
        output = workspace.path / "output" / "InfinityConverter-Merged.pdf"
        merge_pdfs(paths, output)
        return output, output.name, "application/pdf"

    if tool.id == "pdf-split":
        output = workspace.path / "output" / "InfinityConverter-Split.pdf"
        split_pdf(paths[0], output, max_pages=max_pdf_pages)
        return output, output.name, "application/pdf"

    if tool.id == "image-to-jpg":
        output = workspace.path / "output" / "InfinityConverter.jpg"
        convert_image(paths[0], output, "JPEG")
        return output, output.name, "image/jpeg"

    if tool.id == "image-to-png":
        output = workspace.path / "output" / "InfinityConverter.png"
        convert_image(paths[0], output, "PNG")
        return output, output.name, "image/png"

    if tool.id in {"word-to-pdf", "excel-to-pdf", "ppt-to-pdf"}:
        output = workspace.path / "output"
        pdf = office_to_pdf(paths[0], output, timeout=timeout)
        return pdf, pdf.name, "application/pdf"

    raise ValueError("هذه الأداة لم تُوصل بمحرك التحويل بعد.")

import csv
import os
import subprocess
from pathlib import Path

try:
    import markdown as markdown_lib
except ImportError:  # Optional at import time; requirements install it in production.
    markdown_lib = None
from openpyxl import Workbook

def office_to_pdf(source: Path, output_dir: Path, timeout: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = "/tmp"

    cmd = [
        "libreoffice",
        "--headless",
        "--nologo",
        "--nodefault",
        "--nofirststartwizard",
        "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(source),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("محرك LibreOffice غير مثبت على الخادم.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("استغرق التحويل وقتًا أطول من المسموح.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("فشل محرك Office في تحويل الملف.") from exc

    produced = output_dir / f"{source.stem}.pdf"
    if not produced.exists() or produced.stat().st_size == 0:
        raise RuntimeError("لم يُنتج LibreOffice ملف PDF صالحًا.")
    return produced


def _basic_markdown(text: str) -> str:
    # Small, dependency-free fallback for headings, bullets, code, and paragraphs.
    # The full markdown package remains the preferred parser when installed.
    import html
    blocks = []
    paragraph = []
    in_code = False
    code_lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines, in_code = [], False
            else:
                if paragraph:
                    blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
                    paragraph = []
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            if paragraph:
                blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
                paragraph = []
            continue
        if line.startswith("### "):
            if paragraph:
                blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
                paragraph = []
            blocks.append("<h3>" + html.escape(line[4:]) + "</h3>")
        elif line.startswith("## "):
            if paragraph:
                blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
                paragraph = []
            blocks.append("<h2>" + html.escape(line[3:]) + "</h2>")
        elif line.startswith("# "):
            if paragraph:
                blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
                paragraph = []
            blocks.append("<h1>" + html.escape(line[2:]) + "</h1>")
        elif line.startswith("- "):
            if paragraph:
                blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
                paragraph = []
            if blocks and blocks[-1].startswith("<ul>"):
                blocks[-1] = blocks[-1][:-5] + "<li>" + html.escape(line[2:]) + "</li></ul>"
            else:
                blocks.append("<ul><li>" + html.escape(line[2:]) + "</li></ul>")
        else:
            paragraph.append(line.strip())
    if paragraph:
        blocks.append("<p>" + html.escape(" ".join(paragraph)) + "</p>")
    if in_code:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "".join(blocks)


def markdown_to_html(source: Path, output: Path):
    text = source.read_text(encoding="utf-8")
    if markdown_lib is not None:
        body = markdown_lib.markdown(text, extensions=["extra", "tables", "sane_lists"])
    else:
        body = _basic_markdown(text)
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>body{font-family:sans-serif;max-width:800px;margin:40px auto;line-height:1.6}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px}</style>"
        f"</head><body>{body}</body></html>"
    )
    output.write_text(html, encoding="utf-8")


def markdown_to_pdf(source: Path, workspace_input: Path, output_dir: Path, timeout: int) -> Path:
    intermediate = workspace_input / f"{source.stem}.html"
    markdown_to_html(source, intermediate)
    return office_to_pdf(intermediate, output_dir, timeout)


def csv_to_xlsx(source: Path, output: Path):
    workbook = Workbook()
    sheet = workbook.active
    with source.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        row_count = 0
        for row in reader:
            sheet.append(row)
            row_count += 1
            if row_count > 200_000:
                raise ValueError("عدد الصفوف يتجاوز الحد الآمن للتحويل.")
    if row_count == 0:
        raise ValueError("ملف CSV فارغ.")
    workbook.save(output)


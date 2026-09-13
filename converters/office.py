from __future__ import annotations

import csv
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from uuid import uuid4

try:
    import markdown as markdown_lib
except ImportError:  # Optional at import time; requirements install it in production.
    markdown_lib = None
from openpyxl import Workbook


_REMOTE_HTML_PATTERNS = (
    re.compile(r"\b(?:src|poster)\s*=\s*['\"]\s*(?:https?|ftp|file):", re.I),
    re.compile(r"<link\b[^>]*\bhref\s*=\s*['\"]\s*(?:https?|ftp|file):", re.I),
    re.compile(r"url\(\s*['\"]?\s*(?:https?|ftp|file):", re.I),
    re.compile(r"@import\s+(?:url\()?\s*['\"]?\s*(?:https?|ftp|file):", re.I),
)


def _reject_remote_html_resources(source: Path) -> None:
    if source.suffix.lower() not in {".html", ".htm"}:
        return
    try:
        text = source.read_text(encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("ملف HTML يجب أن يكون UTF-8 صالحًا.") from exc
    if any(pattern.search(text) for pattern in _REMOTE_HTML_PATTERNS):
        raise ValueError(
            "لأسباب الخصوصية والأمان، HTML الذي يعتمد على صور أو CSS خارجية غير مدعوم. "
            "استخدم موارد مضمنة داخل الملف."
        )


def _run_libreoffice(cmd: list[str], *, timeout: int, env: dict[str, str]) -> None:
    """Run LibreOffice in its own process group so timeouts kill child workers too."""
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("محرك LibreOffice غير مثبت على الخادم.") from exc

    try:
        _stdout, _stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise RuntimeError("استغرق التحويل وقتًا أطول من المسموح.") from exc

    if process.returncode != 0:
        raise RuntimeError("فشل محرك Office في تحويل الملف.")


def office_to_pdf(source: Path, output_dir: Path, timeout: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    _reject_remote_html_resources(source)

    # A private LibreOffice profile prevents cross-request state leakage and
    # avoids sharing locks/extensions/preferences between concurrent users.
    profile = output_dir / f".lo-profile-{uuid4().hex}"
    home = profile / "home"
    tmp = profile / "tmp"
    home.mkdir(parents=True, mode=0o700)
    tmp.mkdir(parents=True, mode=0o700)

    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "SAL_DISABLE_OPENCL": "1",
        "SAL_USE_VCLPLUGIN": "svp",
        # Block network fetches from document/HTML renderers. A malformed or
        # remote-linked document must never turn the conversion worker into an
        # SSRF client. Local conversion does not need HTTP/HTTPS/FTP egress.
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ftp_proxy": "http://127.0.0.1:9",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "FTP_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "localhost,127.0.0.1",
    })

    cmd = [
        "libreoffice",
        "--headless",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
        "--nofirststartwizard",
        "--norestore",
        f"-env:UserInstallation={profile.resolve().as_uri()}",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(source),
    ]

    try:
        _run_libreoffice(cmd, timeout=timeout, env=env)
    finally:
        shutil.rmtree(profile, ignore_errors=True)

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


def _safe_spreadsheet_cell(value):
    """Neutralize CSV/Excel formula injection while preserving displayed text."""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def csv_to_xlsx(source: Path, output: Path):
    workbook = Workbook()
    sheet = workbook.active
    with source.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        row_count = 0
        for row in reader:
            sheet.append([_safe_spreadsheet_cell(value) for value in row])
            row_count += 1
            if row_count > 200_000:
                raise ValueError("عدد الصفوف يتجاوز الحد الآمن للتحويل.")
    if row_count == 0:
        raise ValueError("ملف CSV فارغ.")
    workbook.save(output)

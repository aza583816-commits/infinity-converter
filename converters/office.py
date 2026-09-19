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
    from html.parser import HTMLParser
    import html

    class ResourceGuard(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in {"base", "object", "embed", "iframe", "script", "link"}:
                raise ValueError("HTML يحتوي على موارد نشطة أو خارجية غير مدعومة.")
            for key, value in attrs:
                if key in {"src", "poster", "background", "data", "srcset"}:
                    if not value or not value.strip().lower().startswith("data:image/") or key == "srcset":
                        raise ValueError("لحماية الخصوصية، موارد HTML يجب أن تكون صورًا مضمنة فقط.")
        handle_startendtag = handle_starttag

    ResourceGuard(convert_charrefs=True).feed(text)
    # Reject CSS resource syntax, including escapes/comments which can disguise
    # url()/@import. Plain styles and embedded images remain supported.
    styles = re.findall(r"<style\b[^>]*>(.*?)</style\s*>|\bstyle\s*=\s*['\"](.*?)['\"]", text, re.I | re.S)
    for pair in styles:
        css = html.unescape(" ".join(pair)).lower()
        if any(token in css for token in ("url", "@import", "\\", "/*")):
            raise ValueError("موارد CSS الخارجية غير مدعومة.")
    if any(pattern.search(text) for pattern in _REMOTE_HTML_PATTERNS):
        raise ValueError("موارد HTML الخارجية غير مدعومة.")


def _bounded_native_command(cmd: list[str], timeout: int) -> list[str]:
    """Wrap a native renderer with OS rlimits when prlimit is available.

    CPU time complements the wall-clock timeout; file-size and descriptor limits
    reduce blast radius if a malformed document drives abnormal renderer output.
    Full outbound-network denial still belongs at the dedicated worker layer.
    """
    prlimit = shutil.which("prlimit")
    if not prlimit:
        return cmd
    cpu_seconds = max(30, min(int(timeout), 180))
    # PDF tools currently cap output well below this; leave headroom for
    # LibreOffice temporary/output bookkeeping while preventing runaway files.
    file_size_bytes = 512 * 1024 * 1024
    return [
        prlimit,
        f"--cpu={cpu_seconds}:{cpu_seconds}",
        f"--fsize={file_size_bytes}:{file_size_bytes}",
        "--nofile=128:128",
        "--core=0:0",
        "--",
        *cmd,
    ]


def _run_libreoffice(cmd: list[str], *, timeout: int, env: dict[str, str]) -> None:
    """Run LibreOffice in its own process group so timeouts kill child workers too."""
    cmd = _bounded_native_command(cmd, timeout)
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


def _html_pdf_heading_fallback(source: Path, output_dir: Path) -> Path:
    """Render heading text as styled paragraphs for LibreOffice Writer/Web.

    Some lean LibreOffice installs produce an empty page in place of an HTML
    heading while still converting the rest of the text. A print-only copy
    keeps heading text visible without modifying the uploaded document.
    The independently checked PDF output must still include source headings.
    """
    import re

    html_text = source.read_text(encoding="utf-8")
    if not re.search(r"<h[1-6]\b", html_text, flags=re.I):
        return source

    def open_heading(match):
        level = int(match.group(1))
        attributes = match.group(2)
        size = {1: 24, 2: 20, 3: 17, 4: 15, 5: 13, 6: 12}[level]
        # Preserve existing style/class/id attributes while applying a
        # print-visible bold heading to the PDF-rendering copy only.
        return f'<p{attributes} style="font-size:{size}pt;font-weight:bold">'

    adapted = re.sub(r"<h([1-6])\b([^>]*)>", open_heading, html_text, flags=re.I)
    adapted = re.sub(r"</h[1-6]\s*>", "</p>", adapted, flags=re.I)
    if adapted == html_text:
        return source
    copy = output_dir / f"{source.stem}-pdf-headings.html"
    copy.write_text(adapted, encoding="utf-8")
    return copy


def office_to_pdf(source: Path, output_dir: Path, timeout: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    _reject_remote_html_resources(source)
    render_source = (
        _html_pdf_heading_fallback(source, output_dir)
        if source.suffix.lower() in {".html", ".htm"} else source
    )

    # A private LibreOffice profile prevents cross-request state leakage and
    # avoids sharing locks/extensions/preferences between concurrent users.
    profile = output_dir / f".lo-profile-{uuid4().hex}"
    home = profile / "home"
    tmp = profile / "tmp"
    home.mkdir(parents=True, mode=0o700)
    tmp.mkdir(parents=True, mode=0o700)

    # The renderer does not need database credentials, AI keys or billing keys.
    user_profile = profile / "user"
    user_profile.mkdir(mode=0o700)
    (user_profile / "registrymodifications.xcu").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
        '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
        '</item></oor:items>', encoding="utf-8")
    env = {name: os.environ[name] for name in ("PATH", "LANG", "LC_ALL", "TZ") if name in os.environ}
    env.update({
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "SAL_DISABLE_OPENCL": "1",
        "SAL_USE_VCLPLUGIN": "svp",
        # Defense in depth for proxy-aware fetches, NOT a network sandbox.
        # Production should isolate renderer egress at the worker/network layer.
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ftp_proxy": "http://127.0.0.1:9",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "FTP_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "",
        "no_proxy": "",
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
        # Writer/Web PDF export can omit HTML heading text in some packaged
        # LibreOffice builds. Use the Writer PDF filter for HTML (including
        # Markdown rendered as intermediate HTML), then enforce source-aware
        # content checks in the independent acceptance suite.
        "--convert-to", "pdf:writer_pdf_Export" if source.suffix.lower() in {".html", ".htm"} else "pdf",
        "--outdir", str(output_dir),
        str(render_source),
    ]

    try:
        _run_libreoffice(cmd, timeout=timeout, env=env)
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    produced = output_dir / f"{render_source.stem}.pdf"
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

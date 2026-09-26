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

from config.settings import settings


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


def _expected_html_headings(source: Path) -> tuple[str, ...]:
    """Read headings from original HTML, never from renderer-produced output."""
    from html.parser import HTMLParser
    import re

    class HeadingParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.in_heading = False
            self.fragments = []
            self.headings = []

        def handle_starttag(self, tag, attrs):
            if re.fullmatch(r"h[1-6]", tag):
                self.in_heading = True
                self.fragments = []

        def handle_data(self, value):
            if self.in_heading:
                self.fragments.append(value)

        def handle_endtag(self, tag):
            if self.in_heading and re.fullmatch(r"h[1-6]", tag):
                title = " ".join(" ".join(self.fragments).split())
                if title:
                    self.headings.append(title)
                self.in_heading = False

    parser = HeadingParser()
    parser.feed(source.read_text(encoding="utf-8"))
    parser.close()
    return tuple(parser.headings)


def _pdf_contains_headings(path: Path, headings: tuple[str, ...]) -> bool:
    """Check actual PDF heading text, including Arabic visual rendering.

    Some native PDF renderers store Arabic presentation glyphs with a broken
    Unicode extraction map even when the printed glyphs are correct. For
    these headings, require independently read-back Latin text AND Arabic
    OCR on the rendered output; never declare headings preserved just
    because an output file exists. Arabic visual OCR does not certify that
    copying or searching its PDF text layer is lossless.
    """
    import re
    import unicodedata
    import pymupdf

    def normalized(value: str) -> str:
        return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

    with pymupdf.open(path) as pdf:
        text = normalized(" ".join(page.get_text("text") for page in pdf))
        pending_arabic = []
        for title in headings:
            expected = normalized(title)
            if expected in text:
                continue
            if not re.search(r"[\u0600-\u06FF]", title):
                return False
            if not all(token in text for token in re.findall(r"[a-z0-9]+", expected)):
                return False
            pending_arabic.append(title)
        if not pending_arabic:
            return True
        # The OCR branch is reached only when Unicode extraction does not
        # reproduce an Arabic heading; it is not run on ordinary documents.
        from PIL import Image
        import pytesseract

        snippets = []
        for page in pdf:
            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            try:
                snippets.append(
                    pytesseract.image_to_string(
                        image, lang="ara+eng",
                        timeout=min(settings.ocr_timeout_seconds, 20),
                    )
                )
            except (RuntimeError, pytesseract.TesseractError):
                return False
            finally:
                image.close()
        visible = normalized(" ".join(snippets))
        return all(
            all(normalized(word) in visible
                for word in re.findall(r"[\u0600-\u06FF]+", title))
            for title in pending_arabic
        )


def _render_html_story_fallback(source: Path, output: Path) -> None:
    """Use an independent paginated HTML renderer only when Writer lost text."""
    import pymupdf

    html_source = source.read_text(encoding="utf-8")
    # Native fallback fonts can corrupt Arabic glyph mapping (for example,
    # producing Ǆ/ǂ characters instead of an Arabic title). Embed an Arabic-
    # capable font with a correct PDF Unicode map and a bundled font archive.
    font_root = Path("/usr/share/fonts/truetype/noto")
    font_file = font_root / "NotoSansArabic-Regular.ttf"
    if font_file.is_file():
        css = (
            "@font-face{font-family:InfinityArabic;"
            "src:url(NotoSansArabic-Regular.ttf)}"
            "html,body,p,span,pre,table,tr,td,th,h1,h2,h3,h4,h5,h6"
            "{font-family:InfinityArabic !important}"
            "h1{font-size:24pt;font-weight:bold}"
        )
        font_archive = pymupdf.Archive(str(font_root))
    else:
        css = "h1{font-size:24pt;font-weight:bold}"
        font_archive = None
    story = pymupdf.Story(html_source, user_css=css, archive=font_archive)
    temporary = output.with_name(output.stem + "-story.pdf")
    writer = pymupdf.DocumentWriter(str(temporary))
    page = pymupdf.Rect(0, 0, 595, 842)
    frame = pymupdf.Rect(44, 44, 551, 798)
    try:
        story.write(writer, lambda _index, _filled: (page, frame, pymupdf.Identity))
    finally:
        writer.close()
    temporary.replace(output)


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


def _source_pdf_text_fragments(source: Path) -> list[str]:
    """Independent expected text from a small plain text / CSV source."""
    if source.suffix.lower() == ".txt":
        return [line.strip() for line in source.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    if source.suffix.lower() == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as file:
            return [cell for row in csv.reader(file) for cell in row if cell.strip()]
    return []


def _pdf_has_text_fragments(output: Path, fragments: list[str]) -> bool:
    """Require every source field as a complete token sequence, not a substring.

    A PDF containing 000012 must not be accepted as preserving source ID
    00001; likewise an Arabic prefix inside a longer word is not equivalent
    to the original field. Normalize compatibility glyphs on both sides.
    """
    import pymupdf
    import re
    import unicodedata

    with pymupdf.open(output) as document:
        actual = " ".join(
            unicodedata.normalize("NFKC", page.get_text("text"))
            for page in document
        )
    actual = " ".join(actual.split())
    # PDF text extraction may concatenate neighboring table cells when their
    # scripts differ (e.g. Arabic name immediately followed by an ASCII ID).
    # Restore only Arabic/ASCII script boundaries; do NOT split ASCII letters
    # from digits, which could make a truncated identifier pass the audit.
    script_boundary = (
        r"(?<=[\u0600-\u06FF])(?=[A-Za-z0-9])"
        r"|(?<=[A-Za-z0-9])(?=[\u0600-\u06FF])"
    )
    actual = re.sub(script_boundary, " ", actual)
    for fragment in fragments:
        expected = " ".join(unicodedata.normalize("NFKC", fragment).split())
        expected = re.sub(script_boundary, " ", expected)
        if not expected:
            continue
        # Delimit only word-like ends. This permits ordinary punctuation around
        # a complete source cell, without accepting a prefix of another cell.
        prefix = r"(?<!\w)" if expected[0].isalnum() or expected[0] == "_" else ""
        suffix = r"(?!\w)" if expected[-1].isalnum() or expected[-1] == "_" else ""
        if re.search(prefix + re.escape(expected) + suffix, actual) is None:
            return False
    return True


def _printable_text_html(source: Path, output_dir: Path) -> Path:
    """Generate bounded, escaped local HTML without loading external resources."""
    import html

    temporary = output_dir / f"{source.stem}-source-print.html"
    if source.suffix.lower() == ".txt":
        text = html.escape(source.read_text(encoding="utf-8"))
        body = '<pre style="white-space:pre-wrap">' + text + "</pre>"
    else:
        with source.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
        body = "<table border='1'>" + "".join(
            "<tr>" + "".join(
                "<td>" + html.escape(cell).replace("\r\n", "\n")
                .replace("\r", "\n").replace("\n", "<br/>") + "</td>"
                for cell in row
            ) + "</tr>" for row in rows
        ) + "</table>"
    temporary.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        "<body>" + body + "</body></html>", encoding="utf-8"
    )
    return temporary


def _xlsx_pdf_fragments(source: Path) -> list[str]:
    """Read each nonempty cell independently, across every original worksheet."""
    from openpyxl import load_workbook

    book = load_workbook(source, read_only=True, data_only=True)
    try:
        return [str(value) for sheet in book
                for row in sheet.iter_rows(values_only=True)
                for value in row if value is not None and str(value).strip()]
    finally:
        book.close()


def _printable_simple_xlsx_html(source: Path, output_dir: Path) -> Path:
    """Keep every data cell when the native PDF lost Unicode on a small, plain XLSX.

    Do not silently flatten chart-heavy, formula-driven or styled workbooks:
    those need a faithful office renderer rather than a plain HTML table.
    """
    from openpyxl import load_workbook
    import html

    book = load_workbook(source, read_only=False, data_only=False)
    try:
        sections = []
        cells = 0
        for sheet in book:
            if sheet._charts or sheet._images or len(sheet.merged_cells.ranges):
                raise ValueError("لا يمكن استخدام التصدير النصي البديل لجداول ذات رسوم أو خلايا مدمجة.")
            rows = []
            for row in sheet:
                cells += len(row)
                if cells > 2000:
                    raise ValueError("تعذر ضمان كامل محتوى الجدول الكبير في تصدير PDF البديل.")
                formatted = []
                for cell in row:
                    if cell.data_type == "f":
                        raise ValueError("تتطلب الصيغ الرياضية إخراج PDF مباشرًا يحفظ نتائجها.")
                    if cell.has_style and cell.style_id not in {0}:
                        raise ValueError("لا يمكن استبدال تنسيق الجدول المعقد بإخراج مبسط دون موافقة المستخدم.")
                    value = "" if cell.value is None else str(cell.value)
                    formatted.append("<td>" + html.escape(value).replace("\n", "<br/>") + "</td>")
                rows.append("<tr>" + "".join(formatted) + "</tr>")
            sections.append("<h2>" + html.escape(sheet.title) + "</h2><table border='1'>" +
                            "".join(rows) + "</table>")
        target = output_dir / f"{source.stem}-text-fidelity.html"
        target.write_text(
            '<!doctype html><html><head><meta charset="utf-8"></head><body>' +
            "".join(sections) + "</body></html>", encoding="utf-8"
        )
        return target
    finally:
        book.close()


def _render_simple_xlsx_paginated_fallback(prepared: Path, output: Path) -> None:
    """Render small plain worksheets in bounded table sections without lost rows.

    A single long HTML table can silently stop at the final page in PyMuPDF
    Story, even when the original source contains additional rows. Give each
    short section an independent Story and merge every resulting PDF page.
    The caller still checks *all* original source cell values afterwards.
    """
    import pymupdf

    source_html = prepared.read_text(encoding="utf-8")
    sections = re.findall(
        r"(<h2>.*?</h2>)<table border='1'>(.*?)</table>",
        source_html, flags=re.S,
    )
    if not sections or len(sections) != source_html.count("<table border='1'>"):
        raise ValueError("تعذر تقسيم صفحات جدول Excel دون فقدان بيانات.")

    temporary = output.with_name(output.stem + "-assembled.pdf")
    generated = []
    part_index = 0
    try:
        with pymupdf.open() as assembled:
            for title, body in sections:
                rows = re.findall(r"<tr>.*?</tr>", body, flags=re.S)
                if len(rows) != body.count("<tr>"):
                    raise ValueError("تعذر الحفاظ على جميع صفوف جدول Excel.")
                for start in range(0, len(rows), 20):
                    part_index += 1
                    part_html = output.with_name(
                        f"{output.stem}-sheet-part-{part_index:04d}.html"
                    )
                    part_pdf = part_html.with_suffix(".pdf")
                    generated.extend((part_html, part_pdf))
                    part_html.write_text(
                        '<!doctype html><html><head><meta charset="utf-8">'
                        '<style>table{border-collapse:collapse;width:100%}'
                        'td{padding:3px;overflow-wrap:anywhere}</style></head>'
                        '<body>' + title + "<table border='1'>" +
                        "".join(rows[start:start + 20]) + "</table></body></html>",
                        encoding="utf-8",
                    )
                    _render_html_story_fallback(part_html, part_pdf)
                    with pymupdf.open(part_pdf) as part:
                        if len(part) == 0:
                            raise ValueError("أنتج تصدير Excel صفحة PDF فارغة.")
                        assembled.insert_pdf(part)
            if len(assembled) == 0:
                raise ValueError("تعذر إخراج صفحات Excel إلى PDF.")
            assembled.save(temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
        for part in generated:
            part.unlink(missing_ok=True)


def _docx_pdf_bidi_spacing_copy(source: Path, output_dir: Path) -> Path:
    """Render-only DOCX copy preserving Arabic-number spaces in extracted PDF.

    LibreOffice sometimes drops ordinary U+0020 between RTL Arabic and an ASCII
    digit from its PDF Unicode map. Replacing only that boundary with U+00A0
    in the *private render copy* preserves the visible space and produces an
    extractable whitespace character; the uploaded original is never changed.
    Keep XML structure, all run styling, images and relationships byte-for-byte.
    """
    import zipfile

    if source.suffix.lower() != ".docx":
        return source

    text_node = re.compile(r"(<w:t\b[^>]*>)([^<]*)(</w:t>)")
    arabic_digit_space = re.compile(r"(?<=[\u0600-\u06FF]) (?=[0-9])")

    def protect_node(match: re.Match[str]) -> str:
        return (match.group(1)
                + arabic_digit_space.sub("\u00a0", match.group(2))
                + match.group(3))

    with zipfile.ZipFile(source) as original:
        changed_parts: dict[str, bytes] = {}
        for name in original.namelist():
            if not (name.startswith("word/") and name.endswith(".xml")):
                continue
            raw = original.read(name)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            updated = text_node.sub(protect_node, content)
            if updated != content:
                changed_parts[name] = updated.encode("utf-8")
        if not changed_parts:
            return source

        private = output_dir / f".lo-word-input-{uuid4().hex}"
        private.mkdir(mode=0o700)
        render_copy = private / source.name
        try:
            with zipfile.ZipFile(render_copy, "w") as copied:
                for member in original.infolist():
                    copied.writestr(member, changed_parts.get(
                        member.filename, original.read(member.filename)))
        except Exception:
            shutil.rmtree(private, ignore_errors=True)
            raise
        return render_copy


def office_to_pdf(source: Path, output_dir: Path, timeout: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    _reject_remote_html_resources(source)
    render_source = (
        _html_pdf_heading_fallback(source, output_dir)
        if source.suffix.lower() in {".html", ".htm"} else
        _docx_pdf_bidi_spacing_copy(source, output_dir)
    )
    private_docx_dir = (
        render_source.parent if render_source != source
        and source.suffix.lower() == ".docx" else None
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
        if private_docx_dir is not None:
            shutil.rmtree(private_docx_dir, ignore_errors=True)

    produced = output_dir / f"{render_source.stem}.pdf"
    if not produced.exists() or produced.stat().st_size == 0:
        raise RuntimeError("لم يُنتج LibreOffice ملف PDF صالحًا.")
    if source.suffix.lower() in {".html", ".htm"}:
        headings = _expected_html_headings(source)
        if headings and not _pdf_contains_headings(produced, headings):
            # Do not report a conversion as successful when the native renderer
            # dropped source headings. Render the *original* sanitized HTML via
            # a separate engine, then verify the real output content again.
            _render_html_story_fallback(source, produced)
            if not _pdf_contains_headings(produced, headings):
                raise ValueError("تعذر الحفاظ على عناوين HTML في ملف PDF الناتج.")
    elif source.suffix.lower() in {".txt", ".csv"} and source.stat().st_size <= 128 * 1024:
        fragments = _source_pdf_text_fragments(source)
        if fragments and not _pdf_has_text_fragments(produced, fragments):
            # Writer may silently omit Arabic text / split quoted CSV cells.
            # Re-render the escaped original with a Unicode-capable font.
            prepared = _printable_text_html(source, output_dir)
            _render_html_story_fallback(prepared, produced)
            if not _pdf_has_text_fragments(produced, fragments):
                raise ValueError("تعذر الحفاظ على كامل النص الأصلي في ملف PDF الناتج.")
    elif source.suffix.lower() == ".xlsx" and source.stat().st_size <= 128 * 1024:
        fragments = _xlsx_pdf_fragments(source)
        if fragments and not _pdf_has_text_fragments(produced, fragments):
            # Restrict this to simple, unstyled, formula-free workbooks. Do not
            # silently discard complex formatting or unsupported sheet objects.
            prepared = _printable_simple_xlsx_html(source, output_dir)
            _render_simple_xlsx_paginated_fallback(prepared, produced)
            if not _pdf_has_text_fragments(produced, fragments):
                raise ValueError("تعذر الحفاظ على جميع قيم خلايا Excel في ملف PDF الناتج.")
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
    # LibreOffice Writer/Web can collapse a Markdown table into extremely
    # narrow columns, especially when the first column is RTL. Give Writer an
    # explicit table width AND explicit per-column widths derived from the
    # source table's first row. This prevents short values such as 00123 from
    # being rendered one glyph per line while preserving ordinary wrapping.
    def _printable_table_block(match):
        attributes, inner = match.group(1), match.group(2)
        if not re.search(r"\bwidth\s*=", attributes, flags=re.I):
            attributes = ' width="100%"' + attributes
        first_row = re.search(r"<tr\b[^>]*>(.*?)</tr>", inner, flags=re.I | re.S)
        column_count = 0
        if first_row:
            column_count = len(re.findall(r"<(?:th|td)\b", first_row.group(1), flags=re.I))
        colgroup = ""
        if column_count:
            share = 100 / column_count
            colgroup = "<colgroup>" + "".join(
                f'<col width="{share:.3f}%">' for _ in range(column_count)
            ) + "</colgroup>"
        return "<table" + attributes + ">" + colgroup + inner + "</table>"

    body = re.sub(
        r"<table\b([^>]*)>(.*?)</table>",
        _printable_table_block,
        body,
        flags=re.I | re.S,
    )
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>body{font-family:sans-serif;max-width:800px;margin:40px auto;line-height:1.6}"
        "table{border-collapse:collapse;width:100%;table-layout:fixed}"
        "td,th{border:1px solid #ccc;padding:6px;white-space:normal;word-break:normal}</style>"
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

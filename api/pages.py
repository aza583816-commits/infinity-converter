from pathlib import Path

from flask import Blueprint, abort, make_response, redirect, render_template, request, send_file
from core.tool_registry import TOOLS, TOOL_META, get_tool, list_tools, related_tools, tool_url
from i18n import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES
from i18n.translations import INFO_CONTENT

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/manifest.json")
def manifest():
    return send_file(Path(__file__).parent.parent / "manifest.json", mimetype="application/manifest+json")


@pages_bp.get("/set-language/<lang>")
def set_language(lang):
    if lang not in SUPPORTED_LANGUAGES:
        abort(404)
    target = request.referrer or "/"
    response = redirect(target)
    response.set_cookie(LANGUAGE_COOKIE, lang, max_age=31536000, samesite="Lax")
    return response

@pages_bp.get("/")
def home():
    return render_template("index.html", tools=list_tools())


@pages_bp.get("/tools")
def tools_page():
    return render_template("tools.html", tools=list_tools())


@pages_bp.get("/tool/<tool_id>")
def tool_page(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        abort(404)
    return render_template("tool.html", tool=tool, tools=list_tools(), related=related_tools(tool_id))


@pages_bp.get("/tools/<tool_slug>")
def tool_slug_page(tool_slug):
    for tool in TOOLS.values():
        if TOOL_META[tool.id]["slug"] == tool_slug:
            return render_template("tool.html", tool=tool, tools=list_tools(), related=related_tools(tool.id))
    abort(404)


@pages_bp.get("/<page_name>")
def info_page(page_name):
    if page_name not in INFO_CONTENT["ar"]:
        abort(404)
    return render_template(
        "info.html",
        page_name=page_name,
        tools=list_tools(),
    )


@pages_bp.get("/sitemap.xml")
def sitemap():
    urls = ["/", "/tools", "/about", "/contact", "/privacy", "/terms", "/cookies"]
    urls.extend(tool_url(get_tool(tool["id"])) for tool in list_tools())
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    body += (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    )
    for url in urls:
        base = f"https://infinityconverter.com{url}"
        body += f"<url><loc>{base}</loc>"
        for code in SUPPORTED_LANGUAGES:
            body += f'<xhtml:link rel="alternate" hreflang="{code}" href="{base}?lang={code}"/>'
        body += "</url>"
    body += "</urlset>"
    response = make_response(body)
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response

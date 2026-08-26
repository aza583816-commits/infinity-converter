from pathlib import Path

from flask import Blueprint, abort, make_response, render_template, send_file
from core.tool_registry import get_tool, list_tools

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/manifest.json")
def manifest():
    return send_file(Path(__file__).parent.parent / "manifest.json", mimetype="application/manifest+json")

@pages_bp.get("/")
def home():
    return render_template("index.html", tools=list_tools(), lang="ar")


@pages_bp.get("/tool/<tool_id>")
def tool_page(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        abort(404)
    return render_template("tool.html", tool=tool, tools=list_tools(), lang="ar")


INFO_PAGES = {
    "about": ("من نحن", "تعرف إلى Infinity Converter ونهجنا في بناء أدوات ملفات عملية وواضحة."),
    "contact": ("تواصل معنا", "نستقبل ملاحظاتك وتقارير المشكلات المتعلقة بأدوات Infinity Converter."),
    "privacy": ("سياسة الخصوصية", "توضح هذه السياسة كيف نتعامل مع الملفات والبيانات أثناء استخدام المنصة."),
    "terms": ("الشروط والأحكام", "تحدد هذه الشروط قواعد الاستخدام المسؤول لخدمات Infinity Converter."),
    "cookies": ("سياسة ملفات تعريف الارتباط", "تشرح هذه الصفحة أنواع ملفات تعريف الارتباط التي قد يستخدمها الموقع."),
}


@pages_bp.get("/<page_name>")
def info_page(page_name):
    if page_name not in INFO_PAGES:
        abort(404)
    title, description = INFO_PAGES[page_name]
    return render_template(
        "info.html",
        page_name=page_name,
        page_title=title,
        page_description=description,
        tools=list_tools(),
        lang="ar",
    )


@pages_bp.get("/sitemap.xml")
def sitemap():
    urls = ["/", "/about", "/contact", "/privacy", "/terms", "/cookies"]
    urls.extend(f"/tool/{tool['id']}" for tool in list_tools())
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    body += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    body += "".join(f"<url><loc>https://infinityconverter.com{url}</loc></url>" for url in urls)
    body += "</urlset>"
    response = make_response(body)
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response

import os
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, send_file
from config.settings import settings
from core.accounts import EmailAlreadyExistsError, authenticate, create_user, csrf_token, get_effective_plan, get_latest_subscription_for_user, login_required, login_user, logout_user, valid_email, verify_csrf
from core.browser_tools import BROWSER_TOOLS, browser_collection_tools, get_browser_tool
from core.tool_registry import AUDIENCE_COLLECTIONS, DEVELOPER_TOOLS, TOOLS, TOOL_META, collection_tools, get_developer_tool, get_tool, list_tools, popular_tools, related_tools, tool_url, _meta_for
from i18n import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES
from i18n.translations import INFO_CONTENT
from core.blog import BLOG_BY_SLUG, BLOG_POSTS

pages_bp = Blueprint("pages", __name__)


def _auth_post_is_valid() -> bool:
    return verify_csrf(request.form.get("csrf_token"))


def _auth_public():
    return bool(current_app.config.get("PUBLIC_AUTH_ENABLED", False))


def _billing_public():
    return bool(current_app.config.get("PUBLIC_BILLING_ENABLED", False))


@pages_bp.route("/register", methods=["GET", "POST"])
def register():
    if not _auth_public():
        abort(404)
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if not _auth_post_is_valid():
            abort(400)
        if not valid_email(email) or len(password) < 12:
            flash("auth.register_invalid")
        else:
            try:
                user = create_user(email, password)
            except EmailAlreadyExistsError:
                flash("auth.register_exists")
            else:
                login_user(user)
                return redirect("/account")
    return render_template("auth.html", mode="register", csrf_token=csrf_token())


@pages_bp.route("/login", methods=["GET", "POST"])
def login():
    if not _auth_public():
        abort(404)
    if request.method == "POST":
        if not _auth_post_is_valid():
            abort(400)
        user = authenticate(request.form.get("email", ""), request.form.get("password", ""))
        if user:
            login_user(user)
            return redirect("/account")
        flash("auth.login_invalid")
    return render_template("auth.html", mode="login", csrf_token=csrf_token())


@pages_bp.post("/logout")
@login_required
def logout():
    if not _auth_public():
        abort(404)
    if not _auth_post_is_valid():
        abort(400)
    logout_user()
    return redirect("/")


@pages_bp.get("/account")
@login_required
def account():
    if not _auth_public():
        abort(404)
    return render_template("account.html", user=g.current_user, plan=get_effective_plan(g.current_user["id"]), subscription=get_latest_subscription_for_user(g.current_user["id"]))


@pages_bp.get("/manifest.json")
def manifest():
    return send_file(Path(__file__).parent.parent / "manifest.json", mimetype="application/manifest+json")



@pages_bp.get("/ads.txt")
def ads_txt():
    """Serve a valid AdSense ads.txt line only after a real publisher ID is configured."""
    publisher_id = os.getenv("ADSENSE_CLIENT_ID", "").strip()
    if not publisher_id.startswith("ca-pub-"):
        abort(404)
    response = make_response(f"google.com, {publisher_id[3:]}, DIRECT, f08c47fec0942fa0\n")
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response

@pages_bp.get("/set-language/<lang>")
def set_language(lang):
    if lang not in SUPPORTED_LANGUAGES:
        abort(404)
    target = request.referrer or "/"
    response = redirect(target)
    response.set_cookie(LANGUAGE_COOKIE, lang, max_age=31536000, samesite="Lax", secure=request.is_secure)
    return response

@pages_bp.get("/")
def home():
    return render_template("index.html", tools=popular_tools(), tool_count=len(TOOLS), collections=AUDIENCE_COLLECTIONS)


@pages_bp.get("/pricing")
def pricing_page():
    if not _billing_public():
        abort(404)
    return render_template(
        "pricing.html",
        tools=list_tools(),
        paddle_client_token=os.getenv("PADDLE_CLIENT_TOKEN", ""),
        checkout_user=getattr(g, "current_user", None),
    )


@pages_bp.get("/tools")
def tools_page():
    return render_template("tools.html", tools=list_tools())


@pages_bp.get("/how-it-works")
def how_it_works_page():
    return render_template("how_it_works.html")

@pages_bp.get("/blog")
def blog_page():
    return render_template("blog.html", posts=BLOG_POSTS)


@pages_bp.get("/blog/<slug>")
def blog_post_page(slug):
    post = BLOG_BY_SLUG.get(slug)
    if not post:
        abort(404)
    related = [item for item in BLOG_POSTS if item["slug"] != slug and item["category_en"] == post["category_en"]][:3]
    if len(related) < 3:
        related.extend(item for item in BLOG_POSTS if item["slug"] != slug and item not in related)
        related = related[:3]
    return render_template("blog_post.html", post=post, related=related)


@pages_bp.get("/collections/<collection_id>")
def collection_page(collection_id):
    result = collection_tools(collection_id)
    if not result:
        abort(404)
    collection, tools = result
    developer_tools = DEVELOPER_TOOLS if collection_id == "developers" else {}
    return render_template("collection.html", collection=collection, tools=tools, browser_tools=browser_collection_tools(collection_id), developer_tools=developer_tools, collections=AUDIENCE_COLLECTIONS)


@pages_bp.get("/browser-tools/<tool_id>")
def browser_tool_page(tool_id):
    tool = get_browser_tool(tool_id)
    if not tool:
        abort(404)
    return render_template("browser_tool.html", tool=tool)


@pages_bp.get("/developer-tools/<tool_id>")
def developer_tool_page(tool_id):
    tool = get_developer_tool(tool_id)
    if not tool:
        abort(404)
    return render_template("developer_tool.html", tool=tool, tool_id=tool_id)


@pages_bp.get("/tool/<tool_id>")
def tool_page(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        abort(404)
    target = tool_url(tool)
    if request.query_string:
        target = f"{target}?{request.query_string.decode('utf-8', errors='ignore')}"
    return redirect(target, code=301)


@pages_bp.get("/tools/<tool_slug>")
def tool_slug_page(tool_slug):
    for tool in TOOLS.values():
        if _meta_for(tool)["slug"] == tool_slug:
            return render_template("tool.html", tool=tool, tool_slug=_meta_for(tool)["slug"], tools=list_tools(), related=related_tools(tool.id))
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
    urls = ["/", "/tools", "/blog", "/how-it-works", "/about", "/contact", "/privacy", "/terms", "/cookies"]
    if _billing_public():
        urls.insert(2, "/pricing")
    urls.extend(f"/blog/{post['slug']}" for post in BLOG_POSTS)
    urls.extend(f"/collections/{collection_id}" for collection_id in AUDIENCE_COLLECTIONS)
    urls.extend(f"/developer-tools/{tool_id}" for tool_id in DEVELOPER_TOOLS)
    urls.extend(f"/browser-tools/{tool.id}" for tool in BROWSER_TOOLS)
    urls.extend(tool_url(get_tool(tool["id"])) for tool in list_tools())
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    body += (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    )
    for url in urls:
        base = f"{settings.public_base_url}{url}"
        body += f"<url><loc>{base}</loc>"
        for code in SUPPORTED_LANGUAGES:
            body += f'<xhtml:link rel="alternate" hreflang="{code}" href="{base}?lang={code}"/>'
        body += "</url>"
    body += "</urlset>"
    response = make_response(body)
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response

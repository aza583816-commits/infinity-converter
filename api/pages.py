import os
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, send_file
from config.settings import adsense_publisher_id, settings
from core.accounts import EmailAlreadyExistsError, authenticate, create_user, csrf_token, get_effective_plan, get_latest_subscription_for_user, login_required, login_user, logout_user, valid_email, verify_csrf
from core.browser_tools import BROWSER_TOOLS, browser_collection_tools, get_browser_tool
from core.tooling import AUDIENCE_COLLECTIONS, DEVELOPER_TOOLS, TOOLS, TOOL_META, collection_tools, get_developer_tool, get_tool, list_tools, popular_tools, related_tools, tool_url, _meta_for
from i18n import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES
from i18n.translations import INFO_CONTENT
from core.blog import BLOG_BY_SLUG, BLOG_POSTS
from core.editorial import get_tool_editorial, reviewed_tool_ids

pages_bp = Blueprint("pages", __name__)


# Old top-level URLs from the pre-6.x site still appear in search indexes.
# Redirect them to the closest current workflow instead of leaving dead ends.
LEGACY_TOP_LEVEL_ALIASES = {
    "percentage-calc": "/collections/everyday",
    "base64-tool": "/developer-tools/base64",
    "summarize-doc": "/blog",
    "html-entity": "/browser-tools/html-entity-converter",
    "arabic-proofreader": "/collections/students",
    "text-to-qr": "/collections/everyday",
    "text-to-csv": "/tools?category=office",
    "text-to-excel": "/tools?category=office",
    "json-beautifier": "/developer-tools/json-formatter",
    "pdf-to-excel": "/tools?category=office",
    "pdf-to-pdf": "/tools?category=pdf",
    "protect-pdf": "/tools/pdf-password-protect",
    "unlock-pdf": "/tools/pdf-unlock",
    "sign-pdf": "/tools?category=pdf",
    "pdf-to-images": "/tools/pdf-to-jpg",
    "image-to-pdf": "/tools/jpg-to-pdf",
    "image-to-text": "/tools/image-ocr",
    "clean-text": "/browser-tools/text-cleaner",
}


def _auth_post_is_valid() -> bool:
    return verify_csrf(request.form.get("csrf_token"))


def _auth_public():
    return bool(current_app.config.get("PUBLIC_AUTH_ENABLED", False))


def _billing_public():
    return bool(current_app.config.get("PUBLIC_BILLING_ENABLED", False))


def _quality_tool_paths() -> set[str]:
    """Return only manually reviewed, content-rich tool pages for indexing.

    The public catalog remains fully usable, but search engines and AdSense are
    intentionally pointed at a smaller set of pages that have tool-specific
    editorial guidance reviewed against the real conversion implementation.
    """
    paths: set[str] = set()
    for tool_id in reviewed_tool_ids():
        tool = get_tool(tool_id)
        if tool:
            paths.add(tool_url(tool))
    return paths


def _guides_for_tool(tool, tool_path: str, limit: int = 3) -> list[dict]:
    """Attach manually reviewed editorial guides to relevant converter pages."""
    exact = [post for post in BLOG_POSTS if post.get("tool") == tool_path]
    category_map = {
        "pdf": "PDF",
        "images": "Images",
        "office": "Documents",
        "ocr": "OCR",
        "archive": "Archives",
    }
    candidates = list(exact)
    article_category = category_map.get(tool.category)
    if article_category:
        candidates.extend(
            post for post in BLOG_POSTS
            if post.get("category_en") == article_category and post not in candidates
        )
    return candidates[:limit]


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
    return render_template("auth.html", mode="register", csrf_token=csrf_token(), page_noindex=True)


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
    return render_template("auth.html", mode="login", csrf_token=csrf_token(), page_noindex=True)


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
    return render_template(
        "account.html",
        csrf_token=csrf_token(),
        user=g.current_user,
        plan=get_effective_plan(g.current_user["id"]),
        subscription=get_latest_subscription_for_user(g.current_user["id"]),
        page_noindex=True,
    )


@pages_bp.get("/manifest.json")
def manifest():
    return send_file(Path(__file__).parent.parent / "manifest.json", mimetype="application/manifest+json")


@pages_bp.get("/sw.js")
def service_worker():
    response = send_file(Path(__file__).parent.parent / "static" / "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@pages_bp.get("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /login\n"
        "Disallow: /register\n"
        "Disallow: /account\n"
        "Disallow: /set-language/\n"
        f"Sitemap: {settings.public_base_url}/sitemap.xml\n"
    )
    response = make_response(body)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@pages_bp.get("/ads.txt")
def ads_txt():
    """Serve a valid AdSense ads.txt line only after a real publisher ID is configured."""
    publisher_id = adsense_publisher_id()
    if not publisher_id:
        abort(404)
    response = make_response(f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0\n")
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
    return render_template(
        "index.html",
        tools=popular_tools(),
        tool_count=len(TOOLS),
        collections=AUDIENCE_COLLECTIONS,
        featured_guides=BLOG_POSTS[:6],
        reviewed_count=len(reviewed_tool_ids()),
        guide_count=len(BLOG_POSTS),
    )


@pages_bp.get("/assistant")
def assistant_page():
    return render_template("assistant.html", page_noindex=True)


@pages_bp.get("/pricing")
def pricing_page():
    if not _billing_public():
        abort(404)
    return render_template(
        "pricing.html",
        tools=list_tools(),
        paddle_client_token=os.getenv("PADDLE_CLIENT_TOKEN", ""),
        checkout_user=getattr(g, "current_user", None),
        page_noindex=True,
    )


@pages_bp.get("/tools")
def tools_page():
    tools = list_tools()
    allowed_filters = {"all", "pdf", "images", "office", "ocr", "archive", "utilities", "popular"}
    requested_filter = (request.args.get("category") or "all").strip().lower()
    active_filter = requested_filter if requested_filter in allowed_filters else "all"
    visible_count = sum(
        1 for tool in tools
        if active_filter == "all"
        or (active_filter == "popular" and tool["popular"])
        or tool["category"] == active_filter
    )
    return render_template(
        "tools.html",
        tools=tools,
        active_filter=active_filter,
        visible_count=visible_count,
    )


@pages_bp.get("/how-it-works")
def how_it_works_page():
    return render_template("how_it_works.html")


@pages_bp.get("/blog")
def blog_page():
    query = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    posts = list(BLOG_POSTS)
    if query:
        needle = query.casefold()

        def searchable(post):
            parts = [
                post.get("title_ar", ""), post.get("title_en", ""),
                post.get("description_ar", ""), post.get("description_en", ""),
                post.get("category_ar", ""), post.get("category_en", ""),
            ]
            parts.extend(text for pair in post.get("sections", []) for text in pair)
            parts.extend(post.get("section_en", []))
            parts.extend(post.get("paragraph_en", []))
            return needle in " ".join(parts).casefold()

        posts = [post for post in posts if searchable(post)]
    if category:
        category_folded = category.casefold()
        posts = [post for post in posts if category_folded in {post.get("category_ar", "").casefold(), post.get("category_en", "").casefold()}]
    categories = []
    seen = set()
    for post in BLOG_POSTS:
        key = (post["category_ar"], post["category_en"])
        if key not in seen:
            seen.add(key)
            categories.append({"ar": key[0], "en": key[1]})
    return render_template("blog.html", posts=posts, categories=categories, query=query, selected_category=category)


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
    return render_template(
        "collection.html",
        collection=collection,
        tools=tools,
        browser_tools=browser_collection_tools(collection_id),
        developer_tools=developer_tools,
        collections=AUDIENCE_COLLECTIONS,
        page_noindex=True,
    )


@pages_bp.get("/browser-tools/<tool_id>")
def browser_tool_page(tool_id):
    tool = get_browser_tool(tool_id)
    if not tool:
        abort(404)
    return render_template("browser_tool.html", tool=tool, page_noindex=True)


@pages_bp.get("/developer-tools/<tool_id>")
def developer_tool_page(tool_id):
    tool = get_developer_tool(tool_id)
    if not tool:
        abort(404)
    return render_template("developer_tool.html", tool=tool, tool_id=tool_id, page_noindex=True)


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
    indexable_paths = _quality_tool_paths()
    for tool in TOOLS.values():
        slug = _meta_for(tool)["slug"]
        if slug == tool_slug:
            path = f"/tools/{slug}"
            editorial = get_tool_editorial(tool.id)
            return render_template(
                "tool.html",
                tool=tool,
                tool_slug=slug,
                tools=list_tools(),
                related=related_tools(tool.id),
                matching_guides=_guides_for_tool(tool, path),
                editorial=editorial,
                page_noindex=path not in indexable_paths,
            )
    abort(404)


@pages_bp.get("/<legacy_type>/<from_unit>/<to_unit>/<value>")
@pages_bp.get("/<legacy_type>/<from_unit>/<to_unit>/<value>/")
def legacy_unit_redirect(legacy_type, from_unit, to_unit, value):
    """Redirect legacy converter URLs still present in older search indexes."""
    if legacy_type in {"length", "weight"}:
        return redirect("/browser-tools/unit-converter", code=301)
    if legacy_type in {"volume", "area", "time"}:
        return redirect("/collections/everyday", code=301)
    abort(404)


@pages_bp.get("/<page_name>")
def info_page(page_name):
    if page_name in INFO_CONTENT["ar"]:
        return render_template(
            "info.html",
            page_name=page_name,
            tools=list_tools(),
        )

    # Preserve old one-segment tool URLs with permanent redirects. A large
    # number of these URLs were indexed before the canonical /tools/<slug>
    # structure shipped, so returning a useful 301 is better for both users
    # and crawlers than a blanket 404.
    direct_tool = get_tool(page_name)
    if direct_tool:
        return redirect(tool_url(direct_tool), code=301)
    for candidate in TOOLS.values():
        if _meta_for(candidate)["slug"] == page_name:
            return redirect(tool_url(candidate), code=301)

    if get_browser_tool(page_name):
        return redirect(f"/browser-tools/{page_name}", code=301)
    if get_developer_tool(page_name):
        return redirect(f"/developer-tools/{page_name}", code=301)

    target = LEGACY_TOP_LEVEL_ALIASES.get(page_name)
    if target:
        return redirect(target, code=301)
    abort(404)


@pages_bp.get("/sitemap.xml")
def sitemap():
    urls = ["/", "/tools", "/blog", "/how-it-works", "/about", "/trust", "/editorial", "/contact", "/privacy", "/terms", "/cookies"]
    urls.extend(f"/blog/{post['slug']}" for post in BLOG_POSTS)
    urls.extend(sorted(_quality_tool_paths()))
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    body += (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    )
    for url in urls:
        base = f"{settings.public_base_url}{url}"
        ar_url = f"{base}?lang=ar"
        en_url = f"{base}?lang=en"
        alternates = (
            f'<xhtml:link rel="alternate" hreflang="ar" href="{ar_url}"/>'
            f'<xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>'
            f'<xhtml:link rel="alternate" hreflang="x-default" href="{base}"/>'
        )
        for canonical_url in (ar_url, en_url):
            body += f"<url><loc>{canonical_url}</loc><lastmod>2026-09-16</lastmod>"
            body += alternates
            body += "</url>"
    body += "</urlset>"
    response = make_response(body)
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    return response

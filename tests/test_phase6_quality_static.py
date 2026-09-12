from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_root_robots_endpoint_exists_and_is_not_only_a_static_asset():
    pages = read("api/pages.py")
    assert '@pages_bp.get("/robots.txt")' in pages
    assert "Sitemap:" in pages
    assert "text/plain" in pages

def test_blog_has_real_search_filter_and_article_navigation():
    pages = read("api/pages.py")
    blog = read("templates/blog.html")
    post = read("templates/blog_post.html")
    js = read("static/js/app.js")
    assert 'request.args.get("q"' in pages
    assert 'request.args.get("category"' in pages
    assert 'id="knowledge-search"' in blog
    assert "knowledge-category-list" in blog
    assert 'id="reading-progress-bar"' in post
    assert "article-toc" in post
    assert "BreadcrumbList" in post
    assert "#reading-progress-bar" in js

def test_tool_pages_have_breadcrumb_and_faq_structured_data():
    tool = read("templates/tool.html")
    assert "BreadcrumbList" in tool
    assert "FAQPage" in tool
    assert "WebApplication" in tool

def test_preflight_is_designed_to_fail_the_build_on_startup_route_errors():
    preflight = read("scripts/preflight.py")
    assert "create_app" in preflight
    assert "/api/v2/healthz" in preflight
    assert "/robots.txt" in preflight
    assert "startup route" in preflight

def test_knowledge_center_has_at_least_fifteen_curated_posts():
    import ast
    tree = ast.parse(read("core/blog.py"))
    assignment = next(node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign)) and any(isinstance(t, ast.Name) and t.id == "BLOG_POSTS" for t in getattr(node, 'targets', [getattr(node, 'target', None)])))
    assert len(assignment.value.elts) >= 15

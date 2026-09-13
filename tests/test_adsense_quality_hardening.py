from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_homepage_has_no_under_construction_roadmap():
    home = read("templates/index.html")
    assert 'class="section-block roadmap"' not in home
    assert "featured_guides" in home
    assert "home-knowledge-title" in home


def test_adsense_loader_is_limited_to_content_pages():
    base = read("templates/base.html")
    assert "adsense_content_page" in base
    assert "not noindex_page" in base
    assert "google-adsense-account" in base


def test_thin_surfaces_are_noindex_and_not_in_sitemap():
    pages = read("api/pages.py")
    assert 'page_noindex=True' in pages
    assert 'urls.extend(f"/developer-tools/' not in pages
    assert 'urls.extend(f"/browser-tools/' not in pages
    assert "_quality_tool_paths()" in pages


def test_legacy_unit_urls_have_useful_redirects():
    pages = read("api/pages.py")
    assert "def legacy_unit_redirect" in pages
    assert 'redirect("/browser-tools/unit-converter", code=301)' in pages


def test_language_canonicals_match_hreflang_strategy():
    base = read("templates/base.html")
    pages = read("api/pages.py")
    assert "canonical_suffix" in base
    assert 'hreflang="ar"' in base
    assert 'hreflang="en"' in base
    assert "?lang=en" in pages


def test_knowledge_articles_have_substantial_bilingual_depth_and_unique_slugs():
    import re
    from core.blog import BLOG_POSTS

    assert len(BLOG_POSTS) >= 15
    assert len({post["slug"] for post in BLOG_POSTS}) == len(BLOG_POSTS)
    for post in BLOG_POSTS:
        assert len(post["sections"]) >= 6
        assert len(post["sections"]) == len(post["section_en"]) == len(post["paragraph_en"])
        arabic = " ".join([post["title_ar"], post["description_ar"]] + [text for pair in post["sections"] for text in pair])
        english = " ".join([post["title_en"], post["description_en"]] + post["section_en"] + post["paragraph_en"])
        assert len(re.findall(r"\S+", arabic)) >= 230
        assert len(re.findall(r"\S+", english)) >= 280


def test_every_article_tool_link_resolves_to_registered_tool_or_tools_index():
    from core.blog import BLOG_POSTS
    from core.tool_registry import TOOLS, _meta_for

    registered = {f"/tools/{_meta_for(tool)['slug']}" for tool in TOOLS.values()}
    for post in BLOG_POSTS:
        target = post.get("tool", "")
        assert target == "/tools" or target in registered


def test_legacy_top_level_indexed_urls_have_redirect_strategy():
    pages = read("api/pages.py")
    assert "LEGACY_TOP_LEVEL_ALIASES" in pages
    for old_path in ("percentage-calc", "base64-tool", "html-entity", "arabic-proofreader", "text-to-qr", "json-beautifier", "pdf-to-pdf"):
        assert f'"{old_path}"' in pages
    assert "direct_tool = get_tool(page_name)" in pages
    assert '_meta_for(candidate)["slug"] == page_name' in pages


def test_manual_ad_slots_are_also_blocked_on_noindex_pages():
    for rel, slot in (("templates/tool.html", "adsense_slot_tool"), ("templates/blog_post.html", "adsense_slot_article"), ("templates/index.html", "adsense_slot_home")):
        template = read(rel)
        assert f"adsense_client_id and {slot} and not noindex_page" in template

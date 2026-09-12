from pathlib import Path

from core.editorial import TOOL_EDITORIAL, reviewed_tool_ids
from core.tool_registry import TOOLS, _meta_for

ROOT = Path(__file__).resolve().parents[1]


def _read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_release_version_and_new_support_email_are_consistent():
    assert '"version": "6.1.2"' in _read("manifest.json")
    assert '"6.1.2"' in _read("config/settings.py")
    corpus = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in {".py", ".html", ".md", ".js", ".css", ".json"}
        and "__pycache__" not in p.parts
    )
    assert "v.infinityconverter@gmail.com" in corpus
    assert ("2saree3.tech" + "@gmail.com") not in corpus


def test_reviewed_tool_surface_is_small_real_and_fully_editorialized():
    assert len(TOOL_EDITORIAL) == 21
    assert reviewed_tool_ids() == set(TOOL_EDITORIAL)
    required = {
        "processing", "engine_ar", "engine_en", "sample_urls", "sample_names",
        "best_for_ar", "best_for_en", "how_ar", "how_en", "limits_ar",
        "limits_en", "check_ar", "check_en", "faq_ar", "faq_en",
    }
    for tool_id, editorial in TOOL_EDITORIAL.items():
        assert tool_id in TOOLS
        assert required <= set(editorial)
        assert editorial["processing"] == "server_local"
        assert len(editorial["sample_urls"]) == len(editorial["sample_names"]) >= 1
        assert len(editorial["faq_ar"]) >= 2
        assert len(editorial["faq_en"]) >= 2
        # Guard against collapsing reviewed pages back to one-line templated copy.
        ar_words = sum(len(str(editorial[key]).split()) for key in ("best_for_ar", "how_ar", "limits_ar", "check_ar"))
        en_words = sum(len(str(editorial[key]).split()) for key in ("best_for_en", "how_en", "limits_en", "check_en"))
        assert ar_words >= 70, (tool_id, ar_words)
        assert en_words >= 80, (tool_id, en_words)
        for url, name in zip(editorial["sample_urls"], editorial["sample_names"]):
            sample = ROOT / url.lstrip("/")
            assert sample.exists(), (tool_id, url)
            assert sample.name == name
            assert sample.stat().st_size > 0
            tool = TOOLS[tool_id]
            if tool.input_required and ".*" not in tool.input_ext and "*" not in tool.input_ext:
                assert sample.suffix.lower() in tool.input_ext, (tool_id, sample.suffix, tool.input_ext)


def test_sample_demo_values_cover_required_empty_inputs():
    for tool_id, editorial in TOOL_EDITORIAL.items():
        tool = TOOLS[tool_id]
        sample_options = editorial.get("sample_options", {})
        sample_param = editorial.get("sample_param", tool.param_default or "")
        if tool.param_field and not tool.param_default:
            assert sample_param, tool_id
        for field in tool.fields:
            if field.required and not field.default:
                assert sample_options.get(field.id), (tool_id, field.id)


def test_language_switch_uses_crawlable_query_urls_and_hreflang():
    base = _read("templates/base.html")
    assert "?lang=en" in base
    assert 'rel="alternate" hreflang="ar"' in base
    assert 'rel="alternate" hreflang="en"' in base
    assert 'rel="alternate" hreflang="x-default"' in base
    # The visible language switch must not rely on the cookie-setting endpoint.
    visible_nav = base.split('<header class="site-header">', 1)[1]
    assert "/set-language/" not in visible_nav


def test_adsense_loader_and_manual_units_stay_off_noindex_surfaces():
    base = _read("templates/base.html")
    tool = _read("templates/tool.html")
    index = _read("templates/index.html")
    article = _read("templates/blog_post.html")
    assert "not noindex_page" in base
    assert "request.path.startswith('/tools/')" in base
    assert "request.path.startswith('/blog/')" in base
    assert "adsense_slot_tool and not noindex_page" in tool
    assert "adsense_slot_home and not noindex_page" in index
    assert "adsense_slot_article and not noindex_page" in article


def test_trust_editorial_pwa_and_premium_experience_are_wired():
    pages = _read("api/pages.py")
    base = _read("templates/base.html")
    index = _read("templates/index.html")
    tool = _read("templates/tool.html")
    js = _read("static/js/app.js")
    sw = _read("static/sw.js")
    css = _read("static/css/app.css")
    assert '"/trust"' in pages and '"/editorial"' in pages
    assert '@pages_bp.get("/sw.js")' in pages
    assert "INFINITY QUICK JUMP" in base
    assert "SMART FILE ROUTER" in index
    assert "INFINITY FLOW" in index
    assert "PROCESSING TRANSPARENCY" in tool
    assert "Try safe sample" in tool
    assert "result-metrics" in tool
    assert "serviceWorker.register('/sw.js'" in js
    assert "infinity-static-v6.1.2" in sw
    assert "url.pathname.startsWith('/static/') || url.pathname === '/manifest.json'" in sw
    assert "Infinity Converter 6.1.2 — Quiet Luxury / Living Interface" in css
    assert "prefers-reduced-motion:reduce" in css


def test_sitemap_is_quality_first_not_all_tools():
    pages = _read("api/pages.py")
    assert "for tool_id in reviewed_tool_ids()" in pages
    assert "urls.extend(sorted(_quality_tool_paths()))" in pages
    # Quality pages are indexable publisher-content destinations.
    assert '"/trust"' in pages and '"/editorial"' in pages
    # Make sure every reviewed page has a real canonical slug.
    slugs = {_meta_for(TOOLS[tool_id])["slug"] for tool_id in reviewed_tool_ids()}
    assert len(slugs) == 21


def test_no_public_construction_language_in_templates():
    text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "templates").glob("*.html"))
    banned = ["Coming Soon", "Under Construction", "قيد البناء", "قريبًا"]
    for phrase in banned:
        assert phrase not in text

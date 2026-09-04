from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_how_it_works_and_error_pages_exist():
    assert (ROOT / "templates/how_it_works.html").exists()
    assert (ROOT / "templates/error.html").exists()
    pages = (ROOT / "api/pages.py").read_text()
    assert '"/how-it-works"' in pages

def test_premium_motion_hooks_exist():
    css = (ROOT / "static/css/app.css").read_text()
    js = (ROOT / "static/js/app.js").read_text()
    assert ".tool-workflow-strip" in css
    assert ".how-hero" in css
    assert "reveal-on-scroll" in js
    assert "safeStorageArray" in js

def test_core_navigation_targets_are_declared():
    base = (ROOT / "templates/base.html").read_text()
    assert 'href="/tools"' in base
    assert 'href="/blog"' in base
    assert 'href="/how-it-works"' in base
    assert 'href="/privacy"' in base

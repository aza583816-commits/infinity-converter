from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_hidden_attribute_is_a_cross_browser_state_contract():
    css = re.sub(r"\s+", "", read("static/css/app.css"))
    assert "[hidden]{display:none!important}" in css


def test_theme_storage_failure_cannot_abort_all_ui_handlers():
    js = read("static/js/app.js")
    assert "try { return localStorage.getItem('infinity-theme'); } catch (_) { return null; }" in js
    assert "try { localStorage.setItem('infinity-theme', theme); } catch (_) {}" in js
    assert "persistTheme(theme);" in js


def test_tool_filter_state_is_validated_and_exposed_accessibly():
    js = read("static/js/app.js")
    assert "const validFilters = new Set" in js
    assert "if (!validFilters.has(selectedFilter))" in js
    assert 'item.setAttribute("aria-pressed", String(active));' in js
    assert js.count("syncFilterTabs();") >= 2


def test_722_cache_bust_is_consistent():
    from config.settings import settings

    manifest = json.loads(read("manifest.json"))
    service_worker = read("static/sw.js")
    env_example = read(".env.example")

    assert settings.app_version == "7.2.2"
    assert manifest["version"] == settings.app_version
    assert f"infinity-static-v{settings.app_version}" in service_worker
    assert service_worker.count(f"?v={settings.app_version}") == 5
    assert f"APP_VERSION={settings.app_version}" in env_example

import re
from pathlib import Path

from app_factory import create_app
from core.tooling import list_tools


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _tool_card_tags(html: str) -> list[str]:
    return re.findall(r'<a class="tool-card"[^>]+>', html)


def test_hidden_attribute_is_an_author_level_state_contract():
    css = read("static/css/app.css")
    rule = "html [hidden]{display:none!important}"
    assert rule in css
    assert css.rfind(rule) > css.rfind(".v7-tool-card")
    assert css.rfind(rule) > css.rfind(".result-panel")


def test_tools_filter_has_safe_storage_and_accessible_state_sync():
    javascript = read("static/js/app.js")
    assert "function storageGet(key)" in javascript
    assert "function storageSet(key, value)" in javascript
    assert "function storageRemove(key)" in javascript
    assert "const validFilters = new Set" in javascript
    assert 'tab.setAttribute("aria-current", "true")' in javascript
    assert 'card.hidden = !text.includes(query) || !matchesFilter' in javascript
    assert 'history.replaceState(null, "", tab.href)' in javascript
    reset_block = javascript.split('$("#reset-tool")?.addEventListener', 1)[1].split("});", 1)[0]
    assert "releaseResult();" in reset_block
    assert "window.setTimeout(() => input.focus(), 30)" in javascript
    assert "window.setTimeout(() => lastTrigger?.focus(), 0)" in javascript


def test_tools_category_is_rendered_progressively_without_javascript():
    client = create_app().test_client()
    response = client.get("/tools?lang=ar&category=archive")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-active-filter="archive"' in html
    assert 'data-filter="archive"' in html
    assert 'aria-current="true"' in html

    tags = _tool_card_tags(html)
    assert len(tags) == len(list_tools()) == 162
    visible = [tag for tag in tags if " hidden" not in tag]
    assert visible
    assert all('data-category="archive"' in tag for tag in visible)
    assert f'id="listing-visible-count">{len(visible)}</strong>' in html


def test_invalid_tools_category_falls_back_to_all():
    html = create_app().test_client().get(
        "/tools?lang=en&category=not-a-real-category"
    ).get_data(as_text=True)
    assert 'data-active-filter="all"' in html
    tags = _tool_card_tags(html)
    assert len(tags) == 162
    assert all(" hidden" not in tag for tag in tags)


def test_800_version_and_worker_cache_are_consistent():
    from config.settings import settings

    assert settings.app_version == "8.0.0"
    assert 'APP_VERSION=8.0.0' in read('.env.example')
    assert '"version": "8.0.0"' in read('manifest.json')
    worker = read('static/sw.js')
    assert "infinity-static-v8.0.0" in worker
    for asset in (
        "/static/css/app.css?v=8.0.0",
        "/static/css/a11y.css?v=8.0.0",
        "/static/js/app.js?v=8.0.0",
        "/static/js/smart-flow.js?v=8.0.0",
    ):
        assert asset in worker

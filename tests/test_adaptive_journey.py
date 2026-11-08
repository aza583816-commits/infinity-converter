"""Stable contracts for the selected Adaptive Journey design."""
from html.parser import HTMLParser
from pathlib import Path
import pytest
from app_factory import create_app


class SurfaceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "img" and attrs.get("src", "").startswith("/static/icons/"):
            self.assets.append(attrs["src"])


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_journey_controls_are_unique_and_assets_are_available(lang):
    client = create_app().test_client()
    page = client.get(f"/?lang={lang}")
    assert page.status_code == 200
    parser = SurfaceParser()
    parser.feed(page.get_data(as_text=True))
    for control in ("ai-form", "ai-prompt", "ai-answer", "ai-status", "smart-drop",
                    "smart-file-input", "smart-file-summary", "smart-tool-results",
                    "journey-attach", "tool-search"):
        assert parser.ids.count(control) == 1
    assert b'data-surface="adaptive-journey"' in page.data
    assert len(parser.assets) >= 8
    for asset in set(parser.assets):
        response = client.get(asset)
        assert response.status_code == 200
        assert response.mimetype == "image/svg+xml"
    assert client.get("/static/images/adaptive-journey.webp").status_code == 200
    assert client.get("/static/fonts/cairo.ttf").status_code == 200


def test_home_styles_do_not_load_on_conversion_pages():
    page = create_app().test_client().get("/tools/pdf-to-docx?lang=en")
    assert page.status_code == 200
    assert b"adaptive-journey.css" not in page.data


def test_empty_prompt_has_feedback_and_file_router_remains_local():
    script = (Path(__file__).resolve().parents[1] / "static/js/app.js").read_text()
    assert "if (!homePrompt.value.trim())" in script
    router = script.split('const picker = document.getElementById("smart-file-input")')[1].split('// Global Quick Jump')[0]
    assert "fetch(" not in router
    assert "journey-attach" in router

from collections import Counter

from app_factory import create_app
from core.browser_tools import BROWSER_TOOLS


def test_all_browser_tool_routes_render_and_are_in_sitemap():
    client = create_app().test_client()
    assert len(BROWSER_TOOLS) == 35
    assert Counter(tool.collection for tool in BROWSER_TOOLS) == {
        "students": 7,
        "educators": 7,
        "developers": 7,
        "business": 7,
        "everyday": 7,
    }
    for tool in BROWSER_TOOLS:
        response = client.get(f"/browser-tools/{tool.id}?lang=ar")
        assert response.status_code == 200
        assert tool.name_ar in response.get_data(as_text=True)
        assert tool.name_en in client.get(f"/browser-tools/{tool.id}?lang=en").get_data(as_text=True)
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    for tool in BROWSER_TOOLS:
        assert f"/browser-tools/{tool.id}".encode() in sitemap.data


def test_invalid_browser_tool_route_is_not_found():
    assert create_app().test_client().get("/browser-tools/not-a-real-tool").status_code == 404
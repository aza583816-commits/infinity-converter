from collections import Counter

from app_factory import create_app
from core.browser_tools import BROWSER_TOOLS, BROWSER_TOOL_MAP


def test_all_browser_tool_routes_render_and_are_in_sitemap():
    client = create_app().test_client()
    assert len(BROWSER_TOOLS) == 101
    assert Counter(tool.collection for tool in BROWSER_TOOLS) == {
        "students": 21,
        "educators": 20,
        "developers": 20,
        "business": 20,
        "everyday": 20,
    }
    for index, tool in enumerate(BROWSER_TOOLS, start=1):
        address = f"10.1.{index // 250}.{index % 250}"
        response = client.get(f"/browser-tools/{tool.id}?lang=ar", environ_overrides={"REMOTE_ADDR": address})
        assert response.status_code == 200
        assert tool.name_ar in response.get_data(as_text=True)
        english = client.get(f"/browser-tools/{tool.id}?lang=en", environ_overrides={"REMOTE_ADDR": address})
        assert tool.name_en in english.get_data(as_text=True)
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    for tool in BROWSER_TOOLS:
        assert f"/browser-tools/{tool.id}".encode() in sitemap.data


def test_invalid_browser_tool_route_is_not_found():
    assert create_app().test_client().get("/browser-tools/not-a-real-tool").status_code == 404


def test_browser_tool_registry_has_unique_ids_and_valid_select_choices():
    assert len(BROWSER_TOOL_MAP) == len(BROWSER_TOOLS)
    for tool in BROWSER_TOOLS:
        for field in tool.fields:
            if field["type"] == "select":
                assert field["choices"]
                assert field["value"] in {choice[0] for choice in field["choices"]}
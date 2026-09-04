from app_factory import create_app
from core.tool_registry import AUDIENCE_COLLECTIONS, list_tools

def test_health():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v2/healthz")
    assert response.status_code == 200
    assert response.get_json()["version"] == "6.0.1"


def test_homepage_has_bento_navigation_and_filterable_featured_tools():
    page = create_app().test_client().get("/?lang=en")
    assert page.status_code == 200
    assert b"category-dock" in page.data
    assert b"audience-bento" in page.data
    assert b'id="tool-search"' in page.data
    assert page.data.count(b"data-category=") == 9


def test_pricing_uses_clean_hardcoded_annual_prices():
    client = create_app().test_client()
    page = client.get("/pricing?lang=en")
    assert page.status_code == 200
    assert b'data-price-yearly="29"' in page.data
    assert b'data-price-yearly="99"' in page.data
    assert b'data-period-yearly="/ year"' in page.data


def test_public_tool_pages_and_metadata_routes():
    app = create_app()
    client = app.test_client()
    for tool in list_tools():
        response = client.get(f"/tools/{tool['slug']}")
        assert response.status_code == 200
        assert tool["name_ar"].encode() in response.data
    assert client.get("/tools").status_code == 200
    for collection_id in AUDIENCE_COLLECTIONS:
        assert client.get(f"/collections/{collection_id}").status_code == 200
    assert client.get("/sitemap.xml").status_code == 200
    assert client.get("/manifest.json").status_code == 200

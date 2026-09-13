from app_factory import create_app
from core.tool_registry import AUDIENCE_COLLECTIONS, list_tools

def test_health():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v2/healthz")
    assert response.status_code == 200
    assert response.get_json()["version"] == "7.2.0"


def test_homepage_has_intelligence_workspace_and_filterable_tools():
    page = create_app().test_client().get("/?lang=en")
    assert page.status_code == 200
    assert b"v7-intelligence-console" in page.data
    assert b"SMART FILE ROUTER" in page.data
    assert b"INFINITY FLOW" in page.data
    assert b'id="tool-search"' in page.data
    assert b"Infinity Intelligence" in page.data


def test_pricing_uses_clean_hardcoded_annual_prices(monkeypatch):
    monkeypatch.setenv("PUBLIC_BILLING_ENABLED", "1")
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


def test_language_fallback_matches_device_policy():
    client = create_app().test_client()
    ar = client.get("/", headers={"Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8"})
    en = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"})
    other = client.get("/", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
    assert b'<html lang="ar" dir="rtl">' in ar.data
    assert b'<html lang="en" dir="ltr">' in en.data
    assert b'<html lang="en" dir="ltr">' in other.data

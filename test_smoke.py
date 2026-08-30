from app_factory import create_app
from core.tool_registry import list_tools

def test_health():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v2/healthz")
    assert response.status_code == 200
    assert response.get_json()["version"] == "3.0.0"


def test_public_tool_pages_and_metadata_routes():
    app = create_app()
    client = app.test_client()
    for tool in list_tools():
        response = client.get(f"/tools/{tool['slug']}")
        assert response.status_code == 200
        assert tool["name_ar"].encode() in response.data
    assert client.get("/tools").status_code == 200
    assert client.get("/sitemap.xml").status_code == 200
    assert client.get("/manifest.json").status_code == 200

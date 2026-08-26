from app_factory import create_app

def test_health():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v2/healthz")
    assert response.status_code == 200
    assert response.get_json()["version"] == "2.0.0"

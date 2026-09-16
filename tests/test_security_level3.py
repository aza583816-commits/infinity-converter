from app_factory import create_app


def test_public_health_metadata_is_coarse():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        response = client.get("/api/v2/healthz")

    assert response.status_code == 200
    payload = response.get_json()
    assert "limits" not in payload
    assert set(payload["architecture"]) == {"healthy", "tools", "operations"}


def test_tools_api_does_not_expose_capacity_details():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        response = client.get("/api/v2/tools")

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload["runtime"]) == {"healthy", "tools", "operations"}
    assert "limits" not in payload["runtime"]

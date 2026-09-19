from app_factory import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_language_switch_rejects_external_referrer():
    client = _client()
    response = client.get(
        "/set-language/en",
        headers={"Referer": "https://evil.example/phish?x=1"},
    )
    assert response.status_code in {301, 302, 303, 307, 308}
    assert response.headers["Location"] == "/"
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_language_switch_preserves_only_same_origin_path_and_query():
    client = _client()
    response = client.get(
        "/set-language/en",
        headers={"Host": "infinityconverter.com", "Referer": "https://infinityconverter.com/tools?category=pdf"},
    )
    assert response.status_code in {301, 302, 303, 307, 308}
    assert response.headers["Location"].endswith("/tools?category=pdf")
    assert "HttpOnly" in response.headers.get("Set-Cookie", "")


def test_sitemap_contains_workflows_in_both_languages():
    client = _client()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "https://infinityconverter.com/workflows?lang=ar" in body
    assert "https://infinityconverter.com/workflows?lang=en" in body


def test_untrusted_request_id_is_not_reflected():
    client = _client()
    response = client.get("/api/v2/readyz", headers={"X-Request-ID": "bad id with spaces"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") != "bad id with spaces"


def test_safe_request_id_is_preserved():
    client = _client()
    response = client.get("/api/v2/readyz", headers={"X-Request-ID": "edge-req_2026.09:17"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "edge-req_2026.09:17"

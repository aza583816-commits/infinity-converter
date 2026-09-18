from app_factory import create_app


def test_bare_indexable_url_is_self_canonical():
    client = create_app().test_client()
    response = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<link rel="canonical" href="https://infinityconverter.com/">' in html
    assert '<link rel="alternate" hreflang="en" href="https://infinityconverter.com/?lang=en">' in html
    assert '<link rel="alternate" hreflang="ar" href="https://infinityconverter.com/?lang=ar">' in html


def test_explicit_language_variant_remains_self_canonical():
    client = create_app().test_client()
    response = client.get("/tools/image-to-jpg?lang=en")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<link rel="canonical" href="https://infinityconverter.com/tools/image-to-jpg?lang=en">' in html


def test_search_console_legacy_excel_redirect_resolves():
    client = create_app().test_client()
    response = client.get("/en/excel-to-json", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/tools/xlsx-to-json?lang=en")

    target = client.get(response.headers["Location"])
    assert target.status_code == 200


def test_retired_office_urls_keep_search_equity_with_useful_redirects():
    client = create_app().test_client()
    for path in ("/word-to-csv", "/csv-to-word"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 301
        assert "/tools?category=office" in response.headers["Location"]

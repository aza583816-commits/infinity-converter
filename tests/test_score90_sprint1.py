from app_factory import create_app
from config.settings import settings
from converters.engine import workload_class
from converters.operations import get_operation


def test_heavy_native_workloads_have_dedicated_classes():
    office = get_operation("word-to-pdf")
    ocr = get_operation("pdf-ocr")
    light = get_operation("file-hash")
    assert office and workload_class(office) == "office"
    assert ocr and workload_class(ocr) == "ocr"
    assert light and workload_class(light) == "default"
    assert settings.max_concurrent_office >= 1
    assert settings.max_concurrent_ocr >= 1


def test_versioned_static_assets_are_long_lived_and_immutable():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        response = client.get(f"/static/css/a11y.css?v={settings.app_version}")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert response.headers.get("Server-Timing", "").startswith("app;dur=")


def test_api_responses_are_private_and_not_search_indexable():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        response = client.get("/api/v2/healthz")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"


def test_liveness_and_readiness_are_separate_and_versioned():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        live = client.get("/api/v2/livez")
        ready = client.get("/api/v2/readyz")
    assert live.status_code == 200
    assert live.get_json() == {"status": "ok", "version": settings.app_version}
    assert ready.status_code == 200
    payload = ready.get_json()
    assert payload["version"] == settings.app_version
    assert payload["status"] == "ok"
    assert payload["limits"]["max_concurrent_office"] == settings.max_concurrent_office
    assert payload["limits"]["max_concurrent_ocr"] == settings.max_concurrent_ocr


def test_shared_shell_exposes_keyboard_and_screen_reader_guards():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        response = client.get("/?lang=en")
        html = response.get_data(as_text=True)
    assert '/static/css/a11y.css?v=' in html
    assert 'class="skip-link"' in html
    assert 'id="main-content" tabindex="-1"' in html
    assert 'aria-label="Open Quick Jump search"' in html
    assert 'aria-autocomplete="list"' in html
    assert 'aria-label="Search results"' in html
    assert 'aria-live="polite"' in html
    assert "Accept-Language" in response.headers.get("Vary", "")
    assert "Cookie" in response.headers.get("Vary", "")

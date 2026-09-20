"""Guard against production pages losing all styles after a deploy."""
from pathlib import Path

from app_factory import create_app


def test_homepage_has_both_versioned_stylesheets():
    app = create_app()
    with app.test_client() as client:
        response = client.get("/?lang=en")
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert '/static/css/app.css?v=' in page
        assert '/static/css/a11y.css?v=' in page
        for path in ("app.css", "a11y.css"):
            asset = client.get("/static/css/" + path)
            assert asset.status_code == 200
            assert asset.mimetype == "text/css"
            assert len(asset.data) > (10000 if path == "app.css" else 50)
            assert b"<html" not in asset.data[:100].lower()


def test_service_worker_never_serves_stale_css():
    script = (Path(__file__).resolve().parents[1] / "static" / "sw.js").read_text(encoding="utf-8")
    assert "url.pathname.startsWith('/static/css/')" in script
    assert "fetch(request, {cache: 'no-store'})" in script
    assert "'/static/css/app.css?v=8.0.0'," not in script

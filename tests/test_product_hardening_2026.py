import io

import pytest
from PIL import Image

from app_factory import create_app
from converters.office import _bounded_native_command
from core import ai_budget
from core.workflows import WORKFLOWS, validate_workflow_registry


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'product-hardening.db'}")
    monkeypatch.setenv("PUBLIC_AUTH_ENABLED", "0")
    monkeypatch.setenv("PUBLIC_BILLING_ENABLED", "0")
    return create_app().test_client()


def _png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (48, 32), (32, 96, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_legacy_search_urls_migrate_to_real_current_destinations(client):
    exact = client.get("/image-to-jpg", follow_redirects=False)
    assert exact.status_code == 301
    assert exact.headers["Location"].endswith("/tools/image-to-jpg")

    prefixed = client.get("/en/word-to-pdf", follow_redirects=False)
    assert prefixed.status_code == 301
    assert prefixed.headers["Location"].endswith("/tools/word-to-pdf?lang=en")

    developer = client.get("/en/hmac-generator", follow_redirects=False)
    assert developer.status_code == 301
    assert developer.headers["Location"].endswith("/developer-tools/hmac-generator?lang=en")

    ambiguous_signing = client.get("/sign-pdf", follow_redirects=False)
    assert ambiguous_signing.status_code == 301
    assert "/tools?category=pdf" in ambiguous_signing.headers["Location"]


def test_retired_legacy_pages_return_explicit_gone(client):
    for path in ("/word-to-csv", "/smallpdf-alternative", "/en/ilovepdf-alternative"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 410, path
        assert b"410" in response.data


def test_workflow_registry_is_compatible_and_discoverable(client):
    validate_workflow_registry()
    assert {"office-share-ready", "repair-and-compress-pdf", "scan-to-searchable-pdf", "web-ready-image"} <= set(WORKFLOWS)
    page = client.get("/workflows?lang=en")
    assert page.status_code == 200
    assert b"One upload. Several verified steps." in page.data
    catalog = client.get("/api/v2/workflows")
    assert catalog.status_code == 200
    assert len(catalog.get_json()["workflows"]) == len(WORKFLOWS)


def test_image_workflow_revalidates_handoffs_and_returns_final_artifact(client):
    response = client.post(
        "/api/v2/workflows/execute",
        data={
            "workflow": "web-ready-image",
            "file": (io.BytesIO(_png_bytes()), "sample.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["X-Workflow-ID"] == "web-ready-image"
    assert response.headers["X-Workflow-Steps"] == "3"
    assert response.mimetype == "image/png"
    with Image.open(io.BytesIO(response.data)) as image:
        assert image.format == "PNG"
        assert image.size == (48, 32)


def test_vitals_endpoint_accepts_only_coarse_bounded_metrics(client):
    valid = client.post("/api/v2/vitals", json={"metric": "LCP", "value": 1875.4, "path": "/tools/word-to-pdf?secret=no", "device": "mobile"})
    assert valid.status_code == 202
    assert valid.get_json()["status"] == "accepted"
    assert valid.headers["Cache-Control"] == "no-store, private"

    assert client.post("/api/v2/vitals", json={"metric": "EMAIL", "value": 1}).status_code == 400
    assert client.post("/api/v2/vitals", json={"metric": "LCP", "value": -1}).status_code == 400


def test_ai_daily_cost_fuse_is_hard_and_process_shared_file_backed(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_budget, "_BUDGET_PATH", tmp_path / "budget.json")
    monkeypatch.setenv("AI_MAX_ENHANCED_CALLS_PER_DAY", "1")
    allowed, used, limit = ai_budget.consume_enhanced_ai_budget()
    assert (allowed, used, limit) == (True, 1, 1)
    allowed, used, limit = ai_budget.consume_enhanced_ai_budget()
    assert (allowed, used, limit) == (False, 1, 1)


def test_libreoffice_command_gets_os_resource_limits(monkeypatch):
    monkeypatch.setattr("converters.office.shutil.which", lambda name: "/usr/bin/prlimit" if name == "prlimit" else None)
    wrapped = _bounded_native_command(["libreoffice", "--headless"], 240)
    assert wrapped[0] == "/usr/bin/prlimit"
    assert "--cpu=180:180" in wrapped
    assert "--nofile=128:128" in wrapped
    assert "--core=0:0" in wrapped
    assert wrapped[-2:] == ["libreoffice", "--headless"]


def test_shared_shell_loads_privacy_minimal_rum_and_trust_layers(client):
    response = client.get("/tools/word-to-pdf?lang=en")
    html = response.get_data(as_text=True)
    assert "/static/js/vitals.js?v=" in html
    assert "/static/js/trust-badges.js?v=" in html
    assert "AI file access" not in html  # injected by JS, not fabricated server-side data

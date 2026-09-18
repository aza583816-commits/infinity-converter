import io
import json
from pathlib import Path

from app_factory import create_app


def test_workspace_route_renders():
    client = create_app().test_client()
    response = client.get("/workspace?lang=en")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "INFINITY 8" in body
    assert "workspace-inspector-form" in body
    assert "workspace.js" in body
    assert 'name="robots" content="noindex,follow"' in body


def test_unified_discovery_exposes_both_tool_namespaces():
    client = create_app().test_client()
    response = client.get("/api/v2/discovery")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["counts"]["converter"] == 162
    assert payload["counts"]["browser"] >= 100
    assert payload["counts"]["total"] == payload["counts"]["converter"] + payload["counts"]["browser"]
    ids = {item["id"] for item in payload["items"]}
    assert "pdf-compress" in ids
    assert any(item_id.startswith("browser:") for item_id in ids)


def test_workspace_recommendations_are_catalog_grounded():
    script = (Path(__file__).parents[1] / "static" / "js" / "workspace.js").read_text(encoding="utf-8")
    assert "/api/v2/inspect" in script
    assert "/api/v2/discovery" in script
    assert "catalogIndex" in script
    assert "VISUAL WORKFLOW BUILDER" in (Path(__file__).parents[1] / "templates" / "workspace.html").read_text(encoding="utf-8")
    assert "builderCatalog" in script
    assert "PROFILE_STEPS" in script


def test_workspace_is_in_primary_navigation():
    base = (Path(__file__).parents[1] / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'href="/workspace"' in base


def test_smart_plan_execution_is_catalog_bounded():
    workflows = (Path(__file__).parents[1] / "api" / "workflows.py").read_text(encoding="utf-8")
    app_js = (Path(__file__).parents[1] / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "def _dynamic_recipe" in workflows
    assert 'tool_id.startswith("browser:")' in workflows
    assert 'len(steps) <= 4' in workflows
    assert "executeSmartPlan" in app_js
    assert "/api/v2/workflows/execute" in app_js


def test_dynamic_workspace_chain_executes_real_converters():
    root = Path(__file__).parents[1]
    sample = (root / "static" / "samples" / "sample-image.png").read_bytes()
    client = create_app().test_client()
    response = client.post(
        "/api/v2/workflows/execute",
        data={
            "steps": json.dumps(["image-to-jpg", "image-compress"]),
            "file": (io.BytesIO(sample), "workspace-sample.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.headers["X-Workflow-ID"] == "smart-plan"
    assert response.headers["X-Workflow-Completed"] == "image-to-jpg,image-compress"
    assert response.mimetype == "image/jpeg"
    assert len(response.data) > 100


def test_dynamic_workspace_chain_rejects_browser_and_duplicate_steps():
    root = Path(__file__).parents[1]
    sample = (root / "static" / "samples" / "sample-image.png").read_bytes()
    client = create_app().test_client()

    browser = client.post(
        "/api/v2/workflows/execute",
        data={
            "steps": json.dumps(["browser:text-diff"]),
            "file": (io.BytesIO(sample), "workspace-sample.png"),
        },
        content_type="multipart/form-data",
    )
    assert browser.status_code == 400

    duplicate = client.post(
        "/api/v2/workflows/execute",
        data={
            "steps": json.dumps(["image-compress", "image-compress"]),
            "file": (io.BytesIO(sample), "workspace-sample.png"),
        },
        content_type="multipart/form-data",
    )
    assert duplicate.status_code == 400


def test_infinity_8_knowledge_clusters_are_installed_and_indexable():
    from core.blog import BLOG_POSTS

    slugs = [post["slug"] for post in BLOG_POSTS]
    assert len(slugs) >= 24
    assert len(slugs) == len(set(slugs))
    assert "safe-multi-step-file-workflows" in slugs
    assert "browser-local-tools-and-privacy" in slugs

    client = create_app().test_client()
    article = client.get("/blog/safe-multi-step-file-workflows?lang=en")
    assert article.status_code == 200
    assert "AI can suggest; the server still verifies" in article.get_data(as_text=True)

    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/blog/safe-multi-step-file-workflows" in sitemap

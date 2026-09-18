from pathlib import Path


def test_workspace_route_renders(client):
    response = client.get("/workspace?lang=en")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "INFINITY 8" in body
    assert "workspace-inspector-form" in body
    assert "workspace.js" in body
    assert 'name="robots" content="noindex,follow"' in body


def test_unified_discovery_exposes_both_tool_namespaces(client):
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

import json
import re

from app_factory import create_app
from core.browser_tools import BROWSER_TOOLS
from core.discovery import BROWSER_PREFIX, WORKFLOW_PREFIX, catalog_counts, command_palette_catalog, unified_catalog
from core.tooling import TOOLS
from core.workflows import WORKFLOWS


def test_unified_catalog_covers_all_public_tool_surfaces_with_unique_ids():
    catalog = unified_catalog()
    counts = catalog_counts()
    assert counts == {
        "converter": len(TOOLS),
        "browser": len(BROWSER_TOOLS),
        "workflow": len(WORKFLOWS),
        # Workflows orchestrate existing tools and intentionally do not inflate
        # the historical public-tool total used by existing API/marketing guards.
        "total": len(TOOLS) + len(BROWSER_TOOLS),
    }
    assert len(catalog) == counts["total"]
    assert len({item["id"] for item in catalog}) == len(catalog)
    assert sum(item["kind"] == "converter" for item in catalog) == len(TOOLS)
    assert sum(item["kind"] == "browser" for item in catalog) == len(BROWSER_TOOLS)


def test_browser_ids_are_namespaced_to_avoid_server_collisions():
    browser_entries = [item for item in unified_catalog() if item["kind"] == "browser"]
    assert browser_entries
    assert all(item["id"].startswith(BROWSER_PREFIX) for item in browser_entries)
    assert all(item["url"].startswith("/browser-tools/") for item in browser_entries)
    # text-diff exists in both historical namespaces; the unified catalog must stay unambiguous.
    matching = [item for item in unified_catalog() if item["raw_id"] == "text-diff"]
    assert len(matching) == 2
    assert len({item["id"] for item in matching}) == 2


def test_quick_jump_catalog_includes_tools_and_curated_workflows():
    entries = command_palette_catalog()
    expected = len(TOOLS) + len(BROWSER_TOOLS) + len(WORKFLOWS)
    assert len(entries) == expected
    assert len({item["id"] for item in entries}) == len(entries)
    assert any(item["href"] == "/tools/compress-pdf" for item in entries)
    assert any(item["href"] == "/browser-tools/vat-calculator" for item in entries)
    assert any(item["id"] == f"{WORKFLOW_PREFIX}web-ready-image" for item in entries)


def test_shared_shell_embeds_the_complete_quick_jump_catalog():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        html = client.get("/?lang=en").get_data(as_text=True)
    match = re.search(
        r'<script id="command-palette-data"[^>]*>(.*?)</script>',
        html,
        flags=re.S,
    )
    assert match
    payload = json.loads(match.group(1))
    assert len(payload) == len(TOOLS) + len(BROWSER_TOOLS) + len(WORKFLOWS)
    assert any(item["id"] == "browser:vat-calculator" for item in payload)
    assert any(item["id"] == "workflow:web-ready-image" for item in payload)

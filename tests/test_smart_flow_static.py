from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_tool_page_loads_smart_flow_as_a_versioned_tool_only_module():
    template = read("templates/tool.html")
    assert '/static/js/smart-flow.js?v={{ app_version }}' in template
    assert '/static/js/app.js?v={{ app_version }}' in template


def test_smart_flow_keeps_handoff_private_bounded_and_expiring():
    script = read("static/js/smart-flow.js")
    assert 'const MAX_HANDOFF_BYTES = 32 * 1024 * 1024' in script
    assert 'const HANDOFF_TTL_MS = 15 * 60 * 1000' in script
    assert 'indexedDB.open(DB_NAME, 1)' in script
    assert 'DataTransfer' in script
    assert 'targetToolId' in script and 'expiresAt' in script
    assert 'params.get("handoff") !== "1"' in script
    assert 'store.delete(RECORD_KEY)' in script
    # The handoff must never call the conversion or AI APIs itself. It only
    # reads the already-created local blob URL, stores it in IndexedDB, and
    # lets the destination tool use the normal explicit Convert action.
    assert '/api/v2/convert' not in script
    assert '/api/v2/ai/' not in script
    assert 'fetch(blobUrl)' in script


def test_smart_flow_explains_privacy_and_offers_real_follow_up_tools():
    script = read("static/js/smart-flow.js")
    for phrase in (
        "Infinity Finish Line",
        "Privacy receipt",
        "Smart Continue",
        "File contents are not attached to Infinity Intelligence automatically",
        "No permanent public conversion file history",
    ):
        assert phrase in script
    for tool_id in (
        "pdf-compress", "pdf-password-protect", "pdf-merge",
        "ocr-pdf-to-searchable", "pdf-to-docx", "image-compress",
        "image-to-webp", "csv-to-xlsx", "zip-integrity",
    ):
        assert f'"{tool_id}"' in script

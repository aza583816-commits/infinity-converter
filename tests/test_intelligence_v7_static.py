from core.browser_tools import BROWSER_TOOLS
from core.intelligence import fallback_plan, intent_route, public_catalog, sanitize_context
from core.tool_registry import TOOLS


def test_live_intelligence_catalog_matches_complete_workspace():
    catalog = public_catalog()
    assert len(catalog) == len(TOOLS) + len(BROWSER_TOOLS)
    assert len({item["id"] for item in catalog}) == len(catalog)
    assert {item["id"] for item in catalog if item["kind"] == "converter"} == set(TOOLS)
    assert {item["raw_id"] for item in catalog if item["kind"] == "browser"} == {tool.id for tool in BROWSER_TOOLS}
    assert all(item["url"].startswith(("/tools/", "/browser-tools/")) for item in catalog)


def test_arabic_scanned_pdf_to_editable_word_is_multistep():
    assert intent_route("عندي PDF سكان وأبيه وورد قابل للتعديل")[:2] == [
        "ocr-pdf-to-searchable",
        "pdf-to-docx",
    ]


def test_arabic_pdf_compress_is_direct_not_filler():
    plan = fallback_plan("صغر لي ملف PDF عشان أرسله بالإيميل", lang="ar")
    assert [step["tool_id"] for step in plan["steps"]] == ["pdf-compress"]


def test_browser_local_utility_is_grounded_and_namespaced():
    plan = fallback_plan("احسب ضريبة القيمة المضافة 15%", lang="ar")
    assert [step["tool_id"] for step in plan["steps"]] == ["browser:vat-calculator"]
    assert plan["steps"][0]["url"] == "/browser-tools/vat-calculator"
    assert plan["steps"][0]["kind"] == "browser"


def test_common_direct_routes_are_grounded():
    prompts = {
        "أبي أشيل كلام حساس من PDF": "pdf-redact",
        "اجمع الصور في ملف PDF واحد": "image-to-pdf",
        "repair a broken pdf": "pdf-repair",
    }
    for prompt, expected in prompts.items():
        route = intent_route(prompt)
        assert route and route[0] == expected
        assert all(tool_id in TOOLS for tool_id in route)


def test_browser_context_is_normalized_without_file_content():
    clean = sanitize_context({"tool": {"id": "vat-calculator"}, "content": "private"})
    assert clean["tool"]["id"] == "browser:vat-calculator"
    assert "content" not in clean


def test_context_sanitizer_drops_file_payload_fields():
    clean = sanitize_context({
        "tool": {"id": "pdf-compress"},
        "content": "secret document text",
        "file_content": "more secret text",
        "base64": "AAA...",
        "blob": "binary-ish",
        "nested": {"bytes": "should disappear", "mime": "application/pdf"},
    })
    assert "content" not in clean
    assert "file_content" not in clean
    assert "base64" not in clean
    assert "blob" not in clean
    assert "bytes" not in clean["nested"]
    assert clean["nested"]["mime"] == "application/pdf"

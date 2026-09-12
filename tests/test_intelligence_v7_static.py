from core.intelligence import fallback_plan, intent_route, public_catalog, sanitize_context
from core.tool_registry import TOOLS


def test_live_intelligence_catalog_matches_registry():
    catalog = public_catalog()
    assert len(catalog) == len(TOOLS) == 162
    assert {item["id"] for item in catalog} == set(TOOLS)
    assert all(item["url"].startswith("/tools/") for item in catalog)


def test_arabic_scanned_pdf_to_editable_word_is_multistep():
    assert intent_route("عندي PDF سكان وأبيه وورد قابل للتعديل")[:2] == [
        "ocr-pdf-to-searchable",
        "pdf-to-docx",
    ]


def test_arabic_pdf_compress_is_direct_not_filler():
    plan = fallback_plan("صغر لي ملف PDF عشان أرسله بالإيميل", lang="ar")
    assert [step["tool_id"] for step in plan["steps"]] == ["pdf-compress"]


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

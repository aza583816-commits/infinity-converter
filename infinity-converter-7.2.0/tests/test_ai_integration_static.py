from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_ai_status_keeps_smart_core_available_without_exposing_key():
    text = (ROOT / "api" / "ai.py").read_text()
    assert "_model_probe" in text
    assert "x-goog-api-key" in text
    assert '"core_ready": True' in text
    assert '"enhanced_ready"' in text

def test_tool_page_has_contextual_copilot():
    text = (ROOT / "templates" / "tool.html").read_text()
    assert 'id="tool-ai-context"' in text
    assert 'data-tool-ai-action="explain"' in text
    assert 'data-tool-ai-action="troubleshoot"' in text

def test_frontend_uses_structured_plan_endpoint_and_real_status():
    text = (ROOT / "static" / "js" / "app.js").read_text()
    assert "fetch('/api/v2/ai/status'" in text
    assert "fetch('/api/v2/ai/plan'" in text
    assert "file_contents_attached: false" in text
    assert "Gemini" not in text

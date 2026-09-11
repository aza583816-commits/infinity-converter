from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_ai_status_probes_model_without_exposing_key():
    text = (ROOT / "api" / "ai.py").read_text()
    assert "_model_probe" in text
    assert 'x-goog-api-key' in text
    assert "supportedGenerationMethods" in text
    assert "API key" not in text.split("return jsonify(result)", 1)[-1]

def test_tool_ai_button_has_homepage_fallback():
    text = (ROOT / "templates" / "tool.html").read_text()
    assert 'data-ai-prefill' in text
    assert '/?ai=' in text

def test_frontend_checks_real_ai_status():
    text = (ROOT / "static" / "js" / "app.js").read_text()
    assert "fetch('/api/v2/ai/status'" in text
    assert "Connected & ready" in text

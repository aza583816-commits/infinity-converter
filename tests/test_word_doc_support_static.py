from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_word_to_pdf_declares_doc_and_docx():
    text = (ROOT / "core" / "tool_registry.py").read_text()
    assert '"word-to-pdf": Tool(' in text
    assert '(".doc", ".docx")' in text


def test_doc_ole_signature_is_registered():
    text = (ROOT / "security" / "file_guard.py").read_text()
    assert '".doc": (b"\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1",)' in text


def test_doc_mime_is_registered():
    text = (ROOT / "converters" / "validation.py").read_text()
    assert '".doc": "application/msword"' in text


def test_gemini_38_config_avoids_deprecated_temperature():
    text = (ROOT / "api" / "ai.py").read_text()
    assert '"thinkingLevel": "medium"' in text
    assert '"temperature"' not in text

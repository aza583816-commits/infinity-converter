"""When LibreOffice drops a source heading, do not return a partial PDF."""
from pathlib import Path

import pymupdf

from converters import office


def test_missing_heading_falls_back_to_independent_pdf_renderer(
    tmp_path: Path, monkeypatch,
) -> None:
    original_html = ("<!doctype html><html><head><meta charset='utf-8'></head>"
                     "<body><h1>Infinity</h1><p>Hello world</p></body></html>")
    source = tmp_path / "source.html"
    source.write_text(original_html, encoding="utf-8")
    out_dir = tmp_path / "output"

    def fake_libreoffice(command, *, timeout, env):
        # Reproduce the real CI regression: native conversion succeeds and
        # produces a structurally valid PDF but silently omits the first title.
        output = out_dir / (Path(command[-1]).stem + ".pdf")
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((72, 100), "Hello world")
            document.save(output)

    monkeypatch.setattr(office, "_run_libreoffice", fake_libreoffice)
    result = office.office_to_pdf(source, out_dir, timeout=30)

    import unicodedata
    with pymupdf.open(result) as document:
        text = unicodedata.normalize("NFKC", " ".join(page.get_text("text") for page in document))
        assert len(document) == 1
        import unicodedata
        normalized = unicodedata.normalize("NFKC", text)
        assert "Infinity" in normalized
        assert "Hello world" in normalized
    assert source.read_text(encoding="utf-8") == original_html

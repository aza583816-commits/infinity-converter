import pymupdf

from converters.ocr_advanced import _insert_searchable_text, pdf_to_searchable_pdf


def test_dense_hidden_layer_keeps_every_unicode_line(tmp_path):
    source = [f"سجل السلامة RECORD {i:05d}" for i in range(160)]
    output = tmp_path / "dense-layer.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=300, height=420)
        _insert_searchable_text(page, "\n".join(source), 8)
        doc.save(output)
    with pymupdf.open(output) as doc:
        # LRM marks isolate direction at script boundaries; they carry no
        # source letters/numbers and must not alter logical Arabic order.
        actual = doc[0].get_text().replace('\u200e', '')
        for value in source:
            assert value in actual, (value, actual)


def test_digital_searchable_pdf_preserves_all_native_page_text(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "searchable.pdf"
    expected = []
    with pymupdf.open() as doc:
        for index in range(3):
            page = doc.new_page(width=842 if index % 2 else 595, height=595 if index % 2 else 842)
            page.insert_text((40, 50), f"UNIQUE PAGE {index:05d}")
            page.insert_htmlbox(pymupdf.Rect(40, 90, 540, 400),
                                f"<p>السلامة Safety 00123 رقم السجل {index:05d}</p>")
            expected.append(page.get_text())
        doc.save(source)
    pdf_to_searchable_pdf(source, output)
    with pymupdf.open(output) as doc:
        assert len(doc) == len(expected)
        for page, original in zip(doc, expected):
            assert page.get_images(), "visual page background lost"
            assert " ".join(page.get_text().split()) == " ".join(original.split())

"""Actual OCR over mildly degraded synthetic multilingual receipts."""
import json
import re
import unicodedata

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from converters.mega_tools import ocr_receipt_fields
from converters.ocr import ocr_image


@pytest.mark.parametrize("language", ("english", "arabic", "mixed"))
def test_degraded_multilingual_receipt_retains_words_and_all_fields(tmp_path, language):
    source = tmp_path / f"receipt-{language}.jpg"
    image = Image.new("RGB", (1800, 1200), "#f4f1e8")
    draw = ImageDraw.Draw(image)
    english = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52)
    arabic = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf", 58)
    reference = {"english": "SAFETY EQUIPMENT RECEIPT",
                 "arabic": "فاتورة معدات السلامة",
                 "mixed": "فاتورة معدات السلامة Safety equipment"}[language]
    if language == "mixed":
        # Use fonts with real glyph coverage; missing-glyph boxes are not a
        # valid known-answer OCR fixture.
        draw.text((80, 75), "Safety equipment", fill="#202020", font=english)
        draw.text((950, 75), "فاتورة معدات السلامة", fill="#202020", font=arabic)
    else:
        draw.text((80, 75), reference, fill="#202020", font=arabic if language != "english" else english)
    for row, value in enumerate(("Email test@example.com", "Date 26/09/2026",
                                 "Phone +966501234567", "Total SAR 1250.50",
                                 "Item 00123 | Qty 02 | Unit 625.25")):
        draw.text((90, 260 + row * 145), value, fill="#303030", font=english)
    image = image.rotate(.6, resample=Image.Resampling.BICUBIC, fillcolor="#f4f1e8")
    image = image.filter(ImageFilter.GaussianBlur(.45))
    image.save(source, quality=80)
    image.close()
    fields_path, text_path = tmp_path / "fields.json", tmp_path / "text.txt"
    ocr_receipt_fields(source, fields_path, "ara+eng")
    fields = json.loads(fields_path.read_text(encoding="utf-8"))
    assert fields["emails"] == ["test@example.com"], fields
    assert "26/09/2026" in fields["dates"], fields
    assert "SAR 1250.50" in fields["money"], fields
    assert "966501234567" in [re.sub(r"\D", "", p) for p in fields["phones"]], fields
    ocr_image(source, text_path, lang="ar+eng")
    actual = unicodedata.normalize("NFKC", text_path.read_text(encoding="utf-8")).casefold()
    for word in reference.casefold().split():
        assert word in actual, (word, actual)

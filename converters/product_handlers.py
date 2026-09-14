"""Product-specific handlers that need options, generators, or mixed inputs.

Keeping these workflows outside the legacy compatibility dispatcher makes their
contracts explicit without changing the proven converter implementations.
"""
from __future__ import annotations

import csv
from pathlib import Path

from converters import archive, images, pdf, utility

_UNSAFE_NAME_CHARS = '\\/:*?"<>|'


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "file").stem.strip()
    cleaned = "".join(ch for ch in stem if ch not in _UNSAFE_NAME_CHARS).strip()
    return (cleaned or "file")[:80]


def csv_merge_deduplicate(safe_inputs, output_dir, param):
    out = output_dir / "InfinityConverter-Merged.csv"
    utility.merge_and_deduplicate_csv([item["path"] for item in safe_inputs], out)
    return out, "text/csv"


def pdf_booklet(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-booklet.pdf"
    pdf.make_booklet(safe_input["path"], out, options["layout"])
    return [(out, "application/pdf")]


def lms_pdf_optimizer(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-lms-optimized.pdf"
    pdf.optimize_pdf_for_lms(safe_input["path"], out, options["target"])
    return [(out, "application/pdf")]


def social_resize(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-social.png"
    images.resize_for_social(safe_input["path"], out, options["preset"], options["fit"])
    return [(out, "image/png")]


def question_bank(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    out = output_dir / f"{_safe_stem(safe_input['filename'])}-gift.txt"
    utility.text_to_gift(safe_input["path"], out)
    return [(out, "text/plain")]


def bulk_certificates(safe_input, output_dir, param, timeout, max_pdf_pages, options):
    certificates = []
    try:
        with safe_input["path"].open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if not reader.fieldnames or "name" not in reader.fieldnames:
                raise ValueError("يجب أن يحتوي CSV على عمود باسم name.")
            for index, row in enumerate(reader, start=1):
                if index > 500:
                    raise ValueError("الحد الأقصى هو 500 شهادة في العملية الواحدة.")
                certificate = output_dir / f"certificate-{index:03d}.pdf"
                pdf.create_certificate(
                    certificate,
                    (row.get("name") or "").strip(),
                    options["title"],
                    options.get("issuer", ""),
                )
                certificates.append((certificate, certificate.name))
    except csv.Error as exc:
        raise ValueError("ملف CSV غير صالح.") from exc
    if not certificates:
        raise ValueError("لا يحتوي CSV على أسماء شهادات.")
    out = output_dir / "InfinityConverter-Certificates.zip"
    archive.create_zip(certificates, out)
    return [(out, "application/zip")]


def assignment_cover(output_dir, options):
    out = output_dir / "InfinityConverter-Assignment-Cover.pdf"
    pdf.create_assignment_cover(out, options)
    return out, "application/pdf"


def omr_sheet(output_dir, options):
    out = output_dir / "InfinityConverter-OMR-Sheet.pdf"
    pdf.create_omr_sheet(out, int(options["questions"]))
    return out, "application/pdf"


def quote_graphic(output_dir, options):
    out = output_dir / "InfinityConverter-Quote.png"
    images.quote_social_graphic(
        out,
        options["quote"],
        options.get("author", ""),
        options["preset"],
        options["theme"],
    )
    return out, "image/png"


OPTION_SINGLE_HANDLERS = {
    "pdf-booklet": pdf_booklet,
    "lms-pdf-size-optimizer": lms_pdf_optimizer,
    "social-media-image-resizer": social_resize,
    "bulk-certificate-maker": bulk_certificates,
    "lms-question-bank-formatter": question_bank,
}

GENERATOR_HANDLERS = {
    "assignment-cover-page": assignment_cover,
    "omr-bubble-sheet": omr_sheet,
    "quote-social-graphic": quote_graphic,
}

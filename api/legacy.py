from __future__ import annotations

from flask import Blueprint, abort, redirect, request

from core.tooling import TOOLS, _meta_for, get_tool, tool_url
from core.browser_tools import get_browser_tool

legacy_bp = Blueprint("legacy", __name__)

# URLs observed in Search Console or historical public releases that no longer
# match the canonical 7.x structure. Redirect only when there is a genuinely
# equivalent destination. Dead/ambiguous pages return 410 instead of polluting
# the index with soft-404 redirects to the homepage.
LEGACY_REDIRECTS = {
    "/compress-image": "/tools/compress-image",
    "/compress-pdf-target": "/tools/compress-pdf",
    "/excel-to-json": "/tools/excel-to-json",
    "/extract-pdf-images": "/tools/pdf-to-jpg",
    "/image-to-jpg": "/tools/image-to-jpg",
    "/image-to-png": "/tools/image-to-png",
    "/json-to-excel": "/tools/json-to-xlsx",
    "/pdf-compare": "/tools/pdf-compare",
    "/pdf-page-number": "/tools/pdf-page-numbers",
    "/pdf-to-images": "/tools/pdf-to-jpg",
    "/pdf-to-text": "/tools/pdf-to-text",
    "/protect-pdf": "/tools/pdf-password-protect",
    "/redact-pdf": "/tools/pdf-redact",
    "/remove-pdf-pages": "/tools/delete-pdf-pages",
    # The old signing page promised a capability that is not represented by one
    # equivalent current tool, so route users to the PDF collection rather than
    # inventing a signing tool or soft-404ing to the homepage.
    "/sign-pdf": "/tools?category=pdf",
    "/unlock-pdf": "/tools/pdf-unlock",
    "/watermark-pdf": "/tools/pdf-watermark-text",
    "/arabic-proofreader": "/collections/students",
    "/clean-study-sheet": "/collections/students",
    "/html-entity": "/browser-tools/html-entity-converter",
    "/text-counter": "/browser-tools/text-counter",
    "/unit-converter": "/browser-tools/unit-converter",
}

# Old pages whose promise is not represented by one equivalent current surface.
# A 410 makes removal explicit to crawlers instead of creating a misleading
# redirect. Comparison/alternative landing pages are also retired until we have
# current, independently maintained editorial content for them.
LEGACY_GONE = {
    "/word-to-csv",
    "/csv-to-word",
    "/ink-saver-pdf",
    "/ilovepdf-alternative",
    "/smallpdf-alternative",
}


def _canonical_for_slug(slug: str) -> str | None:
    tool = get_tool(slug)
    if tool:
        return tool_url(tool)
    for candidate in TOOLS.values():
        if _meta_for(candidate)["slug"] == slug:
            return tool_url(candidate)
    if get_browser_tool(slug):
        return f"/browser-tools/{slug}"
    return LEGACY_REDIRECTS.get(f"/{slug}")


def _with_lang(target: str, lang: str) -> str:
    separator = "&" if "?" in target else "?"
    return f"{target}{separator}lang={lang}"


@legacy_bp.get("/en/<path:legacy_path>")
def legacy_en(legacy_path: str):
    clean = legacy_path.strip("/")
    target = _canonical_for_slug(clean)
    if target:
        return redirect(_with_lang(target, "en"), code=301)
    if f"/{clean}" in LEGACY_GONE:
        abort(410)
    abort(404)


@legacy_bp.get("/ar/<path:legacy_path>")
def legacy_ar(legacy_path: str):
    clean = legacy_path.strip("/")
    target = _canonical_for_slug(clean)
    if target:
        return redirect(_with_lang(target, "ar"), code=301)
    if f"/{clean}" in LEGACY_GONE:
        abort(410)
    abort(404)


def _legacy_exact_view():
    path = request.path.rstrip("/") or "/"
    target = LEGACY_REDIRECTS.get(path)
    if target:
        lang = request.args.get("lang")
        return redirect(_with_lang(target, lang) if lang in {"ar", "en"} else target, code=301)
    if path in LEGACY_GONE:
        abort(410)
    abort(404)


for index, path in enumerate(sorted(set(LEGACY_REDIRECTS) | LEGACY_GONE)):
    # Static rules outrank the generic one-segment page route in api.pages.
    legacy_bp.add_url_rule(path, endpoint=f"legacy_exact_{index}", view_func=_legacy_exact_view, methods=["GET"])

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from core.tooling import TOOLS, _meta_for

AR_STOP = {
    "ابي", "أبي", "ابغى", "أبغى", "اريد", "أريد", "احتاج", "أحتاج", "عندي", "هذا", "هذه", "في", "من", "الى", "إلى", "على", "مع", "بدون", "وش", "كيف", "لي", "و", "او", "أو",
}
EN_STOP = {
    "i", "a", "an", "the", "to", "for", "of", "and", "or", "with", "without", "my", "need", "want", "have", "this", "that", "file", "files",
}


def public_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tool in TOOLS.values():
        meta = _meta_for(tool)
        items.append({
            "id": tool.id,
            "slug": meta["slug"],
            "url": f"/tools/{meta['slug']}",
            "name_ar": tool.name_ar,
            "name_en": tool.name_en,
            "description_ar": tool.description_ar,
            "description_en": tool.description_en,
            "category": tool.category,
            "category_ar": tool.category_ar,
            "category_en": tool.category_en,
            "icon": tool.icon,
            "input_ext": list(tool.input_ext),
            "output_ext": tool.output_ext,
            "max_files": tool.max_files,
            "input_required": tool.input_required,
            "batch": tool.batch,
            "keywords": meta.get("keywords", ""),
        })
    return items


def catalog_prompt() -> str:
    lines = []
    for item in public_catalog():
        inp = ",".join(item["input_ext"]) or "no-upload"
        lines.append(
            f"{item['id']} | {item['name_en']} | {item['name_ar']} | "
            f"{item['category']} | in:{inp} | out:{item['output_ext']} | {item['url']} | "
            f"{item['description_en']} | {item['description_ar']}"
        )
    return "\n".join(lines)


def _tokens(text: str) -> set[str]:
    text = text.casefold()
    words = re.findall(r"[\w.+#-]+", text, flags=re.UNICODE)
    return {word for word in words if len(word) > 1 and word not in AR_STOP and word not in EN_STOP}


# Default-deny context: free-form options (passwords, redaction text, names),
# error messages and unknown nested fields must never reach a remote provider.
_CONTEXT_CONTAINERS = {"tool", "file", "files", "smart_file", "result", "privacy", "nested"}
_CONTEXT_NUMBERS = {"size_bytes", "input_bytes", "output_bytes", "duration_ms", "pages", "width", "height", "pixels", "batch_total", "batch_succeeded"}


def _safe_context(context: Any, depth: int = 0) -> Any:
    import math
    if depth > 4:
        return None
    if isinstance(context, list):
        return [_safe_context(item, depth + 1) for item in context[:20] if isinstance(item, dict)]
    if not isinstance(context, dict):
        return {}
    result = {}
    for key, value in list(context.items())[:40]:
        if key in _CONTEXT_CONTAINERS and isinstance(value, (dict, list)):
            result[key] = _safe_context(value, depth + 1)
        elif key in {"id", "tool_id"} and isinstance(value, str) and value in TOOLS:
            result[key] = value
        elif key in _CONTEXT_NUMBERS and isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 10**12:
            result[key] = value
        elif key == "extension" and isinstance(value, str) and re.fullmatch(r"\.[a-z0-9]{1,10}", value):
            result[key] = value
        elif key == "mime" and isinstance(value, str) and re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", value) and len(value) < 120:
            result[key] = value
        elif key in {"safe", "encrypted"} and isinstance(value, bool):
            result[key] = value
        elif key == "error" and isinstance(value, dict):
            result[key] = {"present": True}  # raw exception text may contain personal data
    return result


def sanitize_context(context: Any) -> dict[str, Any]:
    cleaned = _safe_context(context)
    return cleaned if isinstance(cleaned, dict) else {}


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def intent_route(prompt: str, context: dict[str, Any] | None = None) -> list[str]:
    """High-confidence routes for common goals, used before fuzzy ranking.

    This is intentionally conservative: it only fires when the user's wording
    contains a clear task/format signal. Gemini can still refine or replace the
    route when enhanced AI is available.
    """
    text = " ".join([prompt, str((context or {}).get("tool", ""))]).casefold()
    ids: list[str] = []
    pdf = _has_any(text, ("pdf", "بي دي اف"))
    image = _has_any(text, ("image", "images", "jpg", "jpeg", "png", "webp", "صورة", "صور"))
    scanned = _has_any(text, ("scanned", "scan", "ocr", "سكان", "سكانر", "ممسوح", "ممسوحة", "مصوّر", "مصور", "صورة pdf", "صور pdf"))
    editable = _has_any(text, ("editable", "edit", "word", "docx", "قابل للتعديل", "وورد", "word"))
    smaller = _has_any(text, ("compress", "smaller", "reduce size", "small size", "ضغط", "تصغير", "صغر", "صغّر", "أصغر", "اصغر", "خفف", "أخف", "اخف"))
    sensitive = _has_any(text, ("redact", "sensitive", "private info", "remove information", "تنقيح", "حساس", "حساسة", "معلومات شخصية", "اخفاء", "إخفاء"))
    protect = _has_any(text, ("password", "protect", "encrypt", "كلمة مرور", "حماية", "احمي", "أحمي"))
    merge = _has_any(text, ("merge", "combine", "join", "دمج", "اجمع", "جمع"))
    split = _has_any(text, ("split", "separate", "تقسيم", "قسم", "افصل", "فصل"))
    repair = _has_any(text, ("repair", "broken", "corrupt", "fix pdf", "إصلاح", "اصلح", "أصلح", "تالف", "خربان"))
    compare = _has_any(text, ("compare", "difference", "diff", "مقارنة", "قارن", "فرق", "الفروقات"))
    extract_text = _has_any(text, ("extract text", "get text", "text from", "استخراج نص", "استخرج النص", "طلع النص"))

    # Strong format + goal routes.
    if pdf and scanned and editable:
        ids += ["ocr-pdf-to-searchable", "pdf-to-docx"]
    elif pdf and scanned and extract_text:
        ids += ["pdf-ocr"]
    elif pdf and scanned:
        ids += ["ocr-pdf-to-searchable", "pdf-ocr"]
    if pdf and smaller:
        ids += ["pdf-compress"]
    if pdf and sensitive:
        ids += ["pdf-redact"]
    if pdf and protect:
        ids += ["pdf-password-protect"]
    if pdf and repair:
        ids += ["pdf-repair"]
    if pdf and compare:
        ids += ["pdf-compare"]
    if pdf and merge:
        ids += ["pdf-merge"]
    if pdf and split:
        ids += ["pdf-split"]

    # Images → PDF or image processing.
    if image and pdf and _has_any(text, ("to pdf", "into pdf", "one pdf", "pdf واحد", "إلى pdf", "الى pdf", "لـ pdf", "pdf مرتب")):
        ids = ["image-to-pdf"] + [x for x in ids if x != "pdf-merge"]
    if image and smaller:
        ids += ["image-compress"]
    if image and _has_any(text, ("resize", "dimensions", "width", "height", "ابعاد", "أبعاد", "مقاس", "حجم بالبكسل")):
        ids += ["image-resize"]
    if image and extract_text:
        ids += ["image-ocr"]
    if image and _has_any(text, ("upscale", "enhance", "increase resolution", "تكبير الجودة", "رفع الدقة", "تحسين الصورة")):
        ids += ["image-upscale"]
    if image and _has_any(text, ("background", "خلفية", "remove background", "white background")):
        ids += ["image-background-cleaner"]

    # Direct format conversions.
    if _has_any(text, ("word to pdf", "docx to pdf", "وورد إلى pdf", "word إلى pdf", "وورد ل pdf")):
        ids += ["word-to-pdf"]
    if _has_any(text, ("pdf to word", "pdf to docx", "pdf إلى word", "pdf الى word", "pdf إلى وورد", "pdf لوورد")) and not scanned:
        ids += ["pdf-to-docx"]
    if _has_any(text, ("excel to pdf", "xlsx to pdf", "اكسل إلى pdf", "إكسل إلى pdf")):
        ids += ["excel-to-pdf"]
    if _has_any(text, ("powerpoint to pdf", "ppt to pdf", "pptx to pdf", "بوربوينت إلى pdf")):
        ids += ["ppt-to-pdf"]
    if _has_any(text, ("pdf to jpg", "pdf to image", "pdf إلى صور", "pdf الى صور", "pdf إلى jpg")):
        ids += ["pdf-to-jpg"]
    if _has_any(text, ("png to jpg", "png إلى jpg", "png الى jpg")):
        ids += ["image-to-jpg"]
    if _has_any(text, ("jpg to png", "jpeg to png", "jpg إلى png", "jpg الى png")):
        ids += ["image-to-png"]
    if _has_any(text, ("to webp", "إلى webp", "الى webp")):
        ids += ["image-to-webp"]

    # Archives / data / developer workflows.
    if _has_any(text, ("create zip", "make zip", "zip files", "إنشاء zip", "انشاء zip", "اضغط الملفات zip")):
        ids += ["zip-create"]
    if _has_any(text, ("extract zip", "unzip", "فك zip", "فك الضغط")):
        ids += ["zip-extract"]
    if _has_any(text, ("json minify", "minify json", "تصغير json")):
        ids += ["json-minify"]
    if _has_any(text, ("csv statistics", "analyze csv", "احصائيات csv", "إحصائيات csv", "حلل csv")):
        ids += ["csv-statistics"]
    if _has_any(text, ("compare text", "text diff", "قارن نص", "مقارنة نص")):
        ids += ["text-diff"]

    # Current-tool modes should keep the active tool grounded in the response.
    current = (context or {}).get("tool")
    if isinstance(current, dict):
        current_id = str(current.get("id", ""))
        if current_id in TOOLS and current_id not in ids:
            ids.append(current_id)

    seen: set[str] = set()
    return [tool_id for tool_id in ids if tool_id in TOOLS and not (tool_id in seen or seen.add(tool_id))]

def rank_tools(prompt: str, context: dict[str, Any] | None = None, limit: int = 6) -> list[dict[str, Any]]:
    query = " ".join([prompt, str((context or {}).get("tool", "")), str((context or {}).get("file", ""))])
    q_tokens = _tokens(query)
    q_folded = query.casefold()
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in public_catalog():
        haystack = " ".join([
            item["id"], item["name_ar"], item["name_en"], item["description_ar"], item["description_en"],
            item["category"], item["category_ar"], item["category_en"], item["keywords"], " ".join(item["input_ext"]), item["output_ext"],
        ]).casefold()
        h_tokens = _tokens(haystack)
        overlap = len(q_tokens & h_tokens)
        score = overlap * 4.0
        if item["name_en"].casefold() in q_folded or item["name_ar"].casefold() in q_folded:
            score += 12
        if item["id"].replace("-", " ") in q_folded:
            score += 8
        for ext in item["input_ext"]:
            clean = ext.lstrip(".").casefold()
            if clean and clean in q_tokens:
                score += 5
        if item["output_ext"].lstrip(".").casefold() in q_tokens:
            score += 3
        category = item["category"].casefold()
        if category in q_tokens:
            score += 4
        # Intent nudges for common natural-language requests in Arabic and English.
        intent_pairs = {
            "ocr": ("ocr", "ممسوح", "مصوّر", "مصور", "scan", "scanned", "extract text", "استخراج نص"),
            "compress": ("compress", "smaller", "reduce size", "ضغط", "تصغير", "خفف", "أصغر"),
            "merge": ("merge", "combine", "دمج", "اجمع"),
            "redact": ("redact", "sensitive", "privacy", "تنقيح", "حساس", "إخفاء"),
            "convert": ("convert", "تحويل", "حوّل", "حول"),
            "repair": ("repair", "fix", "broken", "إصلاح", "خربان", "تالف"),
        }
        for marker, phrases in intent_pairs.items():
            if any(p in q_folded for p in phrases) and marker in haystack:
                score += 5
        if score > 0:
            scored.append((score, item))
    priority = intent_route(prompt, context)
    priority_map = {tool_id: (len(priority) - index) * 100.0 for index, tool_id in enumerate(priority)}
    if priority_map:
        for item in public_catalog():
            bonus = priority_map.get(item["id"])
            if bonus:
                scored.append((bonus, item))
    best: dict[str, tuple[float, dict[str, Any]]] = {}
    for score, item in scored:
        previous = best.get(item["id"])
        if previous is None or score > previous[0]:
            best[item["id"]] = (score, item)
    ordered = sorted(best.values(), key=lambda pair: (-pair[0], pair[1]["name_en"]))
    return [item for _, item in ordered[:limit]]


def fallback_plan(prompt: str, context: dict[str, Any] | None = None, lang: str = "ar", mode: str = "plan") -> dict[str, Any]:
    context = sanitize_context(context or {})
    route = intent_route(prompt, context)
    ranked = rank_tools(prompt, context, limit=5)
    by_id = {item["id"]: item for item in public_catalog()}
    matches = [by_id[tool_id] for tool_id in route if tool_id in by_id]
    if not matches:
        matches = ranked[:1]
    # Keep only a compatible prefix: recommendations are sequential steps,
    # not a bag of similarly named tools with incompatible input formats.
    compatible = []
    for item in matches:
        if compatible:
            previous_output = compatible[-1]["output_ext"]
            accepted = item["input_ext"]
            if previous_output not in accepted and not {"*", ".*"}.intersection(accepted):
                break
        compatible.append(item)
    matches = compatible
    ar = lang != "en"
    if not matches:
        return {
            "title": "أحتاج وصفًا أدق للنتيجة" if ar else "I need a little more detail about the result",
            "summary": "اذكر نوع الملف والنتيجة التي تريدها، مثل: PDF ممسوح إلى Word قابل للتعديل." if ar else "Mention the file type and desired outcome, for example: scanned PDF to editable Word.",
            "steps": [],
            "tips": ["لن يرسل Infinity ملفاتك للذكاء تلقائيًا." if ar else "Infinity does not attach your conversion files to AI automatically."],
            "source": "smart-core",
        }
    steps = []
    for idx, item in enumerate(matches[:3], start=1):
        steps.append({
            "order": idx,
            "tool_id": item["id"],
            "tool_name": item["name_ar"] if ar else item["name_en"],
            "url": item["url"],
            "why": item["description_ar"] if ar else item["description_en"],
            "input": ", ".join(item["input_ext"]) or ("بدون رفع ملف" if ar else "No upload required"),
            "output": item["output_ext"],
        })
    title = "مسار مقترح من Infinity" if ar else "Infinity suggested workflow"
    if mode == "troubleshoot":
        title = "تشخيص أولي وخطوات إصلاح" if ar else "Initial diagnosis and recovery path"
    elif mode == "next":
        title = "أفضل خطوة تالية" if ar else "Best next step"
    return {
        "title": title,
        "summary": ("بنيت هذا المسار من الأدوات الفعلية الموجودة في الموقع. فعّل Infinity AI المتقدم لتحليل أعمق عند توفره." if ar else "This path is built from the real tools available on the site. Enhanced Infinity AI can add deeper reasoning when available."),
        "steps": steps,
        "tips": [
            "ابدأ بأول خطوة فقط، ثم قيّم الناتج قبل الانتقال للخطوة التالية." if ar else "Start with the first step, then inspect the result before continuing.",
            "السياق المرسل للذكاء لا يتضمن محتوى الملف تلقائيًا." if ar else "Context sent to AI does not automatically include file contents.",
        ],
        "source": "smart-core",
    }

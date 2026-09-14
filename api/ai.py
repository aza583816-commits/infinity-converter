from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

from flask import Blueprint, jsonify, request

from core.discovery import unified_index
from core.intelligence import catalog_prompt, fallback_plan, sanitize_context
from core.limiter import limiter

ai_bp = Blueprint("ai", __name__)
logger = logging.getLogger(__name__)
_probe_cache = {"at": 0.0, "result": None}
PROBE_TTL_SECONDS = 45


def _gemini_config():
    return os.getenv("GEMINI_API_KEY", "").strip(), os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()


def _model_probe():
    """Probe the optional enhanced provider without making the site depend on it."""
    now = time.monotonic()
    cached = _probe_cache.get("result")
    if cached and now - float(_probe_cache.get("at", 0.0)) < PROBE_TTL_SECONDS:
        return dict(cached)

    key, model = _gemini_config()
    if not key:
        result = {
            "configured": False,
            "ready": True,
            "core_ready": True,
            "enhanced_ready": False,
            "message": "Infinity Smart Core is ready. Enhanced AI is not configured.",
        }
        _probe_cache.update(at=now, result=result)
        return dict(result)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("Provider response too large")
            payload = json.loads(raw.decode("utf-8"))
        supported = payload.get("supportedGenerationMethods") or []
        enhanced = "generateContent" in supported
        result = {
            "configured": True,
            "ready": True,
            "core_ready": True,
            "enhanced_ready": enhanced,
            "message": "Infinity AI is fully ready." if enhanced else "Infinity Smart Core is ready; enhanced AI is temporarily unavailable.",
        }
    except Exception as exc:  # provider outage must never disable the local smart core
        logger.warning("AI provider probe failed: %s", type(exc).__name__)
        result = {
            "configured": True,
            "ready": True,
            "core_ready": True,
            "enhanced_ready": False,
            "message": "Infinity Smart Core is ready; enhanced AI is temporarily unavailable.",
        }
    _probe_cache.update(at=now, result=result)
    return dict(result)


def _call_gemini(prompt: str, system: str = "", max_tokens: int = 1800) -> str:
    key, model = _gemini_config()
    if not key:
        raise RuntimeError("Enhanced Infinity AI is not configured.")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingLevel": "medium"},
        },
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    data = json.dumps(body).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("Provider response too large")
            payload = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("AI provider request failed with HTTP %s", exc.code)
        raise RuntimeError("Enhanced Infinity AI is temporarily unavailable.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not reach enhanced Infinity AI right now.") from exc
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Enhanced Infinity AI returned no answer.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    if not text.strip():
        raise RuntimeError("Enhanced Infinity AI returned an empty answer.")
    return text.strip()


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def _lang(payload: dict) -> str:
    requested = str(payload.get("lang", "")).strip().lower()
    if requested in {"ar", "en"}:
        return requested
    prompt = str(payload.get("prompt", ""))
    return "ar" if re.search(r"[\u0600-\u06ff]", prompt) else "en"


def _system_prompt(lang: str) -> str:
    language_rule = "Reply in Arabic." if lang == "ar" else "Reply in English."
    return (
        "You are Infinity Intelligence, the site-wide orchestration brain inside Infinity Converter. "
        "You are not a generic chatbot. You understand the current page, safe file metadata, tool options, conversion result metadata, and the complete real tool catalog. "
        "The catalog includes server conversion tools and browser-local utilities. Browser tool IDs are namespaced with browser:. "
        "Your job is to turn the user's goal into the shortest reliable workflow using ONLY tools in the catalog. "
        "Never invent a tool, URL, completed action, benchmark, guarantee, or file analysis that did not happen. "
        "Never claim to have read file contents unless the request explicitly includes text content. Metadata such as extension, MIME and size is not content. "
        "Prefer 1-3 steps. Browser-local utilities should normally be standalone steps; do not pretend their result is an uploaded file. "
        "Explain trade-offs when quality, editability, OCR, privacy, layout, or file size matter. "
        "If context contains a conversion error, diagnose it and recommend the most likely recovery path. "
        "If context contains a successful result, recommend only useful next steps, not busywork. "
        f"{language_rule}\n\nREAL INFINITY TOOL CATALOG:\n{catalog_prompt()}"
    )


def _structured_prompt(prompt: str, mode: str, context: dict, history: list, lang: str) -> str:
    schema = {
        "title": "short title",
        "summary": "2-5 sentence answer",
        "steps": [{"order": 1, "tool_id": "exact catalog id", "tool_name": "localized name", "url": "/tools/... or /browser-tools/...", "why": "why this step", "input": "expected input", "output": "expected output"}],
        "tips": ["important trade-off or quality/privacy check"],
        "questions": ["only if a missing detail materially changes the path"],
    }
    safe_history = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))[:20]
        text = str(item.get("text", ""))[:1200]
        safe_history.append({"role": role, "text": text})
    return (
        f"MODE: {mode}\n"
        f"USER GOAL: {prompt}\n"
        f"SAFE PAGE CONTEXT: {json.dumps(context, ensure_ascii=False)}\n"
        f"RECENT CONVERSATION: {json.dumps(safe_history, ensure_ascii=False)}\n\n"
        "Return ONLY valid JSON matching this shape. Do not wrap it in markdown. "
        "Every step tool_id and url must exist exactly in the catalog. If no tool is needed, steps can be empty. "
        f"SCHEMA EXAMPLE: {json.dumps(schema, ensure_ascii=False)}"
    )


def _normalize_plan(plan: dict, fallback: dict, lang: str) -> dict:
    catalog = unified_index()
    fallback_by_id = {step["tool_id"]: step for step in fallback.get("steps", [])}
    steps = []
    for raw in plan.get("steps", [])[:4]:
        if not isinstance(raw, dict):
            continue
        tool_id = str(raw.get("tool_id", ""))
        item = catalog.get(tool_id)
        if not item:
            continue
        if steps:
            previous = catalog[steps[-1]["tool_id"]]
            # Browser utilities produce UI results, not files. Do not fabricate
            # cross-tool file chaining to or from them.
            if previous["kind"] != "converter" or item["kind"] != "converter":
                return fallback
            accepted = item["input_ext"]
            if previous["output_ext"] not in accepted and not {"*", ".*"}.intersection(accepted):
                return fallback
        canonical = fallback_by_id.get(tool_id)
        url = canonical["url"] if canonical else item["url"]
        tool_name = canonical["tool_name"] if canonical else (item["name_ar"] if lang == "ar" else item["name_en"])
        steps.append({
            "order": len(steps) + 1,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "url": url,
            "why": str(raw.get("why", ""))[:600],
            "input": str(raw.get("input", ""))[:220],
            "output": str(raw.get("output", ""))[:120],
            "kind": item["kind"],
        })
    return {
        "title": str(plan.get("title") or fallback.get("title") or "Infinity")[:160],
        "summary": str(plan.get("summary") or fallback.get("summary") or "")[:2400],
        "steps": steps or fallback.get("steps", []),
        "tips": [str(x)[:600] for x in plan.get("tips", [])[:5] if str(x).strip()] or fallback.get("tips", []),
        "questions": [str(x)[:500] for x in plan.get("questions", [])[:3] if str(x).strip()],
    }


@ai_bp.get("/status")
@limiter.limit("30 per minute")
def status():
    return jsonify(_model_probe())


@ai_bp.post("/plan")
@limiter.limit("12 per minute")
def plan():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Expected a JSON object."), 400
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return jsonify(error="اكتب هدفك أولاً."), 400
    if len(prompt) > 24000:
        return jsonify(error="الطلب طويل جدًا."), 400
    mode = str(payload.get("mode", "plan")).strip().lower()[:30]
    if mode not in {"plan", "explain", "troubleshoot", "next", "optimize"}:
        mode = "plan"
    lang = _lang(payload)
    context = sanitize_context(payload.get("context") or {})
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    local = fallback_plan(prompt, context, lang=lang, mode=mode)
    key, _model = _gemini_config()
    if not key:
        local["enhanced"] = False
        return jsonify(local)
    try:
        raw = _call_gemini(_structured_prompt(prompt, mode, context, history, lang), _system_prompt(lang), max_tokens=2200)
        parsed = _extract_json(raw)
        result = _normalize_plan(parsed, local, lang)
        result["source"] = "infinity-ai"
        result["enhanced"] = True
        return jsonify(result)
    except Exception as exc:
        logger.warning("Enhanced planning fell back to Smart Core: %s", type(exc).__name__)
        local["enhanced"] = False
        local["fallback_reason"] = "enhanced_unavailable"
        return jsonify(local)


@ai_bp.post("/ask")
@limiter.limit("10 per minute")
def ask():
    """Compatibility endpoint. It now benefits from Smart Core fallback."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Expected a JSON object."), 400
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return jsonify(error="اكتب سؤالك أولاً."), 400
    if len(prompt) > 24000:
        return jsonify(error="الطلب طويل جدًا."), 400
    lang = _lang(payload)
    context = sanitize_context(payload.get("context") or {})
    local = fallback_plan(prompt, context, lang=lang, mode="plan")
    key, _model = _gemini_config()
    if key:
        try:
            raw = _call_gemini(_structured_prompt(prompt, "plan", context, [], lang), _system_prompt(lang), max_tokens=1600)
            local = _normalize_plan(_extract_json(raw), local, lang)
            enhanced = True
        except Exception:
            enhanced = False
    else:
        enhanced = False
    parts = [local["title"], local["summary"]]
    for step in local.get("steps", []):
        parts.append(f"{step['order']}. {step['tool_name']} — {step['why']} ({step['url']})")
    return jsonify(answer="\n".join(parts), enhanced=enhanced)

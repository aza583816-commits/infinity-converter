from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import logging
import time

from flask import Blueprint, jsonify, request

from core.limiter import limiter
from core.tool_registry import TOOLS, _meta_for

ai_bp = Blueprint("ai", __name__)
logger = logging.getLogger(__name__)
_probe_cache = {"at": 0.0, "result": None}
PROBE_TTL_SECONDS = 45


def _gemini_config():
    return os.getenv("GEMINI_API_KEY", "").strip(), os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()


def _model_probe():
    """Probe the configured provider while exposing only Infinity AI state to clients."""
    now = time.monotonic()
    cached = _probe_cache.get("result")
    if cached and now - float(_probe_cache.get("at", 0.0)) < PROBE_TTL_SECONDS:
        return dict(cached)

    key, model = _gemini_config()
    if not key:
        result = {"configured": False, "ready": False, "message": "Infinity AI is not configured yet."}
        _probe_cache.update(at=now, result=result)
        return dict(result)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        supported = payload.get("supportedGenerationMethods") or []
        ready = "generateContent" in supported
        result = {
            "configured": True,
            "ready": ready,
            "message": "Infinity AI is ready." if ready else "Infinity AI is temporarily unavailable.",
        }
        if not ready:
            logger.warning("Configured AI model does not support generateContent: %s", model)
    except urllib.error.HTTPError as exc:
        logger.warning("AI provider probe failed with HTTP %s for model %s", exc.code, model)
        result = {"configured": True, "ready": False, "message": "Infinity AI is temporarily unavailable."}
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("AI provider probe failed: %s", type(exc).__name__)
        result = {"configured": True, "ready": False, "message": "Infinity AI is temporarily unavailable."}

    _probe_cache.update(at=now, result=result)
    return dict(result)


def _call_gemini(prompt: str, system: str = "") -> str:
    key, model = _gemini_config()
    if not key:
        raise RuntimeError("Infinity AI is not configured on the server.")
    body = {
        "system_instruction": {"parts": [{"text": system}]} if system else None,
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1200,
            "thinkingConfig": {"thinkingLevel": "medium"},
        },
    }
    if body["system_instruction"] is None:
        body.pop("system_instruction")
    data = json.dumps(body).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403, 404, 429):
            messages = {
                400: "Infinity AI could not process that request. Try rephrasing it.",
                401: "Infinity AI is temporarily unavailable.",
                403: "Infinity AI is temporarily unavailable.",
                404: "Infinity AI is temporarily unavailable.",
                429: "Infinity AI is busy right now. Try again shortly.",
            }
            raise RuntimeError(messages[exc.code]) from exc
        logger.warning("AI provider request failed with HTTP %s", exc.code)
        raise RuntimeError("Infinity AI is temporarily unavailable.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach Infinity AI right now.") from exc
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Infinity AI returned no answer.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    if not text.strip():
        raise RuntimeError("Infinity AI returned an empty answer.")
    return text.strip()


@ai_bp.get("/status")
def status():
    result = _model_probe()
    return jsonify(result), (200 if result["ready"] else 503)


@ai_bp.post("/ask")
@limiter.limit("8 per minute")
def ask():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return jsonify(error="اكتب سؤالك أولاً."), 400
    if len(prompt) > 12000:
        return jsonify(error="الطلب طويل جدًا."), 400
    catalog = "\n".join(f"- {tool.id}: {tool.name_en} | {tool.name_ar} | /tools/{_meta_for(tool)['slug']}" for tool in TOOLS.values())
    system = (
        "You are Infinity AI, a practical file-work assistant inside Infinity Converter. "
        "Answer clearly, recommend only tools that appear in the catalog, and when the user describes a task, prefer a short workflow with concrete Infinity tool URLs. "
        "Never claim an operation happened unless it actually did, never request or reveal secrets, and reply in the user's language when obvious.\n\n"
        "Infinity Converter tool catalog:\n" + catalog
    )
    try:
        answer = _call_gemini(prompt, system)
        return jsonify(answer=answer)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503

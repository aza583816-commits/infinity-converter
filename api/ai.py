from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from flask import Blueprint, jsonify, request

from core.limiter import limiter
from core.tool_registry import TOOLS

ai_bp = Blueprint("ai", __name__)


def _gemini_config():
    return os.getenv("GEMINI_API_KEY", "").strip(), os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()


def _model_probe():
    key, model = _gemini_config()
    if not key:
        return {"configured": False, "ready": False, "model": model, "message": "Gemini API key is not configured."}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        supported = payload.get("supportedGenerationMethods") or []
        if "generateContent" not in supported:
            return {"configured": True, "ready": False, "model": model, "message": "The selected Gemini model does not support generateContent."}
        return {"configured": True, "ready": True, "model": model, "message": "Gemini is ready."}
    except urllib.error.HTTPError as exc:
        # Never expose the API key or the full provider response to the browser.
        if exc.code in (401, 403):
            message = "Gemini authentication failed. Create/use a current Google AI Studio auth key and update Railway."
        elif exc.code == 404:
            message = f"Gemini model '{model}' was not found or is unavailable to this key."
        else:
            message = f"Gemini is temporarily unavailable (HTTP {exc.code})."
        return {"configured": True, "ready": False, "model": model, "message": message}
    except (urllib.error.URLError, TimeoutError):
        return {"configured": True, "ready": False, "model": model, "message": "Could not reach Gemini right now."}
    except (ValueError, json.JSONDecodeError):
        return {"configured": True, "ready": False, "model": model, "message": "Gemini returned an unexpected response."}


def _call_gemini(prompt: str, system: str = "") -> str:
    key, model = _gemini_config()
    if not key:
        raise RuntimeError("Gemini is not configured on the server.")
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
        with urllib.request.urlopen(req, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach Gemini right now.") from exc
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no answer.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    if not text.strip():
        raise RuntimeError("Gemini returned an empty answer.")
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
    catalog = "\n".join(f"- {tool.id}: {tool.name_en} | {tool.name_ar} | /tools/{tool.slug}" for tool in TOOLS.values())
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

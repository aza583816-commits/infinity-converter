from __future__ import annotations

import math
import re

from flask import Blueprint, current_app, jsonify, request

from core.limiter import limiter

telemetry_bp = Blueprint("telemetry", __name__)

_ALLOWED_METRICS = {"LCP", "CLS", "INP", "TTFB", "FCP"}
_ALLOWED_PRODUCT_EVENTS = {
    "workspace_open",
    "workspace_inspect",
    "workspace_builder_run",
    "workspace_builder_success",
    "workspace_builder_failure",
    "workspace_preset_save",
    "workspace_queue_run",
    "workspace_queue_success",
    "workspace_queue_failure",
    "workspace_install_prompt",
}
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]{0,200}$")


@telemetry_bp.post("/api/v2/vitals")
@limiter.limit("60 per minute")
def collect_vital():
    """Record coarse Web Vitals without identifiers, filenames, prompts, or content."""
    payload = request.get_json(silent=True) or {}
    metric = str(payload.get("metric") or "").upper()
    if metric not in _ALLOWED_METRICS:
        return jsonify(error="invalid metric"), 400

    try:
        value = float(payload.get("value"))
    except (TypeError, ValueError):
        return jsonify(error="invalid value"), 400
    if not math.isfinite(value) or value < 0 or value > 600_000:
        return jsonify(error="invalid value"), 400

    path = str(payload.get("path") or "/").split("?", 1)[0]
    if not _SAFE_PATH.fullmatch(path):
        path = "/"
    device = str(payload.get("device") or "unknown").lower()
    if device not in {"mobile", "desktop", "tablet", "unknown"}:
        device = "unknown"

    # Structured key=value logging lets Railway/observability tooling aggregate
    # production performance without collecting user identity or file metadata.
    current_app.logger.info(
        "web_vital metric=%s value=%.2f path=%s device=%s",
        metric,
        value,
        path,
        device,
    )
    response = jsonify(status="accepted")
    response.headers["Cache-Control"] = "no-store, private"
    return response, 202


@telemetry_bp.post("/api/v2/product-event")
@limiter.limit("120 per minute")
def collect_product_event():
    """Record a tiny allowlisted product event without user/file identifiers.

    The endpoint intentionally rejects arbitrary properties so filenames, file
    contents, prompts, emails, account IDs, and other user data cannot be sent.
    """
    payload = request.get_json(silent=True) or {}
    event = str(payload.get("event") or "").strip().lower()
    if event not in _ALLOWED_PRODUCT_EVENTS:
        return jsonify(error="invalid event"), 400

    path = str(payload.get("path") or "/").split("?", 1)[0]
    if not _SAFE_PATH.fullmatch(path):
        path = "/"
    current_app.logger.info("product_event event=%s path=%s", event, path)
    response = jsonify(status="accepted")
    response.headers["Cache-Control"] = "no-store, private"
    return response, 202


@telemetry_bp.post("/api/v2/events")
@limiter.limit("60 per minute")
def collect_product_event():
    """Record a tiny allowlisted product event with no user/file/content fields."""
    payload = request.get_json(silent=True) or {}
    event = str(payload.get("event") or "").strip().lower()
    if event not in _ALLOWED_EVENTS:
        return jsonify(error="invalid event"), 400

    path = str(payload.get("path") or "/").split("?", 1)[0]
    if not _SAFE_PATH.fullmatch(path):
        path = "/"

    # Deliberately ignore every other client field. This endpoint never logs
    # filenames, file types/sizes, prompts, IDs, account data, or free text.
    current_app.logger.info("product_event event=%s path=%s", event, path)
    response = jsonify(status="accepted")
    response.headers["Cache-Control"] = "no-store, private"
    return response, 202

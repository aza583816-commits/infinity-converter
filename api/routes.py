from __future__ import annotations

import re
from datetime import date

from flask import Blueprint, jsonify, request, send_file, g, current_app
from werkzeug.exceptions import RequestEntityTooLarge
from flask_limiter.errors import RateLimitExceeded

from config.settings import settings
from core.limiter import limiter
from core.accounts import PLAN_LIMITS, consume_credit, get_effective_plan
from core.tooling import PREMIUM_TOOL_IDS, get_tool, list_tools
from core.tooling.runtime import runtime_coverage
from core.storage import TempWorkspace
from security.file_guard import validate_upload
from converters.dispatcher import convert
from converters.validation import OutputValidationError

api_bp = Blueprint("api", __name__)


_DANGEROUS_NESTED_REGEX = re.compile(r"\([^)]*[+*][^)]*\)\s*(?:[+*]|\{\d*,?\d*\})")


def _validated_options(tool):
    options = {}
    for field in tool.fields:
        value = request.form.get(field.id, "").strip()
        if field.required and not value:
            raise ValueError("أكمل جميع الحقول المطلوبة.")
        if len(value) > (600 if field.type == "textarea" else 160):
            raise ValueError("إحدى القيم المدخلة طويلة جدًا.")
        if field.type == "select" and value not in {choice[0] for choice in field.choices}:
            raise ValueError("خيار الأداة غير صالح.")
        if field.type == "date" and value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("صيغة التاريخ غير صالحة.") from exc
        options[field.id] = value
    return options


def _validated_param(tool) -> str:
    value = request.form.get("param", "").strip()
    if len(value) > 600:
        raise ValueError("قيمة الإعداد الإضافي طويلة جدًا.")
    if tool.id == "regex-extract":
        if len(value) > 200:
            raise ValueError("نمط Regex أطول من الحد الآمن.")
        if value and _DANGEROUS_NESTED_REGEX.search(value):
            raise ValueError("نمط Regex يحتوي على تكرار متداخل غير آمن.")
    return value


@api_bp.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error="الملف أو الطلب أكبر من الحد المسموح."), 413


@api_bp.errorhandler(RateLimitExceeded)
def too_many_requests(_):
    return jsonify(error="عدد الطلبات كبير جدًا. حاول مرة أخرى بعد قليل."), 429


@api_bp.get("/healthz")
@limiter.exempt
def healthz():
    coverage = runtime_coverage()
    payload = {
        "status": "ok" if coverage.healthy else "degraded",
        "version": settings.app_version,
        "tools": len(list_tools()),
        "architecture": coverage.as_dict(),
        "limits": {
            "max_file_mb": settings.max_file_mb,
            "max_batch_files": settings.max_batch_files,
            "max_pdf_pages": settings.max_pdf_pages,
            "max_output_mb": settings.max_output_mb,
            "max_concurrent_conversions": settings.max_concurrent_conversions,
            "max_image_pixels": settings.max_image_pixels,
        },
    }
    return jsonify(payload), (200 if coverage.healthy else 503)


@api_bp.get("/tools")
def tools():
    return jsonify({
        "version": settings.app_version,
        "runtime": runtime_coverage().as_dict(),
        "tools": list_tools(),
    })


@api_bp.post("/inspect")
@limiter.limit("30 per minute")
def inspect():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify(error="لم يتم إرفاق ملف."), 400
    try:
        result = validate_upload(
            uploaded,
            max_bytes=settings.max_file_bytes,
            inspect_only=True,
            max_pdf_pages=settings.max_pdf_pages,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@api_bp.post("/convert")
@limiter.limit("10 per minute")
def convert_route():
    tool_id = request.form.get("tool", "").strip()
    tool = get_tool(tool_id)
    if not tool:
        return jsonify(error="الأداة غير موجودة."), 404

    current_user = getattr(g, "current_user", None)
    plan = get_effective_plan(current_user["id"]) if current_user else "free"
    auth_enabled = bool(current_app.config.get("PUBLIC_AUTH_ENABLED", False))

    # Entitlement checks are dormant on today's free public product, but they
    # remain correct and testable for the future account launch. Check them
    # before upload validation so a protected operation never leaks work to an
    # anonymous/free request.
    if auth_enabled and tool.id in PREMIUM_TOOL_IDS:
        if not current_user:
            return jsonify(error="سجّل الدخول لاستخدام هذه الأداة."), 401
        if plan == "free":
            return jsonify(error="هذه الأداة تتطلب خطة Pro أو Business."), 403

    # Auth/billing remains available in code but intentionally disabled on the
    # public free product until those product switches are enabled.
    files = request.files.getlist("files")
    if not files:
        single = request.files.get("file")
        if single:
            files = [single]

    if not files and tool.input_required:
        return jsonify(error="ارفع ملفًا واحدًا على الأقل."), 400

    plan_limits = PLAN_LIMITS.get(plan, {})
    public_max_files = settings.max_batch_files if not auth_enabled else plan_limits.get("max_files", tool.max_files)
    public_max_file_mb = settings.max_file_mb if not auth_enabled else plan_limits.get("max_file_mb", settings.max_file_mb)
    max_files = min(tool.max_files, public_max_files)
    if len(files) > max_files:
        return jsonify(error=f"الحد الأقصى المسموح به هو {max_files} ملف/ملفات."), 400

    # Do not use a normal `with TempWorkspace()` here. send_file can stream
    # after the view returns, so cleanup is deferred until the response closes.
    workspace = TempWorkspace().__enter__()
    cleanup_deferred = False
    try:
        options = _validated_options(tool)
        param = _validated_param(tool)
        safe_inputs = []
        for uploaded in files:
            safe_input = validate_upload(
                uploaded,
                max_bytes=min(settings.max_file_bytes, public_max_file_mb * 1024 * 1024),
                inspect_only=False,
                workspace=workspace.path,
                max_pdf_pages=settings.max_pdf_pages,
            )
            if not safe_input.get("safe"):
                raise ValueError("تم رفض ملف لم يجتز التحقق الأمني.")
            if not workspace.contains_input(safe_input["path"]):
                raise ValueError("مسار ملف الإدخال خارج مساحة المعالجة الآمنة.")
            if safe_input.get("encrypted") and tool.id != "pdf-unlock":
                raise ValueError("ملف PDF محمي بكلمة مرور. استخدم أداة فتح قفل PDF أولًا.")
            if ".*" not in tool.input_ext and "*" not in tool.input_ext and safe_input["extension"] not in tool.input_ext:
                supported = ", ".join(tool.input_ext)
                raise ValueError(f"هذه الأداة تقبل الملفات التالية فقط: {supported}.")
            safe_inputs.append(safe_input)

        result = convert(
            tool=tool,
            safe_inputs=safe_inputs,
            workspace=workspace,
            timeout=settings.subprocess_timeout,
            max_pdf_pages=settings.max_pdf_pages,
            param=param,
            options=options,
        )
        if not workspace.contains_output(result.path):
            raise OutputValidationError("مسار الملف الناتج خارج مساحة المعالجة الآمنة.")

        response = send_file(
            result.path,
            mimetype=result.mime,
            as_attachment=True,
            download_name=result.name,
            conditional=False,
        )
        response.call_on_close(workspace.cleanup)
        cleanup_deferred = True

        if current_user:
            consume_credit(current_user["id"])
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Batch-Total"] = str(result.batch_total)
        response.headers["X-Batch-Succeeded"] = str(result.batch_succeeded)
        response.headers["X-Batch-Failed"] = str(len(result.batch_failures))
        response.headers["X-Conversion-Engine"] = result.engine
        response.headers["X-Conversion-Duration-MS"] = str(result.duration_ms)
        response.headers["X-Input-Bytes"] = str(result.input_bytes)
        response.headers["X-Output-Bytes"] = str(result.output_bytes)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response

    except OutputValidationError:
        return jsonify(error="تعذر التحقق من الملف الناتج. جرّب العملية مرة أخرى."), 500
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        return jsonify(error="تعذر إكمال التحويل. جرّب ملفًا آخر أو أعد المحاولة."), 500
    finally:
        if not cleanup_deferred:
            workspace.cleanup()

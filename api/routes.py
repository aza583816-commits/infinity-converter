from datetime import date

from flask import Blueprint, jsonify, request, send_file, g
from werkzeug.exceptions import RequestEntityTooLarge
from flask_limiter.errors import RateLimitExceeded

from config.settings import settings
from core.limiter import limiter
from core.accounts import PLAN_LIMITS, PREMIUM_TOOL_IDS, consume_credit, get_effective_plan
from core.tool_registry import get_tool, list_tools
from core.storage import TempWorkspace
from security.file_guard import validate_upload
from converters.dispatcher import convert
from converters.validation import OutputValidationError

api_bp = Blueprint("api", __name__)


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

@api_bp.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error="الملف أو الطلب أكبر من الحد المسموح."), 413

@api_bp.errorhandler(RateLimitExceeded)
def too_many_requests(_):
    return jsonify(error="عدد الطلبات كبير جدًا. حاول مرة أخرى بعد قليل."), 429

@api_bp.get("/healthz")
@limiter.exempt
def healthz():
    return jsonify(
        status="ok",
        version=settings.app_version,
        tools=len(list_tools()),
        limits={
            "max_file_mb": settings.max_file_mb,
            "max_batch_files": settings.max_batch_files,
            "max_pdf_pages": settings.max_pdf_pages,
            "max_output_mb": settings.max_output_mb,
            "max_concurrent_conversions": settings.max_concurrent_conversions,
        },
    )

@api_bp.get("/tools")
def tools():
    return jsonify({"version": settings.app_version, "tools": list_tools()})

@api_bp.post("/inspect")
@limiter.limit("30 per minute")
def inspect():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify(error="لم يتم إرفاق ملف."), 400
    try:
        result = validate_upload(uploaded, max_bytes=settings.max_file_bytes, inspect_only=True, max_pdf_pages=settings.max_pdf_pages)
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

    # إتاحة الأدوات لجميع الزوار مع الإبقاء على منطق الحسابات للمستقبل
    current_user = getattr(g, "current_user", None)
    plan = get_effective_plan(current_user["id"]) if current_user else "free"

    # تم تعطيل فحص الأدوات المدفوعة والأرصدة مؤقتاً لتسهيل الاستخدام المجاني
    # if tool_id in PREMIUM_TOOL_IDS:
    #     if not current_user:
    #         return jsonify(error="يلزم تسجيل الدخول لاستخدام هذه الأداة."), 401
    #     if plan == "free":
    #         return jsonify(error="تتطلب هذه الأداة اشتراك Pro أو Business."), 403
    # if current_user and current_user["credits_balance"] <= 0:
    #     return jsonify(error="لا توجد أرصدة متبقية. اشحن رصيدك أو جدد اشتراكك."), 402

    files = request.files.getlist("files")
    if not files:
        single = request.files.get("file")
        if single:
            files = [single]

    if not files and tool.input_required:
        return jsonify(error="ارفع ملفًا واحدًا على الأقل."), 400

    max_files = min(tool.max_files, PLAN_LIMITS.get(plan, {}).get("max_files", tool.max_files))
    if len(files) > max_files:
        return jsonify(error=f"الحد الأقصى المسموح به هو {max_files} ملف/ملفات."), 400

    with TempWorkspace() as workspace:
        safe_inputs = []
        try:
            options = _validated_options(tool)
            for uploaded in files:
                safe_input = validate_upload(
                    uploaded,
                    max_bytes=min(settings.max_file_bytes, PLAN_LIMITS.get(plan, {}).get("max_file_mb", settings.max_file_mb) * 1024 * 1024),
                    inspect_only=False,
                    workspace=workspace.path,
                    max_pdf_pages=settings.max_pdf_pages,
                )
                if safe_input["extension"] not in tool.input_ext:
                    supported = ", ".join(tool.input_ext)
                    raise ValueError(f"هذه الأداة تقبل الملفات التالية فقط: {supported}.")
                safe_inputs.append(safe_input)

            result = convert(
                tool=tool,
                safe_inputs=safe_inputs,
                workspace=workspace,
                timeout=settings.subprocess_timeout,
                max_pdf_pages=settings.max_pdf_pages,
                param=request.form.get("param", ""),
                options=options,
            )
            response = send_file(
                result.path, mimetype=result.mime, as_attachment=True, download_name=result.name
            )
            if current_user:
                consume_credit(current_user["id"])
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Batch-Total"] = str(result.batch_total)
            response.headers["X-Batch-Succeeded"] = str(result.batch_succeeded)
            response.headers["X-Batch-Failed"] = str(len(result.batch_failures))
            response.headers["X-Conversion-Engine"] = result.engine
            response.headers["X-Request-ID"] = getattr(g, "request_id", "")
            return response

        except OutputValidationError:
            return jsonify(error="تعذر التحقق من الملف الناتج. جرّب العملية مرة أخرى."), 500
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            return jsonify(error="تعذر إكمال التحويل. جرّب ملفًا آخر أو أعد المحاولة."), 500

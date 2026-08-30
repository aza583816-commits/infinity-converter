from flask import Blueprint, jsonify, request, send_file, g
from werkzeug.exceptions import RequestEntityTooLarge
from flask_limiter.errors import RateLimitExceeded

from config.settings import settings
from core.limiter import limiter
from core.tool_registry import get_tool, list_tools
from core.storage import TempWorkspace
from security.file_guard import validate_upload
from converters.dispatcher import convert
from converters.validation import OutputValidationError

api_bp = Blueprint("api", __name__)

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

    files = request.files.getlist("files")
    if not files:
        single = request.files.get("file")
        if single:
            files = [single]

    if not files:
        return jsonify(error="ارفع ملفًا واحدًا على الأقل."), 400

    if len(files) > tool.max_files:
        return jsonify(error=f"الأداة تسمح بحد أقصى {tool.max_files} ملف/ملفات."), 400

    with TempWorkspace() as workspace:
        safe_inputs = []
        try:
            for uploaded in files:
                safe_input = validate_upload(
                    uploaded,
                    max_bytes=settings.max_file_bytes,
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
            )
            response = send_file(
                result.path, mimetype=result.mime, as_attachment=True, download_name=result.name
            )
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
        except Exception as exc:
            # Do not leak converter internals to users.
            return jsonify(error="تعذر إكمال التحويل. جرّب ملفًا آخر أو أعد المحاولة."), 500

from flask import Blueprint, jsonify, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from config.settings import settings
from core.tool_registry import get_tool, list_tools
from core.storage import TempWorkspace
from security.file_guard import validate_upload
from converters.dispatcher import convert
from converters.validation import OutputValidationError

api_bp = Blueprint("api", __name__)

@api_bp.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error="الملف أو الطلب أكبر من الحد المسموح."), 413

@api_bp.get("/healthz")
def healthz():
    return jsonify(status="ok", version="2.0.0")

@api_bp.get("/tools")
def tools():
    return jsonify({"version": "2.0.0", "tools": list_tools()})

@api_bp.post("/inspect")
def inspect():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify(error="لم يتم إرفاق ملف."), 400
    try:
        result = validate_upload(uploaded, max_bytes=settings.max_file_bytes, inspect_only=True)
        return jsonify(result)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

@api_bp.post("/convert")
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
                )
                if safe_input["extension"] not in tool.input_ext:
                    supported = ", ".join(tool.input_ext)
                    raise ValueError(f"هذه الأداة تقبل الملفات التالية فقط: {supported}.")
                safe_inputs.append(safe_input)

            output_path, output_name, mime = convert(
                tool=tool,
                safe_inputs=safe_inputs,
                workspace=workspace,
                timeout=settings.subprocess_timeout,
                max_pdf_pages=settings.max_pdf_pages,
            )
            return send_file(output_path, mimetype=mime, as_attachment=True, download_name=output_name)

        except OutputValidationError:
            return jsonify(error="تعذر التحقق من الملف الناتج. جرّب العملية مرة أخرى."), 500
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception as exc:
            # Do not leak converter internals to users.
            return jsonify(error="تعذر إكمال التحويل. جرّب ملفًا آخر أو أعد المحاولة."), 500

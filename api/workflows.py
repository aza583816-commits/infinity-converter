from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, current_app, g, jsonify, render_template, request, send_file
from werkzeug.wsgi import ClosingIterator

from config.settings import settings
from converters.dispatcher import convert
from converters.validation import OutputValidationError
from core.accounts import PLAN_LIMITS, consume_credit, get_effective_plan
from core.limiter import limiter
from core.storage import TempWorkspace
from core.tooling import PREMIUM_TOOL_IDS, get_tool
from core.workflows import get_workflow, public_workflows
from security.file_guard import validate_upload

workflow_bp = Blueprint("workflows", __name__)


class _PathUpload:
    """File-like adapter used to re-validate an intermediate workflow artifact."""

    def __init__(self, path: Path, mimetype: str):
        self.path = Path(path)
        self.filename = self.path.name
        self.mimetype = mimetype or "application/octet-stream"
        self._handle = self.path.open("rb")

    def read(self, size: int = -1):
        return self._handle.read(size)

    def close(self):
        self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def _defaults_for(tool):
    options = {}
    for field in tool.fields:
        value = field.default or ""
        if field.required and not value:
            raise ValueError(f"Workflow step {tool.id} requires an interactive option.")
        options[field.id] = value
    if tool.param_field and not tool.param_default:
        raise ValueError(f"Workflow step {tool.id} requires an interactive parameter.")
    return tool.param_default or "", options


def _accepts(tool, extension: str) -> bool:
    allowed = {value.lower() for value in tool.input_ext}
    return extension.lower() in allowed or "*" in allowed or ".*" in allowed


def _dynamic_recipe(raw_steps: str):
    """Validate an AI-proposed converter chain against the real server registry.

    Only existing converter tools with safe non-interactive defaults can enter
    this execution path. Compatibility is checked between every handoff.
    """
    try:
        steps = json.loads(raw_steps or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("خطة Infinity غير صالحة.") from exc
    if not isinstance(steps, list) or not 1 <= len(steps) <= 4:
        raise ValueError("خطة Infinity يجب أن تحتوي من خطوة إلى أربع خطوات.")
    normalized: list[str] = []
    previous = None
    for raw in steps:
        tool_id = str(raw or "").strip()
        if not tool_id or tool_id.startswith("browser:"):
            raise ValueError("الخطة تحتوي على خطوة غير قابلة للتنفيذ على الملفات.")
        tool = get_tool(tool_id)
        if tool is None:
            raise ValueError("الخطة تشير إلى أداة غير متاحة.")
        _defaults_for(tool)
        if previous is not None:
            produced = (previous.output_ext or "").lower()
            accepted = {value.lower() for value in tool.input_ext}
            if produced not in accepted and "*" not in accepted and ".*" not in accepted:
                raise ValueError("خطوات الخطة غير متوافقة مع بعضها.")
        normalized.append(tool.id)
        previous = tool
    return SimpleNamespace(id="smart-plan", steps=tuple(normalized))


def _entitled(recipe, current_user, plan: str, auth_enabled: bool) -> tuple[bool, int, str | None]:
    if not auth_enabled:
        return True, 200, None
    for tool_id in recipe.steps:
        if tool_id not in PREMIUM_TOOL_IDS:
            continue
        if not current_user:
            return False, 401, "سجّل الدخول لتشغيل هذا المسار."
        if plan == "free":
            return False, 403, "هذا المسار يحتوي على أداة تتطلب خطة Pro أو Business."
    return True, 200, None


@workflow_bp.get("/workflows")
def workflows_page():
    return render_template("workflows.html", workflows=public_workflows())


@workflow_bp.get("/api/v2/workflows")
def workflow_catalog():
    return jsonify({"workflows": public_workflows()})


@workflow_bp.post("/api/v2/workflows/execute")
@limiter.limit("3 per minute")
def execute_workflow():
    workflow_id = (request.form.get("workflow") or "").strip()
    if workflow_id:
        recipe = get_workflow(workflow_id)
        if recipe is None:
            return jsonify(error="مسار العمل غير موجود."), 404
    else:
        try:
            recipe = _dynamic_recipe(request.form.get("steps") or "")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify(error="ارفع ملفًا واحدًا لبدء المسار."), 400

    current_user = getattr(g, "current_user", None)
    plan = get_effective_plan(current_user["id"]) if current_user else "free"
    auth_enabled = bool(current_app.config.get("PUBLIC_AUTH_ENABLED", False))
    allowed, status, error = _entitled(recipe, current_user, plan, auth_enabled)
    if not allowed:
        return jsonify(error=error), status

    plan_limits = PLAN_LIMITS.get(plan, {})
    public_max_file_mb = settings.max_file_mb if not auth_enabled else plan_limits.get("max_file_mb", settings.max_file_mb)
    max_bytes = min(settings.max_file_bytes, int(public_max_file_mb) * 1024 * 1024)

    workspace = TempWorkspace().__enter__()
    cleanup_deferred = False
    completed_steps: list[str] = []
    try:
        first_tool = get_tool(recipe.steps[0])
        if first_tool is None:
            raise RuntimeError("تعذر تحميل أول خطوة في المسار.")
        safe_input = validate_upload(
            uploaded,
            max_bytes=max_bytes,
            inspect_only=False,
            workspace=workspace.path,
            max_pdf_pages=settings.max_pdf_pages,
        )
        if not _accepts(first_tool, safe_input["extension"]):
            raise ValueError("نوع الملف لا يناسب أول خطوة في هذا المسار.")

        final_result = None
        for index, tool_id in enumerate(recipe.steps):
            tool = get_tool(tool_id)
            if tool is None:
                raise RuntimeError("إحدى خطوات المسار غير متاحة.")
            if not _accepts(tool, safe_input["extension"]):
                raise ValueError(f"الناتج الوسيط لا يناسب الخطوة {index + 1}.")

            param, options = _defaults_for(tool)
            result = convert(
                tool=tool,
                safe_inputs=[safe_input],
                workspace=workspace,
                timeout=settings.subprocess_timeout,
                max_pdf_pages=settings.max_pdf_pages,
                param=param,
                options=options,
            )
            completed_steps.append(tool_id)
            final_result = result

            if index == len(recipe.steps) - 1:
                break

            next_workspace = TempWorkspace().__enter__()
            try:
                with _PathUpload(result.path, result.mime) as intermediate:
                    next_safe = validate_upload(
                        intermediate,
                        max_bytes=settings.max_output_bytes,
                        inspect_only=False,
                        workspace=next_workspace.path,
                        max_pdf_pages=settings.max_pdf_pages,
                    )
            except Exception:
                next_workspace.cleanup()
                raise

            workspace.cleanup()
            workspace = next_workspace
            safe_input = next_safe

        if final_result is None:
            raise RuntimeError("لم ينتج المسار ملفًا نهائيًا.")

        response = send_file(
            final_result.path,
            mimetype=final_result.mime,
            as_attachment=True,
            download_name=final_result.name,
            conditional=False,
        )
        response.response = ClosingIterator(response.response, workspace.cleanup)
        response.call_on_close(workspace.cleanup)
        cleanup_deferred = True
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Workflow-ID"] = recipe.id
        response.headers["X-Workflow-Steps"] = str(len(completed_steps))
        response.headers["X-Workflow-Completed"] = ",".join(completed_steps)
        response.headers["X-Conversion-Engine"] = final_result.engine
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if current_user:
            consume_credit(current_user["id"])
        return response
    except OutputValidationError:
        return jsonify(error="تعذر التحقق من ناتج إحدى خطوات المسار."), 500
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        current_app.logger.exception("workflow_failed id=%s steps=%s", recipe.id, completed_steps)
        return jsonify(error="تعذر إكمال مسار العمل. جرّب ملفًا آخر أو استخدم الأدوات خطوة بخطوة."), 500
    finally:
        if not cleanup_deferred:
            workspace.cleanup()

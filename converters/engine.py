from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from config.settings import settings
from converters import archive
from converters.contracts import ConversionBusyError, ConversionResult, Operation
from converters.operations import get_operation
from converters.validation import MIME_BY_EXTENSION, OutputValidationError, validate_output
from core.admission import AdmissionToken, acquire_slot

logger = logging.getLogger(__name__)
_UNSAFE_NAME_CHARS = '\\/:*?"<>|'


def workload_class(operation: Operation) -> str:
    engine = (operation.engine or "").lower()
    if "libreoffice" in engine:
        return "office"
    if "tesseract" in engine:
        return "ocr"
    return "default"


def _acquire_required_slot(name: str, slots: int, timeout: int, message: str) -> AdmissionToken:
    token = acquire_slot(name, slots, timeout)
    if token is None:
        raise ConversionBusyError(message)
    return token


def _acquire_workload_limit(operation: Operation, timeout: int) -> AdmissionToken | None:
    kind = workload_class(operation)
    if kind == "office":
        return _acquire_required_slot(
            "office",
            settings.max_concurrent_office,
            timeout,
            "هذا النوع من التحويلات مشغول حاليًا. حاول مرة أخرى بعد قليل.",
        )
    if kind == "ocr":
        return _acquire_required_slot(
            "ocr",
            settings.max_concurrent_ocr,
            timeout,
            "هذا النوع من التحويلات مشغول حاليًا. حاول مرة أخرى بعد قليل.",
        )
    return None


def _safe_stem(filename: str) -> str:
    stem = Path(filename or "file").stem.strip()
    cleaned = "".join(ch for ch in stem if ch not in _UNSAFE_NAME_CHARS).strip()
    return (cleaned or "file")[:80]


def _unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while f"{stem}-{counter}{suffix}" in used:
        counter += 1
    unique = f"{stem}-{counter}{suffix}"
    used.add(unique)
    return unique


def _safe_input_paths(safe_inputs: list[dict], workspace) -> None:
    for item in safe_inputs:
        if not item.get("safe"):
            raise ValueError("تم رفض ملف لم يجتز التحقق الأمني.")
        path = Path(item.get("path", ""))
        if not workspace.contains_input(path):
            raise ValueError("مسار ملف الإدخال خارج مساحة المعالجة الآمنة.")
        if path.is_symlink() or not path.exists() or not path.is_file():
            raise ValueError("ملف الإدخال الآمن لم يعد متاحًا للمعالجة.")


def _artifact_guard(path: Path, mime: str, workspace) -> dict:
    path = Path(path)
    if not workspace.contains_output(path):
        raise OutputValidationError("مسار الملف الناتج خارج مساحة المعالجة الآمنة.")
    if path.is_symlink() or not path.exists() or not path.is_file():
        raise OutputValidationError("محرك التحويل لم يُنتج ملفًا عاديًا صالحًا.")
    if path.stat().st_size <= 0:
        raise OutputValidationError("محرك التحويل أنتج ملفًا فارغًا.")
    if path.stat().st_size > settings.max_output_bytes:
        raise OutputValidationError("حجم الملف الناتج يتجاوز الحد الآمن.")
    if mime == "application/octet-stream":
        return {"bytes": path.stat().st_size, "generic": True}
    return validate_output(
        path,
        expected_extension=path.suffix,
        expected_mime=mime,
        max_bytes=settings.max_output_bytes,
    )


def _declared_output_guard(path: Path, mime: str, tool, *, batch_container: bool = False) -> None:
    if batch_container:
        if path.suffix.lower() != ".zip" or mime != "application/zip":
            raise OutputValidationError("حاوية نتائج الدفعة لا تطابق عقد التنزيل الآمن.")
        return
    declared = (tool.output_ext or "").lower()
    if declared and not path.name.lower().endswith(declared):
        raise OutputValidationError("الملف الناتج لا يطابق امتداد الأداة المعلن.")
    expected_mime = MIME_BY_EXTENSION.get(declared)
    if expected_mime and mime != expected_mime:
        raise OutputValidationError("نوع الملف الناتج لا يطابق عقد الأداة المعلن.")


class ConversionEngine:
    """Generic orchestrator over the declarative backend operation registry."""

    def convert(self, *, tool, safe_inputs, workspace, timeout, max_pdf_pages, param="", options=None) -> ConversionResult:
        operation = get_operation(tool.id)
        if operation is None:
            raise ValueError("هذه الأداة لم تُوصل بمحرك التحويل بعد.")
        if workspace.path is None or workspace.output_dir is None:
            raise RuntimeError("مساحة المعالجة غير مهيأة.")

        # This gate is process-shared on Linux, so multiplying Gunicorn web
        # workers does not accidentally multiply expensive conversion capacity.
        conversion_slot = _acquire_required_slot(
            "conversion",
            settings.max_concurrent_conversions,
            timeout,
            "عدد عمليات التحويل الحالية تجاوز الحد المؤقت.",
        )
        workload_limit = None
        started = time.perf_counter()
        options = options or {}
        input_bytes = sum(int(item.get("size_bytes", 0)) for item in safe_inputs)
        try:
            workload_limit = _acquire_workload_limit(operation, timeout)
            _safe_input_paths(safe_inputs, workspace)
            output_dir = workspace.output_dir

            if operation.mode == "single":
                output, mime, details, batch_total, batch_succeeded, batch_failures = self._run_single(
                    operation, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, workspace
                )
            else:
                output, mime = operation.handler(
                    safe_inputs, output_dir, param, timeout, max_pdf_pages, options
                )
                details = _artifact_guard(output, mime, workspace)
                if operation.mode == "combine":
                    batch_total = len(safe_inputs)
                    batch_succeeded = len(safe_inputs)
                else:
                    batch_total = 0
                    batch_succeeded = 0
                batch_failures = []

            is_batch_container = operation.mode == "single" and output.name == "InfinityConverter-Batch.zip"
            _declared_output_guard(output, mime, tool, batch_container=is_batch_container)

            duration_ms = round((time.perf_counter() - started) * 1000)
            output_bytes = output.stat().st_size
            logger.info(
                "conversion_completed tool=%s engine=%s workload=%s duration_ms=%s input_bytes=%s output_bytes=%s batch_total=%s batch_succeeded=%s",
                tool.id, operation.engine, workload_class(operation), duration_ms, input_bytes, output_bytes,
                batch_total, batch_succeeded,
            )
            return ConversionResult(
                path=output,
                name=output.name,
                mime=mime,
                engine=operation.engine,
                duration_ms=duration_ms,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                details=details,
                batch_total=batch_total,
                batch_succeeded=batch_succeeded,
                batch_failures=tuple(batch_failures),
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.warning(
                "conversion_failed tool=%s engine=%s workload=%s duration_ms=%s input_bytes=%s error=%s",
                tool.id, operation.engine, workload_class(operation), duration_ms, input_bytes, type(exc).__name__,
            )
            raise
        finally:
            if workload_limit is not None:
                workload_limit.release()
            conversion_slot.release()

    @staticmethod
    def _run_single(operation: Operation, safe_inputs, output_dir, param, timeout, max_pdf_pages, options, workspace):
        outputs: list[tuple[Path, str, str]] = []
        failures: list[tuple[str, str]] = []
        succeeded_inputs = 0

        for index, safe_input in enumerate(safe_inputs):
            item_dir = output_dir / f"item-{index}"
            item_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                produced = operation.handler(
                    safe_input, item_dir, param, timeout, max_pdf_pages, options
                )
                if not produced:
                    raise ValueError("تعذر إنتاج ملف لهذا الإدخال.")
                item_outputs = []
                for path, mime in produced:
                    _artifact_guard(path, mime, workspace)
                    if not operation.force_zip:
                        from core.tooling import TOOLS
                        _declared_output_guard(Path(path), mime, TOOLS[operation.id])
                    item_outputs.append((Path(path), mime, safe_input["filename"]))
                outputs.extend(item_outputs)
                succeeded_inputs += 1
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else "تعذرت معالجة هذا الملف."
                failures.append((safe_input["filename"], message))

        if not outputs:
            raise ValueError(failures[0][1] if failures else "تعذر إنتاج أي ملف.")

        already_packaged = len(outputs) == 1 and outputs[0][1] == "application/zip"
        if len(outputs) == 1 and not failures and (not operation.force_zip or already_packaged):
            path, mime, _source_name = outputs[0]
            details = _artifact_guard(path, mime, workspace)
            return path, mime, details, 1, 1, []

        used_names: set[str] = set()
        entries: list[tuple[Path, str]] = []
        multi_source = len({name for _, _, name in outputs}) > 1
        for path, _mime, source_name in outputs:
            base = f"{_safe_stem(source_name)}-{path.name}" if multi_source else path.name
            entries.append((path, _unique_name(base, used_names)))

        if failures:
            report = {
                "succeeded": succeeded_inputs,
                "failed": [{"file": name, "error": message} for name, message in failures],
            }
            report_path = output_dir / "batch-report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            _artifact_guard(report_path, "application/json", workspace)
            entries.append((report_path, "batch-report.json"))

        zip_path = output_dir / "InfinityConverter-Batch.zip"
        archive.create_zip(entries, zip_path)
        details = _artifact_guard(zip_path, "application/zip", workspace)
        total = len(safe_inputs)
        return zip_path, "application/zip", details, total, succeeded_inputs, [name for name, _ in failures]

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings
from converters.images import convert_image
from converters.office import office_to_pdf
from converters.pdf import merge_pdfs, split_pdf
from converters.validation import validate_output


logger = logging.getLogger(__name__)
CONVERSION_LIMIT = threading.BoundedSemaphore(settings.max_concurrent_conversions)


@dataclass(frozen=True)
class ConversionResult:
    path: Path
    name: str
    mime: str
    engine: str
    duration_ms: int
    input_bytes: int
    output_bytes: int
    details: dict


class ConversionEngine:
    """Selects a specialized local engine and validates its output."""

    def convert(self, *, tool, safe_inputs, workspace, timeout, max_pdf_pages) -> ConversionResult:
        if not CONVERSION_LIMIT.acquire(timeout=timeout):
            raise RuntimeError("عدد عمليات التحويل الحالية تجاوز الحد المؤقت.")
        started = time.perf_counter()
        input_bytes = sum(item["size_bytes"] for item in safe_inputs)
        engine = self._engine_name(tool.id)
        try:
            output, mime = self._run(
                tool.id,
                [item["path"] for item in safe_inputs],
                workspace.path,
                timeout,
                max_pdf_pages,
            )
            details = validate_output(
                output,
                expected_extension=tool.output_ext,
                expected_mime=mime,
            )
            duration_ms = round((time.perf_counter() - started) * 1000)
            output_bytes = output.stat().st_size
            logger.info(
                "conversion_completed tool=%s engine=%s duration_ms=%s input_bytes=%s output_bytes=%s",
                tool.id,
                engine,
                duration_ms,
                input_bytes,
                output_bytes,
            )
            return ConversionResult(
                path=output,
                name=output.name,
                mime=mime,
                engine=engine,
                duration_ms=duration_ms,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                details=details,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.warning(
                "conversion_failed tool=%s engine=%s duration_ms=%s input_bytes=%s error=%s",
                tool.id,
                engine,
                duration_ms,
                input_bytes,
                type(exc).__name__,
            )
            raise
        finally:
            CONVERSION_LIMIT.release()

    @staticmethod
    def _engine_name(tool_id: str) -> str:
        if tool_id.startswith("pdf-"):
            return "pypdf"
        if tool_id.startswith("image-"):
            return "pillow"
        if tool_id.endswith("-to-pdf"):
            return "libreoffice"
        return "unknown"

    @staticmethod
    def _run(tool_id, paths, workspace_path, timeout, max_pdf_pages):
        output_dir = workspace_path / "output"
        if tool_id == "pdf-merge":
            output = output_dir / "InfinityConverter-Merged.pdf"
            merge_pdfs(paths, output)
            return output, "application/pdf"
        if tool_id == "pdf-split":
            output = output_dir / "InfinityConverter-Split.pdf"
            split_pdf(paths[0], output, max_pages=max_pdf_pages)
            return output, "application/pdf"
        if tool_id == "image-to-jpg":
            output = output_dir / "InfinityConverter.jpg"
            convert_image(paths[0], output, "JPEG")
            return output, "image/jpeg"
        if tool_id == "image-to-png":
            output = output_dir / "InfinityConverter.png"
            convert_image(paths[0], output, "PNG")
            return output, "image/png"
        if tool_id in {"word-to-pdf", "excel-to-pdf", "ppt-to-pdf"}:
            return office_to_pdf(paths[0], output_dir, timeout=timeout), "application/pdf"
        raise ValueError("هذه الأداة لم تُوصل بمحرك التحويل بعد.")

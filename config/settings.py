import os
import re
from dataclasses import dataclass, field


def _csv(name: str, default: str):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _int(name: str, default: int, minimum: int = 0):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


_ADSENSE_ID = re.compile(r"^(?:ca-)?pub-(\d{16})$")


def adsense_client_id(value: str | None = None) -> str:
    """Normalize either Google publisher form to the browser-facing client ID."""
    raw = (os.getenv("ADSENSE_CLIENT_ID", "") if value is None else value).strip()
    match = _ADSENSE_ID.fullmatch(raw)
    return f"ca-pub-{match.group(1)}" if match else ""


def adsense_publisher_id(value: str | None = None) -> str:
    """Return the strictly validated pub-* form required by ads.txt."""
    client_id = adsense_client_id(value)
    return client_id[3:] if client_id else ""


@dataclass(frozen=True)
class Settings:
    debug: bool = os.getenv("DEBUG", "0") == "1"
    max_file_mb: int = _int("MAX_FILE_MB", 200, 1)
    max_total_upload_mb: int = _int("MAX_TOTAL_UPLOAD_MB", 200, 1)
    max_batch_files: int = _int("MAX_BATCH_FILES", 20, 1)
    max_pdf_pages: int = _int("MAX_PDF_PAGES", 1000, 1)
    max_output_mb: int = _int("MAX_OUTPUT_MB", 200, 1)
    max_ocr_pages: int = _int("MAX_OCR_PAGES", 25, 1)
    max_image_pixels: int = _int("MAX_IMAGE_PIXELS", 80_000_000, 1_000_000)
    subprocess_timeout: int = _int("SUBPROCESS_TIMEOUT", 180, 5)
    ocr_timeout_seconds: int = _int("OCR_TIMEOUT_SECONDS", 60, 5)
    max_concurrent_conversions: int = _int("MAX_CONCURRENT_CONVERSIONS", 2, 1)
    # Native renderers are materially heavier than text/hash utilities. Keep
    # separate gates so a burst of Office/OCR work cannot consume every
    # conversion slot or trigger avoidable memory pressure inside one web pod.
    max_concurrent_office: int = _int("MAX_CONCURRENT_OFFICE", 1, 1)
    max_concurrent_ocr: int = _int("MAX_CONCURRENT_OCR", 1, 1)
    asset_cache_seconds: int = _int("ASSET_CACHE_SECONDS", 86400, 0)
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "https://infinityconverter.com").rstrip("/")
    allowed_origins: list[str] = field(default_factory=lambda: _csv(
        "ALLOWED_ORIGINS",
        "https://infinityconverter.com,https://www.infinityconverter.com"
    ))
    app_version: str = os.getenv("APP_VERSION", "7.2.2")
    max_archive_entries: int = _int("MAX_ARCHIVE_ENTRIES", 2000, 1)
    max_archive_uncompressed_mb: int = _int("MAX_ARCHIVE_UNCOMPRESSED_MB", 300, 1)
    max_archive_ratio: int = _int("MAX_ARCHIVE_RATIO", 150, 1)
    request_timeout_seconds: int = _int("REQUEST_TIMEOUT_SECONDS", 210, 5)

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def max_output_bytes(self) -> int:
        return self.max_output_mb * 1024 * 1024

    @property
    def max_archive_uncompressed_bytes(self) -> int:
        return self.max_archive_uncompressed_mb * 1024 * 1024

    @property
    def max_request_bytes(self) -> int:
        return self.max_total_upload_mb * 1024 * 1024


settings = Settings()

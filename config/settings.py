import os
from dataclasses import dataclass, field

def _csv(name: str, default: str):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

@dataclass(frozen=True)
class Settings:
    debug: bool = os.getenv("DEBUG", "0") == "1"
    max_file_mb: int = int(os.getenv("MAX_FILE_MB", "25"))
    max_batch_files: int = int(os.getenv("MAX_BATCH_FILES", "20"))
    max_pdf_pages: int = int(os.getenv("MAX_PDF_PAGES", "1000"))
    max_ocr_pages: int = int(os.getenv("MAX_OCR_PAGES", "25"))
    subprocess_timeout: int = int(os.getenv("SUBPROCESS_TIMEOUT", "180"))
    max_concurrent_conversions: int = int(os.getenv("MAX_CONCURRENT_CONVERSIONS", "2"))
    asset_cache_seconds: int = int(os.getenv("ASSET_CACHE_SECONDS", "86400"))
    allowed_origins: list[str] = field(default_factory=lambda: _csv(
        "ALLOWED_ORIGINS",
        "https://infinityconverter.com,https://www.infinityconverter.com"
    ))

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def max_request_bytes(self) -> int:
        return self.max_file_bytes * self.max_batch_files + 2 * 1024 * 1024

settings = Settings()

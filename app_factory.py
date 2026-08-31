import os
import json
import secrets
import uuid
import logging
from flask import Flask, g, request
from flask_compress import Compress
from flask_cors import CORS

from config.settings import settings
from core.limiter import limiter
from i18n import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES, resolve_language, translator
from i18n.translations import INFO_CONTENT, TRANSLATIONS
from api.routes import api_bp
from api.pages import pages_bp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", secrets.token_hex(32)),
        MAX_CONTENT_LENGTH=settings.max_request_bytes,
        JSON_SORT_KEYS=False,
        SEND_FILE_MAX_AGE_DEFAULT=settings.asset_cache_seconds,
    )

    Compress(app)
    limiter.init_app(app)
    # CORS only applies to the JSON API; page routes stay same-origin only.
    CORS(app, resources={r"/api/v2/*": {"origins": settings.allowed_origins}})

    @app.before_request
    def resolve_locale():
        g.request_id = request.headers.get("X-Request-ID", "")[:80] or uuid.uuid4().hex
        g.request_started = __import__("time").perf_counter()
        g.csp_nonce = secrets.token_urlsafe(18)
        lang, is_explicit = resolve_language(request)
        g.lang = lang
        g.lang_is_explicit = is_explicit

    @app.context_processor
    def inject_i18n():
        lang = getattr(g, "lang", "ar")
        js_strings = {
            key: value
            for key, value in TRANSLATIONS.get(lang, TRANSLATIONS["ar"]).items()
            if key.startswith("js.")
        }
        return {
            "lang": lang,
            "t": translator(lang),
            "supported_languages": SUPPORTED_LANGUAGES,
            "info_content": INFO_CONTENT,
            "i18n_json": json.dumps(js_strings, ensure_ascii=False),
            "max_file_mb": settings.max_file_mb,
            "public_base_url": settings.public_base_url,
            "csp_nonce": getattr(g, "csp_nonce", ""),
        }

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "connect-src 'self'; "
            f"script-src 'self' 'nonce-{g.csp_nonce}'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if request.path.startswith("/api/v2/convert"):
            response.headers["Cache-Control"] = "no-store, private"

        if getattr(g, "lang_is_explicit", False):
            response.set_cookie(
                LANGUAGE_COOKIE,
                g.lang,
                max_age=31536000,
                samesite="Lax",
                secure=not settings.debug,
            )

        return response

    app.register_blueprint(api_bp, url_prefix="/api/v2")
    app.register_blueprint(pages_bp)

    return app

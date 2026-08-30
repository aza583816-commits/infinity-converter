import os
import json
from flask import Flask, g, request
from flask_compress import Compress
from flask_cors import CORS

from config.settings import settings
from core.limiter import limiter
from i18n import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES, resolve_language, translator
from i18n.translations import INFO_CONTENT, TRANSLATIONS
from api.routes import api_bp
from api.pages import pages_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    app.config.update(
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
        }

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

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

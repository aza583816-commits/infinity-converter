import os
import json
import secrets
import uuid
import logging
from flask import Flask, current_app, g, request, session
from flask_compress import Compress
from flask_cors import CORS

from config.settings import settings
from core.limiter import limiter
from core.accounts import PLAN_LIMITS, csrf_token, ensure_account_tables, get_effective_plan, get_user
from core.tool_registry import PREMIUM_TOOL_IDS, TOOLS
from i18n import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES, resolve_language, translator
from i18n.translations import INFO_CONTENT, TRANSLATIONS
from api.routes import api_bp
from api.pages import pages_bp
from api.paddle import paddle_bp
from api.ai import ai_bp

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
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not settings.debug,
        # Product switches: keep auth/billing code deployed but hidden until ready.
        PUBLIC_AUTH_ENABLED=os.getenv("PUBLIC_AUTH_ENABLED", "0") == "1",
        PUBLIC_BILLING_ENABLED=os.getenv("PUBLIC_BILLING_ENABLED", "0") == "1",
    )

    Compress(app)
    limiter.init_app(app)
    ensure_account_tables()
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
        g.current_user = get_user(session.get("user_id"))
        if session.get("user_id") and not g.current_user:
            session.clear()

    @app.context_processor
    def inject_i18n():
        lang = getattr(g, "lang", "ar")
        current_user = getattr(g, "current_user", None)
        current_plan = get_effective_plan(current_user["id"]) if current_user else "free"
        public_auth_enabled = bool(current_app.config.get("PUBLIC_AUTH_ENABLED", False))
        public_billing_enabled = bool(current_app.config.get("PUBLIC_BILLING_ENABLED", False))
        public_max_file_mb = settings.max_file_mb if not public_auth_enabled else min(settings.max_file_mb, PLAN_LIMITS[current_plan]["max_file_mb"])
        public_max_files = settings.max_batch_files if not public_auth_enabled else min(settings.max_batch_files, PLAN_LIMITS[current_plan]["max_files"])
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
            "current_user": current_user,
            "current_plan": current_plan,
            "plan_max_file_mb": public_max_file_mb,
            "plan_max_files": public_max_files,
            "public_auth_enabled": public_auth_enabled,
            "public_billing_enabled": public_billing_enabled,
            "gemini_enabled": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            "adsense_client_id": os.getenv("ADSENSE_CLIENT_ID", "").strip(),
            "google_site_verification": os.getenv("GOOGLE_SITE_VERIFICATION", "").strip(),
            "organization_schema": {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "Infinity Converter",
                "url": settings.public_base_url,
                "logo": f"{settings.public_base_url}/static/icon-512.png?v=6.0.1",
                "description": "Free and privacy-first tools for PDF, documents, images, OCR, archives, and everyday file tasks.",
            },
            "tool_count": len(TOOLS),
            "app_version": settings.app_version,
            "csrf_token": csrf_token(),
            "premium_tool_ids": PREMIUM_TOOL_IDS,
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

        adsense_enabled = bool(os.getenv("ADSENSE_CLIENT_ID", "").strip())
        nonce = getattr(g, "csp_nonce", "")
        connect_src = "connect-src 'self' https://*.paddle.com"
        frame_src = "frame-src https://*.paddle.com"
        if adsense_enabled:
            # Google documents a nonce + strict-dynamic CSP for AdSense because its
            # resource domains can change over time. All template scripts carry the same nonce.
            script_src = f"script-src 'nonce-{nonce}' 'strict-dynamic' https: http:"
            connect_src += " https://pagead2.googlesyndication.com https://googleads.g.doubleclick.net"
            frame_src += " https://googleads.g.doubleclick.net"
            base_uri = "base-uri 'none'"
            object_src = "object-src 'none'"
        else:
            script_src = f"script-src 'self' 'nonce-{nonce}' https://cdn.paddle.com"
            base_uri = "base-uri 'self'"
            object_src = "object-src 'none'"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            f"{connect_src}; "
            f"{script_src}; "
            f"{frame_src}; "
            "frame-ancestors 'none'; "
            f"{base_uri}; "
            f"{object_src}; "
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

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", code=500), 500

    app.register_blueprint(api_bp, url_prefix="/api/v2")
    app.register_blueprint(paddle_bp)
    app.register_blueprint(ai_bp, url_prefix="/api/v2/ai")
    app.register_blueprint(pages_bp)

    return app

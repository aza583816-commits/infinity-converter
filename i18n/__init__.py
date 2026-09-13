from flask import request

from i18n.translations import TRANSLATIONS

SUPPORTED_LANGUAGES = ("ar", "en")
DEFAULT_LANGUAGE = "en"
LANGUAGE_COOKIE = "lang"


def resolve_language(req=None) -> tuple[str, bool]:
    """Return (language, is_explicit_choice).

    Priority: explicit ?lang= query param > saved cookie > browser Accept-Language > default.
    is_explicit is True only when the query param was used, so the caller knows to persist it.
    """
    req = req or request

    query_lang = req.args.get("lang")
    if query_lang in SUPPORTED_LANGUAGES:
        return query_lang, True

    cookie_lang = req.cookies.get(LANGUAGE_COOKIE)
    if cookie_lang in SUPPORTED_LANGUAGES:
        return cookie_lang, False

    # Device/browser language fallback follows product policy: Arabic devices
    # get Arabic, English devices get English, and every other primary browser
    # language falls back to English. We intentionally use the primary language
    # token instead of IP/geolocation or a secondary weighted language.
    accept_language = (req.headers.get("Accept-Language") or "").strip()
    primary = accept_language.split(",", 1)[0].split(";", 1)[0].strip().lower()
    if primary == "ar" or primary.startswith("ar-"):
        return "ar", False
    if primary == "en" or primary.startswith("en-"):
        return "en", False

    return DEFAULT_LANGUAGE, False


def translator(lang: str):
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    strings = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    fallback = TRANSLATIONS[DEFAULT_LANGUAGE]

    def t(key: str, **kwargs) -> str:
        value = strings.get(key, fallback.get(key, key))
        return value.format(**kwargs) if kwargs else value

    return t

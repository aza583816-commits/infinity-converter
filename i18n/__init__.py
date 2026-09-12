from flask import request

from i18n.translations import TRANSLATIONS

SUPPORTED_LANGUAGES = ("ar", "en")
DEFAULT_LANGUAGE = "ar"
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

    best_match = req.accept_languages.best_match(SUPPORTED_LANGUAGES)
    if best_match:
        return best_match, False

    return DEFAULT_LANGUAGE, False


def translator(lang: str):
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    strings = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    fallback = TRANSLATIONS[DEFAULT_LANGUAGE]

    def t(key: str, **kwargs) -> str:
        value = strings.get(key, fallback.get(key, key))
        return value.format(**kwargs) if kwargs else value

    return t

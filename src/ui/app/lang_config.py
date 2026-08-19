SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "flag": "us.svg", "english_name": "English"},
    {"code": "zh", "name": "简体中文", "flag": "cn.svg", "english_name": "Simplified Chinese"},
    {"code": "hi", "name": "हिन्दी", "flag": "in.svg", "english_name": "Hindi"},
    {"code": "es", "name": "Español", "flag": "es.svg", "english_name": "Spanish"},
    {"code": "ar", "name": "العربية", "flag": "ae.svg", "english_name": "Arabic"},
    {"code": "fr", "name": "Français", "flag": "fr.svg", "english_name": "French"},
    {"code": "bn", "name": "বাংলা", "flag": "bd.svg", "english_name": "Bengali"},
    {"code": "pt", "name": "Português", "flag": "pt.svg", "english_name": "Portuguese"},
    {"code": "br", "name": "Português (Brasil)", "flag": "br.svg", "english_name": "Brazilian Portuguese"},
    {"code": "ru", "name": "Русский", "flag": "ru.svg", "english_name": "Russian"},
    {"code": "ur", "name": "اردو", "flag": "pk.svg", "english_name": "Urdu"},
    {"code": "de", "name": "Deutsch", "flag": "de.svg", "english_name": "German"},
    {"code": "ko", "name": "한국어", "flag": "kr.svg", "english_name": "Korean"},
    {"code": "tw", "name": "繁體中文", "flag": "tw.svg", "english_name": "Traditional Chinese"},
    {"code": "tr", "name": "Türkçe", "flag": "tr.svg", "english_name": "Turkish"},
    {"code": "it", "name": "Italiano", "flag": "it.svg", "english_name": "Italian"},
    {"code": "pl", "name": "Polski", "flag": "pl.svg", "english_name": "Polish"},
    {"code": "tl", "name": "Filipino", "flag": "ph.svg", "english_name": "Filipino"},
]

# The UI's language codes are not all valid locale identifiers, and two of them name a different
# language than the one they are used for:
#
#   `br` is this UI's Brazilian Portuguese, but `br` is **Breton** in CLDR/ISO-639
#   `tw` is this UI's Traditional Chinese, but `tw` is **Twi**
#
# That is harmless while translation is a JSON lookup keyed by the code, and stops being harmless
# the moment a real i18n library reads them: Babel would give Brazilian users Breton's four plural
# forms and Taiwanese users Twi's two. The UI codes stay as they are — they are persisted on user
# records, drive the flag lookup, and are what `/set_language` accepts — and this maps them to the
# locale each one actually means.
BABEL_LOCALES = {"br": "pt_BR", "tw": "zh_Hant"}

DEFAULT_LANGUAGE = "en"


def babel_locale(code: str) -> str:
    """The CLDR locale identifier for a UI language code."""
    return BABEL_LOCALES.get(code, code)


def ui_language(locale_id: str) -> str:
    """The UI language code for a CLDR locale identifier — the inverse of `babel_locale`."""
    for code, mapped in BABEL_LOCALES.items():
        if mapped == locale_id:
            return code
    return locale_id


SUPPORTED_LANGUAGE_CODES = frozenset(entry["code"] for entry in SUPPORTED_LANGUAGES)

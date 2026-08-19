#!/usr/bin/env python3
"""Server-side translation: Flask-Babel, and the rule for picking a locale.

Lot A of the native-i18n work. Until now every string was translated in the browser: the page
shipped in English, i18next fetched a 2338-key JSON catalog, then rewrote the DOM. That costs a
visible flash of English on every load, a full-document scan per page, and it makes anything
rendered after that scan (a table row built on draw, a toast) responsible for re-translating
itself. Serving the page already translated removes all three.

The two runtimes coexist during the migration: a template that has been converted uses `_()` and
arrives translated, one that has not still carries `data-i18n` and is translated by i18next. Both
read the same message ids, because `misc/dev/i18n/json_to_po.py` generates the gettext catalogs
from the same JSON files i18next loads.
"""

from functools import lru_cache
from json import dumps, loads
from os.path import isfile, join
from typing import Optional

from flask import has_request_context, request, session
from flask_babel import Babel
from flask_login import current_user

from app.lang_config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGE_CODES, babel_locale, ui_language

# What `request.accept_languages` is matched against, and the identifiers the catalogs are
# stored under — `pt_BR` and `zh_Hant`, not the UI's `br` and `tw`. See lang_config.
SUPPORTED_LOCALES = tuple(babel_locale(code) for code in sorted(SUPPORTED_LANGUAGE_CODES))
RTL_LANGUAGE_CODES = frozenset({"ar", "ur"})


def resolve_locale() -> str:
    """The locale for this request.

    An explicit choice beats a guess, and the most recent explicit choice wins:

    1. the session language — the last deliberate pick in *this* browser that could not be saved
       to the account: an anonymous visitor on the login page, a read-only database, an API write
       that failed. `/set_language` clears this key the moment a save succeeds, so it can never
       shadow a newer saved preference.
    2. the signed-in user's saved language — their default, and it follows them between browsers
    3. `Accept-Language`, matched against the locales that have a catalog
    4. English

    The order matters: with the user record first, nobody on a read-only database could change
    language at all, because their unsaveable choice would lose to the record every time.

    Never raises: a request that cannot resolve a locale still has to render a page, and
    Flask-Babel calls this from places that are not always one.
    """
    if not has_request_context():
        return DEFAULT_LANGUAGE

    language = session.get("language")
    if language in SUPPORTED_LANGUAGE_CODES:
        return babel_locale(language)

    try:
        if current_user and current_user.is_authenticated:
            language = getattr(current_user, "language", None)
            if language in SUPPORTED_LANGUAGE_CODES:
                return babel_locale(language)
    except Exception:  # a login backend that is not ready yet must not break the render
        pass

    best = request.accept_languages.best_match(SUPPORTED_LOCALES)
    if best:
        return best

    return DEFAULT_LANGUAGE


def locale_tag() -> str:
    """The resolved locale as a BCP-47 language tag, for `<html lang>`.

    Gettext identifiers use an underscore (`pt_BR`); HTML wants a hyphen. The attribute has to
    follow the rendered language or a screen reader reads French copy with English pronunciation
    rules — and with the chrome now translated on the server, a hardcoded `lang="en"` is wrong on
    every non-English page load rather than only after the DOM pass.
    """
    return resolve_locale().replace("_", "-")


def locale_code() -> str:
    """The resolved locale as the UI's own language code — `br`, not `pt_BR`.

    The JSON catalogs the browser loads are named by these codes, and so is `/set_language`. Only
    gettext and `<html lang>` use the CLDR identifier.
    """
    return ui_language(resolve_locale())


def locale_direction() -> str:
    """The native writing direction for the resolved UI language."""
    return "rtl" if locale_code() in RTL_LANGUAGE_CODES else "ltr"


@lru_cache(maxsize=len(SUPPORTED_LANGUAGE_CODES))
def browser_catalog(static_folder: str, lang: str) -> Optional[str]:
    """The JavaScript the browser loads for `lang`, or None if there is no such catalog.

    The JSON is emitted verbatim and still nested, because `t()` walks the dots: flattening it
    here would repeat every key's prefix on the wire for no gain. Served this way — a plain
    script rather than the XHR i18next used to make — the catalog is a parse-time constant, which
    is what let the readiness flag and the whole DOM-rewriting pass go away.

    The eighteen catalogs are at strict key parity, enforced by `test_i18n_catalogs`, so there is
    no English fallback to merge in: a locale either has every key or the suite is already red.
    """
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return None

    catalog = join(static_folder, "locales", f"{lang}.json")
    if not isfile(catalog):
        return None

    with open(catalog, "r", encoding="utf-8") as messages:
        # Re-serialised without the source file's indentation: this is a blocking script in front
        # of every page script, and the pretty-printing is a third of its weight (140 KB -> 90 KB
        # for French). Cached per locale because the file cannot change under a running process.
        return f'window.BW_I18N={dumps(loads(messages.read()), separators=(",", ":"), ensure_ascii=False)};window.BW_LANG="{lang}";'


def init_i18n(app) -> Babel:
    """Attach Flask-Babel. `translations/` sits next to `main.py`, inside what every image copies
    with `COPY src/ui ui`, so no packaging target can ship without the catalogs."""
    app.config.setdefault("BABEL_DEFAULT_LOCALE", DEFAULT_LANGUAGE)
    app.config.setdefault("BABEL_DEFAULT_TIMEZONE", "UTC")
    app.context_processor(lambda: {"ui_locale_tag": locale_tag(), "ui_locale_code": locale_code(), "ui_locale_direction": locale_direction()})
    return Babel(app, locale_selector=resolve_locale)


def translated(key: str, /, **variables) -> Optional[str]:
    """`gettext`, but returning None when a key has no translation instead of echoing the key.

    The message ids are dotted keys (`button.create_service`), so an un-translated lookup renders
    as that key in the page — worse than useless in a UI. Callers that have a sensible fallback
    use this; templates use `_()` directly, because a key missing from the catalog is a bug the
    parity test already fails on.
    """
    from flask_babel import gettext

    rendered = gettext(key, **variables) if variables else gettext(key)
    return None if rendered == key else rendered

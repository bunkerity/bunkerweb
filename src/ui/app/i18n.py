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
from logging import getLogger
from os.path import join
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from flask import g, has_app_context, has_request_context, request, session
from flask_babel import Babel
from flask_login import current_user

import plugin_extensions  # type: ignore

from app.lang_config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGE_CODES, babel_locale, ui_language

LOGGER = getLogger("UI")

# What `request.accept_languages` is matched against, and the identifiers the catalogs are
# stored under — `pt_BR` and `zh_Hant`, not the UI's `br` and `tw`. See lang_config.
SUPPORTED_LOCALES = tuple(babel_locale(code) for code in sorted(SUPPORTED_LANGUAGE_CODES))
RTL_LANGUAGE_CODES = frozenset({"ar", "ur"})

# Where a plugin's own catalog lives, relative to the plugin's root — checked in order, first
# match wins. 12 of the 13 PRO plugins ship a Flask blueprint and put it under that blueprint's
# static folder; `alerting` has no blueprint (a plain `ui/template.html` page) and puts it directly
# under `ui/static/`. Both layouts are what `window.BunkerWebExtraI18nPath` used to point PRO's own
# i18next fetch at, so adopting this extension point moves no file either way. `en.json` is the
# mandatory fallback; other languages are optional. No `plugin.json` declaration is required —
# shipping the file is the whole opt-in, so there is no build step for a plugin author to run.
PLUGIN_LOCALES_SUBPATHS: Tuple[Tuple[str, ...], ...] = (
    ("ui", "blueprints", "static", "locales"),
    ("ui", "static", "locales"),
)


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


def _plugin_roots() -> Tuple[Path, ...]:
    """The on-disk plugin roots to scan for a shipped catalog — the same three the `extensions.*`
    mechanism scans (`plugin_extensions.py`), read as module attributes rather than imported by
    name so a test's `monkeypatch.setattr(plugin_extensions, ...)` is honoured here too."""
    return (
        Path(plugin_extensions.CORE_PLUGINS_PATH),
        Path(plugin_extensions.EXTERNAL_PLUGINS_PATH),
        Path(plugin_extensions.PRO_PLUGINS_PATH),
    )


def _plugin_catalog(plugin_dir: Path, lang: str) -> Optional[dict]:
    """The plugin's own catalog dict for `lang`, falling back to its `en.json`, or None if it
    ships neither (or ships this locale only, invalid), trying each of `PLUGIN_LOCALES_SUBPATHS`
    in order — a plugin whose first candidate has neither file falls through to the next one.
    Invalid JSON is a WARNING naming the plugin and file, never an exception — one broken catalog
    must not break every other plugin's.

    Not process-cached: a plugin's files can change under a running process (install, upgrade,
    reload), unlike the core catalogs `_core_catalog` below memoises. `_plugin_catalogs_for_request`
    memoises this for the lifetime of one request instead, which is enough to keep a plugin
    template's `_()` calls from re-scanning the disk once per key while still re-reading on the
    very next request.
    """
    for subpath in PLUGIN_LOCALES_SUBPATHS:
        locales_dir = plugin_dir.joinpath(*subpath)
        for candidate in dict.fromkeys((lang, DEFAULT_LANGUAGE)):
            catalog_file = locales_dir / f"{candidate}.json"
            if not catalog_file.is_file():
                continue
            try:
                catalog = loads(catalog_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                LOGGER.warning(f"Plugin '{plugin_dir.name}': invalid i18n catalog {catalog_file}: {e}")
                continue
            if isinstance(catalog, dict):
                return catalog
            LOGGER.warning(f"Plugin '{plugin_dir.name}': i18n catalog {catalog_file} is not a JSON object")
    return None


def iter_plugin_catalogs(lang: str, roots: Optional[Tuple[Path, ...]] = None) -> Iterator[Tuple[str, dict]]:
    """Yield `(plugin_id, catalog)` for every plugin under `roots` (default: `_plugin_roots()`)
    that ships a catalog at one of `PLUGIN_LOCALES_SUBPATHS` for `lang` or `en`. Never raises: a
    root that does not exist, or that this process cannot list, is silently skipped. `lang` is
    trusted to be a validated UI code by its one caller (`_merged_catalog`, behind `_core_catalog`'s
    allow-list check) — guarded here too, since this is a public-looking helper a future caller
    could hand request data to.
    """
    if lang not in SUPPORTED_LANGUAGE_CODES:
        lang = DEFAULT_LANGUAGE
    for root in roots if roots is not None else _plugin_roots():
        if not root.is_dir():
            continue
        try:
            plugin_dirs = sorted(entry for entry in root.iterdir() if entry.is_dir())
        except OSError:
            continue
        for plugin_dir in plugin_dirs:
            catalog = _plugin_catalog(plugin_dir, lang)
            if catalog is not None:
                yield plugin_dir.name, catalog


def _plugin_catalogs_for_request(lang: str) -> List[Tuple[str, dict]]:
    """`iter_plugin_catalogs(lang)`, memoised for the lifetime of one request.

    A plugin page can call `_()` dozens of times, and every one of them is a core-catalog miss by
    construction — without this, each of those misses re-scans every plugin root and re-parses
    every catalog it finds. `flask.g` is per-request, so the memo is gone before the next request
    even starts: a plugin install, upgrade or reload is visible immediately, unlike `_core_catalog`
    above (which is correct to cache for the process lifetime, because the core files cannot
    change under it). Outside a request or app context (a script, a bare test call) this falls
    back to the uncached scan every time — correct, just not memoised.
    """
    if not has_app_context():
        return list(iter_plugin_catalogs(lang))
    cache = g.setdefault("_plugin_i18n_catalogs", {})
    if lang not in cache:
        cache[lang] = list(iter_plugin_catalogs(lang))
    return cache[lang]


# Suppresses a repeat WARNING for a collision this process has already logged once. Without it,
# every `_()` miss re-runs the whole merge (`_merged_catalog` isn't cached, only the disk scan
# is — see `_plugin_catalogs_for_request`), so a single page render with N missed keys against a
# plugin that collides on M paths logs N x M lines: measured at 1350 WARNING lines for one real
# page (30 misses x the 45 genuine collisions the stock PRO catalogs produce). The set is
# process-lifetime, matching `_core_catalog`'s cache — a collision fixed by editing a plugin's
# catalog goes quiet again only on the next worker restart, which is an acceptable trade for not
# drowning every other WARNING in the log on every request.
_WARNED_COLLISIONS: set = set()


def _merge_plugin_catalog(base: dict, overlay: dict, plugin_id: str, path: str = "") -> dict:
    """`overlay` merged onto `base`, returned as a NEW dict — `base` is never mutated, because it
    may be `_core_catalog`'s cached, shared dict, or another plugin's already-merged result.

    A leaf collides, not a whole top-level namespace: the merge descends into a key both sides
    define as a dict, and only refuses (with a WARNING naming the dotted path and the plugin) at
    the point where `base` already has a concrete value. A shallower, top-level-only rule was
    tried first and measured against the 13 real PRO catalogs: 2 of them (`user_manager`,
    `easy_resolve`) nest strings under top-level names BunkerWeb's own core catalog also uses
    (`button`, `flash`, `footer`, ...) for unrelated keys, so a top-level rule silently dropped 179
    real strings — 66% of one plugin's page. A leaf rule refuses only the 45 that are genuine
    duplicates of an existing core (or earlier-plugin) leaf; the other 134 near-misses are new
    keys under a shared namespace and now merge fine.
    """
    merged = base.copy()
    for key, value in overlay.items():
        full_path = f"{path}.{key}" if path else key
        if key not in merged:
            merged[key] = value
            continue
        existing = merged[key]
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = _merge_plugin_catalog(existing, value, plugin_id, full_path)
        else:
            collision = (plugin_id, full_path)
            if collision not in _WARNED_COLLISIONS:
                _WARNED_COLLISIONS.add(collision)
                LOGGER.warning(f"Plugin '{plugin_id}' i18n key '{full_path}' collides with an existing key; keeping the existing one")
    return merged


@lru_cache(maxsize=len(SUPPORTED_LANGUAGE_CODES))
def _core_catalog(static_folder: str, lang: str) -> Optional[dict]:
    """The parsed core JSON catalog for `lang`, or None. Cached: the core catalogs are baked into
    the image and cannot change under a running process — unlike a plugin's (see `_plugin_catalog`),
    which is why only the core half of `_merged_catalog` is memoised for the process lifetime.

    The eighteen catalogs are at strict key parity, enforced by `test_i18n_catalogs`, so there is
    no English fallback to apply here: a locale either has every core key or the suite is already
    red. A plugin catalog is different — merged in unparsed, with its own `en` fallback.
    """
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return None
    path = join(static_folder, "locales", f"{lang}.json")
    if not Path(path).is_file():
        return None
    with open(path, "r", encoding="utf-8") as messages:
        return loads(messages.read())


def _merged_catalog(static_folder: str, lang: str) -> Optional[dict]:
    """The core catalog with every loaded plugin's own catalog merged in (leaf-level, core wins —
    see `_merge_plugin_catalog`), or None if there is no core catalog for `lang`. The one structure
    `browser_catalog` serialises as-is and `gettext_or_plugin` walks one dotted key at a time, so a
    key resolves (or doesn't) exactly the same way in both places — including between two plugins:
    the second plugin loaded collides with the first's key the same way it would with a core one.
    """
    core = _core_catalog(static_folder, lang)
    if core is None:
        return None
    merged = core  # do not mutate: this may still be `_core_catalog`'s cached dict, by reference
    for plugin_id, catalog in _plugin_catalogs_for_request(lang):
        merged = _merge_plugin_catalog(merged, catalog, plugin_id)
    return merged


def _dotted_lookup(catalog: dict, key: str) -> Optional[str]:
    """`catalog["a"]["b"]` for dotted `key` `"a.b"`, or None if any segment is missing or the
    leaf isn't a string (partial path, or a whole namespace rather than one message)."""
    node = catalog
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def browser_catalog(static_folder: str, lang: str) -> Optional[str]:
    """The JavaScript the browser loads for `lang`, or None if there is no core catalog.

    The JSON is emitted verbatim and still nested, because `t()` walks the dots: flattening it
    here would repeat every key's prefix on the wire for no gain. Served this way — a plain
    script rather than the XHR i18next used to make — the catalog is a parse-time constant, which
    is what let the readiness flag and the whole DOM-rewriting pass go away.

    `_merged_catalog` does the actual merge (core + every loaded plugin's own catalog for `lang`,
    falling back to its `en`). Only the active language is ever emitted — the script stays sync
    and small regardless of how many plugins are installed.
    """
    merged = _merged_catalog(static_folder, lang)
    if merged is None:
        return None

    # Re-serialised without the source file's indentation: this is a blocking script in front
    # of every page script, and the pretty-printing is a third of its weight (140 KB -> 90 KB
    # for French).
    return f'window.BW_I18N={dumps(merged, separators=(",", ":"), ensure_ascii=False)};window.BW_LANG="{lang}";'


def init_i18n(app) -> Babel:
    """Attach Flask-Babel. `translations/` sits next to `main.py`, inside what every image copies
    with `COPY src/ui ui`, so no packaging target can ship without the catalogs."""
    app.config.setdefault("BABEL_DEFAULT_LOCALE", DEFAULT_LANGUAGE)
    app.config.setdefault("BABEL_DEFAULT_TIMEZONE", "UTC")
    app.context_processor(lambda: {"ui_locale_tag": locale_tag(), "ui_locale_code": locale_code(), "ui_locale_direction": locale_direction()})
    babel = Babel(app, locale_selector=resolve_locale)

    # `json_to_po.py` compiles the core JSON catalogs into `translations/*/LC_MESSAGES/messages.mo`
    # at build time — a plugin's catalog cannot join that .mo without a build step, which the
    # extension point promises no plugin author has to run. So instead of touching the converter,
    # the gettext callable Flask-Babel just installed into Jinja is re-installed with a plugin
    # fallback: unchanged on a `.mo` hit, and on a miss (an untranslated lookup echoes its own key
    # — see `translated()` below) it walks `_merged_catalog` — the exact same core+plugins
    # structure `browser_catalog` serialises — for the same dotted id a plugin's template would
    # already call `_()` with.
    #
    # This needs no separate "is that already a core key" check, even though the `.mo` and the
    # core JSON do NOT have identical key sets: `json_to_po.py` folds each plural pair into one
    # `.mo` entry (`msgid`/`msgid_plural`), so the plural half (e.g.
    # `modal.body.delete_confirmation_alert_plural`) exists in the JSON but is never a standalone
    # `.mo` id — a real, if harmless, divergence, not the parity the JSON-vs-JSON locale check
    # enforces. What actually makes the check unnecessary is `_merge_plugin_catalog`: it already
    # refuses a plugin value at any leaf the core JSON defines, with a WARNING, *before*
    # `_merged_catalog` is built — so a `.mo` miss that happens to be a real core JSON leaf (one of
    # the folded plural ids) still resolves to the core string here, never a plugin's.
    #
    # `get_locale()` — not `locale_code()` — on purpose: it is the locale `get_translations()` just
    # resolved the core catalog against, so a test (or a caller) forcing the locale a different way
    # (`flask_babel.force_locale`) still gets a plugin fallback in the same language as the core one.
    #
    # `ngettext`/`pgettext`/`npgettext` are re-installed unchanged (flask-babel==4.0.0's own
    # `get_translations().u*gettext` lambdas, pinned in `src/ui/requirements.txt`) because
    # `install_gettext_callables` is the only way to change `gettext` without also handing it the
    # other three: their already-newstyle-wrapped versions aren't retrievable from `jinja_env.globals`
    # to pass back through unchanged, and re-wrapping an already-wrapped callable breaks it.
    from flask_babel import get_locale, get_translations

    def gettext_or_plugin(string: str) -> str:
        value = get_translations().ugettext(string)
        if value != string:
            return value
        lang = ui_language(str(get_locale() or DEFAULT_LANGUAGE))
        merged = _merged_catalog(app.static_folder or "", lang)
        if merged is None:
            return value
        return _dotted_lookup(merged, string) or value

    app.jinja_env.install_gettext_callables(
        gettext=gettext_or_plugin,
        ngettext=lambda s, p, n: get_translations().ungettext(s, p, n),
        newstyle=True,
        pgettext=lambda c, s: get_translations().upgettext(c, s),
        npgettext=lambda c, s, p, n: get_translations().unpgettext(c, s, p, n),
    )
    return babel


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

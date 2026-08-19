"""Flask-Babel end to end: a request resolves a locale, and the catalogs translate.

`test_i18n_catalogs.py` checks the generated files. This checks the thing that actually has to
work — that a render produces translated text, picks the right plural form, and survives the
`%`-formatting rules that would otherwise raise inside a page.
"""

import sys
from pathlib import Path

import pytest
from flask import Flask, render_template_string
from flask_babel import force_locale, gettext, ngettext

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.i18n import init_i18n, resolve_locale, translated  # noqa: E402


def catalog_value(language, key):
    """What `locales/<language>.json` says for `key`.

    Assertions used to name the French string outright, which froze a translator's wording into a
    test about plumbing: a sentence-case pass over the catalogs turned "Créer un nouveau Service"
    into "...service" and four tests went red without anything being broken. Reading the source
    of truth keeps the check meaningful — it proves the compiled catalog matches the JSON — and
    leaves the wording to the people who own it.
    """
    from json import loads

    node = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / f"{language}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    return node


@pytest.fixture
def app():
    application = Flask("bw_ui_i18n_test", root_path=str(REPO / "src" / "ui"))
    application.config["SECRET_KEY"] = "test"
    init_i18n(application)
    return application


# --------------------------------------------------------------------------------------
# It translates
# --------------------------------------------------------------------------------------
def test_a_key_renders_in_the_requested_language(app):
    with app.test_request_context("/"):
        with force_locale("fr"):
            french = gettext("button.create_service")
        with force_locale("en"):
            english = gettext("button.create_service")

    assert english == catalog_value("en", "button.create_service")
    assert french == catalog_value("fr", "button.create_service")
    assert french != english


def test_a_template_arrives_already_translated(app):
    """The point of the whole lot: the HTML leaves the server in the user's language, instead of
    leaving in English and being rewritten by i18next after paint."""
    with app.test_request_context("/"), force_locale("fr"):
        html = render_template_string("<h1>{{ _('button.create_service') }}</h1>")

    assert html == f"<h1>{catalog_value('fr', 'button.create_service')}</h1>"
    assert "button.create_service" not in html


def test_the_two_remapped_locales_load_their_real_catalog(app):
    """`br` and `tw` are stored under `pt_BR` and `zh_Hant`; a lookup under the UI code would
    silently fall through to English."""
    with app.test_request_context("/"):
        with force_locale("pt_BR"):
            brazilian = gettext("button.create_service")
        with force_locale("zh_Hant"):
            traditional = gettext("button.create_service")

    # Not "differs from `pt`": the two Portuguese catalogs agree on plenty of keys, and this is
    # one of them. What has to hold is that each remapped code reaches *its own* catalog rather
    # than falling through to English or echoing the message id.
    assert brazilian == catalog_value("br", "button.create_service")
    assert traditional == catalog_value("tw", "button.create_service")
    assert brazilian != catalog_value("en", "button.create_service")
    assert traditional != catalog_value("en", "button.create_service")
    assert "button" not in traditional


# --------------------------------------------------------------------------------------
# Plurals, in languages whose rules differ
# --------------------------------------------------------------------------------------
KEY = "modal.body.confirm_cache_deletion_alert"


@pytest.mark.parametrize("locale", ["en", "fr", "pl", "ar", "ru"])
def test_one_and_many_pick_different_forms(app, locale):
    with app.test_request_context("/"), force_locale(locale):
        one = ngettext(KEY, f"{KEY}_plural", 1)
        many = ngettext(KEY, f"{KEY}_plural", 5)

    assert one != many, f"{locale} rendered the same string for 1 and 5"
    assert KEY not in one and KEY not in many, "fell through to the message id"


def test_arabic_zero_is_not_the_singular(app):
    """Arabic's slot 0 is `zero`, not `one`. A converter that wrote the singular into slot 0
    would say "the selected file" for none of them, and this is the only test that notices."""
    with app.test_request_context("/"), force_locale("ar"):
        zero = ngettext(KEY, f"{KEY}_plural", 0)
        one = ngettext(KEY, f"{KEY}_plural", 1)

    assert zero != one


def test_polish_uses_its_third_form(app):
    """Polish has three: 1, 2-4, and 5+. Two of the three would pass a naive singular/plural
    check; this asks for the one that would not."""
    with app.test_request_context("/"), force_locale("pl"):
        forms = {ngettext(KEY, f"{KEY}_plural", n) for n in (1, 2, 5)}

    assert len(forms) >= 2
    assert all(KEY not in form for form in forms)


# --------------------------------------------------------------------------------------
# Placeholders — the failure mode here is a 500, not a bad string
# --------------------------------------------------------------------------------------
def test_an_interpolated_string_formats(app):
    with app.test_request_context("/"), force_locale("fr"):
        rendered = gettext("tooltip.link.export_service", service="www.example.com")

    assert "www.example.com" in rendered
    assert "%(" not in rendered


def test_a_literal_percent_survives_formatting(app):
    """`'{{percent}}% used'` becomes `'%(percent)s%% used'`. Unescaped it raises
    `ValueError: unsupported format character ' '` and takes the dashboard down."""
    with app.test_request_context("/"), force_locale("en"):
        rendered = gettext("dashboard.card.ram.usage", percent=42)

    assert rendered == "42% used"


def test_a_percent_in_an_unformatted_string_is_left_alone(app):
    """The other half of the rule: no variables means no formatting, so escaping here would
    print `%%` at the user. DataTables reads these `%d` markers itself."""
    with app.test_request_context("/"), force_locale("en"):
        rendered = gettext("datatable.select_rows_bans_plural")

    assert rendered == "Selected %d Bans"


@pytest.mark.parametrize("locale", ["en", "fr", "ar", "pl", "zh_Hant"])
def test_every_interpolated_key_formats_in_every_tested_locale(locale, app):
    """Sweeps the real catalog rather than a sample: one bad escape anywhere is a 500 on
    whichever page renders it, in whichever language nobody tested."""
    from babel.messages.pofile import read_po

    path = REPO / "src" / "ui" / "translations" / locale / "LC_MESSAGES" / "messages.po"
    with path.open("rb") as handle:
        catalog = read_po(handle, locale=locale)

    from re import findall

    checked = 0
    with app.test_request_context("/"), force_locale(locale):
        for message in catalog:
            if not message.id or message.pluralizable:
                continue
            names = set(findall(r"%\((\w+)\)", message.string or ""))
            if not names:
                continue
            gettext(message.id, **{name: 1 for name in names})
            checked += 1

    assert checked > 50, f"{locale}: only {checked} interpolated keys exercised"


# --------------------------------------------------------------------------------------
# Which locale a request gets
# --------------------------------------------------------------------------------------
def test_an_anonymous_visitor_gets_their_browsers_language(app):
    with app.test_request_context("/", headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}):
        assert resolve_locale() == "fr"


def test_an_unsupported_browser_language_falls_back_to_english(app):
    with app.test_request_context("/", headers={"Accept-Language": "is-IS,is;q=0.9"}):
        assert resolve_locale() == "en"


def test_the_session_choice_beats_a_saved_user_preference(app):
    """The session key only exists when a deliberate choice could *not* be saved — a read-only
    database, an anonymous visitor, a failed API write. With the user record winning instead,
    nobody in those states could change language at all: their pick would lose every time.

    `/set_language` clears the key as soon as a save succeeds, so it can never shadow a newer
    preference made from another browser.
    """
    from flask import session
    from unittest.mock import patch
    from types import SimpleNamespace

    saved_german = SimpleNamespace(is_authenticated=True, language="de")
    with app.test_request_context("/"), patch("app.i18n.current_user", saved_german):
        assert resolve_locale() == "de"
        session["language"] = "it"
        assert resolve_locale() == "it"


def test_a_saved_preference_beats_the_browser(app):
    from unittest.mock import patch
    from types import SimpleNamespace

    saved_german = SimpleNamespace(is_authenticated=True, language="de")
    with app.test_request_context("/", headers={"Accept-Language": "fr"}), patch("app.i18n.current_user", saved_german):
        assert resolve_locale() == "de"


def test_a_saved_preference_the_ui_no_longer_supports_is_ignored(app):
    """Language codes are removed from `SUPPORTED_LANGUAGES` over time; a user record still
    holding one must fall through, not reach `Locale.parse`."""
    from unittest.mock import patch
    from types import SimpleNamespace

    stale = SimpleNamespace(is_authenticated=True, language="eo")
    with app.test_request_context("/", headers={"Accept-Language": "fr"}), patch("app.i18n.current_user", stale):
        assert resolve_locale() == "fr"


def test_a_login_backend_that_is_not_ready_does_not_break_the_render(app):
    """`current_user` is a proxy; touching it before the login manager is attached raises."""
    from unittest.mock import patch

    class Exploding:
        @property
        def is_authenticated(self):
            raise RuntimeError("no login manager yet")

    with app.test_request_context("/", headers={"Accept-Language": "fr"}), patch("app.i18n.current_user", Exploding()):
        assert resolve_locale() == "fr"


def test_a_session_choice_beats_the_browser(app):
    from flask import session

    with app.test_request_context("/", headers={"Accept-Language": "fr-FR,fr;q=0.9"}):
        session["language"] = "de"
        assert resolve_locale() == "de"


def test_the_session_choice_is_mapped_like_any_other(app):
    from flask import session

    with app.test_request_context("/"):
        session["language"] = "br"
        assert resolve_locale() == "pt_BR"


def test_an_unknown_session_language_is_ignored_rather_than_trusted(app):
    """It reaches `Locale.parse`; an arbitrary string there is an exception on every render."""
    from flask import session

    with app.test_request_context("/", headers={"Accept-Language": "fr"}):
        session["language"] = "../../etc/passwd"
        assert resolve_locale() == "fr"


def test_resolving_outside_a_request_still_returns_something(app):
    """Flask-Babel calls the selector from places that are not always a request — a background
    render, a CLI context. Reading `session` there raises, and the raise would surface as a 500
    on whatever triggered it."""
    with app.app_context():
        assert resolve_locale() == "en"
    assert resolve_locale() == "en"  # no context at all


def test_the_accept_language_match_uses_the_mapped_identifiers(app):
    """A browser asking for `pt-BR` has to find the Brazilian catalog, which is not stored under
    the UI's `br`."""
    with app.test_request_context("/", headers={"Accept-Language": "pt-BR,pt;q=0.9"}):
        assert resolve_locale() == "pt_BR"


# --------------------------------------------------------------------------------------
# The fallback helper
# --------------------------------------------------------------------------------------
def test_translated_returns_none_rather_than_echoing_a_key(app):
    with app.test_request_context("/"), force_locale("en"):
        assert translated("button.create_service") == "Create new service"
        assert translated("no.such.key.exists") is None


# --------------------------------------------------------------------------------------
# /set_language — asserted at the source, since booting main.py needs container-only paths.
# The behaviour is verified live in a browser; these pin the invariants that make the four
# states work, each of which otherwise strands a user with no way to change language.
# --------------------------------------------------------------------------------------
MAIN = REPO / "src" / "ui" / "main.py"


def _set_language_source():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index('@app.route("/set_language"')
    end = source.index("@app.route", start + 10)
    return source[start:end]


def test_setting_a_language_does_not_require_an_account():
    """The login and TOTP pages are rendered server-side too, and an anonymous visitor has no
    other way to tell the server which language to use."""
    route = _set_language_source()
    # Only the decorators, not the body — the docstring discusses `@login_required` by name.
    decorators = route[: route.index("def set_language(")]

    assert "@login_required" not in decorators
    assert "@app.route" in decorators


def test_the_session_is_recorded_before_any_branch_that_can_return_early():
    """Every accepted request has to leave the choice somewhere the next render can read, no
    matter which of the four states it is in."""
    route = _set_language_source()
    stored = route.index('session["language"] = lang')

    assert stored < route.index("current_user.is_authenticated")
    assert stored < route.index("READONLY_MODE")
    assert stored < route.index("API_CLIENT.update_user")


def test_a_read_only_database_no_longer_refuses_the_change():
    """It used to answer 423 before doing anything, which — now that the locale is resolved
    server-side — would mean a read-only install could never change language at all."""
    route = _set_language_source()

    assert "423" not in route
    assert 'DATA.get("READONLY_MODE", False)' in route


def test_a_failed_save_still_reports_success_and_keeps_the_session():
    """The language *did* change; only its persistence failed. Returning 500 would make the UI
    show an error for something that visibly worked."""
    route = _set_language_source()

    assert "500" not in route
    assert '"saved": False' in route


def test_a_successful_save_drops_the_session_override():
    """Otherwise a choice made here would outrank a newer one made from another browser, for as
    long as this session lives."""
    route = _set_language_source()
    popped = route.index('session.pop("language", None)')

    assert popped > route.index("API_CLIENT.update_user")
    assert '"saved": True' in route[popped:]


def test_the_language_is_still_checked_against_the_allow_list():
    """It reaches `Locale.parse` and a template lookup; an arbitrary string is an exception on
    every subsequent render of that session."""
    route = _set_language_source()

    assert "allowed_languages" in route
    assert "return Response(status=400" in route


def test_the_html_lang_attribute_follows_the_resolved_locale(app):
    """A hardcoded `lang="en"` used to be merely stale; with the chrome translated on the server
    it is wrong in the initial HTML of every non-English page load."""
    from app.i18n import locale_tag

    with app.test_request_context("/", headers={"Accept-Language": "fr"}):
        assert locale_tag() == "fr"

    # gettext writes `pt_BR`; an HTML language tag is hyphenated.
    with app.test_request_context("/", headers={"Accept-Language": "pt-BR"}):
        assert locale_tag() == "pt-BR"


def test_the_html_direction_follows_the_resolved_locale(app):
    from app.i18n import locale_direction

    for language in ("ar", "ur"):
        with app.test_request_context("/", headers={"Accept-Language": language}):
            assert locale_direction() == "rtl"

    with app.test_request_context("/", headers={"Accept-Language": "fr"}):
        assert locale_direction() == "ltr"


def test_the_layout_reads_that_tag_rather_than_a_literal(app):
    markup = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert '<html lang="{{ ui_locale_tag' in markup
    assert 'dir="{{ ui_locale_direction' in markup
    assert '<html lang="en"' not in markup


# --------------------------------------------------------------------------------------
# The catalog the browser loads
# --------------------------------------------------------------------------------------
def test_the_browser_catalog_names_the_locale_by_the_ui_code(app):
    """The JSON files are named `br.json` and `tw.json`; only gettext and `<html lang>` use the
    CLDR identifier. Asking for `pt_BR.js` has to 404, not silently serve English."""
    from app.i18n import locale_code

    with app.test_request_context("/", headers={"Accept-Language": "pt-BR"}):
        assert locale_code() == "br"

    with app.test_request_context("/", headers={"Accept-Language": "fr"}):
        assert locale_code() == "fr"


def test_the_browser_catalog_is_a_script_that_assigns_both_globals():
    """`i18n.js` reads `window.BW_I18N` and `window.BW_LANG` at parse time. Either one missing and
    every JavaScript-built string renders as its raw dotted key."""
    from json import loads

    from app.i18n import browser_catalog

    static = str(REPO / "src" / "ui" / "app" / "static")
    catalog = browser_catalog(static, "fr")

    assert catalog.startswith("window.BW_I18N={")
    assert catalog.endswith('window.BW_LANG="fr";')

    body = catalog.split("window.BW_I18N=", 1)[1].rsplit(';window.BW_LANG="fr";', 1)[0]
    messages = loads(body)
    assert messages["button"]["create_service"] == catalog_value("fr", "button.create_service")


def test_an_unknown_locale_is_refused_rather_than_guessed():
    """`lang` comes straight off the URL. Anything not in the allow-list must fail before it is
    joined onto a filesystem path."""
    from app.i18n import browser_catalog

    static = str(REPO / "src" / "ui" / "app" / "static")

    assert browser_catalog(static, "pt_BR") is None
    assert browser_catalog(static, "klingon") is None
    assert browser_catalog(static, "../../../etc/passwd") is None

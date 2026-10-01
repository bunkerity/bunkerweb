"""Two login-page locale defects, both about WHEN the request's locale is resolved.

Flask-Babel resolves a request's locale once, on its first translation, and caches it. In the UI
that first translation is the tab title, in `before_request` -- before any view runs.

Q6-M2  `/login?lang=fr` after a logout rendered half French: the view adopted `?lang=` into the
       session, but the locale had already been resolved (English) by then. `resolve_locale` now
       reads the hint itself, on the login page only, validated against the supported codes.
Q6-M3  The 2FA reminder flashed at login followed Accept-Language, not the stored language, in a
       fresh browser: the POST's locale was resolved (and cached) before `login_user`. The reminder
       is now translated under the logged-in user's own language.
"""

from json import loads
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask, session
from flask_login import LoginManager

from app.i18n import init_i18n, resolve_locale, translated

from test_login_language import login_module  # noqa: F401 -- pytest fixture

REPO = Path(__file__).resolve().parents[3]


def _catalog_value(language: str, key: str) -> str:
    node = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / f"{language}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    return node


@pytest.fixture
def app(login_module):  # noqa: F811
    application = Flask("bw_ui_login_locale_test", root_path=str(REPO / "src" / "ui"))
    application.secret_key = "test"
    init_i18n(application)
    manager = LoginManager()
    manager.init_app(application)
    manager.user_loader(lambda user_id: None)
    application.register_blueprint(login_module.login)
    for rule, endpoint in (("/setup", "setup.setup_page"), ("/home", "home.home_page"), ("/loading", "loading"), ("/profile", "profile.profile_page")):
        application.add_url_rule(rule, endpoint=endpoint, view_func=lambda: "")
    return application


# ------------------------------------------------------------------------------ Q6-M2


def test_the_login_hint_is_the_locale_of_this_very_request(app):
    with app.test_request_context("/login?lang=fr", headers={"Accept-Language": "en"}):
        assert resolve_locale() == "fr"
        # The tab title is the first translation of the request, before the view writes the session.
        assert translated("navigation.home") == _catalog_value("fr", "navigation.home")


def test_the_hint_is_validated(app):
    with app.test_request_context("/login?lang=xx", headers={"Accept-Language": "de"}):
        assert resolve_locale() == "de"


def test_a_session_pick_still_beats_the_hint(app):
    with app.test_request_context("/login?lang=fr"):
        session["language"] = "de"
        assert resolve_locale() == "de"


def test_the_hint_only_counts_on_the_login_page(app):
    with app.test_request_context("/home?lang=fr", headers={"Accept-Language": "en"}):
        assert resolve_locale() == "en"


# ------------------------------------------------------------------------------ Q6-M3


def _login_reminder(app, login, *, stored_language, accept_language, session_language=None):  # noqa: F811
    login.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
    login.API_CLIENT.get_user_for_auth.return_value = {
        "username": "admin",
        "password": "$2b$12$stubstubstubstubstubstubstubstubstubstubstubstubstubs",
        "email": None,
        "method": "manual",
        "admin": True,
        "theme": "light",
        "language": stored_language,
        "totp_secret": None,  # no second factor: the reminder path
        "webauthn_credentials_count": 0,
    }
    flashed = []

    def fake_establish_session(ui_user, user_data, *, mfa_done, remember_me):
        session.clear()
        return True

    with app.test_request_context("/login", method="POST", data={"username": "admin", "password": "x"}, headers={"Accept-Language": accept_language}):
        if session_language:
            session["language"] = session_language
        translated("navigation.home")  # what `before_request` does first: resolves and caches the locale
        with patch.object(login, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None, get_id=lambda: "admin")), patch.object(
            login, "_establish_session", side_effect=fake_establish_session
        ), patch.object(login, "checkpw", return_value=True), patch.object(login, "dismissed_notices", return_value={}), patch.object(
            login, "flash", side_effect=lambda message, *args, **kwargs: flashed.append(str(message))
        ):
            login.login_page()
        # The rest of the request is untouched by the forced locale.
        assert translated("navigation.home") == _catalog_value(session_language or accept_language, "navigation.home")

    login.API_CLIENT.update_user.reset_mock()
    assert len(flashed) == 1, flashed
    return flashed[0]


def test_a_fresh_browser_gets_the_reminder_in_the_stored_language(app, login_module):  # noqa: F811
    reminder = _login_reminder(app, login_module, stored_language="de", accept_language="en")

    assert _catalog_value("de", "notice.dismiss_mfa") in reminder, reminder
    assert _catalog_value("en", "notice.dismiss_mfa") not in reminder, reminder


def test_a_language_picked_on_the_login_page_still_wins(app, login_module):  # noqa: F811
    reminder = _login_reminder(app, login_module, stored_language="fr", accept_language="en", session_language="de")

    assert _catalog_value("de", "notice.dismiss_mfa") in reminder, reminder

"""H11: a login must never overwrite the user's saved language with a guess.

Before the fix, `login_page()` unconditionally wrote `request.form.get("language", "en")` onto the
user record on every successful login. The login form's hidden `language` input is set by
`i18n.js` to whatever locale the *anonymous* page happened to render in -- the session's stored
pick if any, else an `Accept-Language` match, else English -- none of which is "the user deliberately
chose this on the login page". The result: a user with `language: fr` on their account who simply
logs in from a browser that does not send `Accept-Language: fr` gets silently reset to English.

`/set_language` (`main.py`) is the only writer of `session["language"]`, and it only ever runs from
an explicit selector click (`i18n.js:changeLanguage`). Its presence in the session at login time is
therefore the one reliable signal that the user actually touched the selector on this visit. The fix
reads that key -- before `_establish_session` clears the session -- and only then includes
`language` in the `update_user` call.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask, session
from flask_login import LoginManager

UI = Path(__file__).resolve().parents[3] / "src" / "ui"


@pytest.fixture(scope="module")
def login_module():
    """`login.py` loaded with its container-only dependencies stubbed -- same shape as
    `test_login_notices.py`'s `routes` fixture, trimmed to the one blueprint this file needs."""
    dependencies = ModuleType("app.dependencies")
    for name in ("API_CLIENT", "BW_CONFIG", "BW_INSTANCES_UTILS", "LOGGER"):
        setattr(dependencies, name, Mock())
    dependencies.DATA = {}
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    biscuit_module = ModuleType("app.models.biscuit")
    biscuit_module.BiscuitTokenFactory = Mock()
    biscuit_module.PrivateKey = Mock()

    stubs = {"app.dependencies": dependencies, "app.models.biscuit": biscuit_module, "qrcode": qrcode, "qrcode.main": qrcode_main}
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location("app.routes.login", UI / "app" / "routes" / "login.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["app.routes.login"] = module
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def app(login_module):
    application = Flask("bw_ui_login_language_test")
    application.secret_key = "test"
    manager = LoginManager()
    manager.init_app(application)
    manager.user_loader(lambda user_id: None)
    application.register_blueprint(login_module.login)
    # Redirect/build targets `login_page` reaches on a successful login; nothing below renders them.
    application.add_url_rule("/setup", endpoint="setup.setup_page", view_func=lambda: "")
    application.add_url_rule("/home", endpoint="home.home_page", view_func=lambda: "")
    application.add_url_rule("/loading", endpoint="loading", view_func=lambda: "")
    return application


def _login(app, login, *, session_language, stored_language):
    """Run one successful `POST /login` and return the kwargs `update_user` was called with."""
    login.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
    login.API_CLIENT.get_user_for_auth.return_value = {
        "username": "admin",
        "password": "$2b$12$stubstubstubstubstubstubstubstubstubstubstubstubstubs",
        "email": None,
        "method": "manual",
        "admin": True,
        "theme": "light",
        "language": stored_language,
        "totp_secret": "already-enrolled",  # skips the MFA-reminder flash path
        "webauthn_credentials_count": 0,
    }
    login.API_CLIENT.mark_user_login.return_value = 1

    def fake_establish_session(ui_user, user_data, *, mfa_done, remember_me):
        # The real function's one behaviour that matters here: it clears the session. A fix that
        # reads `session["language"]` after this call, instead of before, would see it gone.
        session.clear()
        return True

    with app.test_request_context("/login", method="POST", data={"username": "admin", "password": "whatever"}):
        if session_language is not None:
            session["language"] = session_language
        with patch.object(login, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None, get_id=lambda: "admin")), patch.object(
            login, "_establish_session", side_effect=fake_establish_session
        ), patch.object(login, "checkpw", return_value=True):
            login.login_page()

    assert login.API_CLIENT.update_user.called, "a successful login did not update the user at all"
    _, kwargs = login.API_CLIENT.update_user.call_args
    login.API_CLIENT.update_user.reset_mock()
    return kwargs


def test_a_user_who_never_touched_the_selector_keeps_their_stored_language(app, login_module):
    kwargs = _login(app, login_module, session_language=None, stored_language="fr")

    assert "language" not in kwargs, "no explicit pick was made, but the login still sent a language"


def test_an_explicit_pick_on_the_login_page_is_saved(app, login_module):
    kwargs = _login(app, login_module, session_language="de", stored_language="fr")

    assert kwargs.get("language") == "de"


def test_a_stale_or_unsupported_session_value_is_not_forwarded(app, login_module):
    kwargs = _login(app, login_module, session_language="not-a-real-language", stored_language="fr")

    assert "language" not in kwargs

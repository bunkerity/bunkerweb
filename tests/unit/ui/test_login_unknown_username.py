"""Security: logging in with an unknown username must answer exactly like a wrong password.

`API_CLIENT.get_user_for_auth` raises `ApiClientError` on a 404 (unknown username) instead of
returning `None` -- `login_page()` called it with no try/except, so that exception propagated
into a bare, unhandled 500. That response is trivially distinguishable from the styled 401 a real
username with a wrong password gets, which is a username-enumeration oracle: an attacker can
tell which usernames exist from the response alone, no timing needed.

The fix also closes the cheap half of the *timing* side of the same oracle: `checkpw` (bcrypt) is
expensive by design, and the original `user_data and ... and checkpw(...)` short-circuited past it
entirely for a nonexistent username, so even a byte-identical response would have come back faster
for "no such user" than for "wrong password" on a real one. `checkpw` now always runs once, against
a dummy hash when there is no real user.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from flask_login import LoginManager

UI = Path(__file__).resolve().parents[3] / "src" / "ui"


@pytest.fixture(scope="module")
def login_module():
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
        spec = importlib.util.spec_from_file_location("app.routes._login_unknown_username_test", UI / "app" / "routes" / "login.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["app.routes._login_unknown_username_test"] = module
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def app(login_module):
    application = Flask("bw_ui_login_unknown_username_test")
    application.secret_key = "test"
    manager = LoginManager()
    manager.init_app(application)
    manager.user_loader(lambda user_id: None)
    application.register_blueprint(login_module.login)
    application.add_url_rule("/setup", endpoint="setup.setup_page", view_func=lambda: "")
    return application


def _attempt_login(app, login, *, username, get_user_for_auth, password="whatever"):
    """Run one POST /login and return `(status_code, render_template kwargs, flash calls)`.

    `render_template` is faked (a bare `Flask()` here has no app templates configured, and this
    test cares about the response's substance -- status and the `error`/flash text the failure
    path carries -- not the rendered HTML bytes, which a real render would make identical between
    scenarios anyway and so prove nothing extra)."""
    login.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
    login.API_CLIENT.get_user_for_auth.side_effect = get_user_for_auth
    captured = {}
    render = Mock(return_value="rendered")
    flashed = Mock()

    with app.test_request_context("/login", method="POST", data={"username": username, "password": password}):
        with patch.object(login, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None)), patch.object(
            login, "render_template", lambda name, **kwargs: (captured.update(kwargs), render(name, **kwargs))[1]
        ), patch.object(login, "flash", flashed):
            body = login.login_page()

    status = body[1] if isinstance(body, tuple) else 200
    return status, captured, flashed.call_args_list


def test_an_unknown_username_does_not_crash(app, login_module):
    """The bug: this used to raise `ApiClientError` straight out of the view."""
    login = login_module

    def raises_not_found(username):
        raise login.ApiClientError(f"User {username} not found", status_code=404)

    status, captured, flashed = _attempt_login(app, login, username="nobody", get_user_for_auth=raises_not_found)

    assert status == 401
    assert captured.get("error") == "Invalid username or password"
    assert flashed == [(("Invalid username or password", "error"), {"save": False})]


def test_an_unknown_username_answers_exactly_like_a_wrong_password(app, login_module):
    login = login_module

    def raises_not_found(username):
        raise login.ApiClientError(f"User {username} not found", status_code=404)

    unknown_status, unknown_captured, unknown_flashed = _attempt_login(app, login, username="nobody", get_user_for_auth=raises_not_found)

    login.API_CLIENT.get_user_for_auth.reset_mock(side_effect=True)
    wrong_status, wrong_captured, wrong_flashed = _attempt_login(
        app,
        login,
        username="admin",
        get_user_for_auth=lambda username: {
            "username": "admin",
            "password": login_module.gen_password_hash("a-real-but-different-password").decode("utf-8"),
        },
    )

    assert unknown_status == wrong_status == 401
    assert unknown_captured == wrong_captured
    assert unknown_flashed == wrong_flashed


def test_overlong_utf8_password_answers_like_invalid_credentials(app, login_module):
    login = login_module
    password = "é" * 37  # 74 UTF-8 bytes, beyond bcrypt's 72-byte limit.

    def raises_not_found(username):
        raise login.ApiClientError(f"User {username} not found", status_code=404)

    unknown = _attempt_login(app, login, username="nobody", get_user_for_auth=raises_not_found, password=password)
    known = _attempt_login(
        app,
        login,
        username="admin",
        get_user_for_auth=lambda username: {
            "username": "admin",
            "password": login.gen_password_hash("a-real-but-different-password").decode("utf-8"),
        },
        password=password,
    )

    assert unknown == known
    assert unknown[0] == 401
    assert unknown[1]["error"] == "Invalid username or password"


def test_an_api_outage_on_lookup_also_fails_closed_like_a_wrong_password(app, login_module):
    """Same treatment for the other exception `get_user_for_auth` can raise -- an outage must not
    read differently from "no such user" either."""
    login = login_module

    def raises_unavailable(username):
        raise login.ApiUnavailableError("offline")

    status, captured, flashed = _attempt_login(app, login, username="admin", get_user_for_auth=raises_unavailable)

    assert status == 401
    assert captured.get("error") == "Invalid username or password"
    assert flashed == [(("Invalid username or password", "error"), {"save": False})]


def test_checkpw_still_runs_for_an_unknown_username():
    """Closes the timing half: without a dummy-hash check, `user_data and ... and checkpw(...)`
    short-circuits past `checkpw` entirely whenever `user_data` is falsy, so a nonexistent
    username returns well before a real one with a wrong password does."""
    import importlib.util as _ilu

    spec = _ilu.spec_from_file_location("app.routes._login_dummy_hash_test", UI / "app" / "routes" / "login.py")
    module = _ilu.module_from_spec(spec)
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
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "app.models.biscuit": biscuit_module, "qrcode": qrcode, "qrcode.main": qrcode_main}):
        spec.loader.exec_module(module)

    application = Flask("bw_ui_login_dummy_hash_test")
    application.secret_key = "test"
    manager = LoginManager()
    manager.init_app(application)
    manager.user_loader(lambda user_id: None)
    application.register_blueprint(module.login)

    module.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
    module.API_CLIENT.get_user_for_auth.side_effect = module.ApiClientError("not found", status_code=404)

    real_checkpw = module.checkpw
    spy = Mock(side_effect=real_checkpw)
    with application.test_request_context("/login", method="POST", data={"username": "nobody", "password": "whatever"}):
        with patch.object(module, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None)), patch.object(
            module, "checkpw", spy
        ), patch.object(module, "render_template", Mock(return_value="rendered")):
            module.login_page()

    spy.assert_called_once()

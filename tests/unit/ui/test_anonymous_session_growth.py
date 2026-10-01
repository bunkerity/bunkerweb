"""H17: unauthenticated requests must not grow the non-evicting session store.

Measured on the dev stack (`proofs/fix-qa5-sec/h17-live-red.txt`): every cookieless GET of a
protected URL (`/home`, `/loading`, `/instances`) stored a 93-byte, 12 h key in the broker. The key
held one thing, Flask-Login's "Please log in to access this page." flash, written by
`LoginManager.unauthorized()` before the redirect to /login. A GET of `/login` itself stored the
login form's CSRF token for 12 h as well.

* The flash is dropped (`login_message = None`): it told a visitor already on the login page to log
  in, and it was the only thing those requests wrote.
* A session with nobody logged in (the login form's CSRF token, a language picked on the login
  page) is stored for at most an hour, the lifetime of the CSRF token it carries. A logged-in
  session keeps the full lifetime.
"""

import ast
from datetime import timedelta
from typing import Any

import pytest
from flask import Flask, session
from flask_login import LoginManager, login_required

from test_session_plumbing import MAIN, UTILS, FakeServerSideInterface, _Session, _shipped, _tree

LIFETIME = timedelta(hours=12)


def _main_login_message():
    """The value main.py assigns to `login_manager.login_message`, or the attribute's absence."""
    for node in ast.walk(_tree(MAIN)):
        if isinstance(node, ast.Assign) and any(ast.unparse(target) == "login_manager.login_message" for target in node.targets):
            return ast.literal_eval(node.value)
    pytest.fail("main.py leaves Flask-Login's login_message at its default flash")


def _anonymous_hit(login_message):
    app = Flask("bw_ui_h17_test")
    app.secret_key = "test"
    manager = LoginManager()
    manager.init_app(app)
    manager.login_view = "login"
    manager.user_loader(lambda user_id: None)
    manager.login_message = login_message
    app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
    app.add_url_rule("/home", endpoint="home", view_func=login_required(lambda: "home"))

    with app.test_request_context("/home"):
        response = app.full_dispatch_request()
        return response, dict(session)


def test_the_default_flash_is_what_filled_the_session():
    """The mechanism, with the library's own default: one redirect, one stored flash."""
    _, stored = _anonymous_hit(LoginManager().login_message)

    assert "_flashes" in stored


def test_an_anonymous_hit_on_a_protected_url_writes_nothing_to_its_session():
    response, stored = _anonymous_hit(_main_login_message())

    assert response.status_code == 302
    assert response.location.startswith("/login?next=")
    assert stored == {}, f"an anonymous redirect still writes {sorted(stored)} to a server-side session"


# ------------------------------------------------------------------ anonymous session lifetime


class _RecordingInterface(FakeServerSideInterface):
    def __init__(self):
        super().__init__("bunkerweb_ui_session:")
        self.lifetimes = {}

    def _upsert_session(self, session_lifetime, session, store_id):
        super()._upsert_session(session_lifetime, session, store_id)
        self.lifetimes[store_id] = session_lifetime


def _capped():
    namespace = _shipped(UTILS, ("ANONYMOUS_SESSION_SECONDS", "cap_anonymous_session_lifetime"), {"Any": Any, "timedelta": timedelta})
    interface = _RecordingInterface()
    namespace["cap_anonymous_session_lifetime"](interface)
    return namespace, interface


def test_a_session_with_nobody_logged_in_is_stored_for_an_hour_at_most():
    namespace, interface = _capped()

    interface._upsert_session(LIFETIME, _Session({"csrf_token": "x"}, sid="anon"), "bunkerweb_ui_session:anon")

    assert interface.lifetimes["bunkerweb_ui_session:anon"] == timedelta(seconds=namespace["ANONYMOUS_SESSION_SECONDS"]) <= timedelta(hours=1)
    assert interface.store["bunkerweb_ui_session:anon"] == {"csrf_token": "x"}


def test_a_logged_in_session_keeps_the_full_lifetime():
    """A session pending its second factor is logged in too (Flask-Login's `_user_id` is set)."""
    _, interface = _capped()

    interface._upsert_session(LIFETIME, _Session({"_user_id": "admin", "csrf_token": "x"}, sid="user"), "bunkerweb_ui_session:user")

    assert interface.lifetimes["bunkerweb_ui_session:user"] == LIFETIME


def test_main_caps_the_session_interface_it_serves():
    source = MAIN.read_text(encoding="utf-8")

    assert "cap_anonymous_session_lifetime(app.session_interface)" in source
    # Capped after the Redis/file chaining, so the cap reaches the chained writer.
    assert source.index("chain_session_fallback(app.session_interface") < source.index("cap_anonymous_session_lifetime(app.session_interface)")

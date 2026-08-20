"""Revocation has to mean something: the three ways it did not.

1. **The Flask-Login remember cookie was an unrevocable bearer credential.**
   `login_user(ui_user, remember=True)` issued `__Host-bw_ui_remember_token`, carrying only the
   username HMAC'd with the static `FLASK_SECRET`, for flask-login's default 365 days. It touched
   no server-side state, so nothing could revoke it — logout only cleared it in the browser doing
   the logging out, and "wipe other sessions" and a password change never saw it. Redeeming it
   minted a *fresh* session with no `session_id` key, so `main.py`'s revocation check could not
   match it, and `ip` / `user_agent` / `creation_date` were re-stamped from the redeeming request,
   so IP+UA pinning and `SESSION_ABSOLUTE_HOURS` were bypassed too.
   Measured, not reasoned: `.cache/results-2026-08-20/remember-me-harness.py` puts that to the real
   flask-login 0.6.3 with both configs. What is pinned *here* is the wiring the harness models, so
   the two cannot drift apart.

2. **Revocations did not outlive the container.** The revoked ids lived in `DATA`, i.e.
   `/var/tmp/bunkerweb/ui_data.json` — outside the persistent volume and per-container — while the
   sessions they revoke live under `LIB_DIR`. A recreate forgot every revocation and kept every
   session, and a revocation never reached a second UI replica. They now go in the store that backs
   Flask-Session, which is the only thing that has exactly the durability and reach of the sessions
   it guards.

3. **"Wipe other sessions" un-revoked everything else.** `profile.py` *assigned*
   `DATA["REVOKED_SESSIONS"]` a fresh list, dropping every id an earlier logout had revoked.
   Nothing to test in isolation any more — the assignment is gone and `revoke_sessions` only ever
   adds — so it is pinned by the static check that no route writes that key again.
"""

import ast
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

_UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "ui"
MAIN_PY = _UI_ROOT / "main.py"
LOGIN_PY = _UI_ROOT / "app" / "routes" / "login.py"
LOGOUT_PY = _UI_ROOT / "app" / "routes" / "logout.py"
PROFILE_PY = _UI_ROOT / "app" / "routes" / "profile.py"

if str(_UI_ROOT) not in sys.path:  # conftest does this too; ordering between test files is not ours
    sys.path.insert(0, str(_UI_ROOT))

from app.utils import is_session_revoked, revoke_sessions  # noqa: E402

# The sentinel the harness in .cache/results-2026-08-20/remember-me-harness.py models.
SENTINEL_REMEMBER_COOKIE = "bw_ui_remember_disabled"


# ── the wiring, asserted against the source ────────────────────────────────────────────


def test_no_real_remember_cookie_is_configured():
    """A sentinel name, and none of the settings that make a remember cookie work."""
    source = MAIN_PY.read_text(encoding="utf-8")
    assert f'app.config["REMEMBER_COOKIE_NAME"] = "{SENTINEL_REMEMBER_COOKIE}"' in source

    # Anything that configures a *usable* remember cookie is the defect coming back.
    for setting in ("REMEMBER_COOKIE_SECURE", "REMEMBER_COOKIE_PATH", "REMEMBER_COOKIE_HTTPONLY", "REMEMBER_COOKIE_SAMESITE", "REMEMBER_COOKIE_DURATION"):
        assert f'app.config["{setting}"]' not in source, f"{setting} is set again: a remember cookie is being issued"

    # ...including through the proxy auto-detection, which used to switch the name per environment.
    assert "__Host-bw_ui_remember_token" not in source.split("legacy_cookie")[0], "the real remember cookie name is configured again"


def test_login_does_not_ask_flask_login_to_remember():
    """`remember=` on `login_user` is what issues the cookie. `session.permanent` is the feature."""
    source = LOGIN_PY.read_text(encoding="utf-8")
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "login_user"
    ]
    assert calls, "login_user is not called any more -- this test is checking nothing"
    for call in calls:
        assert not any(kw.arg == "remember" for kw in call.keywords), "login_user(remember=...) issues the unrevocable cookie again"
    assert "session.permanent = True" in source, '"remember me" must still survive a browser restart'


def test_a_pre_upgrade_token_is_evicted():
    """Already-issued tokens are inert (sentinel name), but should not sit in browsers either."""
    source = MAIN_PY.read_text(encoding="utf-8")
    for legacy in ("__Host-bw_ui_remember_token", "bw_ui_remember_token"):
        assert legacy in source, f"{legacy} is no longer evicted from browsers that still hold it"
    assert "response.delete_cookie(legacy_cookie" in source


def test_revocation_no_longer_goes_through_the_data_file():
    """DATA is per-container and outside the persistent volume; sessions are not."""
    assert "is_session_revoked(session[" in MAIN_PY.read_text(encoding="utf-8")
    for path in (MAIN_PY, LOGIN_PY, LOGOUT_PY, PROFILE_PY):
        assert "REVOKED_SESSIONS" not in path.read_text(encoding="utf-8"), f"{path.name} still reads or writes the DATA key"


# ── the helpers, against both backend shapes ───────────────────────────────────────────


class FakeRedis:
    """The two calls `revoke_sessions`/`is_session_revoked` make on a redis client."""

    def __init__(self):
        self.store = {}

    def setex(self, key, ttl, value):
        self.store[key] = (ttl, value)

    def exists(self, key):
        return 1 if key in self.store else 0


class FakeCache:
    """...and on a cachelib cache."""

    def __init__(self):
        self.store = {}

    def set(self, key, value, timeout=None):
        self.store[key] = (timeout, value)

    def get(self, key):
        return self.store.get(key, (None, None))[1]


# main.py's defaults: SESSION_LIFETIME_HOURS=12 (idle) under a SESSION_ABSOLUTE_HOURS=168 cap.
IDLE_LIFETIME = timedelta(hours=12)
ABSOLUTE_SECONDS = 168 * 3600


def _app(interface):
    app = Flask(__name__)
    app.config["PERMANENT_SESSION_LIFETIME"] = IDLE_LIFETIME
    app.config["SESSION_ABSOLUTE_SECONDS"] = ABSOLUTE_SECONDS
    app.session_interface = interface
    return app


@pytest.fixture(params=("redis", "cachelib"))
def backend(request):
    if request.param == "redis":
        client = FakeRedis()
        return _app(SimpleNamespace(client=client, key_prefix="bunkerweb_ui_session:")), client
    cache = FakeCache()
    return _app(SimpleNamespace(cache=cache)), cache


def test_a_revoked_session_reads_back_as_revoked(backend):
    app, _ = backend
    with app.app_context():
        assert revoke_sessions(["sid-1", "sid-2"]) == ""
        assert is_session_revoked("sid-1") is True
        assert is_session_revoked("sid-2") is True
        assert is_session_revoked("sid-3") is False


def test_revoking_does_not_drop_earlier_revocations(backend):
    """The 1.7 defect: "wipe other sessions" replaced the whole set, un-revoking every logout."""
    app, _ = backend
    with app.app_context():
        revoke_sessions(["logged-out-earlier"])
        revoke_sessions(["wiped-now"])
        assert is_session_revoked("logged-out-earlier") is True
        assert is_session_revoked("wiped-now") is True


def test_the_entry_expires_with_the_sessions_it_guards(backend):
    """No pruning code any more: the backend has to be told the lifetime, or it never expires.

    It has to be the *longest* a session can live -- the absolute cap, not the idle one -- or an
    id stops being rejected while the session it names is still usable.
    """
    app, store = backend
    with app.app_context():
        revoke_sessions(["sid-1"])
    ttl = next(iter(store.store.values()))[0]
    assert ttl == ABSOLUTE_SECONDS
    assert ttl > IDLE_LIFETIME.total_seconds()


def test_an_empty_or_missing_id_is_not_an_error(backend):
    app, store = backend
    with app.app_context():
        assert revoke_sessions([]) == ""
        assert revoke_sessions([None, ""]) == ""
        assert is_session_revoked(None) is False
    assert store.store == {}


def test_a_missing_backend_is_reported_not_swallowed():
    """wipe-other-sessions must abort rather than report success having revoked nothing."""
    app = _app(SimpleNamespace())
    with app.app_context():
        assert revoke_sessions(["sid-1"]) != ""
        # ...while the read side fails open: with no store there is no session to authenticate.
        assert is_session_revoked("sid-1") is False


def test_a_broken_backend_fails_open_on_read_and_closed_on_write():
    class Broken:
        def setex(self, *_args, **_kwargs):
            raise RuntimeError("redis is down")

        def exists(self, *_args, **_kwargs):
            raise RuntimeError("redis is down")

    app = _app(SimpleNamespace(client=Broken(), key_prefix="p:"))
    with app.app_context():
        assert revoke_sessions(["sid-1"]) != ""
        assert is_session_revoked("sid-1") is False

"""Failed logins are throttled per client IP and per username, in the database, through the real routes.

Ported from dev's `tests/unit/ui/routes/test_routes_login_throttle.py` (1.6.18~rc3, commit bda10b007). On
dev the routes held a `UIDatabase`; on 1.7 the UI never touches the database, so the same behaviour runs
through `API_CLIENT` to three `/users/login-throttle/*` endpoints. Here the client is a fake whose three
throttle methods call the real `Database` mixin on SQLite, so the count really lives in
`bw_ui_login_failures` and survives from one request (one worker) to the next.

The login, TOTP and profile blueprints are the real source files, loaded with `app.dependencies` stubbed
(the pattern of `test_login_unknown_username.py`). Beyond dev's cases this file pins what 1.7 adds:
the throttle fails closed when its endpoint is down, passkeys are neither counted nor locked, and the
profile page's current-password check shares the counters, so a stolen session cannot guess the password there.
"""

import ast
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from bcrypt import gensalt, hashpw
from flask import Flask, redirect
from flask_login import LoginManager

UI = Path(__file__).resolve().parents[3] / "src" / "ui"
PASSWORD = "Correct-Horse1!"
HASH = hashpw(PASSWORD.encode(), gensalt(rounds=4)).decode()
WRONG = {"username": "alice", "password": "wrong"}
RIGHT = {"username": "alice", "password": PASSWORD}
THROTTLE_ENV = ("LOGIN_THROTTLE", "LOGIN_MAX_ATTEMPTS", "LOGIN_WINDOW_MINUTES", "LOGIN_LOCKOUT_MINUTES")


def _stubs():
    dependencies = ModuleType("app.dependencies")
    for name in ("API_CLIENT", "BW_CONFIG", "BW_INSTANCES_UTILS", "LOGGER", "CONFIG_TASKS_EXECUTOR"):
        setattr(dependencies, name, Mock())
    dependencies.DATA = {}
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    biscuit_module = ModuleType("app.models.biscuit")
    biscuit_module.BiscuitTokenFactory = Mock()
    biscuit_module.PrivateKey = Mock()
    # passlib and user_agents are not in the unit venv; neither is under test here
    totp_module = ModuleType("app.models.totp")
    totp_module.totp = Mock()
    user_agents = ModuleType("user_agents")
    user_agents.parse = Mock()
    return {
        "app.dependencies": dependencies,
        "app.models.biscuit": biscuit_module,
        "app.models.totp": totp_module,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        "user_agents": user_agents,
    }


def _load(name):
    with patch.dict(sys.modules, _stubs()):
        spec = importlib.util.spec_from_file_location(f"app.routes._login_throttle_{name}", UI / "app" / "routes" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


@pytest.fixture(scope="module")
def login_module():
    return _load("login")


@pytest.fixture(scope="module")
def totp_module():
    return _load("totp")


@pytest.fixture(scope="module")
def profile_module():
    return _load("profile")


class FakeApi:
    """What `ApiClient` does for the routes under test; the throttle calls run the real DB mixin."""

    def __init__(self, db, errors):
        # the exception classes of the module under test: it was loaded under stubs, so its `app.api_client`
        # is not the one an import in this file would find
        self.db, self.errors = db, errors
        self.users = {"alice": {"username": "alice", "password": HASH, "totp_secret": None, "webauthn_credentials_count": 0}}
        self.up = True
        self.calls = []
        self.readonly = False

    def _guard(self, name):
        self.calls.append(name)
        if not self.up:
            raise self.errors.ApiUnavailableError("API unavailable")

    # the pre-existing surface login.py/totp.py/profile.py use
    def get_admin_user(self, auth=False):
        return {"username": "alice"}

    def get_user_for_auth(self, username):
        if username not in self.users:
            raise self.errors.ApiClientError(f"User {username} not found", status_code=404)
        return dict(self.users[username])

    def mark_user_login(self, *args):
        return 1

    def update_user(self, *args, **kwargs):
        return {}

    # the three throttle calls
    def check_login_throttle(self, username, ip, *, max_attempts, window, lockout):
        self._guard("check")
        return self.db.get_ui_login_lock(username, ip, max_attempts=max_attempts, window=window, lockout=lockout)

    def record_login_failure(self, username, ip, *, retention):
        self._guard("record")
        if self.db.readonly:
            raise self.errors.ApiClientError("The database is read-only", status_code=409)
        return self.db.add_ui_login_failure(username, ip, retention=retention)

    def clear_login_failures(self, username):
        self._guard("clear")
        return self.db.clear_ui_login_failures(username)


def _failures(db):
    from model import UserLoginFailures

    with db._db_session() as session:
        return [(row.username, row.ip) for row in session.query(UserLoginFailures).order_by(UserLoginFailures.id).all()]


def _age(db, minutes):
    from model import UserLoginFailures

    with db._db_session() as session:
        for row in session.query(UserLoginFailures).all():
            stored = row.failure_date if row.failure_date.tzinfo else row.failure_date.replace(tzinfo=timezone.utc)
            row.failure_date = stored - timedelta(minutes=minutes)
        session.commit()


def _seed(db, *minutes_ago, username="alice", ip="203.0.113.1"):
    from model import UserLoginFailures

    now = datetime.now(timezone.utc)
    with db._db_session() as session:
        for minutes in minutes_ago:
            session.add(UserLoginFailures(username=username, ip=ip, failure_date=now - timedelta(minutes=minutes)))
        session.commit()


class Harness:
    def __init__(self, app, login, api, db, monkeypatch):
        self.app, self.login, self.api, self.db, self.monkeypatch = app, login, api, db, monkeypatch
        self.renders = []
        self.flashes = []

    def client(self, ip="203.0.113.1"):
        client = self.app.test_client()
        client.environ_base["REMOTE_ADDR"] = ip
        return client

    def post(self, form, ip="203.0.113.1", **kwargs):
        return self.client(ip).post("/login", data=form, **kwargs)

    def fail(self, count, form=WRONG, ip="203.0.113.1"):
        for _ in range(count):
            assert self.post(form, ip).status_code == 401

    @property
    def error(self):
        return self.renders[-1]["error"]


@pytest.fixture
def h(db, login_module, monkeypatch):
    for name in THROTTLE_ENV:
        monkeypatch.delenv(name, raising=False)
    api = FakeApi(db, login_module)
    app = Flask("bw_ui_login_throttle_test")
    app.secret_key = "test"
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(login_module.login)
    app.add_url_rule("/setup", endpoint="setup.setup_page", view_func=lambda: "")
    app.add_url_rule("/home", endpoint="home.home_page", view_func=lambda: "")
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "")
    harness = Harness(app, login_module, api, db, monkeypatch)

    def render(name, **kwargs):
        harness.renders.append(kwargs)
        return "rendered"

    monkeypatch.setattr(login_module, "API_CLIENT", api)
    monkeypatch.setattr(login_module, "render_template", render)
    monkeypatch.setattr(login_module, "flash", lambda *args, **kwargs: harness.flashes.append(args[0]))
    monkeypatch.setattr(login_module, "_establish_session", lambda *args, **kwargs: True)
    monkeypatch.setattr(login_module, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None, get_id=lambda: "alice"))
    monkeypatch.setattr(login_module, "dismissed_notices", lambda username: {"mfa": True})
    return harness


# ── password form ───────────────────────────────────────────────────


def test_the_sixth_failure_is_locked_out_even_with_the_right_password(h):
    h.fail(5)

    response = h.post(RIGHT)

    assert response.status_code == 429 and response.headers["Retry-After"]
    assert "Too many failed attempts, try again in 15 min." in h.error
    assert h.post(RIGHT).status_code == 429  # a locked attempt does not extend or end the lock
    assert len(_failures(h.db)) == 5  # and is not counted


def test_a_locked_attempt_never_looks_the_user_up_or_checks_the_password(h):
    h.fail(5)
    h.api.calls.clear()
    h.login.API_CLIENT = Mock(wraps=h.api)

    h.post(RIGHT)

    names = [call[0] for call in h.login.API_CLIENT.method_calls]
    assert "get_user_for_auth" not in names


def test_the_fifth_failure_is_not_yet_locked(h):
    h.fail(4)

    assert h.post(WRONG).status_code == 401
    assert h.post(RIGHT).status_code == 429


def test_the_lock_expires(h):
    h.fail(5)
    assert h.post(RIGHT).status_code == 429

    _age(h.db, 16)

    response = h.post(RIGHT)
    assert response.status_code == 302 and "/loading" in response.headers["Location"]


def test_a_successful_login_resets_that_usernames_count(h):
    h.fail(4)
    assert len(_failures(h.db)) == 4
    assert h.post(RIGHT).status_code == 302
    assert _failures(h.db) == []

    h.fail(4)  # 8 failures in all: only a reset keeps this under the limit

    assert h.post(RIGHT).status_code == 302


def test_five_failures_from_one_ip_lock_that_ip_whatever_the_username(h):
    for name in ("bob", "carol", "dave", "erin", "frank"):
        assert h.post({"username": name, "password": "x"}, "198.51.100.7").status_code == 401

    assert h.post(RIGHT, "198.51.100.7").status_code == 429
    assert h.post({"username": "zoe", "password": "x"}, "198.51.100.7").status_code == 429
    assert h.post(RIGHT, "198.51.100.8").status_code == 302  # another IP is untouched


def test_five_failures_for_one_username_lock_it_from_every_ip(h):
    for octet in range(10, 15):
        assert h.post(WRONG, f"192.0.2.{octet}").status_code == 401

    assert h.post(RIGHT, "192.0.2.99").status_code == 429


def test_the_username_is_folded_so_another_case_shares_the_count(h):
    for octet, name in enumerate(("alice", "ALICE", "Alice", " alice", "alice ")):
        assert h.post({"username": name, "password": "x"}, f"192.0.2.{octet + 10}").status_code == 401

    assert h.post(RIGHT, "192.0.2.99").status_code == 429


def test_a_lock_looks_the_same_for_a_known_and_an_unknown_username(h):
    for octet in range(10, 15):
        h.post(WRONG, f"192.0.2.{octet}")
        h.post({"username": "ghost", "password": "x"}, f"192.0.2.{octet}")

    known = h.post(RIGHT, "192.0.2.99")
    known_error = h.error
    unknown = h.post({"username": "ghost", "password": "x"}, "192.0.2.99")

    assert known.status_code == unknown.status_code == 429
    assert known_error == h.error
    assert known_error.startswith("Invalid username or password.")
    assert known.headers["Retry-After"] == unknown.headers["Retry-After"]


def test_an_unknown_username_fails_like_a_known_one_until_the_lock(h):
    known = h.post(WRONG)
    known_error = h.error
    unknown = h.post({"username": "ghost", "password": "x"})

    assert known.status_code == unknown.status_code == 401
    assert h.error == known_error == "Invalid username or password"
    assert [name for name, _ in _failures(h.db)] == ["alice", "ghost"]  # unknown usernames are counted too


def test_the_ip_is_the_one_the_reverse_proxy_layer_trusts(h):
    from app.models.reverse_proxied import ReverseProxied

    h.monkeypatch.setattr(h.app, "wsgi_app", ReverseProxied(h.app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1))

    # the proxy appended 9.9.9.9; the leading entry is whatever the client claimed
    h.client("10.0.0.2").post("/login", data=WRONG, headers={"X-Forwarded-For": "6.6.6.6, 9.9.9.9"})

    assert _failures(h.db) == [("alice", "9.9.9.9")]


def test_a_forwarded_header_is_ignored_when_no_proxy_layer_is_in_front(h):
    h.client("10.0.0.2").post("/login", data=WRONG, headers={"X-Forwarded-For": "6.6.6.6"})

    assert _failures(h.db) == [("alice", "10.0.0.2")]


def test_old_failures_are_pruned_when_a_new_one_is_recorded(h):
    h.fail(2)
    _age(h.db, 120)

    h.fail(1)

    assert len(_failures(h.db)) == 1


def test_the_pruning_keeps_the_failures_a_lock_still_needs(h):
    _seed(h.db, 26, 23, 20, 17, 14)  # the lock runs for another minute and needs all five

    assert h.post({"username": "bob", "password": "x"}, "198.51.100.7").status_code == 401  # a failure prunes first

    assert len(_failures(h.db)) == 6
    assert h.post(RIGHT).status_code == 429


def test_the_throttle_can_be_turned_off(h):
    h.monkeypatch.setenv("LOGIN_THROTTLE", "no")
    h.fail(8)

    assert h.post(RIGHT).status_code == 302
    assert _failures(h.db) == []
    assert h.api.calls == []  # no round trip at all


def test_the_three_numbers_are_tunable(h):
    h.monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "2")
    h.monkeypatch.setenv("LOGIN_LOCKOUT_MINUTES", "30")
    h.monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "20")
    h.fail(2)

    assert h.post(RIGHT).status_code == 429
    assert "30 min" in h.error

    _age(h.db, 25)  # out of the 20 minute window, still inside the 30 minute lockout: still locked
    assert h.post(RIGHT).status_code == 429

    _age(h.db, 10)  # 35 minutes after the last failure
    assert h.post(RIGHT).status_code == 302


def test_an_invalid_setting_falls_back_to_the_default(h):
    h.monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "many")
    h.monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "0")
    h.fail(5)

    assert h.post(RIGHT).status_code == 429


def test_a_read_only_database_cannot_count_so_it_does_not_lock(h):
    h.db.readonly = True
    for _ in range(7):
        assert h.post(WRONG).status_code == 401

    assert _failures(h.db) == []


# ── API down (1.7): fail closed ─────────────────────────────────────


def test_an_unreachable_throttle_refuses_the_attempt_without_checking_the_password(h):
    h.api.up = False
    h.login.API_CLIENT = Mock(wraps=h.api)

    response = h.post(RIGHT)

    assert response.status_code == 503
    assert "temporarily unavailable" in h.error
    assert "get_user_for_auth" not in [call[0] for call in h.login.API_CLIENT.method_calls]
    assert not h.error.startswith("Invalid username or password")


def test_the_unavailable_answer_is_the_same_for_every_username(h):
    h.api.up = False

    known = h.post(RIGHT)
    known_error = h.error
    unknown = h.post({"username": "ghost", "password": "x"})

    assert known.status_code == unknown.status_code == 503
    assert known_error == h.error


def test_turning_the_throttle_off_is_the_way_back_in_when_its_endpoint_is_broken(h):
    h.api.up = False
    h.monkeypatch.setenv("LOGIN_THROTTLE", "no")

    assert h.post(RIGHT).status_code == 302


def test_a_failure_that_cannot_be_recorded_does_not_change_the_answer(h):
    def boom(*args, **kwargs):
        raise RuntimeError("database gone")

    h.api.record_login_failure = boom

    assert h.post(WRONG).status_code == 401  # the attempt was refused anyway; only the count is lost


def test_a_clear_that_cannot_run_does_not_stop_a_login(h):
    def boom(*args, **kwargs):
        raise RuntimeError("database gone")

    h.api.clear_login_failures = boom

    assert h.post(RIGHT).status_code == 302


# ── passkeys: neither counted nor locked ────────────────────────────


def test_a_locked_username_and_ip_do_not_block_the_passkey_ceremony(h):
    """A passkey is possession, not a guessable secret: a lock on the password never reaches it."""
    h.fail(5)
    h.api.calls.clear()
    h.monkeypatch.setattr(
        h.login,
        "WEBAUTHN",
        SimpleNamespace(enabled=True, credential_id_from_response=Mock(side_effect=h.login.WebauthnCeremonyError("bad")), log_failure=Mock()),
    )

    response = h.client().post("/login/webauthn/verify", json={"id": "x"}, headers={"Sec-Fetch-Mode": "cors"})

    assert response.status_code == 401  # the ceremony's own verdict, not 429
    assert h.api.calls == []  # no throttle round trip: nothing counted, nothing checked
    assert len(_failures(h.db)) == 5


def test_a_passkey_login_clears_the_usernames_count(h):
    _seed(h.db, 1, 2, 3)
    h.monkeypatch.setattr(
        h.login,
        "WEBAUTHN",
        SimpleNamespace(
            enabled=True,
            credential_id_from_response=Mock(return_value="cred"),
            user_handle_from_response=Mock(return_value=None),
            verify_authentication=Mock(return_value=1),
            log_failure=Mock(),
        ),
    )
    h.api.resolve_webauthn_credential = lambda credential_id: {"username": "alice", "user_handle": "h"}
    h.api.update_user_webauthn_credential = lambda *args, **kwargs: {}

    response = h.client().post("/login/webauthn/verify", json={"id": "x"}, headers={"Sec-Fetch-Mode": "cors"})

    assert response.status_code == 200
    assert _failures(h.db) == []


# ── second factor ───────────────────────────────────────────────────


@pytest.fixture
def mfa(h, totp_module):
    """alice has a TOTP secret; the TOTP page runs over the same fake client."""
    h.api.users["alice"]["totp_secret"] = "a-totp-secret"
    totp = SimpleNamespace(verify_totp=Mock(return_value=False), verify_recovery_code=Mock(return_value=None))
    state = SimpleNamespace(module=totp_module, totp=totp, refusals=[])
    h.monkeypatch.setattr(totp_module, "API_CLIENT", h.api)
    h.monkeypatch.setattr(totp_module, "TOTP", totp)
    h.monkeypatch.setattr(
        totp_module,
        "current_user",
        SimpleNamespace(get_id=lambda: "alice", totp_secret="a-totp-secret", list_recovery_codes=[1, 2], webauthn_credentials_count=0),
    )

    def handle_error(message, redirect_url="", **kwargs):
        state.refusals.append(message)
        return redirect("/totp-page")

    h.monkeypatch.setattr(totp_module, "handle_error", handle_error)
    h.monkeypatch.setattr(totp_module, "flash", lambda *args, **kwargs: state.refusals.append(args[0]))
    h.app.add_url_rule("/totp-page", endpoint="totp.totp_page", view_func=lambda: "")
    return state


def _totp(h, mfa, token="000000", ip="203.0.113.1"):
    with h.app.test_request_context("/totp", method="POST", data={"totp_token": token}, environ_base={"REMOTE_ADDR": ip}):
        from flask import session

        response = mfa.module.totp_page.__wrapped__()
        return response, dict(session)


def test_a_wrong_totp_code_counts_and_five_lock_the_username(h, mfa):
    for _ in range(5):
        _totp(h, mfa)
    assert [name for name, _ in _failures(h.db)] == ["alice"] * 5

    mfa.totp.verify_totp.reset_mock()
    mfa.totp.verify_totp.return_value = True  # the right code is not even looked at once locked
    mfa.refusals.clear()
    response, session = _totp(h, mfa, "123456")

    assert response.status_code == 302
    mfa.totp.verify_totp.assert_not_called()
    assert any("Too many failed attempts" in message for message in mfa.refusals)
    assert not session.get("mfa_validated")
    assert h.post(RIGHT, "198.51.100.77").status_code == 429


def test_a_wrong_recovery_code_counts_too(h, mfa):
    for _ in range(5):
        _totp(h, mfa, "not-a-code")

    assert len(_failures(h.db)) == 5


def test_a_recovery_code_that_the_api_refuses_as_invalid_counts(h, mfa):
    mfa.totp.verify_recovery_code.return_value = "hashed"

    def refuse(username, code):
        raise mfa.module.ApiClientError("Invalid recovery code", status_code=400)

    h.api.use_recovery_code = refuse

    _totp(h, mfa, "replayed")

    assert len(_failures(h.db)) == 1


def test_a_recovery_code_refused_by_a_read_only_database_does_not_count(h, mfa):
    mfa.totp.verify_recovery_code.return_value = "hashed"

    def refuse(username, code):
        raise mfa.module.ApiClientError("read-only", status_code=409)

    h.api.use_recovery_code = refuse

    response, session = _totp(h, mfa, "valid-code")

    assert _failures(h.db) == []
    assert session.get("mfa_validated") is True


def test_the_right_totp_code_clears_the_count(h, mfa):
    _totp(h, mfa)
    assert len(_failures(h.db)) == 1

    mfa.totp.verify_totp.return_value = True
    response, session = _totp(h, mfa, "123456")

    assert _failures(h.db) == []
    assert session["mfa_validated"] is True


def test_a_password_alone_does_not_clear_the_count_when_a_second_factor_is_set(h, mfa):
    for _ in range(4):  # each cycle: log in with the right password, then miss the code
        assert h.post(RIGHT).status_code == 302
        _totp(h, mfa)
    assert len(_failures(h.db)) == 4  # logging in again never wiped them

    _totp(h, mfa)
    assert h.post(RIGHT).status_code == 429


def test_a_password_alone_does_not_clear_the_count_when_only_a_security_key_is_set(h):
    h.api.users["alice"]["webauthn_credentials_count"] = 1
    _seed(h.db, 1, 2)

    assert h.post(RIGHT).status_code == 302

    assert len(_failures(h.db)) == 2


def test_the_totp_page_fails_closed_when_the_throttle_is_unreachable(h, mfa):
    h.api.up = False
    mfa.totp.verify_totp.return_value = True

    response, session = _totp(h, mfa, "123456")

    assert response.status_code == 302
    mfa.totp.verify_totp.assert_not_called()
    assert not session.get("mfa_validated")
    assert any("temporarily unavailable" in message for message in mfa.refusals)


# ── profile: the current-password checks share the counters ─────────


@pytest.fixture
def profile(h, profile_module):
    state = SimpleNamespace(module=profile_module, errors=[])
    user = SimpleNamespace(
        get_id=lambda: "alice",
        username="alice",
        totp_secret=None,
        email=None,
        method="ui",
        theme="light",
        language="en",
        check_password=lambda password: password == PASSWORD,
    )
    h.api.readonly = False
    h.api.get_user_sessions = lambda username: []
    h.api.delete_user_sessions = lambda *args, **kwargs: {}
    h.monkeypatch.setattr(profile_module, "API_CLIENT", h.api)
    h.monkeypatch.setattr(profile_module, "current_user", user)

    def handle_error(message, redirect_url="", **kwargs):
        state.errors.append(message)
        return redirect("/profile-page")

    h.monkeypatch.setattr(profile_module, "handle_error", handle_error)
    h.monkeypatch.setattr(profile_module, "flash", lambda *args, **kwargs: None)
    h.monkeypatch.setattr(profile_module, "revoke_sessions", lambda ids: "")
    h.app.add_url_rule("/profile-page", endpoint="profile.profile_page", view_func=lambda: "")
    return state


def _wipe(h, profile, password, ip="203.0.113.1"):
    with h.app.test_request_context("/profile/wipe-other-sessions", method="POST", data={"password": password}, environ_base={"REMOTE_ADDR": ip}):
        return profile.module.wipe_old_sessions.__wrapped__()


def test_a_wrong_current_password_on_the_profile_counts_and_five_lock_the_username(h, profile):
    for _ in range(5):
        _wipe(h, profile, "wrong")
    assert [name for name, _ in _failures(h.db)] == ["alice"] * 5
    assert profile.errors == ["The current password is incorrect."] * 5

    profile.errors.clear()
    _wipe(h, profile, PASSWORD)  # the right password is refused while locked

    assert profile.errors and "Too many failed attempts, try again in 15 min." in profile.errors[0]
    assert h.post(RIGHT, "198.51.100.77").status_code == 429  # the same counters as the login form


def test_login_failures_lock_the_profile_check_too(h, profile):
    h.fail(5)

    _wipe(h, profile, PASSWORD)

    assert "Too many failed attempts" in profile.errors[0]


def test_a_right_current_password_does_not_clear_the_count(h, profile):
    _seed(h.db, 1, 2, 3)

    _wipe(h, profile, PASSWORD)

    assert len(_failures(h.db)) == 3  # only a complete login clears it


def test_the_profile_check_fails_closed_when_the_throttle_is_unreachable(h, profile):
    h.api.up = False

    _wipe(h, profile, PASSWORD)

    assert profile.errors and "temporarily unavailable" in profile.errors[0]


def test_the_passkey_enrollment_password_check_is_throttled_too(h, profile):
    _seed(h.db, 1, 2, 3, 4, 5)
    with h.app.test_request_context(
        "/profile/webauthn/register/options", method="POST", json={"password": PASSWORD}, environ_base={"REMOTE_ADDR": "203.0.113.1"}
    ):
        response, status = profile.module.webauthn_register_options.__wrapped__.__wrapped__()

    assert status == 429
    assert "Too many failed attempts" in response.get_json()["message"]


def test_no_route_checks_the_current_password_outside_the_throttled_helper():
    """Every `current_user.check_password(` in profile.py sits behind the throttle, bar the new-equals-old comparison."""
    source = (UI / "app" / "routes" / "profile.py").read_text()
    tree = ast.parse(source)
    offenders = []
    for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
        for call in [node for node in ast.walk(function) if isinstance(node, ast.Call)]:
            target = call.func
            if isinstance(target, ast.Attribute) and target.attr == "check_password":
                argument = ast.unparse(call.args[0]) if call.args else ""
                if function.name != "_current_password_error" and argument.replace("'", '"') != 'request.form["new_password"]':
                    offenders.append(f"{function.name}:{call.lineno}")
    assert offenders == []


# ── ApiClient ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.api_client import ApiClient

    api_client = ApiClient("http://api.test", "token")
    try:
        yield api_client
    finally:
        api_client.session.close()
        api_client._no_retry_session.close()


def _respond(client, payload, *, status_code=200):
    response = Mock(status_code=status_code, content=b"{}")
    response.json.return_value = payload
    client.session.request = Mock(return_value=response)
    return client.session.request


def test_check_posts_the_policy_and_returns_the_seconds_left(client):
    request = _respond(client, {"status": "success", "remaining": 42})

    assert client.check_login_throttle("alice", "203.0.113.1", max_attempts=5, window=900, lockout=900) == 42

    args, kwargs = request.call_args
    assert args[0] == "POST" and args[1].endswith("/users/login-throttle/check")
    assert kwargs["json"] == {"username": "alice", "ip": "203.0.113.1", "max_attempts": 5, "window": 900, "lockout": 900}


def test_record_and_clear_post_to_their_endpoints(client):
    request = _respond(client, {"status": "success"})

    client.record_login_failure("alice", "203.0.113.1", retention=1800)
    client.clear_login_failures("alice")

    first, second = request.call_args_list
    assert first.args[1].endswith("/users/login-throttle/failures") and first.kwargs["json"] == {"username": "alice", "ip": "203.0.113.1", "retention": 1800}
    assert second.args[1].endswith("/users/login-throttle/clear") and second.kwargs["json"] == {"username": "alice"}


def test_a_username_with_a_slash_never_reaches_the_path(client):
    request = _respond(client, {"status": "success", "remaining": 0})

    client.check_login_throttle("a/../b", "1.1.1.1", max_attempts=5, window=900, lockout=900)

    assert "a/../b" not in request.call_args.args[1]

"""`POST /users/login-throttle/{check,failures,clear}`: the API half of the Web UI login throttle.

The UI never touches the database, so dev's `UIDatabase` throttle methods (1.6.18~rc3) became DB mixin
methods behind these three endpoints. Contracts the UI depends on:

* the router module declares the three routes, each behind the guard (like their siblings);
* `check` answers 200 with the seconds left (0 = not locked), never a 4xx for a lock: the lock is a
  verdict, not an error, and the UI reads any non-200 as "throttle unavailable";
* a read-only database is a 409 on the two writers, so the UI can tell it from an outage.

Same loader as `test_users_totp_endpoint.py`: the router module runs with its imports stubbed and its
handlers are called directly against a Mock db.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import password_utils  # type: ignore
import pytest

ROOT = Path(__file__).resolve().parents[3]
GUARD = object()


class _Router:
    routes = []

    def __init__(self, **_kwargs):
        self.routes = []

    def _decorator(self, method):
        def register(path, **kwargs):
            def wrap(function):
                self.routes.append((method, path, kwargs.get("dependencies") or []))
                return function

            return wrap

        return register

    def __getattr__(self, name):
        if name in ("get", "post", "patch", "delete", "put"):
            return self._decorator(name)
        raise AttributeError(name)


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


_DB = Mock()


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_users_lt": ModuleType("bw_users_lt"),
        "bw_users_lt.routers": ModuleType("bw_users_lt.routers"),
        "bw_users_lt.auth": ModuleType("bw_users_lt.auth"),
        "bw_users_lt.auth.guard": ModuleType("bw_users_lt.auth.guard"),
        "bw_users_lt.utils": ModuleType("bw_users_lt.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    for package in ("bw_users_lt", "bw_users_lt.routers", "bw_users_lt.auth"):
        names[package].__path__ = []
    names["bw_users_lt.auth.guard"].guard = GUARD
    names["bw_users_lt.utils"].get_db = lambda: _DB
    for name in ("USER_PASSWORD_RX", "gen_password_hash", "is_bcrypt_hash", "password_exceeds_bcrypt_limit"):
        setattr(names["bw_users_lt.utils"], name, getattr(password_utils, name))

    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "users.py"
        spec = importlib.util.spec_from_file_location("bw_users_lt.routers.users", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture(autouse=True)
def db():
    _DB.reset_mock(return_value=True, side_effect=True)
    _DB.readonly = False
    return _DB


def test_the_three_routes_exist_and_are_guarded():
    routes = {(method, path): dependencies for method, path, dependencies in ROUTER.router.routes}

    for path in ("/login-throttle/check", "/login-throttle/failures", "/login-throttle/clear"):
        assert routes.get(("post", path)) == [GUARD], path


def test_a_static_route_is_never_shadowed_by_a_username_route():
    """`/{username}/login` etc. are registered too; the throttle paths must not collide with one."""
    paths = [path for method, path, _ in ROUTER.router.routes if method == "post"]
    first = {path: index for index, path in enumerate(paths)}

    for path in ("/login-throttle/check", "/login-throttle/failures", "/login-throttle/clear"):
        assert all(first[path] < index for other, index in first.items() if other.startswith("/{username}/") and other.count("/") == 2)


class TestCheck:
    def _request(self, **overrides):
        return SimpleNamespace(**({"username": "alice", "ip": "203.0.113.1", "max_attempts": 5, "window": 900, "lockout": 900} | overrides))

    def test_it_passes_the_policy_through_and_returns_the_seconds_left(self, db):
        db.get_ui_login_lock.return_value = 421

        response = ROUTER.check_login_throttle(self._request())

        assert response.status_code == 200
        assert response.content["remaining"] == 421
        assert db.get_ui_login_lock.call_args.args == ("alice", "203.0.113.1")
        assert db.get_ui_login_lock.call_args.kwargs == {"max_attempts": 5, "window": 900, "lockout": 900}

    def test_a_lock_is_a_200_not_an_error(self, db):
        db.get_ui_login_lock.return_value = 900

        assert ROUTER.check_login_throttle(self._request()).status_code == 200

    def test_a_database_failure_is_a_500_the_ui_can_refuse_on(self, db):
        db.get_ui_login_lock.side_effect = RuntimeError("database gone")

        response = ROUTER.check_login_throttle(self._request())

        assert response.status_code == 500
        assert "database gone" not in str(response.content)  # driver errors can embed credentials


class TestFailures:
    def test_it_records_with_the_retention(self, db):
        db.add_ui_login_failure.return_value = ""

        response = ROUTER.record_login_failure(SimpleNamespace(username="alice", ip="203.0.113.1", retention=1800))

        assert response.status_code == 200
        assert db.add_ui_login_failure.call_args.args == ("alice", "203.0.113.1")
        assert db.add_ui_login_failure.call_args.kwargs == {"retention": 1800}

    def test_read_only_is_a_409(self, db):
        db.add_ui_login_failure.return_value = "The database is read-only, the changes will not be saved"

        assert ROUTER.record_login_failure(SimpleNamespace(username="a", ip="1.1.1.1", retention=60)).status_code == 409

    def test_anything_else_is_a_500(self, db):
        db.add_ui_login_failure.return_value = "boom"

        assert ROUTER.record_login_failure(SimpleNamespace(username="a", ip="1.1.1.1", retention=60)).status_code == 500


class TestClear:
    def test_it_clears_the_username(self, db):
        db.clear_ui_login_failures.return_value = ""

        response = ROUTER.clear_login_failures(SimpleNamespace(username="alice"))

        assert response.status_code == 200
        assert db.clear_ui_login_failures.call_args.args == ("alice",)

    def test_read_only_is_a_409(self, db):
        db.clear_ui_login_failures.return_value = "The database is read-only, the changes will not be saved"

        assert ROUTER.clear_login_failures(SimpleNamespace(username="alice")).status_code == 409


class TestRequestModels:
    @pytest.mark.parametrize("field", ["max_attempts", "window", "lockout"])
    def test_the_policy_numbers_must_be_positive(self, field):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ROUTER.LoginThrottleCheckRequest(username="a", ip="1.1.1.1", **{"max_attempts": 5, "window": 60, "lockout": 60, field: 0})

    def test_the_ip_and_username_are_bounded(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ROUTER.LoginThrottleFailureRequest(username="a", ip="1" * 46, retention=60)

"""`POST /users/{username}/totp/use`, and what a refused recovery code answers.

Two contracts the UI depends on to tell "this code was already used" apart from "nothing can be
written right now" -- and both apart from "the API is down", which is the case that must never be
read as either:

* the TOTP endpoint answers 200 with `consumed` **and** `readonly`, so one round trip carries the
  whole verdict. The UI cannot ask its own `readonly` property instead: that one is a 5-second
  cache which answers True whenever its probe fails, so an outage would read as a read-only
  database and every replayed code would be accepted.
* a recovery code refused because the database is read-only answers **409**, a 4xx. `BaseApiClient`
  raises `ApiUnavailableError` for 5xx *and* for an unreachable API, so a 5xx here would be
  indistinguishable from an outage on the UI side.

Same loader as `test_api_webauthn.py`: the router module is executed with its imports stubbed and
its handlers called directly against a Mock db. No TestClient in tests/unit/api.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = patch = delete = put = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


_DB = Mock()


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_users": ModuleType("bw_users"),
        "bw_users.routers": ModuleType("bw_users.routers"),
        "bw_users.auth": ModuleType("bw_users.auth"),
        "bw_users.auth.guard": ModuleType("bw_users.auth.guard"),
        "bw_users.utils": ModuleType("bw_users.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_users"].__path__ = []
    names["bw_users.routers"].__path__ = []
    names["bw_users.auth"].__path__ = []
    names["bw_users.auth.guard"].guard = object()
    names["bw_users.utils"].get_db = lambda: _DB

    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "users.py"
        spec = importlib.util.spec_from_file_location("bw_users.routers.users", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture(autouse=True)
def db():
    _DB.reset_mock(return_value=True, side_effect=True)
    _DB.readonly = False
    return _DB


def _request(counter=100, totp_secret="SEC"):
    return SimpleNamespace(totp_secret=totp_secret, counter=counter)


class TestUseTotpCounter:
    def test_a_spent_counter_is_reported_consumed(self, db):
        db.use_ui_user_totp.return_value = True

        response = ROUTER.use_totp_counter("alice", _request())

        assert response.status_code == 200
        assert response.content["consumed"] is True
        assert response.content["readonly"] is False
        assert db.use_ui_user_totp.call_args.args == ("alice", "SEC", 100)

    def test_a_replay_is_a_200_refusal_not_an_error(self, db):
        """A replay is the defence firing; a 4xx/5xx here would be read as an outage instead."""
        db.use_ui_user_totp.return_value = False

        response = ROUTER.use_totp_counter("alice", _request())

        assert response.status_code == 200
        assert response.content["consumed"] is False
        assert response.content["readonly"] is False

    def test_a_read_only_database_says_so_in_the_same_answer(self, db):
        """Without this field the caller cannot tell a replay from a database that writes nothing."""
        db.use_ui_user_totp.return_value = False
        db.readonly = True

        response = ROUTER.use_totp_counter("alice", _request())

        assert response.content["consumed"] is False
        assert response.content["readonly"] is True


class TestUseRecoveryCodeStatus:
    def test_read_only_is_a_409(self, db):
        db.use_ui_user_recovery_code.return_value = "The database is read-only, the changes will not be saved"
        assert ROUTER.use_recovery_code("alice", SimpleNamespace(hashed_code="H")).status_code == 409

    def test_an_invalid_code_is_still_a_400(self, db):
        db.use_ui_user_recovery_code.return_value = "Invalid recovery code"
        assert ROUTER.use_recovery_code("alice", SimpleNamespace(hashed_code="H")).status_code == 400

    def test_a_missing_user_is_still_a_400(self, db):
        db.use_ui_user_recovery_code.return_value = "User alice doesn't exist"
        assert ROUTER.use_recovery_code("alice", SimpleNamespace(hashed_code="H")).status_code == 400

    def test_anything_else_is_still_a_500(self, db):
        db.use_ui_user_recovery_code.return_value = "some driver blew up"
        assert ROUTER.use_recovery_code("alice", SimpleNamespace(hashed_code="H")).status_code == 500

    def test_success_is_a_200(self, db):
        db.use_ui_user_recovery_code.return_value = ""
        assert ROUTER.use_recovery_code("alice", SimpleNamespace(hashed_code="H")).status_code == 200

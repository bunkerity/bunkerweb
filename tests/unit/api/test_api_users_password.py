"""`POST /users` / `PATCH /users/{username}` store a bcrypt hash, never the password itself (H15).

The route used to write `req.password` verbatim. The UI's own callers send a bcrypt hash
(`routes/setup.py`, `routes/profile.py`, `utils/gunicorn.conf.py`), so the UI never noticed;
a plain API client did: the plaintext landed in `bw_ui_users.password` and the UI login then
died in `checkpw(...)` with `ValueError: Invalid salt` (a 500). The route now hashes a plaintext
password and passes an existing bcrypt hash through, which is the contract those UI callers rely on.

Same loader as `test_api_webauthn.py`: the router module runs with its imports stubbed and its
handlers are called directly against a Mock db.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import password_utils  # type: ignore
import pytest
from bcrypt import checkpw, gensalt, hashpw

ROOT = Path(__file__).resolve().parents[3]
PLAIN = "Qa3-Reader!2026"


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
        "bw_users_pw": ModuleType("bw_users_pw"),
        "bw_users_pw.routers": ModuleType("bw_users_pw.routers"),
        "bw_users_pw.auth": ModuleType("bw_users_pw.auth"),
        "bw_users_pw.auth.guard": ModuleType("bw_users_pw.auth.guard"),
        "bw_users_pw.utils": ModuleType("bw_users_pw.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_users_pw"].__path__ = []
    names["bw_users_pw.routers"].__path__ = []
    names["bw_users_pw.auth"].__path__ = []
    names["bw_users_pw.auth.guard"].guard = object()
    utils = names["bw_users_pw.utils"]
    utils.get_db = lambda: _DB
    for name in ("USER_PASSWORD_RX", "gen_password_hash", "is_bcrypt_hash", "password_exceeds_bcrypt_limit"):
        setattr(utils, name, getattr(password_utils, name))

    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "users.py"
        spec = importlib.util.spec_from_file_location("bw_users_pw.routers.users", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture(autouse=True)
def db():
    _DB.reset_mock(return_value=True, side_effect=True)
    _DB.create_ui_user.return_value = ""
    _DB.update_ui_user.return_value = ""
    _DB.get_ui_user.return_value = {"password": b"$2b$04$" + b"a" * 53, "theme": "light", "method": "manual", "language": "en"}
    return _DB


def _stored(call) -> bytes:
    return call.kwargs["password"]


def test_create_hashes_a_plaintext_password_and_login_verifies_it(db):
    response = ROUTER.create_user(ROUTER.CreateUserRequest.model_validate({"username": "qa3reader", "password": PLAIN, "roles": ["reader"]}))

    assert response.status_code == 201
    stored = _stored(db.create_ui_user.call_args)
    assert stored != PLAIN.encode("utf-8")
    assert password_utils.is_bcrypt_hash(stored.decode("utf-8"))
    # The exact check the UI login runs (routes/login.py): it raised `Invalid salt` on the plaintext.
    assert checkpw(PLAIN.encode("utf-8"), stored)


def test_create_passes_an_existing_bcrypt_hash_through(db):
    # routes/setup.py and utils/gunicorn.conf.py post a hash they computed themselves.
    prehashed = hashpw(PLAIN.encode("utf-8"), gensalt(rounds=4)).decode("utf-8")

    ROUTER.create_user(ROUTER.CreateUserRequest.model_validate({"username": "admin", "password": prehashed, "admin": True}))

    assert _stored(db.create_ui_user.call_args) == prehashed.encode("utf-8")


@pytest.mark.parametrize("password", ["weak", "é" * 40 + "Aa1!"])
def test_create_refuses_a_weak_or_over_long_plaintext(db, password):
    response = ROUTER.create_user(ROUTER.CreateUserRequest.model_validate({"username": "bob", "password": password}))

    assert response.status_code == 400
    db.create_ui_user.assert_not_called()


def test_update_hashes_a_plaintext_password(db):
    ROUTER.update_user("alice", ROUTER.UpdateUserRequest.model_validate({"password": PLAIN}))

    assert checkpw(PLAIN.encode("utf-8"), _stored(db.update_ui_user.call_args))


def test_update_passes_a_hash_through_and_keeps_the_stored_one_when_absent(db):
    # routes/profile.py sends a fresh hash; routes/login.py sends back the stored one on every login.
    prehashed = hashpw(PLAIN.encode("utf-8"), gensalt(rounds=4)).decode("utf-8")
    ROUTER.update_user("alice", ROUTER.UpdateUserRequest.model_validate({"password": prehashed}))
    assert _stored(db.update_ui_user.call_args) == prehashed.encode("utf-8")

    ROUTER.update_user("alice", ROUTER.UpdateUserRequest.model_validate({"theme": "dark"}))
    assert _stored(db.update_ui_user.call_args) == db.get_ui_user.return_value["password"]


def test_update_refuses_a_weak_plaintext(db):
    response = ROUTER.update_user("alice", ROUTER.UpdateUserRequest.model_validate({"password": "weak"}))

    assert response.status_code == 400
    db.update_ui_user.assert_not_called()

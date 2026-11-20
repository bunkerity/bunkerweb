"""Basic-auth bcrypt checks leave the event loop and cost the same for every username (UB3-B1)."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from bcrypt import gensalt, hashpw
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from starlette.requests import Request
import pytest

import _api_http_helpers  # noqa: F401  (prepares the Biscuit key files before app.auth imports)
import app.auth.guard as guard_module
import app.routers.auth as login_module

LOOP_THREAD = threading.get_ident()


def request(path="/services/example"):
    return Request({"type": "http", "method": "GET", "path": path, "headers": [], "client": ("127.0.0.1", 1000), "scheme": "http", "server": ("localhost", 80)})


@pytest.fixture
def spy(monkeypatch):
    """Record the thread and hash of every bcrypt check and every user lookup in both modules."""
    calls = {"check": [], "lookup": []}
    stored = hashpw(b"correct", gensalt(rounds=4))

    def check_password(password, hashed):
        calls["check"].append((threading.get_ident(), hashed))
        return hashed == stored and password == "correct"

    database = Mock()

    def get_api_user(**_kwargs):
        calls["lookup"].append(threading.get_ident())
        return database.row

    database.get_api_user.side_effect = get_api_user
    database.row = {"username": "alice", "admin": True, "password": stored}
    for module in (guard_module, login_module):
        monkeypatch.setattr(module, "check_password", check_password)
        monkeypatch.setattr(module, "get_api_db", lambda **_: database)
    monkeypatch.setattr(guard_module, "api_config", SimpleNamespace(API_ROOT_PATH=None, API_TOKEN=None))
    monkeypatch.setattr(login_module, "api_config", SimpleNamespace(API_TOKEN=None))
    return calls, database, stored


def guard_call(username, password):
    guard = guard_module.BiscuitWithAdminBearer()
    return asyncio.run(guard(request(), HTTPBasicCredentials(username=username, password=password)))


def login_call(username, password):
    return asyncio.run(login_module.login(request("/auth"), HTTPBasicCredentials(username=username, password=password)))


@pytest.mark.parametrize("call", [guard_call, login_call])
@pytest.mark.parametrize("password", ["correct", "wrong"])
def test_bcrypt_and_user_lookup_run_off_the_event_loop(spy, call, password):
    calls, _, _ = spy
    try:
        call("alice", password)
    except HTTPException:
        pass
    assert calls["check"] and calls["lookup"]
    assert all(thread != LOOP_THREAD for thread, _ in calls["check"])
    assert all(thread != LOOP_THREAD for thread in calls["lookup"])


@pytest.mark.parametrize("call", [guard_call, login_call])
@pytest.mark.parametrize("row", [None, {"username": "bob", "admin": False, "password": b"$2b$04$notused"}])
def test_unknown_and_non_admin_users_spend_the_same_bcrypt_work(spy, call, row):
    calls, database, _ = spy
    database.row = row
    if call is login_call and row is not None:
        pytest.skip("login checks the stored hash of any existing user, admin or not")
    with pytest.raises(HTTPException) as caught:
        call("nobody", "whatever")
    assert caught.value.status_code == 401
    [(thread, hashed)] = calls["check"]
    assert thread != LOOP_THREAD
    assert hashed == guard_module.DUMMY_PASSWORD_HASH


def test_dummy_hash_is_a_valid_cost_13_bcrypt_hash():
    from bcrypt import checkpw

    assert guard_module.DUMMY_PASSWORD_HASH.startswith(b"$2b$13$")
    assert checkpw(b"x", guard_module.DUMMY_PASSWORD_HASH) is False


@pytest.mark.parametrize("call", [guard_call, login_call])
def test_status_codes_are_unchanged(spy, call):
    _, _, _ = spy
    with pytest.raises(HTTPException) as caught:
        call("alice", "wrong")
    assert caught.value.status_code == 401


@pytest.mark.parametrize("call", [guard_call, login_call])
@pytest.mark.parametrize("password", [""])
def test_an_empty_password_is_refused_after_one_bcrypt_check(spy, call, password):
    calls, _, stored = spy
    with pytest.raises(HTTPException) as caught:
        call("alice", password)
    assert caught.value.status_code == 401
    [(thread, hashed)] = calls["check"]
    assert thread != LOOP_THREAD
    assert hashed == stored

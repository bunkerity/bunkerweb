"""Admin Basic/Bearer access and signed Biscuit freshness/IP checks."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from bcrypt import gensalt, hashpw
from biscuit_auth import BiscuitBuilder
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from starlette.requests import Request

import pytest

from _api_http_helpers import ADMIN_TOKEN, VERSION, _KEYPAIR

import app.auth.biscuit as biscuit
import app.auth.guard as auth


def request(path="/services/example", token=None, ip="127.0.0.1"):
    headers = [] if token is None else [(b"authorization", f"Bearer {token}".encode())]
    return Request(
        {"type": "http", "method": "GET", "path": path, "headers": headers, "client": (ip, 1000) if ip else None, "scheme": "http", "server": ("localhost", 80)}
    )


@pytest.fixture
def admin_guard(monkeypatch):
    config = SimpleNamespace(API_ROOT_PATH=None, API_TOKEN=ADMIN_TOKEN, docs_url="/docs", openapi_url="/openapi.json", redoc_url="/redoc")
    monkeypatch.setattr(auth, "api_config", config)
    database = Mock()
    database.get_api_user.return_value = {"admin": True, "password": hashpw(b"correct", gensalt(rounds=4))}
    monkeypatch.setattr(auth, "get_api_db", lambda **_: database)
    return auth.BiscuitWithAdminBearer(), database


def call(guard, req, username=None, password="correct"):
    credentials = HTTPBasicCredentials(username=username, password=password) if username is not None else None
    return asyncio.run(guard(req, credentials))


@pytest.mark.parametrize("path", ["/health", "/ping", "/auth", "/docs/oauth2-redirect", "/redoc", "/openapi.json"])
def test_public_endpoints_skip_credentials(admin_guard, path):
    guard, database = admin_guard
    req = request(path)
    assert call(guard, req) is None
    assert not getattr(req.state, "auth_admin", False)
    database.get_api_user.assert_not_called()


def test_bearer_admin_sets_audit_subject_without_database(admin_guard, monkeypatch):
    guard, database = admin_guard
    monkeypatch.setattr(auth.api_config, "API_ROOT_PATH", "/api")
    req = request("/api/services/example", ADMIN_TOKEN)
    assert call(guard, req) is None
    assert req.state.auth_admin is True
    assert req.state.auth_subject == "api-token"
    database.get_api_user.assert_not_called()


def test_basic_admin_cache_expires_and_password_is_checked_each_time(admin_guard, monkeypatch):
    guard, database = admin_guard
    clock = [100.0]
    monkeypatch.setattr(auth, "time", lambda: clock[0])
    req = request()
    assert call(guard, req, "alice") is None
    assert req.state.auth_admin is True and req.state.auth_subject == "alice"
    with pytest.raises(HTTPException) as caught:
        call(guard, request(), "alice", "wrong")
    assert caught.value.status_code == 401
    assert database.get_api_user.call_count == 1
    clock[0] = 131.0
    database.get_api_user.return_value = {"admin": False, "password": b""}
    with pytest.raises(HTTPException) as caught:
        call(guard, request(), "alice")
    assert caught.value.status_code == 401
    assert database.get_api_user.call_count == 2


@pytest.mark.parametrize(
    "row",
    [
        None,
        {"admin": False},
        {"admin": True, "password": b""},
        pytest.param(
            {"admin": True, "password": "not-a-hash"},
        ),
    ],
)
def test_unknown_nonadmin_and_invalid_password_are_refused(admin_guard, row):
    guard, database = admin_guard
    database.get_api_user.return_value = row
    req = request()
    with pytest.raises(HTTPException) as caught:
        call(guard, req, "alice")
    assert caught.value.status_code == 401
    assert not getattr(req.state, "auth_admin", False)


@pytest.mark.parametrize("token", [None, "not-signed"])
def test_missing_or_forged_bearer_is_refused_by_real_biscuit(admin_guard, token):
    guard, database = admin_guard
    with pytest.raises(HTTPException) as caught:
        call(guard, request(token=token))
    assert caught.value.status_code == 401
    database.get_api_user.assert_not_called()


@pytest.fixture
def biscuit_config(monkeypatch):
    config = SimpleNamespace(API_ROOT_PATH=None, docs_url=None, openapi_url=None, redoc_url=None, biscuit_ttl_seconds=60, check_private_ip=True)
    monkeypatch.setattr(biscuit, "api_config", config)
    return config


def token(*, issued=None, ip="127.0.0.1", version=VERSION, grant=True):
    facts = "time({issued}); client_ip({ip}); version({version});"
    if grant:
        facts += 'api_perm("services", "example", "service_read");'
    return BiscuitBuilder(facts, {"issued": issued or datetime.now(timezone.utc), "ip": ip, "version": version}).build(_KEYPAIR.private_key).to_base64()


def test_biscuit_scoped_grant_reaches_only_matching_resource(biscuit_config):
    signed = token()
    req = request(token=signed)
    assert biscuit.guard(req) is None
    assert req.state.biscuit_token.block_count() == 1
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(request("/services/other", signed))
    assert caught.value.status_code == 403


@pytest.mark.parametrize("kwargs", [{"issued": datetime(2000, 1, 1, tzinfo=timezone.utc)}, {"ip": "192.0.2.4"}, {"version": "wrong"}])
def test_expired_wrong_ip_and_wrong_version_are_unauthorized(biscuit_config, kwargs):
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(request(token=token(**kwargs)))
    assert caught.value.status_code == 401


def test_ttl_disabled_and_private_ip_relaxed_only_when_configured(biscuit_config):
    biscuit_config.biscuit_ttl_seconds = "invalid"
    biscuit_config.check_private_ip = False
    old = datetime.now(timezone.utc) - timedelta(days=30)
    assert biscuit.guard(request(token=token(issued=old, ip="10.0.0.1"))) is None
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(request(token=token(ip="10.0.0.1"), ip="8.8.8.8"))
    assert caught.value.status_code == 401


def test_public_key_empty_file_fails_closed(biscuit_config, tmp_path, monkeypatch):
    key = tmp_path / "public.key"
    key.write_text("")
    monkeypatch.setattr(biscuit, "BISCUIT_PUBLIC_KEY_FILE", key)
    with pytest.raises(RuntimeError, match="public key file is empty"):
        biscuit.BiscuitGuard()

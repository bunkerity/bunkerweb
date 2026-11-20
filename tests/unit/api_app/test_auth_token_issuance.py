"""Login credential sources mint verifiable, scoped Biscuit tokens."""

from types import SimpleNamespace
from unittest.mock import Mock

from bcrypt import gensalt, hashpw
from biscuit_auth import AuthorizerBuilder, Biscuit, Rule
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from _api_http_helpers import ADMIN_HEADERS, ADMIN_TOKEN, _KEYPAIR

import app.routers.auth as login


@pytest.fixture
def login_client(monkeypatch, tmp_path):
    key = tmp_path / "private.key"
    key.write_text(repr(_KEYPAIR.private_key))
    monkeypatch.setattr(login, "BISCUIT_PRIVATE_KEY_FILE", key)
    monkeypatch.setattr(login, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN))
    db = Mock()
    db.get_api_user.return_value = {"username": "alice", "admin": True, "password": hashpw(b"correct", gensalt(rounds=4))}
    db.get_api_permissions.return_value = []
    monkeypatch.setattr(login, "get_api_db", lambda **_: db)
    app = FastAPI()
    app.include_router(login.router)
    return TestClient(app, client=("127.0.0.1", 50000)), db, key


def facts(response, query):
    assert response.status_code == 200, response.text
    signed = Biscuit.from_base64(response.json()["token"], _KEYPAIR.public_key)
    authorizer = AuthorizerBuilder().build(signed)
    return [list(f.terms) for f in authorizer.query(Rule(query))]


@pytest.mark.parametrize("kind", ["basic", "json", "form", "bearer"])
def test_supported_credentials_mint_admin_token(login_client, kind):
    client, db, _ = login_client
    kwargs = {
        "basic": {"auth": ("alice", "correct")},
        "json": {"json": {"username": "alice", "password": "correct"}},
        "form": {"data": {"username": "alice", "password": "correct"}},
        "bearer": {"headers": ADMIN_HEADERS},
    }[kind]
    response = client.post("/auth", **kwargs)
    assert facts(response, "result($u) <- user($u)") == [["alice"]]
    assert facts(response, "result($a) <- admin($a)") == [[True]]
    assert facts(response, "result($ip) <- client_ip($ip)") == [["127.0.0.1"]]
    if kind == "bearer":
        db.get_api_user.assert_called_once_with(as_dict=True)


def test_fine_grained_permissions_remain_bound_to_resource(login_client):
    client, db, _ = login_client
    db.get_api_user.return_value["admin"] = False
    db.get_api_permissions.return_value = [
        SimpleNamespace(permission="service_read", resource_type="services", resource_id="example"),
        SimpleNamespace(permission="service_update", resource_type="services", resource_id=None),
    ]
    response = client.post("/auth", auth=("alice", "correct"), headers={"host": 'evil"); admin(true); domain("x'})
    assert sorted(facts(response, "result($t,$i,$p) <- api_perm($t,$i,$p)")) == [["services", "*", "service_update"], ["services", "example", "service_read"]]
    assert facts(response, "result($a) <- admin($a)") == []
    assert facts(response, "result($h) <- domain($h)") == [['evil"); admin(true); domain("x']]


def test_read_only_token_has_read_role_and_host_is_clamped(login_client):
    client, db, _ = login_client
    db.get_api_user.return_value["admin"] = False
    db.get_api_permissions.return_value = [SimpleNamespace(permission="service_read", resource_type="services", resource_id="example")]
    response = client.post("/auth", auth=("alice", "correct"), headers={"host": "x" * 300})
    assert facts(response, "result($h) <- domain($h)") == [["x" * 255]]
    assert facts(response, 'result($r) <- role($r,$p), $p.contains("read")') == [["api_user"]]
    assert facts(response, 'result($r) <- role($r,$p), $p.contains("write")') == []


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"headers": {"Authorization": "Bearer wrong"}}, {"json": []}, {"content": "{"}, {"json": {"username": "alice"}}, {"auth": ("alice", "wrong")}],
)
def test_missing_or_invalid_credentials_are_refused(login_client, kwargs):
    client, _, _ = login_client
    response = client.post("/auth", **kwargs)
    assert response.status_code == 401
    assert "token" not in response.json()


def test_unknown_user_is_refused(login_client):
    client, db, _ = login_client
    db.get_api_user.return_value = None
    assert client.post("/auth", auth=("unknown", "correct")).status_code == 401


@pytest.mark.parametrize("db_error", [False, True])
def test_no_permissions_or_permission_lookup_failure_cannot_mint(login_client, db_error):
    client, db, _ = login_client
    db.get_api_user.return_value["admin"] = False
    if db_error:
        db.get_api_permissions.side_effect = RuntimeError("unavailable")
    response = client.post("/auth", auth=("alice", "correct"))
    assert response.status_code == 403
    assert response.json() == {"detail": "No permissions assigned to user"}


@pytest.mark.parametrize("content", ["", "not-a-key"])
def test_missing_or_invalid_signing_key_reports_unavailable(login_client, content):
    client, _, key = login_client
    key.write_text(content)
    response = client.post("/auth", auth=("alice", "correct"))
    assert response.status_code == 500
    assert response.json() == {"detail": "Authentication service unavailable"}

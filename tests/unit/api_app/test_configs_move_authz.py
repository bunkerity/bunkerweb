"""Moving a custom config to another service needs permission on the destination as well.

`PATCH /configs/{service}/{type}/{name}` is guarded on the SOURCE service only: the Biscuit guard
derives `resource_id` from the second path segment. The destination arrives in the body (or in the
`new_service` form field) and was never looked at, so a token holding `config_update` on service A
alone could move a config onto service B, or onto global, and the move was applied.

Ported from dev's f3dffc251. Real Biscuit tokens and the real guard, as in
`test_biscuit_run_limit.py`, which this module borrows its keypair and import bootstrap from: the
guard loads its public key once, at import, so two modules cannot each mint their own.

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest

from test_biscuit_run_limit import VERSION, _KEYPAIR  # noqa: E402  (bootstrap: keypair, version, key file)

from biscuit_auth import BiscuitBuilder, Fact  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.guard as guard_mod  # noqa: E402
import app.routers.configs as configs_mod  # noqa: E402

ADMIN_TOKEN = "admin-secret-token"


def _token(*perms: tuple[str, str, str], admin: bool = False) -> str:
    """A single-block token with the same facts `POST /auth` mints for a fine-grained user."""
    builder = BiscuitBuilder(
        "user({user}); time({now}); client_ip({ip}); version({version});",
        {"user": "alice", "now": datetime.now(timezone.utc), "ip": "127.0.0.1", "version": VERSION},
    )
    if admin:
        builder.add_code("admin(true);")
    for rtype, rid, pname in perms:
        builder.add_fact(Fact("api_perm({rtype}, {rid}, {pname})", {"rtype": rtype, "rid": rid, "pname": pname}))
    return builder.build(_KEYPAIR.private_key).to_base64()


def _grant(*services: str) -> str:
    return _token(*(("configs", service, "config_update") for service in services))


class FakeDB:
    """One custom config, `snip`, living on service A. Records every write."""

    def __init__(self, service_id="a.example.com"):
        self.row = {"service_id": service_id, "type": "http", "name": "snip", "data": "old", "method": "api", "is_draft": False}
        self.writes = []

    def get_custom_config(self, ctype, name, *, service_id=None, with_data=True):
        same = (ctype, name, service_id) == (self.row["type"], self.row["name"], self.row["service_id"])
        return dict(self.row) if same else None

    def get_config(self, **_kwargs):
        return {"SERVER_NAME": "a.example.com b.example.com"}

    def upsert_custom_config(self, ctype, name, config, *, service_id=None, new=False):
        self.writes.append({"from": service_id, "to": config["service_id"], "data": config["data"]})
        return ""


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(configs_mod, "get_db", lambda: fake)
    # Only the admin-token lookup is stubbed; the Biscuit guard keeps its real api_config.
    monkeypatch.setattr(guard_mod, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    return fake


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(configs_mod.router)
    return TestClient(app, client=("127.0.0.1", 50000))


def _patch(client, token, body):
    return client.patch("/configs/a.example.com/http/snip", json=body, headers={"Authorization": f"Bearer {token}"})


class TestMoveNeedsTheDestination:
    def test_permission_on_the_source_alone_cannot_move_the_config(self, client, db):
        response = _patch(client, _grant("a.example.com"), {"service": "b.example.com"})
        assert response.status_code == 403
        assert db.writes == []

    def test_permission_on_the_source_alone_cannot_move_it_to_global(self, client, db):
        response = _patch(client, _grant("a.example.com"), {"service": "global"})
        assert response.status_code == 403
        assert db.writes == []

    def test_permission_on_the_destination_alone_is_not_enough(self, client, db):
        # The guard itself refuses: nothing grants config_update on the source.
        response = _patch(client, _grant("b.example.com"), {"service": "b.example.com"})
        assert response.status_code == 403
        assert db.writes == []

    def test_permission_on_both_services_moves_the_config(self, client, db):
        response = _patch(client, _grant("a.example.com", "b.example.com"), {"service": "b.example.com"})
        assert response.status_code == 200, response.text
        assert db.writes == [{"from": "a.example.com", "to": "b.example.com", "data": "old"}]

    def test_global_destination_needs_the_global_grant(self, client, db):
        assert _patch(client, _grant("a.example.com", "b.example.com"), {"service": "global"}).status_code == 403
        assert _patch(client, _grant("a.example.com", "global"), {"service": "global"}).status_code == 200
        assert db.writes == [{"from": "a.example.com", "to": None, "data": "old"}]

    def test_wildcard_grant_covers_every_destination(self, client, db):
        assert _patch(client, _grant("*"), {"service": "b.example.com"}).status_code == 200

    def test_api_token_admin_moves_anything(self, client, db):
        assert _patch(client, ADMIN_TOKEN, {"service": "b.example.com"}).status_code == 200
        assert db.writes[-1]["to"] == "b.example.com"

    def test_biscuit_admin_moves_anything(self, client, db):
        assert _patch(client, _token(admin=True), {"service": "b.example.com"}).status_code == 200

    def test_a_forged_unsigned_grant_does_not_help(self, client, db):
        # A bearer value that is neither API_TOKEN nor a signed Biscuit is refused at the guard.
        assert _patch(client, "not-a-token", {"service": "b.example.com"}).status_code == 401


class TestStayingPutNeedsOnlyTheServiceItself:
    def test_edit_in_place_with_the_source_grant(self, client, db):
        response = _patch(client, _grant("a.example.com"), {"data": "new"})
        assert response.status_code == 200, response.text
        assert db.writes == [{"from": "a.example.com", "to": "a.example.com", "data": "new"}]

    def test_explicit_same_service_is_not_a_move(self, client, db):
        assert _patch(client, _grant("a.example.com"), {"service": "a.example.com", "data": "new"}).status_code == 200

    def test_a_body_without_service_keeps_the_current_one(self, client, db):
        # Before the fix an absent `service` meant "global": a plain content edit silently moved
        # the config out of its service.
        _patch(client, _grant("a.example.com", "global"), {"data": "new"})
        assert [w["to"] for w in db.writes] == ["a.example.com"]


def _request(token_state):
    return SimpleNamespace(state=SimpleNamespace(**token_state))


class TestUploadVariant:
    """`PATCH .../upload` takes the destination as the `new_service` form field. Called directly:
    the route is plain Python once its Form/File defaults are replaced by values."""

    def _call(self, state, new_service):
        upload = SimpleNamespace(filename="snip.conf", file=BytesIO(b"new body"))
        return configs_mod.update_config_upload(
            _request(state), "a.example.com", "http", "snip", file=upload, new_service=new_service, new_type=None, new_name=None, new_is_draft=None
        )

    def test_source_grant_alone_cannot_move_through_upload(self, db):
        # biscuit_token is set by the real guard; here a token holding only the source grant.
        token = _biscuit(_grant("a.example.com"))
        with pytest.raises(HTTPException) as caught:
            self._call({"biscuit_token": token}, "b.example.com")
        assert caught.value.status_code == 403
        assert db.writes == []

    def test_both_grants_move_through_upload(self, db):
        token = _biscuit(_grant("a.example.com", "b.example.com"))
        assert self._call({"biscuit_token": token}, "b.example.com").status_code == 200
        assert db.writes[-1]["to"] == "b.example.com"

    def test_admin_moves_through_upload(self, db):
        assert self._call({"auth_admin": True}, "b.example.com").status_code == 200

    def test_upload_without_new_service_stays_put(self, db):
        token = _biscuit(_grant("a.example.com"))
        assert self._call({"biscuit_token": token}, None).status_code == 200
        assert db.writes[-1]["to"] == "a.example.com"


def _biscuit(token_b64):
    from biscuit_auth import Biscuit

    return Biscuit.from_base64(token_b64, _KEYPAIR.public_key)


class TestAuthorizeResource:
    """The general helper the CrowdSec unban lane will call: a resource type, an id, a permission."""

    def test_no_credential_on_the_request_is_refused(self):
        from app.auth.biscuit import authorize_resource

        with pytest.raises(HTTPException) as caught:
            authorize_resource(_request({}), "configs", "config_update", "a.example.com")
        assert caught.value.status_code == 403

    def test_grant_matches_type_permission_and_id(self):
        from app.auth.biscuit import authorize_resource

        state = {"biscuit_token": _biscuit(_token(("bans", "conn-1", "crowdsec_delete")))}
        authorize_resource(_request(state), "bans", "crowdsec_delete", "conn-1")
        for rtype, perm, rid in (("bans", "crowdsec_delete", "conn-2"), ("bans", "crowdsec_read", "conn-1"), ("configs", "crowdsec_delete", "conn-1")):
            with pytest.raises(HTTPException) as caught:
                authorize_resource(_request(state), rtype, perm, rid)
            assert caught.value.status_code == 403, (rtype, perm, rid)

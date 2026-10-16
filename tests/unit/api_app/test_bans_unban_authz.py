"""Unbanning a CrowdSec lease needs `crowdsec_delete` on every CrowdSec connection it touches.

`POST /bans/unban` is guarded as `ban_delete` on the bans resource. The decision-removing path deletes decisions that
live on CrowdSec connections, so the handler also calls `authorize_resource(request, "bans", "crowdsec_delete", <connection id>)`
once per connection the preview names. Real Biscuit tokens and the real guard, as in `test_configs_move_authz.py`,
which this module borrows its keypair, token builder and bootstrap from.

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

from time import time
from types import SimpleNamespace

import pytest

from test_configs_move_authz import ADMIN_TOKEN, _token  # noqa: E402  (bootstrap: keypair, version, key file)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.guard as guard_mod  # noqa: E402
import app.routers.bans as bans_mod  # noqa: E402
from CrowdSec import CrowdSecError, encode_connection  # noqa: E402

IP = "203.0.113.7"
LOCAL = "a" * 64
OTHER_LOCAL = "b" * 64
CONN = encode_connection("bw-1", LOCAL)
OTHER_CONN = encode_connection("bw-1", OTHER_LOCAL)
LEASE_ID = "0123456789abcdef"


def _lease_row():
    return {
        "ip": IP,
        "reason": "crowdsec",
        "service": "unknown",
        "date": int(time()),
        "ban_scope": "global",
        "exp": 25,
        "expires_at": int(time()) + 25,
        "permanent": False,
        "reason_data": {"lease": True, "version": 1, "lease_id": LEASE_ID, "instance": "node-1", "connection": LOCAL, "service_scope": "global"},
    }


class Calls:
    """What reached the CrowdSec side and the instances, to prove a refusal changed nothing."""

    mutations: list | None = None


class FakeClient:
    """One instance, two global connections (the lease's own and another one), one ban decision on the first."""

    def __init__(self, _db=None):
        self.decisions = {
            CONN: [{"id": 1, "scope": "Ip", "value": IP, "type": "ban", "origin": "crowdsec", "scenario": "x/ssh-bf", "remediation": "ban"}],
            OTHER_CONN: [],
        }

    def _instances(self):
        return [{"hostname": "bw-1", "status": "up"}]

    def instance_request(self, instance, method, path, data=None):
        return [_lease_row()]

    def connections(self):
        def row(conn_id, local_id, services):
            return {
                "id": conn_id,
                "local_id": local_id,
                "instance": "bw-1",
                "node": "node-1",
                "services": services,
                "status": "success",
                "management_configured": True,
            }

        return {"connections": [row(CONN, LOCAL, ["global"]), row(OTHER_CONN, OTHER_LOCAL, ["global"])], "errors": {}}

    def query(self, connection_id, action, params=None):
        if action == "decisions":
            found = self.decisions.get(connection_id, [])
            return {"decisions": found, "total": len(found), "offset": 0, "limit": 200}
        Calls.mutations.append((action, connection_id))
        if action == "unban":
            self.decisions[connection_id] = []
        return {"removed": True, "refreshed": True}

    def remove_lease(self, instance, ip, ban_scope, service, lease_id):
        Calls.mutations.append(("remove_lease", lease_id))
        return "removed"


class FakeDB:
    def __init__(self):
        self.revoked = []

    def revoke_lease(self, ip, *, ban_scope="global", service_id="", lease_id="", revoked_by=""):
        self.revoked.append(lease_id)
        return ""

    def revoke_ban(self, *_args, **_kwargs):
        self.revoked.append("generic")
        return ""

    def get_config(self, **_kwargs):
        return {}


class FakeCaller:
    def send_to_apis(self, *_args, **_kwargs):
        Calls.mutations.append(("generic_unban",))
        return True, {}


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    Calls.mutations = []
    monkeypatch.setattr(bans_mod, "get_db", lambda **_kwargs: fake)
    monkeypatch.setattr(bans_mod, "CrowdSecClient", FakeClient)
    monkeypatch.setattr(bans_mod, "redis_client_from", lambda _settings: None)
    monkeypatch.setattr(guard_mod, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    return fake


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(bans_mod.router)
    app.dependency_overrides[bans_mod.get_instances_api_caller] = lambda: FakeCaller()
    return TestClient(app, client=("127.0.0.1", 50000))


def _unban(client, token, body=None):
    return client.post("/bans/unban", json=body or {"ip": IP}, headers={"Authorization": f"Bearer {token}"})


def _confirm():
    return {"ip": IP, "remove_crowdsec_decisions": True, "confirmed": True, "decision_keys": [f"{CONN}:1"]}


BAN_DELETE = ("bans", "*", "ban_delete")


class TestOnlyBanDeleteCannotRemoveDecisions:
    def test_a_ban_delete_only_token_is_refused_a_plain_unban_of_a_lease_without_a_preview(self, client, db):
        response = _unban(client, _token(BAN_DELETE))
        assert response.status_code == 403
        assert "decisions" not in response.text  # the preview is not disclosed
        assert Calls.mutations == []

    def test_a_ban_delete_only_token_cannot_remove_decisions_with_a_confirmation(self, client, db):
        response = _unban(client, _token(BAN_DELETE), _confirm())
        assert response.status_code == 403
        assert Calls.mutations == []
        assert db.revoked == []

    def test_crowdsec_read_is_not_enough(self, client, db):
        response = _unban(client, _token(BAN_DELETE, ("bans", CONN, "crowdsec_read")), _confirm())
        assert response.status_code == 403
        assert Calls.mutations == []

    def test_the_guard_still_needs_ban_delete(self, client, db):
        response = _unban(client, _token(("bans", CONN, "crowdsec_delete")), _confirm())
        assert response.status_code == 403
        assert Calls.mutations == []


class TestPerConnection:
    def test_a_grant_on_the_wrong_connection_is_refused(self, client, db):
        response = _unban(client, _token(BAN_DELETE, ("bans", OTHER_CONN, "crowdsec_delete")), _confirm())
        assert response.status_code == 403
        assert Calls.mutations == []

    def test_a_global_lease_touches_every_connection_so_one_grant_is_not_enough(self, client, db):
        # the lease is global: both connections can block the IP, so the caller needs both
        response = _unban(client, _token(BAN_DELETE, ("bans", CONN, "crowdsec_delete")), _confirm())
        assert response.status_code == 403
        assert Calls.mutations == []

    def test_a_grant_on_every_connection_gets_the_409_preview(self, client, db):
        response = _unban(client, _token(BAN_DELETE, ("bans", CONN, "crowdsec_delete"), ("bans", OTHER_CONN, "crowdsec_delete")))
        assert response.status_code == 409
        assert response.json()["preview"]["decisions"][0]["key"] == f"{CONN}:1"
        assert Calls.mutations == []

    def test_a_grant_on_every_connection_removes_the_decisions_and_the_lease(self, client, db):
        token = _token(BAN_DELETE, ("bans", CONN, "crowdsec_delete"), ("bans", OTHER_CONN, "crowdsec_delete"))
        response = _unban(client, token, _confirm())
        assert response.status_code == 200, response.text
        assert [call[0] for call in Calls.mutations] == ["unban", "refresh_ip", "refresh_ip", "remove_lease"]
        assert db.revoked == [LEASE_ID]

    def test_the_wildcard_grant_covers_every_connection(self, client, db):
        response = _unban(client, _token(BAN_DELETE, ("bans", "*", "crowdsec_delete")), _confirm())
        assert response.status_code == 200, response.text


class TestAdmin:
    def test_the_api_token_admin_removes_decisions(self, client, db):
        assert _unban(client, ADMIN_TOKEN, _confirm()).status_code == 200
        assert db.revoked == [LEASE_ID]

    def test_a_biscuit_admin_removes_decisions(self, client, db):
        assert _unban(client, _token(admin=True), _confirm()).status_code == 200


class TestExplicitBansAreNotAffected:
    def test_a_ban_delete_only_token_still_unbans_an_explicit_ban(self, client, db, monkeypatch):
        class NoLease(FakeClient):
            def instance_request(self, instance, method, path, data=None):
                return []

        monkeypatch.setattr(bans_mod, "CrowdSecClient", NoLease)
        response = _unban(client, _token(BAN_DELETE))
        assert response.status_code == 200, response.text
        assert db.revoked == ["generic"]
        assert Calls.mutations == [("generic_unban",)]

    def test_an_unreachable_instance_listing_does_not_need_crowdsec_rights_for_an_explicit_ban(self, client, db, monkeypatch):
        class Down(FakeClient):
            def instance_request(self, instance, method, path, data=None):
                raise CrowdSecError("BunkerWeb instance is unavailable")

        monkeypatch.setattr(bans_mod, "CrowdSecClient", Down)
        response = _unban(client, _token(BAN_DELETE))
        assert response.status_code == 502  # the lease check could not complete: reported, not hidden
        assert response.json()["results"][0]["lease_check"] == "incomplete"

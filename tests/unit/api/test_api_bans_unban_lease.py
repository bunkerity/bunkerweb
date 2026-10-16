"""FastAPI /bans/unban for CrowdSec leases: the 409 preview, per-connection authorization, DB revoke last.

The router runs with a fake CrowdSec client and a stubbed `authorize_resource`; the real authorization is exercised
with Biscuit tokens in `tests/unit/api_app/test_bans_unban_authz.py`. Pieces owned by other X1 lanes are stubbed to
the frozen contract: `DB.revoke_lease`, `POST /unban` with `lease_id` and the `refresh_ip` control operation.
"""

import importlib.util
import sys
from pathlib import Path
from time import time
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import schemas  # type: ignore  (src/api/app on sys.path)
from CrowdSec import CrowdSecError, encode_connection

ROOT = Path(__file__).resolve().parents[3]

IP = "203.0.113.7"
LOCAL = "a" * 64
CONN = encode_connection("bw-1", LOCAL)
LEASE_ID = "0123456789abcdef"


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    delete = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


class Forbidden(Exception):
    pass


DB = SimpleNamespace()
AUTH = []


def _authorize(request, resource_type, permission, resource_id):
    AUTH.append((resource_type, permission, resource_id))
    if getattr(request.state, "deny", None) and resource_id in request.state.deny:
        raise Forbidden(resource_id)


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_bansl": ModuleType("bw_bansl"),
        "bw_bansl.routers": ModuleType("bw_bansl.routers"),
        "bw_bansl.auth": ModuleType("bw_bansl.auth"),
        "bw_bansl.auth.guard": ModuleType("bw_bansl.auth.guard"),
        "bw_bansl.auth.biscuit": ModuleType("bw_bansl.auth.biscuit"),
        "bw_bansl.deps": ModuleType("bw_bansl.deps"),
        "bw_bansl.schemas": schemas,
        "bw_bansl.utils": ModuleType("bw_bansl.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Request = object
    names["fastapi.responses"].JSONResponse = _Response
    for name in ("bw_bansl", "bw_bansl.routers", "bw_bansl.auth"):
        names[name].__path__ = []
    names["bw_bansl.auth.guard"].guard = object()
    names["bw_bansl.auth.biscuit"].authorize_resource = _authorize
    names["bw_bansl.deps"].get_instances_api_caller = object()
    names["bw_bansl.utils"].get_db = lambda **_kwargs: DB
    names["bw_bansl.utils"].LOGGER = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "bans.py"
        spec = importlib.util.spec_from_file_location("bw_bansl.routers.bans", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def lease_row(*, lease_id=LEASE_ID, ban_scope="global", service="unknown", scope="global"):
    return {
        "ip": IP,
        "reason": "crowdsec",
        "service": service,
        "date": int(time()),
        "country": "XX",
        "ban_scope": ban_scope,
        "exp": 25,
        "expires_at": int(time()) + 25,
        "permanent": False,
        "reason_data": {
            "lease": True,
            "version": 1,
            "lease_id": lease_id,
            "instance": "node-1",
            "connection": LOCAL,
            "service_scope": scope,
            "remediation": "ban",
        },
    }


def explicit_row(*, ban_scope="service", service="app.example.com"):
    return {"ip": IP, "reason": "manual", "service": service, "ban_scope": ban_scope, "exp": 3600, "expires_at": int(time()) + 3600, "reason_data": {}}


class FakeClient:
    """One instance `bw-1`, one global connection, one ban decision."""

    log = []

    def __init__(self, _db=None):
        type(self).instance = self
        self.bans = {"bw-1": [lease_row()]}
        self.decisions = {CONN: [{"id": 1, "scope": "Ip", "value": IP, "type": "ban", "origin": "crowdsec", "scenario": "x/ssh-bf", "remediation": "ban"}]}
        self.ban_listings = 0
        self.unban_error = None
        self.listing_error = None

    def _instances(self):
        return [{"hostname": "bw-1", "status": "up"}]

    def instance_request(self, instance, method, path, data=None):
        assert (method, path) == ("GET", "/bans")
        self.ban_listings += 1
        if self.listing_error:
            raise CrowdSecError(self.listing_error)
        return list(self.bans[instance["hostname"]])

    def connections(self):
        return {
            "connections": [
                {
                    "id": CONN,
                    "local_id": LOCAL,
                    "instance": "bw-1",
                    "node": "node-1",
                    "services": ["global"],
                    "status": "success",
                    "management_configured": True,
                }
            ],
            "errors": {},
        }

    def query(self, connection_id, action, params=None):
        params = params or {}
        if action == "decisions":
            found = self.decisions.get(connection_id, [])
            return {"decisions": found, "total": len(found), "offset": 0, "limit": 200}
        if action == "unban":
            self.log.append(("unban", params["decision_id"]))
            if self.unban_error:
                raise CrowdSecError(self.unban_error)
            self.decisions[connection_id] = []
            return {"removed": True}
        if action == "refresh_ip":
            self.log.append(("refresh_ip", connection_id))
            return {"refreshed": True}
        raise AssertionError(action)

    def remove_lease(self, instance, ip, ban_scope, service, lease_id):
        self.log.append(("remove_lease", instance["hostname"], ban_scope, service, lease_id))
        return "removed"


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    FakeClient.log = []
    AUTH.clear()
    DB.get_instances = lambda **_kwargs: []
    DB.get_config = lambda **_kwargs: {}
    DB.revoke_ban = Mock(side_effect=lambda *a, **k: FakeClient.log.append(("revoke_ban",)) or "")
    DB.revoke_lease = Mock(
        side_effect=lambda ip, *, ban_scope="global", service_id="", lease_id="", revoked_by="": FakeClient.log.append(
            ("revoke_lease", ip, ban_scope, service_id, lease_id)
        )
        or ""
    )
    monkeypatch.setattr(ROUTER, "CrowdSecClient", FakeClient)
    monkeypatch.setattr(ROUTER, "redis_client_from", lambda _settings: None)
    ROUTER.LOGGER.reset_mock()


def request(*, admin=False, deny=()):
    return SimpleNamespace(state=SimpleNamespace(auth_admin=admin, auth_subject="alice", deny=set(deny)))


def item(**over):
    return schemas.UnbanRequest(ip=IP, **over)


def caller(ok=True):
    mock = Mock()
    mock.send_to_apis.side_effect = lambda *a, **k: FakeClient.log.append(("generic_unban", a[1])) or (ok, {})
    return mock


def confirmed(**over):
    return item(remove_crowdsec_decisions=True, confirmed=True, decision_keys=[f"{CONN}:1"], **over)


# ------------------------------------------------------------------------------------------ schema


def test_unban_request_defaults_are_not_a_confirmation():
    plain = schemas.UnbanRequest(ip=IP)
    assert (plain.remove_crowdsec_decisions, plain.confirmed, plain.decision_keys) == (False, False, None)


def test_unban_request_carries_the_confirmation_fields():
    req = schemas.UnbanRequest(ip=IP, remove_crowdsec_decisions=True, confirmed=True, decision_keys=["k:1"])
    assert (req.remove_crowdsec_decisions, req.confirmed, req.decision_keys) == (True, True, ["k:1"])


# ---------------------------------------------------------------------------------- 409 preview


def test_a_plain_unban_of_a_lease_answers_409_with_the_preview_and_changes_nothing():
    mock = caller()
    response = ROUTER.unban([item()], request(admin=True), mock)

    assert response.status_code == 409
    body = response.content
    assert body["status"] == "error"
    assert body["preview"]["decisions"][0]["key"] == f"{CONN}:1"
    assert body["preview"]["leases"][0]["lease_id"] == LEASE_ID
    assert body["previews"][0]["ip"] == IP
    assert FakeClient.log == []
    DB.revoke_ban.assert_not_called()
    DB.revoke_lease.assert_not_called()
    mock.send_to_apis.assert_not_called()


@pytest.mark.parametrize("over", [{"remove_crowdsec_decisions": True}, {"confirmed": True}, {"remove_crowdsec_decisions": True, "confirmed": True}])
def test_a_partial_confirmation_is_still_a_409(over):
    response = ROUTER.unban([item(**over)], request(admin=True), caller())
    assert response.status_code == 409
    assert FakeClient.log == []


def test_a_lease_is_found_without_the_caller_saying_so():
    # the request carries no "kind": the runtime view decides, never the caller
    response = ROUTER.unban([item()], request(admin=True), caller())
    assert response.status_code == 409


def test_a_confirmed_unban_removes_decisions_then_lease_then_the_database_row():
    mock = caller()
    response = ROUTER.unban([confirmed()], request(admin=True), mock)

    assert response.status_code == 200
    assert response.content["status"] == "success"
    assert response.content["results"][0]["status"] == "success"
    assert [entry[0] for entry in FakeClient.log] == ["unban", "refresh_ip", "remove_lease", "revoke_lease"]
    DB.revoke_lease.assert_called_once_with(IP, ban_scope="global", service_id="", lease_id=LEASE_ID, revoked_by="alice")
    DB.revoke_ban.assert_not_called()
    mock.send_to_apis.assert_not_called()  # the generic unban never touches a lease


def test_decisions_changed_since_the_preview_is_a_409_with_the_new_preview():
    FakeClient.instance = None
    stale = schemas.UnbanRequest(ip=IP, remove_crowdsec_decisions=True, confirmed=True, decision_keys=[f"{CONN}:99"])
    response = ROUTER.unban([stale], request(admin=True), caller())
    assert response.status_code == 409
    assert response.content["preview"]["decisions"][0]["key"] == f"{CONN}:1"
    assert FakeClient.log == []


def test_a_failed_decision_deletion_is_a_502_with_the_partial_result_and_no_revoke():
    original = FakeClient.__init__

    def failing(self, db=None):
        original(self, db)
        self.unban_error = "CrowdSec Local API is unreachable"

    with patch.object(FakeClient, "__init__", failing):
        response = ROUTER.unban([confirmed()], request(admin=True), caller())

    assert response.status_code == 502
    assert response.content["results"][0]["status"] == "partial"
    DB.revoke_lease.assert_not_called()


def test_the_lease_is_looked_up_once_per_request_not_once_per_item():
    other = "198.51.100.9"
    mock = caller()
    ROUTER.unban([schemas.UnbanRequest(ip=other), schemas.UnbanRequest(ip="198.51.100.10")], request(admin=True), mock)
    # one snapshot for the detection of both items (no lease found, so no barrier snapshot)
    assert FakeClient.instance.ban_listings == 1


# ---------------------------------------------------------------------------- explicit bans


def test_an_explicit_unban_is_unchanged_revoke_first_then_fan_out():
    FakeClient.log = []
    original = FakeClient.__init__

    def without_lease(self, db=None):
        original(self, db)
        self.bans = {"bw-1": [explicit_row(ban_scope="global", service="unknown")]}

    with patch.object(FakeClient, "__init__", without_lease):
        response = ROUTER.unban([item()], request(), caller())

    assert response.status_code == 200
    assert response.content == {"status": "success"}
    assert [entry[0] for entry in FakeClient.log] == ["revoke_ban", "generic_unban"]


def test_an_explicit_service_ban_on_the_same_ip_survives_a_global_lease_unban():
    original = FakeClient.__init__

    def both(self, db=None):
        original(self, db)
        self.bans = {"bw-1": [lease_row(), explicit_row()]}

    with patch.object(FakeClient, "__init__", both):
        mock = caller()
        response = ROUTER.unban([confirmed()], request(admin=True), mock)

    assert response.status_code == 200
    DB.revoke_ban.assert_not_called()
    mock.send_to_apis.assert_not_called()
    assert ("remove_lease", "bw-1", "global", None, LEASE_ID) in FakeClient.log
    # the lease is the only thing revoked in the database
    DB.revoke_lease.assert_called_once_with(IP, ban_scope="global", service_id="", lease_id=LEASE_ID, revoked_by="alice")


def test_an_incomplete_lease_check_still_unbans_but_is_reported():
    original = FakeClient.__init__

    def broken(self, db=None):
        original(self, db)
        self.listing_error = "BunkerWeb instance is unavailable"

    with patch.object(FakeClient, "__init__", broken):
        response = ROUTER.unban([item()], request(), caller())

    assert response.status_code == 502
    assert response.content["results"][0]["lease_check"] == "incomplete"
    assert [entry[0] for entry in FakeClient.log] == ["revoke_ban", "generic_unban"]


# --------------------------------------------------------------------------------- authorization


def test_every_connection_the_preview_names_is_authorized_once():
    ROUTER.unban([item()], request(), caller())
    assert AUTH == [("bans", "crowdsec_delete", CONN)]


def test_an_admin_skips_the_per_connection_authorization():
    ROUTER.unban([item()], request(admin=True), caller())
    assert AUTH == []


def test_a_caller_denied_on_a_connection_gets_nothing_not_even_the_preview():
    with pytest.raises(Forbidden):
        ROUTER.unban([item()], request(deny={CONN}), caller())
    assert FakeClient.log == []


def test_a_caller_denied_on_a_connection_changes_nothing_even_with_a_confirmation():
    with pytest.raises(Forbidden):
        ROUTER.unban([confirmed()], request(deny={CONN}), caller())
    assert FakeClient.log == []
    DB.revoke_lease.assert_not_called()


def test_a_batch_changes_nothing_when_one_item_is_not_authorized():
    original = FakeClient.__init__

    def two(self, db=None):
        original(self, db)
        self.bans = {"bw-1": [lease_row()]}

    mock = caller()
    other = schemas.UnbanRequest(ip="198.51.100.10")
    with patch.object(FakeClient, "__init__", two):
        # the first item is an explicit ban; the second is a lease the caller is not allowed on
        with pytest.raises(Forbidden):
            ROUTER.unban([other, confirmed()], request(deny={CONN}), mock)
    mock.send_to_apis.assert_not_called()
    DB.revoke_ban.assert_not_called()


# -------------------------------------------------------------------------------------- audit log


def test_the_decision_removing_path_writes_one_audit_line():
    ROUTER.unban([confirmed()], request(admin=True), caller())
    lines = [call for call in ROUTER.LOGGER.info.call_args_list if "CrowdSec unban" in call.args[0]]
    assert len(lines) == 1
    template, *values = lines[0].args
    rendered = template % tuple(values)
    assert "actor='alice'" in rendered and f"ip={IP}" in rendered and "outcome=success" in rendered


def test_a_partial_outcome_is_logged_as_a_warning():
    original = FakeClient.__init__

    def failing(self, db=None):
        original(self, db)
        self.unban_error = "boom"

    with patch.object(FakeClient, "__init__", failing):
        ROUTER.unban([confirmed()], request(admin=True), caller())
    assert any("CrowdSec unban" in call.args[0] and "outcome=partial" in (call.args[0] % tuple(call.args[1:])) for call in ROUTER.LOGGER.warning.call_args_list)

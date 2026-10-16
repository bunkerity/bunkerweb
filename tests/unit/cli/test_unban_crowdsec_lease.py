"""`bwcli unban` and `bwcli bans` with CrowdSec leases (wave 25, lane X1F).

bwcli bypasses the API: it revokes in the database and posts `/unban` to the instances itself. On a lease
that skips the preview, never deletes the CrowdSec decisions (so the ban comes back one request later) and
takes the generic path that amendment 1 forbids for leases. The CLI therefore classifies the identity with
the shared module the API router uses (`crowdsec_unban`), previews without `-confirm`, and applies through
that module with it. An explicit ban keeps the flow that existed before.

The CLI runs locally as an admin: there is no Biscuit check.
"""

import sys
from pathlib import Path
from time import time
from unittest.mock import Mock

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT / "src" / "common" / "cli", _ROOT / "src" / "common" / "api", _ROOT / "src" / "common" / "utils", _ROOT / "src" / "common" / "db"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import CrowdSec  # noqa: E402
import crowdsec_unban  # noqa: E402
from CLI import CLI  # noqa: E402
from CrowdSec import CrowdSecError, encode_connection  # noqa: E402

IP = "203.0.113.7"
LOCAL = "a" * 64
CONN = encode_connection("bw-1", LOCAL)
LEASE_ID = "0123456789abcdef"


def lease_row(ip=IP, *, ban_scope="global", service="unknown", lease_id=LEASE_ID, exp=25):
    return {
        "ip": ip,
        "reason": "crowdsec",
        "service": service,
        "date": int(time()),
        "country": "XX",
        "ban_scope": ban_scope,
        "exp": exp,
        "permanent": False,
        "reason_data": {
            "lease": True,
            "version": 1,
            "lease_id": lease_id,
            "instance": "node-1",
            "connection": LOCAL,
            "service_scope": "global",
            "remediation": "ban",
            "source": "lapi",
        },
    }


def explicit_row(ip=IP, *, ban_scope="global", service="unknown"):
    return {"ip": ip, "reason": "manual", "service": service, "date": int(time()), "country": "XX", "ban_scope": ban_scope, "exp": 3600, "permanent": False}


def decision(decision_id=1, *, origin="crowdsec", scope="Ip", value=IP):
    return {"id": decision_id, "scope": scope, "value": value, "type": "ban", "origin": origin, "scenario": "x/ssh-bf", "remediation": "ban"}


class FakeClient:
    """Duck-typed `CrowdSecClient`: the same surface `crowdsec_unban` drives."""

    def __init__(self, log, *, bans=None, decisions=None, hosts=None, status="success", unban_errors=None):
        self.log = log
        self._hosts = hosts or [{"hostname": "bw-1", "status": "up"}]
        self.bans = bans if bans is not None else {"bw-1": [lease_row()]}
        self.decisions = {CONN: [decision()]} if decisions is None else decisions
        self.status = status
        self.unban_errors = unban_errors or {}

    def _instances(self):
        return self._hosts

    def instance_request(self, instance, method, path, data=None):
        assert (method, path) == ("GET", "/bans")
        return list(self.bans.get(instance["hostname"], []))

    def connections(self):
        return {
            "connections": [{"id": CONN, "local_id": LOCAL, "instance": "bw-1", "services": ["global"], "status": self.status, "management_configured": True}],
            "errors": {},
        }

    def query(self, connection_id, action, params=None):
        params = params or {}
        if action == "decisions":
            found = [d for d in self.decisions.get(connection_id, []) if d["value"] == params["ip"]]
            return {"decisions": found, "total": len(found)}
        if action == "unban":
            self.log.append(("unban", params["decision_id"]))
            if params["decision_id"] in self.unban_errors:
                raise CrowdSecError(self.unban_errors[params["decision_id"]])
            self.decisions[connection_id] = [d for d in self.decisions[connection_id] if d["id"] != params["decision_id"]]
            return {"removed": True, "already_absent": False}
        if action == "refresh_ip":
            self.log.append(("refresh_ip", params["ip"]))
            return {"refreshed": True}
        raise AssertionError(action)

    def remove_lease(self, instance, ip, ban_scope, service, lease_id):
        self.log.append(("remove_lease", instance["hostname"], ip, ban_scope, service, lease_id))
        return "removed"


def _db(log, *, revoke_error=""):
    db = Mock()
    db.revoke_lease.side_effect = lambda *args, **kwargs: log.append(("revoke_lease", args, kwargs)) or ""
    db.revoke_ban.side_effect = lambda *args, **kwargs: log.append(("revoke_ban", args, kwargs)) or revoke_error
    return db


def _cli(monkeypatch, client, *, db, apis=(Mock(),), push_ok=True):
    """A CLI without __init__ (it opens a database, Redis and a terminal), wired to a fake CrowdSec client."""
    cli = object.__new__(CLI)
    cli._CLI__db = db
    cli._CLI__redis = None
    cli._CLI__logger = Mock()
    cli._CLI__terminal_width = 80
    cli.apis = list(apis)
    cli.send_to_apis = Mock(return_value=(push_ok, {}))
    monkeypatch.setattr(CrowdSec, "CrowdSecClient", lambda database, **kwargs: client)
    return cli


@pytest.fixture
def log():
    return []


# ---------------------------------------------------------------------------------------------
# A lease without -confirm: preview, exit non-zero, change nothing
# ---------------------------------------------------------------------------------------------


def test_a_lease_without_confirm_prints_the_preview_and_changes_nothing(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log), db=db)

    ok, text = cli.unban(IP)

    assert ok is False
    assert IP in text and "x/ssh-bf" in text and "crowdsec" in text
    assert "-confirm" in text
    assert log == []
    db.revoke_ban.assert_not_called()
    db.revoke_lease.assert_not_called()
    cli.send_to_apis.assert_not_called()


def test_the_preview_shows_warnings_and_unavailable_connections(monkeypatch, log):
    client = FakeClient(log, decisions={CONN: [decision(origin="capi"), decision(2, scope="Range", value="203.0.113.0/24")]}, status="error")
    # The range decision is on the IP's own query only when its value matches; widen the fake to return it
    client.decisions[CONN][1]["value"] = IP
    cli = _cli(monkeypatch, client, db=_db(log))

    ok, text = cli.unban(IP)

    assert ok is False
    assert "unavailable" in text.lower()


def test_the_preview_warns_about_a_community_list_decision(monkeypatch, log):
    cli = _cli(monkeypatch, FakeClient(log, decisions={CONN: [decision(origin="capi")]}), db=_db(log))

    ok, text = cli.unban(IP)

    assert ok is False
    assert "list" in text.lower() and "come back" in text.lower()


def test_a_service_lease_is_found_for_its_own_scope_only(monkeypatch, log):
    """`-service app` looks for the service lease; a global unban does not touch it (amendment 1)."""
    client = FakeClient(log, bans={"bw-1": [lease_row(ban_scope="service", service="app")]})
    db = _db(log)
    cli = _cli(monkeypatch, client, db=db)

    ok, text = cli.unban(IP, "app")
    assert ok is False and "-confirm" in text

    cli.send_to_apis.reset_mock()
    ok, _ = cli.unban(IP)  # global: no lease of that identity, the explicit flow runs
    assert ok is True
    db.revoke_ban.assert_called_once()


# ---------------------------------------------------------------------------------------------
# -confirm: apply through the shared module
# ---------------------------------------------------------------------------------------------


def test_confirm_applies_through_the_shared_module_in_order(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log), db=db)

    ok, text = cli.unban(IP, confirm=True)

    assert ok is True, text
    assert [entry[0] for entry in log] == ["unban", "refresh_ip", "remove_lease", "revoke_lease"]
    assert log[2][1:] == ("bw-1", IP, "global", None, LEASE_ID)
    assert log[3][2]["lease_id"] == LEASE_ID and log[3][2]["revoked_by"] == "bwcli"
    assert "1" in text  # the per-item result: one decision deleted


def test_a_lease_is_never_revoked_nor_unbanned_the_generic_way(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log), db=db)

    cli.unban(IP)
    cli.unban(IP, confirm=True)

    db.revoke_ban.assert_not_called()
    for call in cli.send_to_apis.call_args_list:
        assert call.args[:2] != ("POST", "/unban")


def test_a_failed_decision_deletion_is_reported_and_keeps_the_lease(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log, unban_errors={1: "boom"}), db=db)

    ok, text = cli.unban(IP, confirm=True)

    assert ok is False
    assert "boom" in text
    assert [entry[0] for entry in log] == ["unban"]  # nothing after the failed deletion
    db.revoke_ban.assert_not_called()
    db.revoke_lease.assert_not_called()


def test_a_changed_result_says_nothing_was_removed(monkeypatch, log):
    cli = _cli(monkeypatch, FakeClient(log), db=_db(log))
    monkeypatch.setattr(crowdsec_unban, "execute", lambda *args, **kwargs: {"status": "changed", "lease_changed": [{"instance": "bw-1", "lease_id": "x"}]})

    ok, text = cli.unban(IP, confirm=True)

    assert ok is False and "changed" in text.lower()


def test_an_error_of_the_module_is_reported(monkeypatch, log):
    cli = _cli(monkeypatch, FakeClient(log, status="error"), db=_db(log))

    ok, text = cli.unban(IP, confirm=True)

    assert ok is False
    assert "unavailable" in text.lower()


# ---------------------------------------------------------------------------------------------
# An explicit ban keeps today's behaviour
# ---------------------------------------------------------------------------------------------


def test_an_explicit_ban_keeps_the_old_flow(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log, bans={"bw-1": [explicit_row()]}), db=db)

    ok, text = cli.unban(IP)

    assert ok is True and "has been unbanned" in text
    db.revoke_ban.assert_called_once_with(IP, ban_scope="global", service_id="", revoked_by="bwcli")
    cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "global"})
    db.revoke_lease.assert_not_called()
    assert log[0][0] == "revoke_ban"


def test_an_explicit_service_ban_keeps_the_old_flow(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log, bans={"bw-1": [explicit_row(ban_scope="service", service="app")]}), db=db)

    ok, _ = cli.unban(IP, "app")

    assert ok is True
    db.revoke_ban.assert_called_once_with(IP, ban_scope="service", service_id="app", revoked_by="bwcli")
    cli.send_to_apis.assert_called_once_with("POST", "/unban", data={"ip": IP, "ban_scope": "service", "service": "app"})


def test_an_unbanned_ip_with_no_ban_anywhere_keeps_the_old_flow(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log, bans={"bw-1": []}), db=db)

    ok, _ = cli.unban(IP)

    assert ok is True
    db.revoke_ban.assert_called_once()


def test_confirm_on_an_explicit_ban_is_a_plain_unban(monkeypatch, log):
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log, bans={"bw-1": [explicit_row()]}), db=db)

    ok, _ = cli.unban(IP, confirm=True)

    assert ok is True
    db.revoke_ban.assert_called_once()


# ---------------------------------------------------------------------------------------------
# Incomplete checks and installs without a database
# ---------------------------------------------------------------------------------------------


def test_an_unreachable_instance_with_a_persisted_unban_succeeds_and_warns(monkeypatch, log):
    """No lease was found and one instance could not be asked, but the revoke persisted: success (exit 0) with the note as a warning."""
    client = FakeClient(log, bans={"bw-1": [explicit_row()]}, hosts=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "down"}])
    db = _db(log)
    cli = _cli(monkeypatch, client, db=db)

    ok, text = cli.unban(IP)

    db.revoke_ban.assert_called_once()
    assert ok is True
    assert "has been unbanned" in text
    assert "bw-2" in text and "CrowdSec" in text and "run the command again" in text


def test_a_database_that_cannot_list_instances_still_succeeds_when_the_unban_persisted(monkeypatch, log):
    """The instance list cannot be read, so the lease check is incomplete; the explicit revoke persisted, so the unban is a success with the note."""

    class Broken(FakeClient):
        def _instances(self):
            raise CrowdSecError("Unable to read configured BunkerWeb instances")

    db = _db(log)
    cli = _cli(monkeypatch, Broken(log), db=db)

    ok, text = cli.unban(IP)

    db.revoke_ban.assert_called_once()
    assert ok is True
    assert "has been unbanned" in text
    assert "CrowdSec" in text and "run the command again" in text


def test_a_failed_unban_with_an_incomplete_check_stays_a_failure_and_keeps_the_note(monkeypatch, log):
    client = FakeClient(log, bans={"bw-1": [explicit_row()]}, hosts=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "down"}])
    db = _db(log, revoke_error="database is locked")
    cli = _cli(monkeypatch, client, db=db)

    ok, text = cli.unban(IP)

    db.revoke_ban.assert_called_once()
    assert ok is False
    assert "database is locked" in text
    assert "bw-2" in text and "CrowdSec" in text and "run the command again" in text


def test_without_a_database_a_lease_is_refused_not_unbanned_generically(monkeypatch, log):
    cli = _cli(monkeypatch, FakeClient(log), db=None)
    cli.send_to_apis = Mock(return_value=(True, {"bw-1": {"status": "success", "data": [lease_row()]}}))

    ok, text = cli.unban(IP, confirm=True)

    assert ok is False
    assert "CrowdSec" in text and ("Web UI" in text or "API" in text)
    assert [call.args[:2] for call in cli.send_to_apis.call_args_list] == [("GET", "/bans")]


def test_without_a_database_an_explicit_ban_keeps_the_old_local_flow(monkeypatch, log):
    cli = _cli(monkeypatch, FakeClient(log), db=None)
    cli.send_to_apis = Mock(side_effect=[(True, {"bw-1": {"status": "success", "data": [explicit_row()]}}), (True, {})])

    ok, _ = cli.unban(IP)

    assert ok is True
    assert [call.args[:2] for call in cli.send_to_apis.call_args_list] == [("GET", "/bans"), ("POST", "/unban")]


# ---------------------------------------------------------------------------------------------
# bwcli bans shows the kind
# ---------------------------------------------------------------------------------------------


def _bans_output(monkeypatch, log, *, db_rows, instance_rows=()):
    db = _db(log)
    db.get_bans.return_value = db_rows
    cli = _cli(monkeypatch, FakeClient(log), db=db)
    cli.send_to_apis = Mock(return_value=(True, {"bw-1": {"status": "success", "data": list(instance_rows)}}) if instance_rows else (True, {}))
    ok, text = cli.bans()
    assert ok is True
    return text


def test_bans_shows_the_kind_of_database_rows(monkeypatch, log):
    text = _bans_output(
        monkeypatch,
        log,
        db_rows=[{**lease_row(), "kind": "crowdsec_lease"}, {**explicit_row("198.51.100.9"), "kind": "ban"}],
    )

    assert text.count("Kind: CrowdSec lease") == 1
    assert text.count("Kind: ban") == 1


def test_bans_classifies_instance_rows_that_carry_no_kind(monkeypatch, log):
    text = _bans_output(monkeypatch, log, db_rows=[], instance_rows=[lease_row(), explicit_row("198.51.100.9")])

    assert text.count("Kind: CrowdSec lease") == 1
    assert text.count("Kind: ban") == 1


def test_bans_shows_the_kind_of_service_rows_too(monkeypatch, log):
    text = _bans_output(monkeypatch, log, db_rows=[{**lease_row(ban_scope="service", service="app"), "kind": "crowdsec_lease"}])

    assert "Kind: CrowdSec lease" in text

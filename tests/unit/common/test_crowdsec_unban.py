"""Unban flow for CrowdSec leases: discover, preview, revalidate, apply.

The flow runs against a fake client, so every `apply` branch is reachable. Pieces owned by other X1 lanes
are stubbed to the frozen contract (amendments 1 and 2): `POST /unban` with `lease_id` answering
`removed|absent|changed` (lane C), `DB.revoke_lease(ip, scope, service, lease_id)` (lane A), the
`refresh_ip` control operation (lane D) and `node` on a connection row (lane D).
"""

import json
from time import time

import pytest

from CrowdSec import CrowdSecError, encode_connection
import crowdsec_unban as unban

IP = "203.0.113.7"
LOCAL = "a" * 64
OTHER_LOCAL = "b" * 64
CONN = encode_connection("bw-1", LOCAL)
OTHER_CONN = encode_connection("bw-2", LOCAL)
LEASE_ID = "0123456789abcdef"


def lease_row(ip=IP, *, lease_id=LEASE_ID, ban_scope="global", service="unknown", node="node-1", connection=LOCAL, scope="global", exp=25):
    return {
        "ip": ip,
        "reason": "crowdsec",
        "service": service,
        "date": int(time()),
        "country": "XX",
        "ban_scope": ban_scope,
        "exp": exp,
        "expires_at": int(time()) + exp,
        "permanent": False,
        "reason_data": {
            "lease": True,
            "version": 1,
            "lease_id": lease_id,
            "instance": node,
            "connection": connection,
            "service_scope": scope,
            "remediation": "ban",
            "source": "lapi",
        },
    }


def explicit_row(ip=IP, *, ban_scope="service", service="app.example.com", reason="manual"):
    return {
        "ip": ip,
        "reason": reason,
        "service": service,
        "date": int(time()),
        "country": "XX",
        "ban_scope": ban_scope,
        "exp": 3600,
        "expires_at": int(time()) + 3600,
        "permanent": False,
        "reason_data": {},
    }


def decision(decision_id=1, *, value=IP, remediation="ban", origin="crowdsec", scope="Ip"):
    return {"id": decision_id, "scope": scope, "value": value, "type": "ban", "origin": origin, "scenario": "x/ssh-bf", "remediation": remediation}


def connection(conn_id=CONN, *, instance="bw-1", node="node-1", local_id=LOCAL, services=("global",), status="success", management=True):
    return {
        "id": conn_id,
        "local_id": local_id,
        "instance": instance,
        "node": node,
        "services": list(services),
        "status": status,
        "management_configured": management,
    }


class Log(list):
    """One ordered journal shared by the client and the database."""


class FakeClient:
    def __init__(self, log, *, instances=None, bans=None, connections=None, decisions=None):
        self.log = log
        self._hosts = instances or [{"hostname": "bw-1", "status": "up"}]
        self.bans = bans if bans is not None else {"bw-1": [lease_row()]}
        self.listing = connections if connections is not None else {"connections": [connection()], "errors": {}}
        self.decisions = decisions if decisions is not None else {CONN: [decision()]}
        self.unban_errors = {}
        self.refresh_errors = {}
        self.lease_outcomes = {}
        self.lease_errors = {}
        self.ban_errors = {}

    def _instances(self):
        return self._hosts

    def instance_request(self, instance, method, path, data=None):
        assert (method, path) == ("GET", "/bans")
        host = instance["hostname"]
        if host in self.ban_errors:
            raise CrowdSecError(self.ban_errors[host])
        return list(self.bans.get(host, []))

    def connections(self):
        return self.listing

    def query(self, connection_id, action, params=None):
        params = params or {}
        if action == "decisions":
            found = [d for d in self.decisions.get(connection_id, []) if d["value"] == params["ip"]]
            page = found[params.get("offset", 0) : params.get("offset", 0) + params.get("limit", 50)]
            return {"decisions": page, "total": len(found), "offset": params.get("offset", 0), "limit": params.get("limit", 50)}
        if action == "unban":
            self.log.append(("unban", connection_id, params["decision_id"]))
            if connection_id in self.unban_errors:
                raise CrowdSecError(self.unban_errors[connection_id])
            before = self.decisions.get(connection_id, [])
            kept = [d for d in before if d["id"] != params["decision_id"]]
            self.decisions[connection_id] = kept
            return {"removed": len(kept) != len(before), "already_absent": len(kept) == len(before)}
        if action == "refresh_ip":
            self.log.append(("refresh_ip", connection_id, params["ip"]))
            if connection_id in self.refresh_errors:
                raise CrowdSecError(self.refresh_errors[connection_id])
            return {"refreshed": True}
        raise AssertionError(f"unexpected action {action}")

    def remove_lease(self, instance, ip, ban_scope, service, lease_id):
        host = instance["hostname"]
        self.log.append(("remove_lease", host, ip, ban_scope, service, lease_id))
        if host in self.lease_errors:
            raise CrowdSecError(self.lease_errors[host])
        return self.lease_outcomes.get(host, "removed")


class FakeDB:
    def __init__(self, log, error=""):
        self.log = log
        self.error = error

    def revoke_lease(self, ip, *, ban_scope="global", service_id="", lease_id="", revoked_by=""):  # lane A's signature
        self.log.append(("revoke_lease", ip, ban_scope, service_id, lease_id))
        return self.error


class FakeRedis:
    def __init__(self, values=None):
        self.values = values or {}
        self.reads = []

    def get(self, key):
        self.reads.append(key)
        return self.values.get(key)


def preview_of(client, ip=IP, ban_scope="global", service=None, **kwargs):
    return unban.preview(client, ip, ban_scope, service, **kwargs)


def keys(current):
    return [d["key"] for d in current["decisions"]]


# ---------------------------------------------------------------------------------------------- discovery


def test_a_lease_created_before_any_sync_bans_pass_is_found_and_removed():
    # amendment 1 R2: the database has never seen this lease (no DB object exists in this test at all);
    # the runtime view of the instance is the only source.
    log = Log()
    client = FakeClient(log, bans={"bw-1": [lease_row(exp=1)]})

    current = preview_of(client)
    assert [lease["lease_id"] for lease in current["leases"]] == [LEASE_ID]
    assert current["lease"]["exp"] == 1
    assert keys(current) == [f"{CONN}:1"]

    result = unban.apply(client, IP, "global", None, current)

    assert result["status"] == "success"
    assert result["lease_removed"] == ["bw-1"]
    assert ("remove_lease", "bw-1", IP, "global", None, LEASE_ID) in log


def test_a_lease_that_lives_only_in_redis_is_found_and_removed_through_an_up_instance():
    log = Log()
    value = lease_row()
    redis = FakeRedis(
        {f"bans_ip_{IP}": json.dumps({k: value[k] for k in ("reason", "service", "date", "country", "ban_scope", "reason_data", "permanent", "expires_at")})}
    )
    client = FakeClient(log, bans={"bw-1": []})

    current = preview_of(client, redis_client=redis)

    assert redis.reads == [f"bans_ip_{IP}"]
    assert [(lease["source"], lease["lease_id"]) for lease in current["leases"]] == [("redis", LEASE_ID)]
    result = unban.apply(client, IP, "global", None, current)
    assert result["lease_removed"] == ["bw-1"]
    assert ("remove_lease", "bw-1", IP, "global", None, LEASE_ID) in log


def test_a_service_lease_reads_the_service_redis_key():
    redis = FakeRedis()
    client = FakeClient(Log(), bans={"bw-1": []})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client, ban_scope="service", service="app.example.com", redis_client=redis)
    assert caught.value.status == 404
    assert redis.reads == [f"bans_service_app.example.com_ip_{IP}"]


def test_an_expired_redis_value_is_not_a_lease():
    value = lease_row()
    value["expires_at"] = int(time()) - 5
    redis = FakeRedis({f"bans_ip_{IP}": json.dumps(value)})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(FakeClient(Log(), bans={"bw-1": []}), redis_client=redis)
    assert caught.value.status == 404


def test_no_lease_is_a_404():
    with pytest.raises(CrowdSecError) as caught:
        preview_of(FakeClient(Log(), bans={"bw-1": [explicit_row(ban_scope="global", service="unknown")]}))
    assert caught.value.status == 404


def test_absence_needs_a_completed_listing_from_every_instance():
    client = FakeClient(Log(), instances=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "down"}], bans={"bw-1": []})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client)
    assert caught.value.status == 502
    assert "bw-2" in str(caught.value)


def test_a_failed_listing_does_not_hide_a_lease_found_elsewhere_but_is_reported():
    client = FakeClient(Log(), instances=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "up"}], bans={"bw-1": [lease_row()]})
    client.ban_errors["bw-2"] = "BunkerWeb instance is unavailable"
    current = preview_of(client)
    assert "instance:bw-2" in current["unavailable"]


def test_a_malformed_listing_is_a_failure_not_an_absence():
    client = FakeClient(Log(), bans={"bw-1": []})
    client.instance_request = lambda *_args, **_kwargs: "not a list"
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client)
    assert caught.value.status == 502


def test_is_lease_needs_reason_flag_and_id():
    assert unban.is_lease(lease_row())
    assert not unban.is_lease(explicit_row(reason="crowdsec"))
    row = lease_row()
    del row["reason_data"]["lease_id"]
    assert not unban.is_lease(row)
    row = lease_row()
    row["reason"] = "manual"
    assert not unban.is_lease(row)
    assert not unban.is_lease("garbage")


def test_runtime_snapshot_is_taken_once_for_many_lookups():
    calls = []
    client = FakeClient(Log(), bans={"bw-1": [lease_row(), lease_row("198.51.100.4")]})
    original = client.instance_request

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    client.instance_request = counting
    runtime = unban.collect_runtime(client)
    first, _ = unban.find_leases(runtime, IP, "global", None)
    second, _ = unban.find_leases(runtime, "198.51.100.4", "global", None)
    assert (len(first), len(second), len(calls)) == (1, 1, 1)


# ------------------------------------------------------------------------------- explicit bans survive


def test_an_explicit_service_ban_on_the_same_ip_is_never_touched_by_a_global_lease_unban():
    # amendment 1 R1: only lease_id removals; the generic unban and the generic revoke are never used.
    log = Log()
    bans = {"bw-1": [lease_row(), explicit_row()]}
    client = FakeClient(log, bans=bans)
    db = FakeDB(log)

    current = preview_of(client)
    assert [lease["lease_id"] for lease in current["leases"]] == [LEASE_ID]
    result = unban.apply(client, IP, "global", None, current, db=db)

    assert result["status"] == "success"
    removals = [entry for entry in log if entry[0] == "remove_lease"]
    assert removals == [("remove_lease", "bw-1", IP, "global", None, LEASE_ID)]
    assert [entry for entry in log if entry[0] == "revoke_lease"] == [("revoke_lease", IP, "global", "", LEASE_ID)]
    assert bans["bw-1"][1] == explicit_row(ban_scope="service", service="app.example.com") | {
        "date": bans["bw-1"][1]["date"],
        "expires_at": bans["bw-1"][1]["expires_at"],
    }


def test_a_service_lease_is_not_matched_by_a_global_lookup_and_the_reverse():
    client = FakeClient(Log(), bans={"bw-1": [lease_row(ban_scope="service", service="app.example.com", scope="app.example.com")]})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client)
    assert caught.value.status == 404
    current = preview_of(client, ban_scope="service", service="app.example.com")
    assert current["lease"]["service"] == "app.example.com"


def test_the_lease_of_another_service_is_not_matched():
    client = FakeClient(Log(), bans={"bw-1": [lease_row(ban_scope="service", service="other.example.com", scope="other.example.com")]})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client, ban_scope="service", service="app.example.com")
    assert caught.value.status == 404


# ----------------------------------------------------------------------------------- apply branches


def test_apply_success_runs_decisions_refresh_check_lease_then_database_last():
    log = Log()
    client = FakeClient(log)
    db = FakeDB(log)
    current = preview_of(client)

    result = unban.apply(client, IP, "global", None, current, db=db)

    assert result["status"] == "success"
    assert result["deleted"] == [f"{CONN}:1"]
    assert result["refreshed"] == [CONN]
    assert result["db_revoked"] == [LEASE_ID]
    assert [entry[0] for entry in log] == ["unban", "refresh_ip", "remove_lease", "revoke_lease"]


def test_the_database_revoke_runs_after_every_instance_removal():
    log = Log()
    client = FakeClient(
        log,
        instances=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "up"}],
        bans={"bw-1": [lease_row()], "bw-2": [lease_row(lease_id="fedcba9876543210")]},
    )
    current = preview_of(client)
    unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    names = [entry[0] for entry in log]
    assert names.index("revoke_lease") > max(i for i, name in enumerate(names) if name == "remove_lease")
    # each instance gets the id it holds, never the other's
    assert ("remove_lease", "bw-1", IP, "global", None, LEASE_ID) in log
    assert ("remove_lease", "bw-2", IP, "global", None, "fedcba9876543210") in log
    assert not any(entry[0] == "remove_lease" and (entry[1], entry[5]) in {("bw-1", "fedcba9876543210"), ("bw-2", LEASE_ID)} for entry in log)


def test_apply_with_a_failed_decision_deletion_stops_before_refresh_and_lease_removal():
    log = Log()
    client = FakeClient(log)
    client.unban_errors[CONN] = "CrowdSec Local API is unreachable"
    current = preview_of(client)

    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "partial"
    assert result["failed"] == [{"key": f"{CONN}:1", "error": "CrowdSec Local API is unreachable"}]
    assert [entry[0] for entry in log] == ["unban"]


def test_a_decision_that_is_already_gone_counts_as_success():
    log = Log()
    client = FakeClient(log)
    current = preview_of(client)
    client.decisions[CONN] = []  # removed by someone else between the preview and the apply

    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "success"
    assert result["already_absent"] == [f"{CONN}:1"]
    assert result["deleted"] == []


def test_a_failed_refresh_keeps_the_lease_and_the_database_row():
    log = Log()
    client = FakeClient(log)
    client.refresh_errors[CONN] = "refresh_ip failed"
    current = preview_of(client)

    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "partial"
    assert {"connection_id": CONN, "error": "refresh_ip failed"} in result["failed"]
    assert "remove_lease" not in [entry[0] for entry in log]
    assert "revoke_lease" not in [entry[0] for entry in log]


def test_a_ban_decision_that_is_still_active_blocks_the_lease_removal():
    log = Log()
    client = FakeClient(log, decisions={CONN: [decision(1)]})
    current = preview_of(client)
    # CrowdSec answers the delete but a second ban decision for the same IP shows up before the check
    original = client.query

    def sneaky(connection_id, action, params=None):
        outcome = original(connection_id, action, params)
        if action == "refresh_ip":
            client.decisions[connection_id] = [decision(2)]
        return outcome

    client.query = sneaky
    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "partial"
    assert result["failed"] == [{"connection_id": CONN, "error": "a CrowdSec ban decision is still active"}]
    assert "remove_lease" not in [entry[0] for entry in log]


def test_a_down_instance_is_reported_and_the_database_is_still_revoked_for_the_replay():
    log = Log()
    client = FakeClient(log, instances=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "down"}], bans={"bw-1": [lease_row()]})
    client.listing = {"connections": [connection()], "errors": {}}
    current = preview_of(client)
    assert "instance:bw-2" in current["unavailable"]

    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "partial"
    assert result["down"] == ["bw-2"]
    assert result["lease_removed"] == ["bw-1"]
    # the tombstone is what lets sync-bans replay the removal on bw-2 when it returns
    assert result["db_revoked"] == [LEASE_ID]


def test_a_removal_that_returns_changed_reports_it_and_leaves_that_database_row():
    log = Log()
    client = FakeClient(log)
    client.lease_outcomes["bw-1"] = "changed"  # renewed (new lease_id) or replaced by an explicit ban
    current = preview_of(client)

    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "changed"
    assert result["lease_changed"] == [{"instance": "bw-1", "lease_id": LEASE_ID}]
    assert result["lease_removed"] == []
    assert "revoke_lease" not in [entry[0] for entry in log]


def test_changed_on_one_instance_still_revokes_the_ids_that_were_removed():
    log = Log()
    client = FakeClient(
        log,
        instances=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "up"}],
        bans={"bw-1": [lease_row()], "bw-2": [lease_row(lease_id="fedcba9876543210")]},
    )
    client.lease_outcomes["bw-2"] = "changed"
    current = preview_of(client)

    result = unban.apply(client, IP, "global", None, current, db=FakeDB(log))

    assert result["status"] == "partial"
    assert result["db_revoked"] == [LEASE_ID]
    assert ("revoke_lease", IP, "global", "", "fedcba9876543210") not in log


def test_an_absent_lease_counts_as_removed():
    client = FakeClient(Log())
    client.lease_outcomes["bw-1"] = "absent"
    result = unban.apply(client, IP, "global", None, preview_of(client), db=FakeDB(client.log))
    assert result["status"] == "success"
    assert result["lease_absent"] == ["bw-1"]


def test_a_failing_lease_removal_is_partial_and_named():
    client = FakeClient(Log())
    client.lease_errors["bw-1"] = "BunkerWeb instance could not complete the request"
    result = unban.apply(client, IP, "global", None, preview_of(client), db=FakeDB(client.log))
    assert result["status"] == "partial"
    assert result["lease_failed"] == [{"instance": "bw-1", "error": "BunkerWeb instance could not complete the request"}]


def test_a_failed_database_revoke_is_partial():
    client = FakeClient(Log())
    result = unban.apply(client, IP, "global", None, preview_of(client), db=FakeDB(client.log, error="database is read-only"))
    assert result["status"] == "partial"
    assert result["db_failed"] == [{"lease_id": LEASE_ID, "error": "database is read-only"}]


def test_a_service_lease_is_removed_with_its_service():
    log = Log()
    client = FakeClient(
        log,
        bans={"bw-1": [lease_row(ban_scope="service", service="app.example.com", scope="app.example.com")]},
        connections={
            "connections": [connection(), connection(services=("app.example.com",), conn_id=encode_connection("bw-1", OTHER_LOCAL), local_id=OTHER_LOCAL)],
            "errors": {},
        },
    )
    client.listing["connections"][0]["services"] = ["global"]
    current = preview_of(client, ban_scope="service", service="app.example.com")
    result = unban.apply(client, IP, "service", "app.example.com", current, db=FakeDB(log))
    assert result["status"] == "success"
    assert ("remove_lease", "bw-1", IP, "service", "app.example.com", LEASE_ID) in log
    assert ("revoke_lease", IP, "service", "app.example.com", LEASE_ID) in log


def test_apply_without_a_database_leaves_the_revoke_to_the_caller():
    client = FakeClient(Log())
    result = unban.apply(client, IP, "global", None, preview_of(client))
    assert result["status"] == "success"
    assert result["db_revoked"] == []


# ------------------------------------------------------------------------------------ revalidation


def test_revalidate_is_ready_when_the_confirmed_keys_match():
    client = FakeClient(Log())
    current = preview_of(client)
    checked = unban.revalidate(client, IP, "global", None, keys(current))
    assert checked["status"] == "ready"


def test_revalidate_reports_changed_when_a_decision_appeared_since_the_preview():
    client = FakeClient(Log())
    confirmed = keys(preview_of(client))
    client.decisions[CONN].append(decision(9))
    checked = unban.revalidate(client, IP, "global", None, confirmed)
    assert checked["status"] == "changed"
    assert sorted(keys(checked["preview"])) == sorted([f"{CONN}:1", f"{CONN}:9"])


def test_revalidate_reports_changed_when_the_lease_vanished_is_a_404():
    client = FakeClient(Log())
    confirmed = keys(preview_of(client))
    client.bans["bw-1"] = []
    with pytest.raises(CrowdSecError) as caught:
        unban.revalidate(client, IP, "global", None, confirmed)
    assert caught.value.status == 404


def test_revalidate_with_a_fresh_snapshot_does_not_ask_the_instances_again():
    client = FakeClient(Log())
    runtime = unban.collect_runtime(client)
    client.bans["bw-1"] = []  # a second read would find nothing
    checked = unban.revalidate(client, IP, "global", None, [f"{CONN}:1"], runtime=runtime)
    assert checked["status"] == "ready"


def test_a_caller_not_allowed_on_every_connection_gets_changed_without_a_preview():
    client = FakeClient(Log())
    confirmed = keys(preview_of(client))
    assert unban.revalidate(client, IP, "global", None, confirmed, {OTHER_CONN})["status"] == "changed"
    assert unban.revalidate(client, IP, "global", None, confirmed, {CONN})["status"] == "ready"
    assert unban.revalidate(client, IP, "global", None, confirmed, {"*"})["status"] == "ready"
    assert "preview" not in unban.revalidate(client, IP, "global", None, confirmed, {OTHER_CONN})


def test_missing_management_credentials_is_a_409():
    client = FakeClient(Log(), connections={"connections": [connection(management=False)], "errors": {}})
    with pytest.raises(CrowdSecError) as caught:
        unban.revalidate(client, IP, "global", None, [f"{CONN}:1"])
    assert caught.value.status == 409


def test_an_unavailable_source_connection_is_a_409():
    client = FakeClient(Log(), connections={"connections": [connection(status="error")], "errors": {}})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client)
    assert caught.value.status == 409


def test_instances_sharing_one_configuration_are_not_ambiguous():
    # the local id is a hash of the configuration: two instances with the same one both match
    client = FakeClient(Log(), connections={"connections": [connection(), connection(conn_id=OTHER_CONN, instance="bw-2", node="node-2")], "errors": {}})
    assert preview_of(client)["source"]["connection_id"] == CONN


def test_node_names_the_source_instance_when_the_connection_rows_carry_it():
    other = connection(conn_id=OTHER_CONN, instance="bw-2", node="node-2")
    client = FakeClient(Log(), connections={"connections": [other], "errors": {}})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client)  # the lease names node-1, only node-2 serves this configuration
    assert caught.value.status == 409


def test_connection_rows_without_node_match_on_the_local_id_alone():
    row = connection()
    del row["node"]
    client = FakeClient(Log(), connections={"connections": [row], "errors": {}})
    assert preview_of(client)["source"]["connection_id"] == CONN


def test_a_lease_whose_connection_is_gone_is_a_409():
    client = FakeClient(Log(), connections={"connections": [connection(local_id=OTHER_LOCAL, conn_id=OTHER_CONN)], "errors": {}})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client)
    assert caught.value.status == 409


# --------------------------------------------------------------------------------------- preview


def test_preview_lists_only_ban_decisions_and_warns_about_lists_and_ranges():
    decisions = [
        decision(1),
        decision(2, remediation="captcha"),
        decision(3, origin="CAPI"),
        decision(4, value="203.0.113.0/24", scope="Range"),
    ]
    client = FakeClient(Log(), decisions={CONN: decisions})
    # the fake filters on the exact value; a contained range comes back for the IP query too
    client.decisions[CONN][3]["value"] = IP
    client.decisions[CONN][3]["scope"] = "Range"
    current = preview_of(client)
    assert [d["id"] for d in current["decisions"]] == [1, 3, 4]
    assert current["warnings"] == {"list_origin": True, "range": False}


def test_a_wide_range_decision_raises_the_range_warning():
    client = FakeClient(Log(), decisions={CONN: [decision(1, value=IP)]})
    client.decisions[CONN][0].update(scope="Range", value=IP)
    assert unban.preview(client, IP, "global", None)["warnings"]["range"] is False
    assert unban._wide_range({"scope": "range", "value": "203.0.113.0/24"}) is True
    assert unban._wide_range({"scope": "range", "value": "not-a-range"}) is True
    assert unban._wide_range({"scope": "ip", "value": IP}) is False


def test_involved_names_every_connection_and_flags_unknown_failures_for_wildcard():
    client = FakeClient(Log(), instances=[{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "up"}], bans={"bw-1": [lease_row()]})
    client.ban_errors["bw-2"] = "BunkerWeb instance is unavailable"
    ids, wildcard = unban.involved(preview_of(client))
    assert ids == {CONN}
    assert wildcard is True


def test_pagination_collects_every_decision():
    many = [decision(index) for index in range(1, 451)]
    client = FakeClient(Log(), decisions={CONN: many})
    assert len(preview_of(client)["decisions"]) == 450


# ------------------------------------------------------------------------------------ redis client


def test_redis_client_is_none_when_redis_is_off(monkeypatch):
    monkeypatch.setattr(unban, "get_redis_client", lambda **_kwargs: pytest.fail("must not connect"))
    assert unban.redis_client_from({"USE_REDIS": "no"}) is None
    assert unban.redis_client_from({}) is None


def test_redis_client_is_built_from_the_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(unban, "get_redis_client", lambda **kwargs: seen.update(kwargs) or "client")
    settings = {"USE_REDIS": "yes", "REDIS_HOST": "redis", "REDIS_PORT": "6380", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no", "REDIS_PASSWORD": "pw"}
    assert unban.redis_client_from(settings) == "client"
    assert (seen["redis_host"], seen["redis_port"], seen["redis_ssl"], seen["redis_ssl_verify"], seen["redis_password"]) == ("redis", "6380", True, False, "pw")


def test_an_unreachable_redis_makes_the_lookup_incomplete_not_empty():
    class Broken:
        def get(self, _key):
            raise ConnectionError("down")

    client = FakeClient(Log(), bans={"bw-1": []})
    with pytest.raises(CrowdSecError) as caught:
        preview_of(client, redis_client=Broken())
    assert caught.value.status == 502
    assert "redis" in str(caught.value)


# ------------------------------------------------------------------- lane A's real revoke_lease


def test_apply_revokes_the_learned_row_through_the_real_database_and_spares_the_explicit_one(db):
    # Contract check against lane A's DB method (not a fake): same identity rule, explicit service ban kept active.
    from datetime import datetime, timedelta, timezone

    expires = datetime.now(timezone.utc) + timedelta(seconds=30)
    assert db.upsert_ban(IP, ban_scope="global", reason="crowdsec", reason_data=lease_row()["reason_data"], expires_at=expires, origin="redis") == ""
    assert db.upsert_ban(IP, ban_scope="service", service_id="app.example.com", reason="manual", expires_at=expires + timedelta(hours=1), origin="api") == ""

    client = FakeClient(Log())
    result = unban.apply(client, IP, "global", None, preview_of(client), db=db, actor="alice")

    assert result["db_revoked"] == [LEASE_ID] and result["status"] == "success"
    active = db.get_bans()
    assert [(row["ban_scope"], row["service"], row["kind"]) for row in active] == [("service", "app.example.com", "ban")]
    # a second apply is idempotent: nothing matches, no error
    assert unban.apply(client, IP, "global", None, preview_of(FakeClient(Log())), db=db)["db_failed"] == []

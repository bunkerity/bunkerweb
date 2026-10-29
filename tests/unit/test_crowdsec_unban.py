import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
for source_dir in (REPO_ROOT / "src/common/api", REPO_ROOT / "src/common/utils"):
    sys.path.insert(0, str(source_dir))

import CrowdSec  # noqa: E402
from CrowdSec import CrowdSecClient, CrowdSecError  # noqa: E402
from crowdsec_unban import apply, execute, find_lease, involved, lease_in_rows, preview, revalidate  # noqa: E402

IP = "1.2.3.4"


def conn(instance, local, services=("global",), status="success", node=None, management=True, with_id=True):
    return {
        "id": f"{instance}_{local}" if with_id else None,
        "local_id": local,
        "node": node or f"node-{instance}",
        "instance": instance,
        "services": list(services),
        "status": status,
        "management_configured": management,
    }


def lease_row(node, local, scope="global", service=None):
    row = {
        "kind": "crowdsec_lease",
        "ip": IP,
        "ban_scope": "global" if scope == "global" else "service",
        "exp": 100,
        "reason_data": {"instance": node, "connection": local, "service_scope": scope},
    }
    if service:
        row["service"] = service
    return row


def decision(did, remediation="ban", scope="Ip", value=IP, origin="crowdsec"):
    return {"id": did, "scope": scope, "value": value, "type": remediation, "origin": origin, "scenario": "s", "remediation": remediation}


class FakeClient:
    """In-memory stand-in for CrowdSecClient: records every call in self.calls."""

    def __init__(self, hosts=("i1",), connections=(), lookups=None, decisions=None, listing_errors=None):
        self.instances = [{"hostname": host} for host in hosts]
        self.rows = list(connections)
        self.listing_errors = listing_errors or {}
        self.lookups = lookups if lookups is not None else {}  # hostname -> reply dict or Exception
        self.decisions = decisions if decisions is not None else {}  # connection id -> list of decisions
        self.query_errors = {}  # (connection id, action) -> Exception
        self.post_write_errors = {}  # connection id -> Exception, raised by decisions once a write happened
        self.sticky = set()  # connection ids whose unban reports success but deletes nothing
        self.remove_errors = {}  # hostname -> Exception
        self.calls = []
        self.written = False

    def _instances(self):
        return self.instances

    def connections(self):
        self.calls.append(("connections",))
        return {"connections": self.rows, "errors": self.listing_errors}

    def instance_request(self, instance, method, path, data=None):
        host = instance["hostname"]
        self.calls.append((path.strip("/"), host, data))
        if path == "/lease_lookup":
            reply = self.lookups[host]
            if isinstance(reply, Exception):
                raise reply
            return reply
        if path == "/remove_lease":
            if host in self.remove_errors:
                raise self.remove_errors[host]
            return {}
        raise AssertionError(path)

    def query(self, connection_id, action, params=None):
        params = params or {}
        self.calls.append((action, connection_id, params))
        if (connection_id, action) in self.query_errors:
            raise self.query_errors[(connection_id, action)]
        if action == "decisions":
            if self.written and connection_id in self.post_write_errors:
                raise self.post_write_errors[connection_id]
            everything = self.decisions.get(connection_id, [])
            offset, limit = params.get("offset", 0), params["limit"]
            end = offset + limit
            return {"decisions": everything[offset:end], "total": len(everything)}
        if action == "unban":
            self.written = True
            items = self.decisions.get(connection_id, [])
            present = any(d["id"] == params["decision_id"] for d in items)
            if not present:
                return {"already_absent": True}
            if connection_id not in self.sticky:
                self.decisions[connection_id] = [d for d in items if d["id"] != params["decision_id"]]
            return {}
        if action == "refresh_ip":
            self.written = True
            return {}
        raise AssertionError(action)

    def kinds(self):
        return [call[0] for call in self.calls]

    def writes(self):
        return [call for call in self.calls if call[0] in ("unban", "refresh_ip", "remove_lease")]


def found(row):
    return {"found": True, "row": row}


NOT_FOUND = {"found": False}


def simple(connections, decisions=None, scope="global", service=None, hosts=("i1",), **kwargs):
    """Client whose first instance holds the lease sourced from connections[0]."""
    source = connections[0]
    row = lease_row(source["node"], source["local_id"], scope, service)
    lookups = {host: NOT_FOUND for host in hosts}
    lookups[hosts[0]] = found(row)
    return FakeClient(hosts=hosts, connections=connections, lookups=lookups, decisions=decisions, **kwargs)


class CrowdSecUnbanTest(TestCase):
    def test_lease_in_rows_is_exact(self):
        row = lease_row("n", "L")
        other = {**row, "ip": "9.9.9.9"}
        explicit = {**row, "kind": "ban"}
        service_row = lease_row("n", "L", "svc", "svc")
        self.assertIs(lease_in_rows([other, explicit, row], IP, "global", None), row)
        self.assertIsNone(lease_in_rows([service_row], IP, "global", None))
        self.assertIs(lease_in_rows([service_row], IP, "service", "svc"), service_row)
        self.assertIsNone(lease_in_rows([service_row], IP, "service", "other"))
        self.assertIsNone(lease_in_rows([{**row, "reason_data": None}, "junk", None], IP, "global", None))
        self.assertIsNone(lease_in_rows(None, IP, "global", None))

    def test_client_token_and_refresh_ip_allow_list(self):
        client = CrowdSecClient(MagicMock(), token="tok")
        self.assertEqual(client.token, "tok")
        self.assertIsNone(CrowdSecClient(MagicMock()).token)
        api = MagicMock()
        api.request.return_value = (True, "", 200, {"status": "success", "data": {"ok": 1}})
        instance = {"hostname": "h"}
        with patch.object(CrowdSec.API, "from_instance", return_value=api) as from_instance:
            self.assertEqual(client.instance_request(instance, "POST", "/remove_lease", {"ip": IP}), {"ok": 1})
            from_instance.assert_called_with(instance, token="tok")
            with patch.object(client, "_resolve", return_value=(instance, "L")):
                self.assertEqual(client.query("c", "refresh_ip", {"ip": IP}), {"ok": 1})
        api.request.assert_called_with("POST", "/crowdsec/refresh_ip", data={"ip": IP, "connection": "L"}, timeout=(5, 30))
        with self.assertRaises(CrowdSecError) as ctx:
            client.query("c", "nope", {})
        self.assertEqual(ctx.exception.status, 400)

    def test_locate_by_node_not_by_local_id_alone(self):
        a, b = conn("i1", "L"), conn("i2", "L")  # two instances share a local id, only node-i1 matches
        client = simple([a, b], hosts=("i1", "i2"))
        client.decisions = {a["id"]: [decision(1)], b["id"]: [decision(2)]}
        result = preview(client, IP, "global", None)
        self.assertEqual(result["source"], {"connection_id": a["id"], "instance": "i1"})

    def test_source_instance_down_refuses(self):
        source = conn("i1", "L", status="error")
        with self.assertRaises(CrowdSecError) as ctx:
            preview(simple([source]), IP, "global", None)
        self.assertEqual(ctx.exception.status, 409)
        client = simple([conn("i1", "L")])
        client.rows = [conn("i1", "other")]  # the lease source connection is gone
        with self.assertRaises(CrowdSecError) as ctx:
            preview(client, IP, "global", None)
        self.assertEqual(ctx.exception.status, 409)

    def test_preview_keeps_ban_remediation_only_and_flags_ranges_and_lists(self):
        source = conn("i1", "L")
        decisions = {source["id"]: [decision(1, origin="capi"), decision(2, "captcha"), decision(3, scope="Range", value="1.2.3.0/24")]}
        result = preview(simple([source], decisions), IP, "global", None)
        self.assertEqual([d["id"] for d in result["decisions"]], [1, 3])
        self.assertEqual(result["decisions"][0]["key"], f"{source['id']}:1")
        self.assertEqual(result["warnings"], {"list_origin": True, "range": True})
        self.assertEqual(result["management_missing"], [])
        calm = preview(simple([source], {source["id"]: [decision(1), decision(4, scope="Range", value="1.2.3.4/32")]}), IP, "global", None)
        self.assertEqual(calm["warnings"], {"list_origin": False, "range": False})
        garbled = preview(simple([source], {source["id"]: [decision(5, scope="Range", value="not-a-range")]}), IP, "global", None)
        self.assertTrue(garbled["warnings"]["range"])

    def test_preview_discovers_decisions_on_every_connection_serving_the_scope(self):
        a = conn("i1", "A", ["svc"])
        b = conn("i1", "B")
        c = conn("i2", "C", ["other"])
        d = conn("i2", "D")
        rows = [a, b, c, d]
        decisions = {x["id"]: [decision(1)] for x in rows}
        everywhere = preview(simple(rows, decisions), IP, "global", None)
        self.assertEqual(sorted(everywhere["connections"]), sorted(x["id"] for x in rows))
        scoped = preview(simple(rows, decisions, scope="svc", service="svc"), IP, "service", "svc")
        self.assertEqual(sorted(scoped["connections"]), sorted([a["id"], d["id"]]))  # i1 has the service; i2 falls back to its global connection
        without_global = preview(simple([a, c], {a["id"]: [], c["id"]: []}, scope="svc", service="svc"), IP, "service", "svc")
        self.assertEqual(without_global["connections"], [a["id"]])

    def test_id_less_failure_rows_serving_the_scope_make_the_result_partial(self):
        source = conn("i1", "G")
        broken = conn("i1", "bad", ["svc"], status="error", with_id=False)
        client = simple([source, broken], {source["id"]: []}, scope="svc", service="svc")
        result = execute(client, IP, "service", "svc", [])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["unavailable"], ["i1:svc"])
        self.assertEqual(result["lease_removed"], ["i1"])

    def test_failed_service_row_plus_global_connection_discovers_global_decisions(self):
        source = conn("i1", "G")
        broken = conn("i1", "bad", ["svc"], status="error", with_id=False)
        client = simple([source, broken], {source["id"]: [decision(7)]}, scope="svc", service="svc")
        current = preview(client, IP, "service", "svc")
        self.assertEqual([d["key"] for d in current["decisions"]], [f"{source['id']}:7"])
        result = execute(client, IP, "service", "svc", [f"{source['id']}:7"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["deleted"], [f"{source['id']}:7"])

    def test_changed_for_unauthorized_connection_carries_no_preview(self):
        a, b = conn("i1", "A"), conn("i1", "B")
        client = simple([a, b], {a["id"]: [], b["id"]: []})
        result = execute(client, IP, "global", None, [], allowed_connections={a["id"]})
        self.assertEqual(result, {"status": "changed"})
        self.assertEqual(client.writes(), [])

    def test_preview_reports_unhealthy_serving_connections_and_listing_errors(self):
        source = conn("i1", "A")
        sick = conn("i1", "S", status="error")
        flaky = conn("i1", "F")
        client = simple([source, sick, flaky], {source["id"]: [decision(1)]}, listing_errors={"i3": "boom"})
        client.query_errors[(flaky["id"], "decisions")] = CrowdSecError("no decisions")
        current = preview(client, IP, "global", None)
        self.assertEqual(current["unavailable"], [sick["id"], "instance:i3", flaky["id"]])
        self.assertEqual(current["connections"], [source["id"]])
        result = execute(client, IP, "global", None, [f"{source['id']}:1"])
        self.assertEqual(result["status"], "partial")

    def test_discovery_and_postcondition_paginate_past_200(self):
        source = conn("i1", "A")
        old_ban = decision(999)
        decisions = {source["id"]: [decision(n, "captcha") for n in range(200)] + [old_ban]}
        client = simple([source], decisions)
        client.sticky.add(source["id"])
        self.assertEqual([d["id"] for d in preview(client, IP, "global", None)["decisions"]], [999])
        result = execute(client, IP, "global", None, [f"{source['id']}:999"])
        self.assertEqual(result["status"], "partial")  # the postcondition sees the ban hidden on page 2
        self.assertEqual(result["failed"][0]["error"], "a CrowdSec ban decision is still active")
        offsets = [call[2]["offset"] for call in client.calls if call[0] == "decisions"]
        self.assertIn(200, offsets)

    def test_execute_new_connection_outside_allowed_set_returns_changed_without_writes(self):
        a = conn("i1", "A")
        client = simple([a], {a["id"]: [decision(1)]})
        allowed = set(preview(client, IP, "global", None)["connections"])
        newcomer = conn("i1", "N")
        client.rows.append(newcomer)
        client.decisions[newcomer["id"]] = []
        result = execute(client, IP, "global", None, [f"{a['id']}:1"], allowed_connections=allowed)
        self.assertEqual(result, {"status": "changed"})
        self.assertEqual(client.writes(), [])

    def test_new_unavailable_connection_outside_allowed_set_returns_changed_without_writes(self):
        a = conn("i1", "A")
        client = simple([a], {a["id"]: [decision(1)]})
        allowed = involved(preview(client, IP, "global", None))[0]
        sick = conn("i1", "S", status="error")
        client.rows.append(sick)
        result = execute(client, IP, "global", None, [f"{a['id']}:1"], allowed_connections=allowed)
        self.assertEqual(result, {"status": "changed"})
        self.assertEqual(client.writes(), [])

    def test_unavailable_without_identity_needs_wildcard_authorization(self):
        a = conn("i1", "A")
        client = simple([a], {a["id"]: [decision(1)]}, listing_errors={"i3": "boom"})
        ids, wildcard = involved(preview(client, IP, "global", None))
        self.assertEqual((ids, wildcard), ({a["id"]}, True))
        keys = [f"{a['id']}:1"]
        self.assertEqual(execute(client, IP, "global", None, keys, allowed_connections=ids), {"status": "changed"})
        self.assertEqual(client.writes(), [])
        self.assertEqual(execute(client, IP, "global", None, keys, allowed_connections=ids | {"*"})["status"], "partial")

    def test_new_id_less_unavailable_row_returns_changed_without_writes(self):
        a = conn("i1", "A")
        client = simple([a], {a["id"]: [decision(1)]})
        allowed = involved(preview(client, IP, "global", None))[0]
        client.rows.append(conn("i1", "bad", status="error", with_id=False))
        result = execute(client, IP, "global", None, [f"{a['id']}:1"], allowed_connections=allowed)
        self.assertEqual(result, {"status": "changed"})
        self.assertEqual(client.writes(), [])

    def test_source_whose_decisions_fail_stays_in_the_involved_set(self):
        a, b = conn("i1", "A"), conn("i1", "B")
        client = simple([a, b], {a["id"]: [], b["id"]: []})
        client.query_errors[(a["id"], "decisions")] = CrowdSecError("no decisions")
        ids, wildcard = involved(preview(client, IP, "global", None))
        self.assertEqual((ids, wildcard), ({a["id"], b["id"]}, False))
        self.assertEqual(execute(client, IP, "global", None, [], allowed_connections={b["id"]}), {"status": "changed"})
        self.assertEqual(client.writes(), [])

    def test_redis_only_lease_is_found_through_lease_lookup(self):
        row = lease_row("n", "L")
        client = FakeClient(hosts=("i1", "i2"), lookups={"i1": NOT_FOUND, "i2": found(row)})
        self.assertIs(find_lease(client, IP, "global", None), row)
        self.assertEqual(client.calls[0], ("lease_lookup", "i1", {"ip": IP, "ban_scope": "global"}))
        self.assertIsNone(find_lease(FakeClient(hosts=("i1", "i2"), lookups={"i1": NOT_FOUND, "i2": NOT_FOUND}), IP, "global", None))
        client = FakeClient(lookups={"i1": found(row)})
        find_lease(client, IP, "service", "svc")
        self.assertEqual(client.calls[0][2], {"ip": IP, "ban_scope": "service", "service": "svc"})

    def test_lookup_failure_is_not_absence(self):
        for bad in (CrowdSecError("bad gateway"), "down", {"nonsense": 1}, {"found": True, "row": {"reason_data": "x"}}):
            with self.subTest(bad=bad):
                lookups = {"i1": bad if bad != "down" else NOT_FOUND, "i2": NOT_FOUND}
                client = FakeClient(hosts=("i1", "i2"), lookups=lookups)
                if bad == "down":
                    client.instances[0]["status"] = "down"
                with self.assertRaises(CrowdSecError) as ctx:
                    find_lease(client, IP, "global", None)
                self.assertEqual(ctx.exception.status, 502)
                with self.assertRaises(CrowdSecError) as ctx:
                    preview(client, IP, "global", None)
                self.assertEqual(ctx.exception.status, 502)

    def test_unchecked_instance_with_local_only_lease_gives_502_despite_a_redis_negative(self):
        client = FakeClient(hosts=("i1", "i2"), lookups={"i2": NOT_FOUND})
        client.instances[0]["status"] = "down"  # i1 may hold a lease that never reached Redis
        with self.assertRaises(CrowdSecError) as ctx:
            find_lease(client, IP, "global", None)
        self.assertEqual(ctx.exception.status, 502)
        self.assertEqual(client.kinds(), ["lease_lookup"])  # the down instance is never called

    def test_missing_lease_is_404(self):
        client = FakeClient(lookups={"i1": NOT_FOUND})
        with self.assertRaises(CrowdSecError) as ctx:
            preview(client, IP, "global", None)
        self.assertEqual(ctx.exception.status, 404)

    def test_two_source_matches_refuse(self):
        a, b = conn("i1", "L", node="shared"), conn("i2", "L", node="shared")
        with self.assertRaises(CrowdSecError) as ctx:
            preview(simple([a, b], hosts=("i1", "i2")), IP, "global", None)
        self.assertEqual(ctx.exception.status, 409)

    def test_read_only_connection_without_decisions_does_not_block(self):
        source = conn("i1", "A")
        read_only = conn("i1", "R", management=False)
        client = simple([source, read_only], {source["id"]: [decision(1)], read_only["id"]: []})
        checked = revalidate(client, IP, "global", None, [f"{source['id']}:1"])
        self.assertEqual(checked["status"], "ready")
        client.decisions[read_only["id"]] = [decision(2)]
        with self.assertRaises(CrowdSecError) as ctx:
            revalidate(client, IP, "global", None, [f"{source['id']}:1", f"{read_only['id']}:2"])
        self.assertEqual(ctx.exception.status, 409)

    def test_down_instance_makes_result_partial(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: []}, hosts=("i1", "i2"))
        client.instances[1]["status"] = "down"
        result = execute(client, IP, "global", None, [])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["down"], ["i2"])
        self.assertEqual(result["lease_removed"], ["i1"])

    def test_postcondition_query_error_is_partial_and_keeps_lease(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: [decision(1)]})
        client.post_write_errors[source["id"]] = CrowdSecError("lapi down")
        result = execute(client, IP, "global", None, [f"{source['id']}:1"])
        self.assertEqual(result["status"], "partial")
        self.assertIn("postcondition check failed", result["failed"][0]["error"])
        self.assertNotIn("remove_lease", client.kinds())

    def test_execute_changed_selection_returns_changed_and_changes_nothing(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: [decision(1), decision(2)]})
        result = execute(client, IP, "global", None, [f"{source['id']}:1"])
        self.assertEqual(result["status"], "changed")
        self.assertEqual(len(result["preview"]["decisions"]), 2)
        self.assertEqual(client.writes(), [])

    def test_execute_partial_delete_keeps_lease(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: [decision(1), decision(2)]})
        client.query_errors[(source["id"], "unban")] = CrowdSecError("denied", 403)
        result = execute(client, IP, "global", None, [f"{source['id']}:1", f"{source['id']}:2"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["failed"]), 2)
        self.assertNotIn("remove_lease", client.kinds())  # no remove_lease call made
        self.assertNotIn("refresh_ip", client.kinds())

    def test_execute_already_absent_counts_as_success(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: [decision(1)]})
        current = preview(client, IP, "global", None)
        client.decisions[source["id"]] = []  # deleted by someone else after the preview
        result = apply(client, IP, "global", None, current)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["already_absent"], [f"{source['id']}:1"])
        self.assertEqual(result["deleted"], [])

    def test_execute_postcondition_failure_is_partial(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: [decision(1)]})
        client.sticky.add(source["id"])
        result = execute(client, IP, "global", None, [f"{source['id']}:1"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["failed"], [{"connection_id": source["id"], "error": "a CrowdSec ban decision is still active"}])
        self.assertNotIn("remove_lease", client.kinds())

    def test_execute_success_refreshes_then_removes_lease_on_every_up_instance(self):
        a, b = conn("i1", "A"), conn("i2", "B")
        client = simple([a, b], {a["id"]: [decision(1)], b["id"]: [decision(2)]}, hosts=("i1", "i2"))
        result = execute(client, IP, "global", None, [f"{a['id']}:1", f"{b['id']}:2"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(sorted(result["deleted"]), [f"{a['id']}:1", f"{b['id']}:2"])
        self.assertEqual(sorted(result["refreshed"]), sorted([a["id"], b["id"]]))
        self.assertEqual(result["lease_removed"], ["i1", "i2"])
        first_write = next(index for index, kind in enumerate(client.kinds()) if kind == "unban")
        order = []
        for kind in client.kinds()[first_write:]:
            if not order or order[-1] != kind:
                order.append(kind)
        self.assertEqual(order, ["unban", "refresh_ip", "decisions", "remove_lease"])
        removals = [call for call in client.calls if call[0] == "remove_lease"]
        self.assertEqual([call[2] for call in removals], [{"ip": IP, "ban_scope": "global"}] * 2)

    def test_down_instances_are_listed_not_called(self):
        source = conn("i1", "A")
        client = simple([source], {source["id"]: []}, hosts=("i1", "i2", "i3"))
        client.instances[2]["status"] = "down"
        client.remove_errors["i2"] = CrowdSecError("503")
        result = execute(client, IP, "global", None, [])
        self.assertEqual(result["down"], ["i3"])
        self.assertEqual(result["lease_failed"], [{"instance": "i2", "error": "503"}])
        self.assertEqual([call[1] for call in client.calls if call[0] == "remove_lease"], ["i1", "i2"])
        self.assertEqual(result["status"], "partial")


if __name__ == "__main__":
    main()

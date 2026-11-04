"""Gateway API status helpers: conditions keep their transition time unless the status flips, and only owned parents are written."""

from controllers.GatewayController import (
    GATEWAY_API_GROUP,
    build_class_conditions,
    build_gateway_status,
    build_route_parents,
    count_attached_routes,
    merge_conditions,
    normalize_parent_ref,
    utc_now,
)

T0, T1 = "2026-01-01T00:00:00Z", "2026-02-02T00:00:00Z"
CONTROLLER = "bunkerweb.io/gateway-controller"


def by_type(conditions):
    return {c["type"]: c for c in conditions}


def test_utc_now_is_an_rfc3339_second_precision_stamp():
    stamp = utc_now()

    assert len(stamp) == 20 and stamp.endswith("Z") and stamp[10] == "T"


def test_new_condition_takes_the_current_time_and_generation():
    [cond] = merge_conditions(None, [("Accepted", True, "Accepted", "ok")], 4, T1)

    assert cond == {"type": "Accepted", "status": "True", "reason": "Accepted", "message": "ok", "lastTransitionTime": T1, "observedGeneration": 4}


def test_unchanged_status_keeps_its_transition_time_but_updates_the_text():
    existing = [{"type": "Accepted", "status": "True", "reason": "Old", "message": "old", "lastTransitionTime": T0}]

    [cond] = merge_conditions(existing, [("Accepted", True, "New", "new")], 5, T1)

    assert cond["lastTransitionTime"] == T0
    assert (cond["reason"], cond["message"]) == ("New", "new")


def test_flipped_status_moves_the_transition_time():
    existing = [{"type": "Programmed", "status": "False", "lastTransitionTime": T0}]

    [cond] = merge_conditions(existing, [("Programmed", True, "Programmed", "ok")], None, T1)

    assert cond["status"] == "True" and cond["lastTransitionTime"] == T1
    assert "observedGeneration" not in cond


def test_conditions_of_other_controllers_survive_and_everything_is_sorted():
    existing = [{"type": "Zeta", "status": "True"}, "junk", {"type": "Alpha", "status": "True"}]

    merged = merge_conditions(existing, [("Mine", False, "Pending", "wait")], 1, T1)

    assert [c["type"] for c in merged] == ["Alpha", "Mine", "Zeta"]
    assert by_type(merged)["Mine"]["status"] == "False"


def test_status_without_a_stored_transition_time_gets_now():
    existing = [{"type": "Accepted", "status": "True"}]

    [cond] = merge_conditions(existing, [("Accepted", True, "Accepted", "ok")], 1, T1)

    assert cond["lastTransitionTime"] == T1


def test_class_conditions_are_accepted():
    conditions = build_class_conditions({"metadata": {"generation": 3}, "status": {"conditions": [{"type": "Other", "status": "True"}]}}, T1)

    assert by_type(conditions)["Accepted"]["status"] == "True"
    assert by_type(conditions)["Accepted"]["observedGeneration"] == 3
    assert "Other" in by_type(conditions)


def test_gateway_parent_refs_get_their_defaults():
    ref = normalize_parent_ref({"name": "gw", "sectionName": "http", "port": 80}, "prod")

    assert ref == {"group": GATEWAY_API_GROUP, "kind": "Gateway", "namespace": "prod", "name": "gw", "sectionName": "http", "port": 80}
    assert normalize_parent_ref({"name": "gw", "namespace": "infra"}, "prod")["namespace"] == "infra"


def test_foreign_or_malformed_parent_refs_are_rejected():
    assert normalize_parent_ref("gw", "prod") is None
    assert normalize_parent_ref({}, "prod") is None
    assert normalize_parent_ref({"name": "svc", "kind": "Service"}, "prod") is None
    assert normalize_parent_ref({"name": "gw", "group": "other.io"}, "prod") is None
    assert normalize_parent_ref({"name": "gw"}, None) is None


def gateway(name="gw", namespace="prod", listeners=None, status=None, generation=2):
    listeners = listeners if listeners is not None else [{"name": "http", "port": 80, "protocol": "HTTP"}, {"name": "tls", "port": 443, "protocol": "TLS"}]
    return {
        "metadata": {"name": name, "namespace": namespace, "generation": generation},
        "spec": {"gatewayClassName": "bw", "listeners": listeners},
        "status": status or {},
    }


def route(name="r", namespace="prod", parents=None, status=None, backends=None, generation=1):
    rules = [{"backendRefs": backends}] if backends is not None else []
    spec = {"parentRefs": parents if parents is not None else [{"name": "gw"}], "rules": rules}
    return {"kind": "HTTPRoute", "metadata": {"name": name, "namespace": namespace, "generation": generation}, "spec": spec, "status": status or {}}


def test_attached_routes_are_counted_per_listener():
    routes = [
        route("all"),
        route("section", parents=[{"name": "gw", "sectionName": "http"}]),
        route("port", parents=[{"name": "gw", "port": 443}]),
        route("twice", parents=[{"name": "gw", "sectionName": "http"}, {"name": "gw", "port": 80}]),
        route("elsewhere", parents=[{"name": "other"}]),
        route("other-ns", namespace="dev"),
    ]

    assert count_attached_routes(gateway(), routes) == {"http": 3, "tls": 2}


def test_gateway_status_when_applied_reports_programmed_listeners():
    status = build_gateway_status(gateway(), [route()], True, T1)

    gw = by_type(status["conditions"])
    assert gw["Accepted"]["status"] == "True" and gw["Programmed"]["status"] == "True"
    http, tls = status["listeners"]
    assert http["name"] == "http" and http["attachedRoutes"] == 1
    assert http["supportedKinds"] == [{"group": GATEWAY_API_GROUP, "kind": "HTTPRoute"}, {"group": GATEWAY_API_GROUP, "kind": "GRPCRoute"}]
    assert tls["supportedKinds"] == [{"group": GATEWAY_API_GROUP, "kind": "TLSRoute"}]
    assert {c["type"] for c in http["conditions"]} == {"Accepted", "Programmed", "ResolvedRefs"}


def test_gateway_status_when_not_applied_is_pending_and_keeps_old_listener_conditions():
    previous = {"listeners": [{"name": "http", "conditions": [{"type": "Programmed", "status": "True", "lastTransitionTime": T0}]}]}

    status = build_gateway_status(gateway(status=previous), [], False, T1)

    programmed = by_type(status["conditions"])["Programmed"]
    assert (programmed["status"], programmed["reason"]) == ("False", "Pending")
    assert by_type(status["listeners"][0]["conditions"])["Programmed"]["lastTransitionTime"] == T1


def test_unknown_listener_protocols_support_no_kinds():
    status = build_gateway_status(gateway(listeners=[{"name": "x", "protocol": "weird"}, {"name": "u", "protocol": "udp"}]), [], True, T1)

    assert status["listeners"][0]["supportedKinds"] == []
    assert status["listeners"][1]["supportedKinds"] == [{"group": GATEWAY_API_GROUP, "kind": "UDPRoute"}]


OWNED = {("prod", "gw"): gateway()}


def test_route_for_an_unowned_gateway_gets_no_status():
    assert build_route_parents(route(parents=[{"name": "stranger"}]), OWNED, CONTROLLER, T1) is None
    assert build_route_parents(route(parents=[{"name": "gw", "kind": "Service"}]), OWNED, CONTROLLER, T1) is None
    assert build_route_parents(route(parents=[]), OWNED, CONTROLLER, T1) is None


def test_route_is_accepted_and_resolved_by_default():
    [parent] = build_route_parents(route(backends=[{"name": "svc", "port": 80}]), OWNED, CONTROLLER, T1)

    assert parent["controllerName"] == CONTROLLER
    assert parent["parentRef"]["name"] == "gw"
    conds = by_type(parent["conditions"])
    assert conds["Accepted"]["status"] == "True" and conds["ResolvedRefs"]["status"] == "True"
    assert conds["Accepted"]["observedGeneration"] == 1


def test_unknown_listener_section_is_not_accepted():
    [parent] = build_route_parents(route(parents=[{"name": "gw", "sectionName": "nope"}]), OWNED, CONTROLLER, T1)

    accepted = by_type(parent["conditions"])["Accepted"]
    assert (accepted["status"], accepted["reason"]) == ("False", "NoMatchingParent")


def test_unsupported_backend_kind_is_unresolved():
    [parent] = build_route_parents(route(backends=[{"name": "b", "kind": "StorageBucket"}]), OWNED, CONTROLLER, T1)

    resolved = by_type(parent["conditions"])["ResolvedRefs"]
    assert (resolved["status"], resolved["reason"]) == ("False", "InvalidKind")
    assert "StorageBucket" in resolved["message"]


def test_other_controllers_entries_are_kept_in_place_and_ours_updated():
    theirs = {"controllerName": "other.io/c", "parentRef": {"name": "gw"}, "conditions": [{"type": "Accepted", "status": "True"}]}
    stale = {
        "controllerName": CONTROLLER,
        "parentRef": {"group": GATEWAY_API_GROUP, "kind": "Gateway", "namespace": "prod", "name": "gw"},
        "conditions": [{"type": "Accepted", "status": "True", "lastTransitionTime": T0}],
    }
    gone = {"controllerName": CONTROLLER, "parentRef": {"name": "removed"}, "conditions": []}

    parents = build_route_parents(route(status={"parents": [theirs, "junk", stale, gone]}), OWNED, CONTROLLER, T1)

    assert parents[0] == theirs
    assert len(parents) == 2
    assert by_type(parents[1]["conditions"])["Accepted"]["lastTransitionTime"] == T0


def test_a_new_parent_ref_is_appended_and_duplicates_collapse():
    owned = {("prod", "gw"): gateway(), ("prod", "gw2"): gateway("gw2")}

    parents = build_route_parents(route(parents=[{"name": "gw"}, {"name": "gw"}, {"name": "gw2"}]), owned, CONTROLLER, T1)

    assert [p["parentRef"]["name"] for p in parents] == ["gw", "gw2"]

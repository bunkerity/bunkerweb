"""Gateway conditions follow what was actually matched, not what was asked for."""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _port_helpers import GATEWAY  # noqa: E402

OWNER = "bunkerweb.io/gateway-controller"
NOW = "2026-11-13T10:00:00Z"


def _gateway(*listeners):
    return {"metadata": {"namespace": "edge", "name": "gw", "generation": 1}, "spec": {"gatewayClassName": "ours", "listeners": list(listeners)}}


HTTP = {"name": "http", "protocol": "HTTP", "port": 80}
TCP = {"name": "tcp", "protocol": "TCP", "port": 9000}


def _route(parent_ref, kind="HTTPRoute", backends=()):
    return {
        "kind": kind,
        "metadata": {"name": "r", "namespace": "edge", "generation": 1},
        "spec": {"parentRefs": [parent_ref], "rules": [{"backendRefs": list(backends)}] if backends else []},
    }


def _parent_conditions(route, gateway, missing=None):
    parents = GATEWAY.build_route_parents(route, {("edge", "gw"): gateway}, OWNER, NOW, missing or set())
    return {c["type"]: (c["status"], c["reason"]) for c in parents[0]["conditions"]}


def test_a_parent_port_no_listener_serves_is_not_accepted():
    conditions = _parent_conditions(_route({"name": "gw", "port": 9999}), _gateway(HTTP))
    assert conditions["Accepted"] == ("False", "NoMatchingParent")


def test_a_parent_port_a_listener_serves_is_accepted():
    assert _parent_conditions(_route({"name": "gw", "port": 80}), _gateway(HTTP))["Accepted"] == ("True", "Accepted")


def test_a_section_and_port_that_name_different_listeners_are_not_accepted():
    conditions = _parent_conditions(_route({"name": "gw", "sectionName": "http", "port": 9000}), _gateway(HTTP, TCP))
    assert conditions["Accepted"] == ("False", "NoMatchingParent")


def test_a_route_kind_no_matched_listener_carries_is_not_accepted():
    conditions = _parent_conditions(_route({"name": "gw"}, kind="HTTPRoute"), _gateway(TCP))
    assert conditions["Accepted"] == ("False", "NotAllowedByListeners")


def test_a_backend_service_that_does_not_exist_is_not_resolved():
    route = _route({"name": "gw"}, backends=[{"name": "gone", "port": 80}])
    conditions = _parent_conditions(route, _gateway(HTTP), missing={("edge", "gone")})
    assert conditions["ResolvedRefs"] == ("False", "BackendNotFound")


def test_a_backend_service_in_another_namespace_is_looked_up_there():
    route = _route({"name": "gw"}, backends=[{"name": "svc", "namespace": "other", "port": 80}])
    assert _parent_conditions(route, _gateway(HTTP), missing={("edge", "svc")})["ResolvedRefs"] == ("True", "ResolvedRefs")
    assert _parent_conditions(route, _gateway(HTTP), missing={("other", "svc")})["ResolvedRefs"] == ("False", "BackendNotFound")


def test_an_unsupported_backend_kind_keeps_its_reason():
    route = _route({"name": "gw"}, backends=[{"name": "x", "kind": "Other", "port": 80}])
    assert _parent_conditions(route, _gateway(HTTP))["ResolvedRefs"] == ("False", "InvalidKind")


def test_an_unsectioned_http_route_is_not_counted_on_a_tcp_only_listener():
    gateway = _gateway(TCP, HTTP)
    counts = GATEWAY.count_attached_routes(gateway, [_route({"name": "gw"}, kind="HTTPRoute")])
    assert counts == {"tcp": 0, "http": 1}


def test_a_tcp_route_is_counted_on_its_tcp_listener_only():
    counts = GATEWAY.count_attached_routes(_gateway(TCP, HTTP), [_route({"name": "gw"}, kind="TCPRoute")])
    assert counts == {"tcp": 1, "http": 0}


def test_missing_backends_are_the_services_the_cluster_does_not_list():
    controller = object.__new__(GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._corev1 = Mock()
    present = Mock()
    present.metadata.namespace, present.metadata.name = "edge", "here"
    controller._corev1.list_service_for_all_namespaces.return_value.items = [present]
    routes = [_route({"name": "gw"}, backends=[{"name": "here", "port": 80}, {"name": "gone", "port": 80}])]
    assert controller._missing_backends(routes) == {("edge", "gone")}


def test_a_failed_service_listing_is_unknown_and_logged_above_debug():
    controller = object.__new__(GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._corev1 = Mock()
    controller._corev1.list_service_for_all_namespaces.side_effect = RuntimeError("boom")
    assert controller._missing_backends([_route({"name": "gw"}, backends=[{"name": "x", "port": 80}])]) is None
    controller._logger.warning.assert_called_once()


def test_no_service_backend_needs_no_listing():
    controller = object.__new__(GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._corev1 = Mock()
    assert controller._missing_backends([_route({"name": "gw"})]) == set()
    controller._corev1.list_service_for_all_namespaces.assert_not_called()


def _stored_parent(route, conditions):
    route["status"] = {"parents": [{"parentRef": {"name": "gw"}, "controllerName": OWNER, "conditions": conditions}]}
    return route


def _parents_when_lookup_failed(route, gateway):
    """The status.parents list built when the Service listing failed (missing_backends is None)."""
    return GATEWAY.build_route_parents(route, {("edge", "gw"): gateway}, OWNER, NOW, None)


def test_a_failed_listing_keeps_the_resolved_refs_condition_the_route_carries():
    previous = {
        "type": "ResolvedRefs",
        "status": "False",
        "reason": "BackendNotFound",
        "message": "Service gone does not exist",
        "lastTransitionTime": "2026-11-12T08:00:00Z",
        "observedGeneration": 1,
    }
    route = _stored_parent(_route({"name": "gw"}, backends=[{"name": "gone", "port": 80}]), [previous])
    route["metadata"]["generation"] = 2
    conditions = {c["type"]: c for c in _parents_when_lookup_failed(route, _gateway(HTTP))[0]["conditions"]}
    assert conditions["ResolvedRefs"] == previous
    assert conditions["Accepted"]["status"] == "True"


def test_a_failed_listing_publishes_unknown_when_the_route_carries_no_resolved_refs():
    route = _route({"name": "gw"}, backends=[{"name": "x", "port": 80}])
    conditions = {c["type"]: c for c in _parents_when_lookup_failed(route, _gateway(HTTP))[0]["conditions"]}
    assert conditions["ResolvedRefs"]["status"] == "Unknown"
    assert conditions["ResolvedRefs"]["reason"] == "BackendsUnchecked"
    assert conditions["ResolvedRefs"]["lastTransitionTime"] == NOW
    assert "could not be checked" in conditions["ResolvedRefs"]["message"]


def test_a_failed_listing_still_computes_accepted():
    route = _route({"name": "gw", "port": 9999}, backends=[{"name": "x", "port": 80}])
    conditions = {c["type"]: c for c in _parents_when_lookup_failed(route, _gateway(HTTP))[0]["conditions"]}
    assert (conditions["Accepted"]["status"], conditions["Accepted"]["reason"]) == ("False", "NoMatchingParent")


def test_a_failed_listing_does_not_override_invalid_kind():
    route = _stored_parent(
        _route({"name": "gw"}, backends=[{"name": "x", "kind": "Other", "port": 80}]),
        [{"type": "ResolvedRefs", "status": "True", "reason": "ResolvedRefs", "message": "References resolved", "lastTransitionTime": "2026-11-12T08:00:00Z"}],
    )
    conditions = {c["type"]: c for c in _parents_when_lookup_failed(route, _gateway(HTTP))[0]["conditions"]}
    assert (conditions["ResolvedRefs"]["status"], conditions["ResolvedRefs"]["reason"]) == ("False", "InvalidKind")


def test_a_failed_listing_leaves_a_route_without_service_backends_resolved():
    conditions = {c["type"]: c for c in _parents_when_lookup_failed(_route({"name": "gw"}), _gateway(HTTP))[0]["conditions"]}
    assert conditions["ResolvedRefs"]["status"] == "True"

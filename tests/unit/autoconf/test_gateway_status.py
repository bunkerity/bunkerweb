"""Gateway readiness must be published without changing foreign resources or looping on echoes."""

from copy import deepcopy
from threading import Event, get_ident
from unittest.mock import Mock

import pytest

from _port_helpers import GATEWAY

GROUP = "gateway.networking.k8s.io"
OWNER = "bunkerweb.io/gateway-controller"


class GatewayApi:
    def __init__(self):
        self.objects = {
            "gatewayclasses": [
                {"metadata": {"name": name, "generation": 2, "resourceVersion": "1"}, "spec": {"controllerName": owner}}
                for name, owner in (("ours", OWNER), ("foreign", "example.com/other"))
            ],
            "gateways": [
                {
                    "kind": "Gateway",
                    "metadata": {"name": name, "namespace": "edge", "generation": 3, "resourceVersion": "1"},
                    "spec": {"gatewayClassName": name, "listeners": [{"name": "http", "protocol": "HTTP", "port": 80}]},
                }
                for name in ("ours", "foreign")
            ],
            "httproutes": [
                {
                    "kind": "HTTPRoute",
                    "metadata": {"name": "route", "namespace": "edge", "generation": 4, "resourceVersion": "1"},
                    "spec": {"parentRefs": [{"name": "ours", "sectionName": "http"}, {"name": "foreign"}], "rules": []},
                    "status": {"parents": [{"parentRef": {"name": "foreign"}, "controllerName": "example.com/other", "conditions": []}]},
                }
            ],
        }
        self.writes = []
        self.deny_classes = False
        self.deny_patches = False

    def list_cluster_custom_object(self, group, version, plural, **kwargs):
        if plural == "gatewayclasses" and self.deny_classes:
            raise GATEWAY.ApiException(status=403, reason="Forbidden")
        return {"items": deepcopy(self.objects.get(plural, []))}

    def get_namespaced_custom_object(self, group, version, namespace, plural, name, **kwargs):
        return deepcopy(next(obj for obj in self.objects[plural] if obj["metadata"]["name"] == name))

    def patch_cluster_custom_object_status(self, group, version, plural, name, body, **kwargs):
        return self.patch_namespaced_custom_object_status(group, version, None, plural, name, body, **kwargs)

    def patch_namespaced_custom_object_status(self, group, version, namespace, plural, name, body, **kwargs):
        if self.deny_patches:
            raise GATEWAY.ApiException(status=403, reason="Forbidden")
        obj = next(obj for obj in self.objects[plural] if obj["metadata"]["name"] == name)
        if body.get("metadata", {}).get("resourceVersion", obj["metadata"]["resourceVersion"]) != obj["metadata"]["resourceVersion"]:
            raise GATEWAY.ApiException(status=409, reason="Conflict")
        self.writes.append((plural, namespace, name, deepcopy(body)))
        obj.setdefault("status", {}).update(deepcopy(body["status"]))
        obj["metadata"]["resourceVersion"] = str(int(obj["metadata"]["resourceVersion"]) + 1)
        return deepcopy(obj)


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setenv("KUBERNETES_SKIP_FOREIGN_CLASSES", "yes")
    monkeypatch.setenv("KUBERNETES_GATEWAY_CONTROLLER", OWNER)
    monkeypatch.delenv("KUBERNETES_GATEWAY_CLASS", raising=False)
    monkeypatch.delenv("NAMESPACES", raising=False)
    api = GatewayApi()
    monkeypatch.setattr(GATEWAY.client, "CustomObjectsApi", lambda **kwargs: api)
    controller = GATEWAY.GatewayController(api_client=Mock())
    controller._logger = Mock()
    controller._get_loadbalancer_ip = Mock(return_value=["2001:db8::1"])
    controller._get_controller_services()
    return controller, api


def reconcile(controller, applied=True):
    assert hasattr(controller, "_reconcile_status"), "Gateway conditions and route parents are never published"
    controller._reconcile_status(applied, controller._gateways_cache.copy(), controller._routes_cache.copy())


def conditions(obj):
    return {condition["type"]: condition for condition in obj["status"]["conditions"]}


def test_publishes_owned_class_gateway_listeners_and_route_parents(gateway):
    controller, api = gateway
    foreign_before = deepcopy(api.objects["gateways"][1])
    foreign_parent = deepcopy(api.objects["httproutes"][0]["status"]["parents"][0])
    reconcile(controller)
    cls, gw, route = api.objects["gatewayclasses"][0], api.objects["gateways"][0], api.objects["httproutes"][0]
    assert conditions(cls)["Accepted"]["status"] == "True"
    assert conditions(cls)["Accepted"]["observedGeneration"] == 2
    assert conditions(gw)["Programmed"]["status"] == "True"
    assert conditions(gw)["Programmed"]["observedGeneration"] == 3
    assert gw["status"]["addresses"] == [{"type": "IPAddress", "value": "2001:db8::1"}]
    assert gw["status"]["listeners"][0]["attachedRoutes"] == 1
    assert gw["status"]["listeners"][0]["supportedKinds"] == [{"group": GROUP, "kind": "HTTPRoute"}, {"group": GROUP, "kind": "GRPCRoute"}]
    assert api.objects["gateways"][1] == foreign_before
    assert "status" not in api.objects["gatewayclasses"][1]
    assert route["status"]["parents"][0] == foreign_parent
    ours = route["status"]["parents"][1]
    assert ours["controllerName"] == OWNER
    assert ours["parentRef"]["namespace"] == "edge"
    assert {c["type"]: c["status"] for c in ours["conditions"]} == {"Accepted": "True", "ResolvedRefs": "True"}


def test_status_is_idempotent_and_transition_time_survives_generation_change(gateway, monkeypatch):
    controller, api = gateway
    monkeypatch.setattr(GATEWAY, "utc_now", lambda: "2026-11-05T10:00:00Z", raising=False)
    reconcile(controller)
    writes = len(api.writes)
    controller._get_controller_services()
    monkeypatch.setattr(GATEWAY, "utc_now", lambda: "2026-11-05T11:00:00Z")
    reconcile(controller)
    assert len(api.writes) == writes
    api.objects["gateways"][0]["metadata"]["generation"] += 1
    controller._get_controller_services()
    reconcile(controller)
    assert conditions(api.objects["gateways"][0])["Programmed"]["lastTransitionTime"] == "2026-11-05T10:00:00Z"
    reconcile(controller, applied=False)
    assert conditions(api.objects["gateways"][0])["Programmed"]["status"] == "False"
    assert conditions(api.objects["gateways"][0])["Programmed"]["lastTransitionTime"] == "2026-11-05T11:00:00Z"


@pytest.mark.parametrize("change", ["namespace", "annotation", "class"])
def test_stale_gateway_snapshot_cannot_publish_after_scope_transfer(gateway, change):
    controller, api = gateway
    gw = api.objects["gateways"][0]
    if change == "namespace":
        controller._namespaces = ["another"]
    elif change == "annotation":
        controller._should_ignore_annotation = lambda annotation: annotation == "ignore"
        gw["metadata"]["annotations"] = {"ignore": "yes"}
    else:
        gw["spec"]["gatewayClassName"] = "foreign"
    reconcile(controller)
    assert not any(plural in ("gateways", "httproutes") for plural, *_ in api.writes)


def test_address_publication_does_not_touch_foreign_class_even_when_selected(gateway):
    controller, api = gateway
    controller._gateway_class = "foreign"
    controller._patch_controller_status(["192.0.2.1"])
    assert api.writes == []


def test_forbidden_status_writes_warn_without_breaking_reconciliation(gateway):
    controller, api = gateway
    api.deny_patches = True
    reconcile(controller)
    warnings = controller._logger.warning.call_count
    reconcile(controller)
    assert warnings > 0
    assert controller._logger.warning.call_count == warnings
    assert api.writes == []


def test_conflict_refresh_preserves_other_controllers_parent_entries(gateway):
    controller, api = gateway
    stale = deepcopy(api.objects["httproutes"][0])
    fresh = api.objects["httproutes"][0]
    fresh["metadata"]["resourceVersion"] = "2"
    foreign = {"parentRef": {"name": "another"}, "controllerName": "example.com/third", "conditions": []}
    fresh["status"]["parents"].append(deepcopy(foreign))
    assert hasattr(controller, "_reconcile_route_status")
    controller._reconcile_route_status(stale, controller._gateways_cache)
    assert foreign in fresh["status"]["parents"]
    assert len([entry for entry in fresh["status"]["parents"] if entry["controllerName"] == OWNER]) == 1


def test_status_echo_is_ignored_but_spec_annotation_and_deletion_reconcile(gateway):
    controller, api = gateway
    controller._first_start = False
    event = {"type": "MODIFIED", "object": deepcopy(api.objects["gateways"][0])}
    assert controller._process_event(event)
    event["object"]["status"] = {"conditions": []}
    event["object"]["metadata"]["resourceVersion"] = "2"
    assert controller._process_event(event) is False
    event["object"]["metadata"]["generation"] = 4
    assert controller._process_event(event)
    event["object"]["metadata"]["annotations"] = {"bunkerweb.io/USE_REVERSE_PROXY": "yes"}
    assert controller._process_event(event)
    event["type"] = "DELETED"
    assert controller._process_event(event)


def test_status_worker_never_holds_configuration_lock(gateway):
    controller, _ = gateway
    started, finish = Event(), Event()
    lock_free = []
    worker_ids = []

    def reconcile_outside_lock(*args):
        worker_ids.append(get_ident())
        acquired = controller._internal_lock.acquire(blocking=False)
        lock_free.append(acquired)
        if acquired:
            controller._internal_lock.release()
        started.set()
        finish.wait(timeout=2)

    controller._reconcile_status = reconcile_outside_lock
    assert hasattr(controller, "_sync_status"), "status writes still run synchronously under the apply lock"
    controller._sync_status(True)
    try:
        assert started.wait(timeout=2)
        assert lock_free == [True]
        assert worker_ids != [get_ident()]
        with controller._internal_lock:
            pass
    finally:
        finish.set()


@pytest.mark.parametrize("applied", [True, False])
def test_apply_outcome_reaches_status_worker(gateway, applied):
    controller, _ = gateway
    controller._loaded = True
    controller._instances, controller._services, controller._configs, controller._extra_config = [], [], {}, {}
    controller.apply = Mock(return_value=applied)
    published = Event()
    outcomes = []

    def receive(outcome, gateways, routes):
        outcomes.append(outcome)
        published.set()

    controller._reconcile_status = receive
    with controller._internal_lock:
        assert controller.apply_config() is applied
    assert published.wait(timeout=2)
    assert outcomes == [applied]


def test_conditions_are_published_before_loadbalancer_has_an_address(gateway):
    controller, api = gateway
    controller._get_loadbalancer_ip.return_value = None
    reconcile(controller)
    assert conditions(api.objects["gateways"][0])["Programmed"]["status"] == "True"
    assert "addresses" not in api.objects["gateways"][0]["status"]

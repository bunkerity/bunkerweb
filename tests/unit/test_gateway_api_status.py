#!/usr/bin/env python3

from copy import deepcopy
from os import getenv
from pathlib import Path
from sys import path as sys_path
from threading import Event, Lock
from unittest import TestCase, main
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
for rel in (getenv("AUTOCONF_SRC", "src/autoconf"), "src/common/db", "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(rel if rel.startswith("/") else ROOT / rel))

from kubernetes.client.exceptions import ApiException

from controllers.GatewayController import GatewayController

OURS = "bunkerweb.io/gateway-controller"
GROUP = "gateway.networking.k8s.io"


def gateway_class(name, controller):
    return {"metadata": {"name": name, "generation": 1}, "spec": {"controllerName": controller}}


def gateway(name, class_name, namespace="demo", listeners=None):
    return {
        "kind": "Gateway",
        "metadata": {"namespace": namespace, "name": name, "generation": 2, "uid": f"gw-{name}"},
        "spec": {
            "gatewayClassName": class_name,
            "listeners": listeners or [{"name": "http", "port": 80, "protocol": "HTTP"}, {"name": "tls", "port": 443, "protocol": "TLS"}],
        },
    }


def route(name, parents, kind="HTTPRoute", namespace="demo", status=None, backend_kind=None):
    backend = {"name": "svc", "port": 80}
    if backend_kind:
        backend["kind"] = backend_kind
    return {
        "kind": kind,
        "metadata": {"namespace": namespace, "name": name, "generation": 3, "resourceVersion": "10", "uid": f"rt-{name}"},
        "spec": {"parentRefs": parents, "rules": [{"backendRefs": [backend]}]},
        "status": status or {"parents": []},
    }


class FakeApi:
    """Records status patches and keeps them, so a second pass sees what the first one wrote."""

    def __init__(self, classes, conflict_once=False, fail_status=None):
        self.classes = classes
        self.patches = []
        self.conflict_once = conflict_once
        self.fail_status = fail_status
        self.fresh = {}

    def list_cluster_custom_object(self, group, version, plural, **kwargs):
        return {"items": deepcopy(self.classes) if plural == "gatewayclasses" else []}

    def _record(self, plural, namespace, name, body):
        if self.fail_status is not None:
            raise ApiException(status=self.fail_status, reason="Forbidden")
        if self.conflict_once and plural in ("httproutes",):
            self.conflict_once = False
            raise ApiException(status=409, reason="Conflict")
        self.patches.append((plural, namespace, name, deepcopy(body)))

    def patch_cluster_custom_object_status(self, group, version, plural, name, body, **kwargs):
        self._record(plural, None, name, body)

    def patch_namespaced_custom_object_status(self, group, version, namespace, plural, name, body, **kwargs):
        self._record(plural, namespace, name, body)

    def get_namespaced_custom_object(self, group, version, namespace, plural, name, **kwargs):
        return deepcopy(self.fresh[(plural, namespace, name)])


def new_controller(api, gateway_class_filter=""):
    ctrl = GatewayController.__new__(GatewayController)
    ctrl._custom_objects = api
    ctrl._logger = MagicMock()
    ctrl._gateway_class = gateway_class_filter
    ctrl._gateway_controller = OURS
    ctrl._gateway_api_available = True
    ctrl._gateway_api_group = GROUP
    ctrl._gateway_api_version = "v1"
    ctrl._status_enabled = True
    ctrl._resource_versions = {"gateways": "v1", "gatewayclasses": "v1", "httproutes": "v1", "tlsroutes": "v1"}
    ctrl._gateways_cache = {}
    ctrl._routes_cache = []
    ctrl._seen_specs = {}
    ctrl._status_lock = Lock()
    ctrl._status_wakeup = Event()
    ctrl._status_snapshot = None
    ctrl._status_thread = None
    ctrl._status_warned = set()
    return ctrl


def parent(name="gw", namespace=None, section=None):
    ref = {"name": name}
    if namespace:
        ref["namespace"] = namespace
    if section:
        ref["sectionName"] = section
    return ref


def event(kind, name, generation, annotations=None, event_type="MODIFIED"):
    metadata = {"name": name, "namespace": "demo", "uid": f"{kind}-{name}", "generation": generation}
    if annotations:
        metadata["annotations"] = annotations
    return {"type": event_type, "object": {"kind": kind, "metadata": metadata}}


def apply_patches(api, objects):
    """Mimic the API server: merge each recorded status patch into the stored objects."""
    for plural, namespace, name, body in api.patches:
        for obj in objects:
            metadata = obj["metadata"]
            if metadata["name"] == name and metadata.get("namespace") == namespace:
                obj.setdefault("status", {}).update(body["status"])
    api.patches.clear()


class GatewayStatusTest(TestCase):
    def setUp(self):
        self.ours = gateway_class("bunkerweb", OURS)
        self.foreign = gateway_class("istio", "istio.io/gateway-controller")
        self.api = FakeApi([self.ours, self.foreign])
        self.ctrl = new_controller(self.api)
        self.gw = gateway("gw", "bunkerweb")
        self.foreign_gw = gateway("fgw", "istio")
        self.rt = route("web", [parent("gw")])
        self.foreign_rt = route("fweb", [parent("fgw")])
        self.gateways = {("demo", "gw"): self.gw, ("demo", "fgw"): self.foreign_gw}
        self.routes = [self.rt, self.foreign_rt]

    def reconcile(self, applied=True):
        self.ctrl._reconcile_status(applied, self.gateways, self.routes)

    def patched(self):
        return {(plural, name) for plural, _, name, _ in self.api.patches}

    def test_own_class_gets_status_and_foreign_class_nothing(self):
        self.reconcile()

        self.assertEqual(self.patched(), {("gatewayclasses", "bunkerweb"), ("gateways", "gw"), ("httproutes", "web")})
        body = next(body for plural, _, _, body in self.api.patches if plural == "gatewayclasses")
        condition = body["status"]["conditions"][0]
        self.assertEqual((condition["type"], condition["status"], condition["reason"], condition["observedGeneration"]), ("Accepted", "True", "Accepted", 1))

    def test_foreign_controller_name_on_a_class_named_like_ours_is_ignored(self):
        self.api.classes = [gateway_class("bunkerweb", "someone.else/controller")]
        self.reconcile()
        self.assertEqual(self.api.patches, [])

    def test_unknown_class_writes_nothing(self):
        self.api.classes = []
        self.reconcile()
        self.assertEqual(self.api.patches, [])

    def test_class_filter_restricts_ownership(self):
        self.api.classes = [self.ours, gateway_class("other", OURS)]
        self.gateways[("demo", "gw2")] = gateway("gw2", "other")
        self.ctrl._gateway_class = "bunkerweb"
        self.reconcile()
        self.assertIn(("gateways", "gw"), self.patched())
        self.assertNotIn(("gateways", "gw2"), self.patched())
        self.assertNotIn(("gatewayclasses", "other"), self.patched())

    def test_gateway_conditions_and_listeners(self):
        self.rt["spec"]["parentRefs"] = [parent("gw", section="http")]
        self.reconcile()

        status = next(body for plural, _, name, body in self.api.patches if plural == "gateways")["status"]
        self.assertEqual({c["type"]: c["status"] for c in status["conditions"]}, {"Accepted": "True", "Programmed": "True"})
        http, tls = status["listeners"]
        self.assertEqual((http["name"], http["attachedRoutes"], tls["attachedRoutes"]), ("http", 1, 0))
        self.assertEqual(http["supportedKinds"], [{"group": GROUP, "kind": "HTTPRoute"}, {"group": GROUP, "kind": "GRPCRoute"}])
        self.assertEqual(tls["supportedKinds"], [{"group": GROUP, "kind": "TLSRoute"}])
        self.assertEqual({c["type"] for c in http["conditions"]}, {"Accepted", "Programmed", "ResolvedRefs"})

    def test_programmed_false_when_the_apply_failed(self):
        self.reconcile(applied=False)
        status = next(body for plural, _, _, body in self.api.patches if plural == "gateways")["status"]
        programmed = next(c for c in status["conditions"] if c["type"] == "Programmed")
        self.assertEqual((programmed["status"], programmed["reason"]), ("False", "Pending"))
        self.assertEqual(next(c for c in status["conditions"] if c["type"] == "Accepted")["status"], "True")

    def test_route_parents_carry_controller_and_conditions(self):
        self.reconcile()
        parents = next(body for plural, _, _, body in self.api.patches if plural == "httproutes")["status"]["parents"]
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0]["controllerName"], OURS)
        self.assertEqual(parents[0]["parentRef"], {"group": GROUP, "kind": "Gateway", "namespace": "demo", "name": "gw"})
        self.assertEqual(
            {c["type"]: (c["status"], c["observedGeneration"]) for c in parents[0]["conditions"]}, {"Accepted": ("True", 3), "ResolvedRefs": ("True", 3)}
        )

    def test_route_with_unknown_section_is_not_accepted(self):
        self.rt["spec"]["parentRefs"] = [parent("gw", section="nope")]
        self.reconcile()
        parents = next(body for plural, _, _, body in self.api.patches if plural == "httproutes")["status"]["parents"]
        accepted = next(c for c in parents[0]["conditions"] if c["type"] == "Accepted")
        self.assertEqual((accepted["status"], accepted["reason"]), ("False", "NoMatchingParent"))

    def test_route_with_unsupported_backend_kind_fails_resolved_refs(self):
        self.rt["spec"]["rules"][0]["backendRefs"][0]["kind"] = "Bucket"
        self.reconcile()
        parents = next(body for plural, _, _, body in self.api.patches if plural == "httproutes")["status"]["parents"]
        resolved = next(c for c in parents[0]["conditions"] if c["type"] == "ResolvedRefs")
        self.assertEqual((resolved["status"], resolved["reason"]), ("False", "InvalidKind"))

    def test_foreign_parent_entries_are_kept_and_ours_merged(self):
        other = {
            "parentRef": {"group": GROUP, "kind": "Gateway", "namespace": "demo", "name": "fgw"},
            "controllerName": "istio.io/gateway-controller",
            "conditions": [{"type": "Accepted", "status": "True"}],
        }
        stale = {"parentRef": {"group": GROUP, "kind": "Gateway", "namespace": "demo", "name": "gone"}, "controllerName": OURS, "conditions": []}
        self.rt["spec"]["parentRefs"] = [parent("gw"), parent("fgw")]
        self.rt["status"] = {"parents": [other, stale]}
        self.reconcile()

        parents = next(body for plural, _, _, body in self.api.patches if plural == "httproutes")["status"]["parents"]
        self.assertEqual(parents[0], other)
        self.assertEqual([p["parentRef"]["name"] for p in parents], ["fgw", "gw"])
        self.assertEqual(len(parents), 2, "the stale entry of ours is dropped, the foreign gateway is not given an entry")

    def test_route_whose_only_parent_is_foreign_is_never_patched(self):
        self.reconcile()
        self.assertNotIn(("httproutes", "fweb"), self.patched())

    def test_route_patch_carries_the_resource_version_precondition(self):
        self.reconcile()
        body = next(body for plural, _, _, body in self.api.patches if plural == "httproutes")
        self.assertEqual(body["metadata"], {"resourceVersion": "10"})

    def test_conflict_merges_into_the_fresh_object_and_retries_once(self):
        self.api.conflict_once = True
        fresh = deepcopy(self.rt)
        fresh["metadata"]["resourceVersion"] = "11"
        other = {
            "parentRef": {"group": GROUP, "kind": "Gateway", "namespace": "demo", "name": "fgw"},
            "controllerName": "istio.io/gateway-controller",
            "conditions": [],
        }
        fresh["status"] = {"parents": [other]}
        self.api.fresh[("httproutes", "demo", "web")] = fresh
        self.reconcile()

        body = next(body for plural, _, _, body in self.api.patches if plural == "httproutes")
        self.assertEqual(body["metadata"], {"resourceVersion": "11"})
        self.assertEqual(body["status"]["parents"][0], other)

    def test_no_write_when_status_is_already_up_to_date(self):
        self.reconcile()
        self.assertEqual(len(self.api.patches), 3)
        apply_patches(self.api, [self.ours, self.gw, self.rt])
        self.api.classes = [self.ours, self.foreign]

        self.reconcile()

        self.assertEqual(self.api.patches, [], "an unchanged status must not be written again")

    def test_last_transition_time_only_moves_when_the_status_flips(self):
        self.reconcile()
        apply_patches(self.api, [self.ours, self.gw, self.rt])
        before = {c["type"]: c["lastTransitionTime"] for c in self.gw["status"]["conditions"]}
        self.assertRegex(before["Accepted"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

        self.gw["metadata"]["generation"] = 3
        self.ctrl._reconcile_status(False, self.gateways, self.routes)
        stored = next(body for plural, _, _, body in self.api.patches if plural == "gateways")["status"]["conditions"]
        after = {c["type"]: (c["lastTransitionTime"], c["observedGeneration"]) for c in stored}
        self.assertEqual(after["Accepted"], (before["Accepted"], 3))
        self.assertEqual(after["Programmed"][1], 3)
        self.assertEqual({c["type"]: c["status"] for c in stored}["Programmed"], "False")

    def test_permission_error_is_reported_once_and_never_raises(self):
        self.api.fail_status = 403
        self.reconcile()
        self.reconcile()
        warnings = [call.args[0] for call in self.ctrl._logger.warning.call_args_list]
        self.assertEqual(len(warnings), 3, warnings)
        self.assertTrue(all("Cannot write status" in w for w in warnings))
        self.assertEqual(len({w.split("(")[0] for w in warnings}), 3, "one warning per resource")

    def test_status_only_events_are_ignored(self):
        first = event("Gateway", "gw", 2, event_type="ADDED")
        self.assertFalse(self.ctrl._is_status_only_event(first))
        self.assertTrue(self.ctrl._is_status_only_event(event("Gateway", "gw", 2)), "same generation: the echo of a status write")
        self.assertFalse(self.ctrl._is_status_only_event(event("Gateway", "gw", 3)), "spec changed")
        self.assertFalse(self.ctrl._is_status_only_event(event("Gateway", "gw", 3, {"bunkerweb.io/X": "1"})), "annotation changed")
        self.assertTrue(self.ctrl._is_status_only_event(event("Gateway", "gw", 3, {"bunkerweb.io/X": "1"})))

    def test_non_gateway_api_kinds_are_never_filtered(self):
        # No generation on these kinds: a data or status change keeps the same (None, annotations, labels) signature.
        for kind in ("ConfigMap", "Secret", "Pod", "Service"):
            first = event(kind, "obj", None, {"bunkerweb.io/CONFIG_TYPE": "http"}, event_type="ADDED")
            first["object"]["data"] = {"conf": "a"}
            edited = event(kind, "obj", None, {"bunkerweb.io/CONFIG_TYPE": "http"})
            edited["object"]["data"] = {"conf": "b"}
            self.assertFalse(self.ctrl._is_status_only_event(first), kind)
            self.assertFalse(self.ctrl._is_status_only_event(edited), f"{kind} data edit must be processed")
            self.assertFalse(self.ctrl._is_status_only_event(edited), f"{kind} repeated event must be processed")
        self.assertEqual(self.ctrl._seen_specs, {}, "nothing is remembered for kinds the filter does not own")

    def test_every_gateway_api_kind_is_filtered(self):
        for kind in ("GatewayClass", "Gateway", "HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute"):
            self.assertFalse(self.ctrl._is_status_only_event(event(kind, "x", 1, event_type="ADDED")), kind)
            self.assertTrue(self.ctrl._is_status_only_event(event(kind, "x", 1)), f"{kind} status echo")

    def test_addresses_are_written_only_on_owned_gateways(self):
        self.ctrl._gateways_cache = self.gateways
        self.ctrl._patch_controller_status(["10.0.0.1"])
        self.assertEqual({name for plural, _, name, _ in self.api.patches if plural == "gateways"}, {"gw"})
        body = next(body for _, _, _, body in self.api.patches)
        self.assertEqual(body["status"]["addresses"], [{"type": "IPAddress", "value": "10.0.0.1"}])

    def test_addresses_follow_the_class_filter_and_unknown_classes(self):
        self.ctrl._gateways_cache = self.gateways
        self.api.classes = []
        self.ctrl._patch_controller_status(["10.0.0.1"])
        self.assertEqual(self.api.patches, [], "no readable owned class, no write")

    def test_deleted_event_always_passes_and_forgets_the_object(self):
        self.ctrl._is_status_only_event(event("HTTPRoute", "web", 1))
        self.assertFalse(self.ctrl._is_status_only_event(event("HTTPRoute", "web", 1, event_type="DELETED")))
        self.assertFalse(self.ctrl._is_status_only_event(event("HTTPRoute", "web", 1, event_type="ADDED")))


if __name__ == "__main__":
    main()

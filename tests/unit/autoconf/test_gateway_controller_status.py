"""GatewayController status reporting: BunkerWeb writes status only on what it owns, and a refused write never breaks the configuration."""

import logging
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import attach_log
from kubernetes.client.exceptions import ApiException

import controllers.GatewayController as module
from gateway_fakes import OURS, crds, gateway_class, gw, route, served

NOW = "2026-03-03T03:03:03Z"
OWN_CLASS = gateway_class("bw", OURS)
FOREIGN_CLASS = gateway_class("istio", "istio.io/gateway-controller")


class Stop(BaseException):
    pass


@pytest.fixture
def ctrl(gateway_build, monkeypatch):
    monkeypatch.setattr(module, "utc_now", lambda: NOW)
    c = gateway_build(crds(gatewayclasses=[OWN_CLASS, FOREIGN_CLASS]))
    c.api.patch_namespaced_custom_object_status = MagicMock()
    c.api.patch_cluster_custom_object_status = MagicMock()
    c.api.get_namespaced_custom_object = MagicMock()
    return c


def patched(ctrl):
    """(plural, namespace, name) of every status write, in order."""
    out = []
    for call in ctrl.api.patch_cluster_custom_object_status.call_args_list:
        out.append((call.args[2], None, call.args[3]))
    for call in ctrl.api.patch_namespaced_custom_object_status.call_args_list:
        out.append((call.args[3], call.args[2], call.args[4]))
    return out


# --- addresses --------------------------------------------------------------------------------------------


def test_gateway_addresses_distinguish_ips_from_hostnames(ctrl):
    assert ctrl._patch_gateway_status(gw(), ["1.2.3.4", "2001:db8::1", "lb.example.com"]) is True

    ctrl.api.patch_namespaced_custom_object_status.assert_called_once_with(
        module.GATEWAY_API_GROUP,
        "v1",
        "prod",
        "gateways",
        "gw",
        {
            "status": {
                "addresses": [
                    {"type": "IPAddress", "value": "1.2.3.4"},
                    {"type": "IPAddress", "value": "2001:db8::1"},
                    {"type": "Hostname", "value": "lb.example.com"},
                ]
            }
        },
        _request_timeout=module.API_REQUEST_TIMEOUT,
    )


def test_address_patch_refuses_bad_input(ctrl):
    log = attach_log(ctrl)

    assert ctrl._patch_gateway_status(gw(), []) is False
    assert ctrl._patch_gateway_status({"metadata": {"name": "gw"}}, ["1.2.3.4"]) is False
    assert ctrl._patch_gateway_status({}, ["1.2.3.4"]) is False
    ctrl.api.patch_namespaced_custom_object_status.assert_not_called()
    assert log.has("Cannot patch gateway without IP addresses", logging.WARNING)
    assert log.has("Gateway name or namespace is empty", logging.ERROR)


@pytest.mark.parametrize(
    ("error", "fragment", "level"),
    [
        (ApiException(status=404, reason="nf"), "Gateway gw not found in namespace prod, skipping status patch", logging.WARNING),
        (ApiException(status=403, reason="no"), "Insufficient permissions to patch gateway gw status", logging.WARNING),
        (ApiException(status=422, reason="bad"), "Invalid patch data for gateway gw in namespace prod: bad", logging.ERROR),
        (ApiException(status=500, reason="boom"), "API error patching gateway gw in namespace prod: 500 - boom", logging.ERROR),
        (RuntimeError("x"), "Unexpected error patching gateway gw in namespace prod: x", logging.ERROR),
    ],
)
def test_address_patch_failures_are_contained(ctrl, error, fragment, level):
    ctrl.api.patch_namespaced_custom_object_status.side_effect = error
    log = attach_log(ctrl)

    assert ctrl._patch_gateway_status(gw(), ["1.2.3.4"]) is False
    assert log.has(fragment, level)


def test_owned_classes_follow_the_controller_name_and_the_configured_class(gateway_build):
    classes = [OWN_CLASS, FOREIGN_CLASS, gateway_class("bw2", OURS), {"metadata": {}, "spec": {"controllerName": OURS}}]

    assert gateway_build(crds())._owned_class_names(classes) == {"bw", "bw2"}
    assert gateway_build(crds(), KUBERNETES_GATEWAY_CLASS="bw2")._owned_class_names(classes) == {"bw2"}


def test_addresses_are_never_written_on_another_controllers_gateway(ctrl):
    """QAR Q8"""
    served(ctrl, [gw("mine", class_name="bw"), gw("theirs", class_name="istio"), gw("classless", class_name="mystery")], classes=[OWN_CLASS, FOREIGN_CLASS])

    ctrl._patch_controller_status(["1.2.3.4"])

    assert patched(ctrl) == [("gateways", "prod", "mine")]


# --- reconcile --------------------------------------------------------------------------------------------


def reconcile(ctrl, gateways, routes=(), applied=True, classes=(OWN_CLASS, FOREIGN_CLASS)):
    ctrl.api.crds["gatewayclasses"] = (("v1",), list(classes))
    cache = {(g["metadata"]["namespace"], g["metadata"]["name"]): g for g in gateways}
    ctrl._reconcile_status(applied, cache, list(routes))


def test_owned_class_gateway_and_route_statuses_are_written(ctrl):
    gateway = gw("mine", class_name="bw")
    r = route(name="web", parents=[{"name": "mine"}])
    r["kind"] = "HTTPRoute"

    reconcile(ctrl, [gateway], [r])

    assert patched(ctrl) == [("gatewayclasses", None, "bw"), ("gateways", "prod", "mine"), ("httproutes", "prod", "web")]
    class_body = ctrl.api.patch_cluster_custom_object_status.call_args.args[4]
    assert class_body["status"]["conditions"][0]["type"] == "Accepted"
    gateway_body = ctrl.api.patch_namespaced_custom_object_status.call_args_list[0].args[5]
    programmed = {c["type"]: c for c in gateway_body["status"]["conditions"]}["Programmed"]
    assert programmed["status"] == "True" and programmed["lastTransitionTime"] == NOW
    route_body = ctrl.api.patch_namespaced_custom_object_status.call_args_list[1].args[5]
    assert route_body["status"]["parents"][0]["controllerName"] == OURS


def test_a_failed_apply_is_reported_as_not_programmed(ctrl):
    reconcile(ctrl, [gw("mine", class_name="bw")], applied=False)

    body = ctrl.api.patch_namespaced_custom_object_status.call_args.args[5]
    programmed = {c["type"]: c for c in body["status"]["conditions"]}["Programmed"]
    assert (programmed["status"], programmed["reason"]) == ("False", "Pending")


def test_nothing_is_written_on_what_another_controller_owns(ctrl):
    """QAR Q8: a foreign class, its Gateways and the routes attached to them are left untouched."""
    theirs = gw("theirs", class_name="istio")
    r = route(name="web", parents=[{"name": "theirs"}])

    reconcile(ctrl, [theirs], [r])

    assert patched(ctrl) == [("gatewayclasses", None, "bw")]


def test_up_to_date_status_is_not_rewritten(ctrl):
    gateway = gw("mine", class_name="bw")
    gateway["status"] = module.build_gateway_status(gateway, [], True, NOW)
    owned_class = dict(OWN_CLASS, status={"conditions": module.build_class_conditions(OWN_CLASS, NOW)})

    reconcile(ctrl, [gateway], classes=(owned_class,))

    assert patched(ctrl) == []


def test_route_status_is_skipped_when_unchanged_or_without_an_owned_parent(ctrl):
    owned = {("prod", "mine"): gw("mine", class_name="bw")}
    r = route(name="web", parents=[{"name": "mine"}])
    r["kind"] = "HTTPRoute"
    r["status"] = {"parents": module.build_route_parents(r, owned, OURS, NOW)}
    stranger = dict(route(name="other", parents=[{"name": "elsewhere"}]), kind="HTTPRoute")
    unknown_kind = dict(route(name="x"), kind="FancyRoute")

    for candidate in (r, stranger, unknown_kind):
        ctrl._reconcile_route_status(candidate, owned)

    assert patched(ctrl) == []


def test_route_status_carries_the_resource_version_for_optimistic_concurrency(ctrl):
    owned = {("prod", "mine"): gw("mine", class_name="bw")}
    r = dict(route(name="web", parents=[{"name": "mine"}]), kind="HTTPRoute")
    r["metadata"]["resourceVersion"] = "42"

    ctrl._reconcile_route_status(r, owned)

    assert ctrl.api.patch_namespaced_custom_object_status.call_args.args[5]["metadata"] == {"resourceVersion": "42"}


def test_a_conflict_is_retried_once_against_the_fresh_object(ctrl):
    owned = {("prod", "mine"): gw("mine", class_name="bw")}
    stale = dict(route(name="web", parents=[{"name": "mine"}]), kind="HTTPRoute")
    fresh = route(name="web", parents=[{"name": "mine"}])
    fresh["status"] = {"parents": [{"controllerName": "other.io/c", "parentRef": {"name": "mine"}, "conditions": []}]}
    del fresh["kind"]
    ctrl.api.patch_namespaced_custom_object_status.side_effect = [ApiException(status=409, reason="Conflict"), None]
    ctrl.api.get_namespaced_custom_object.return_value = fresh

    ctrl._reconcile_route_status(stale, owned)

    assert len(ctrl.api.patch_namespaced_custom_object_status.call_args_list) == 2
    merged = ctrl.api.patch_namespaced_custom_object_status.call_args_list[1].args[5]["status"]["parents"]
    assert [p["controllerName"] for p in merged] == ["other.io/c", OURS]


def test_a_second_conflict_gives_up_quietly(ctrl):
    owned = {("prod", "mine"): gw("mine", class_name="bw")}
    stale = dict(route(name="web", parents=[{"name": "mine"}]), kind="HTTPRoute")
    ctrl.api.patch_namespaced_custom_object_status.side_effect = ApiException(status=409, reason="Conflict")
    ctrl.api.get_namespaced_custom_object.return_value = dict(route(name="web", parents=[{"name": "mine"}]), kind="HTTPRoute")

    ctrl._reconcile_route_status(stale, owned)

    assert len(ctrl.api.patch_namespaced_custom_object_status.call_args_list) == 2


def test_a_conflict_whose_refresh_fails_is_dropped(ctrl):
    owned = {("prod", "mine"): gw("mine", class_name="bw")}
    stale = dict(route(name="web", parents=[{"name": "mine"}]), kind="HTTPRoute")
    ctrl.api.patch_namespaced_custom_object_status.side_effect = ApiException(status=409, reason="Conflict")
    ctrl.api.get_namespaced_custom_object.side_effect = ApiException(status=404, reason="gone")
    log = attach_log(ctrl)

    ctrl._reconcile_route_status(stale, owned)

    assert len(ctrl.api.patch_namespaced_custom_object_status.call_args_list) == 1
    assert log.has("Cannot refresh HTTPRoute prod/web after a conflict", logging.DEBUG)


# --- _patch_status ----------------------------------------------------------------------------------------


def test_cluster_scoped_and_namespaced_writes_use_the_right_call(ctrl):
    assert ctrl._patch_status("gatewayclasses", None, "bw", {"status": {}}, "GatewayClass") is True
    assert ctrl._patch_status("gateways", "prod", "gw", {"status": {}}, "Gateway") is True

    assert patched(ctrl) == [("gatewayclasses", None, "bw"), ("gateways", "prod", "gw")]


def test_failures_warn_once_per_object_and_success_rearms_the_warning(ctrl):
    ctrl.api.patch_namespaced_custom_object_status.side_effect = ApiException(status=403, reason="Forbidden")
    log = attach_log(ctrl)

    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway") is False
    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway") is False
    assert log.messages(logging.WARNING) == ["Cannot write status of Gateway prod/gw (403 Forbidden), configuration is not affected"]

    ctrl.api.patch_namespaced_custom_object_status.side_effect = None
    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway") is True
    ctrl.api.patch_namespaced_custom_object_status.side_effect = RuntimeError("down")
    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway") is False
    assert log.has("Cannot write status of Gateway prod/gw (down)", logging.WARNING)


def test_conflicts_are_only_swallowed_when_the_caller_can_retry(ctrl):
    ctrl.api.patch_namespaced_custom_object_status.side_effect = ApiException(status=409, reason="Conflict")

    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway", conflict_ok=True) is None
    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway") is False


def test_an_object_deleted_meanwhile_is_not_worth_a_warning(ctrl):
    ctrl.api.patch_namespaced_custom_object_status.side_effect = ApiException(status=404, reason="Not Found")
    log = attach_log(ctrl)

    assert ctrl._patch_status("gateways", "prod", "gw", {}, "Gateway") is False
    assert log.messages(logging.WARNING) == []
    assert log.has("Gateway prod/gw disappeared before its status could be written", logging.DEBUG)


# --- the status worker ------------------------------------------------------------------------------------


class FakeThread:
    created = []

    def __init__(self, target=None, daemon=False):
        self.target, self.daemon, self.started = target, daemon, False
        FakeThread.created.append(self)

    def start(self):
        self.started = True


def test_sync_status_snapshots_the_caches_and_starts_one_worker(ctrl, monkeypatch):
    FakeThread.created = []
    monkeypatch.setattr(module, "Thread", FakeThread)
    served(ctrl, [gw("mine")], route(name="web", parents=[{"name": "mine"}]))
    ctrl._last_apply_ok = False

    ctrl._sync_status()
    ctrl._sync_status(True)

    applied, gateways, routes = ctrl._status_snapshot
    assert applied is True
    assert set(gateways) == {("prod", "mine")} and [r["metadata"]["name"] for r in routes] == ["web"]
    assert len(FakeThread.created) == 1 and FakeThread.created[0].started and FakeThread.created[0].daemon
    assert ctrl._status_wakeup.is_set()


def test_sync_status_uses_the_last_outcome_when_nothing_was_applied(ctrl, monkeypatch):
    monkeypatch.setattr(module, "Thread", FakeThread)
    ctrl._last_apply_ok = False

    ctrl._sync_status()

    assert ctrl._status_snapshot[0] is False


def test_sync_status_is_a_noop_without_gateway_class_support(gateway_build, monkeypatch):
    table = crds()
    del table["gatewayclasses"]
    ctrl = gateway_build(table)
    FakeThread.created = []
    monkeypatch.setattr(module, "Thread", FakeThread)

    ctrl._sync_status()

    assert ctrl._status_snapshot is None and FakeThread.created == []


class OneShotEvent:
    """wait() returns once, then ends the worker loop."""

    def __init__(self):
        self.waits = 0

    def wait(self):
        self.waits += 1
        if self.waits > 1:
            raise Stop

    def clear(self):
        pass


def test_status_worker_reconciles_the_pending_snapshot_once(ctrl):
    ctrl._status_wakeup = OneShotEvent()
    ctrl._status_snapshot = (True, {}, [])
    ctrl._reconcile_status = MagicMock()

    with pytest.raises(Stop):
        ctrl._status_worker()

    ctrl._reconcile_status.assert_called_once_with(True, {}, [])
    assert ctrl._status_snapshot is None


def test_status_worker_survives_a_reconcile_crash(ctrl):
    ctrl._status_wakeup = OneShotEvent()
    ctrl._status_snapshot = (True, {}, [])
    ctrl._reconcile_status = MagicMock(side_effect=RuntimeError("api down"))
    log = attach_log(ctrl)

    with pytest.raises(Stop):
        ctrl._status_worker()

    assert log.has("Unexpected error while writing Gateway API status: api down", logging.WARNING)


def test_status_worker_ignores_a_wakeup_without_a_snapshot(ctrl):
    ctrl._status_wakeup = OneShotEvent()
    ctrl._reconcile_status = MagicMock()

    with pytest.raises(Stop):
        ctrl._status_worker()

    ctrl._reconcile_status.assert_not_called()

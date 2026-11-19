"""Failed Gateway API lists must never become an authoritative empty or broader roster."""

from copy import deepcopy

import pytest
from gateway_fakes import ALL_PLURALS, OURS, backend, crds, gateway_class, gw, route
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import ReadTimeoutError


def list_error(kind):
    if kind == "timeout":
        return ReadTimeoutError(None, "/apis/gateway.networking.k8s.io", "timed out")
    return ApiException(status=kind, reason="temporary list failure")


@pytest.mark.parametrize("plural", ALL_PLURALS)
@pytest.mark.parametrize("failure", [500, 429, "timeout"])
def test_failed_reconciliation_keeps_saved_roster_and_completed_snapshot(gateway_build, fake_db, plural, failure):
    table = crds(
        gateways=[gw(), gw(name="foreign", class_name="other")],
        gatewayclasses=[gateway_class("bw", OURS), gateway_class("other", "other/controller")],
        httproutes=[
            route(hostnames=["owned.example.com"], rules=[{"backendRefs": [backend()]}]),
            route(name="foreign", hostnames=["foreign.example.com"], parents=[{"name": "foreign"}], rules=[{"backendRefs": [backend()]}]),
        ],
    )
    healthy = deepcopy(table)
    ctrl = gateway_build(table, KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    ctrl._services = ctrl.get_services()
    assert [service["SERVER_NAME"] for service in ctrl._services] == ["owned.example.com"]
    assert ctrl.apply([], ctrl._services, first=True)
    saved = deepcopy(fake_db.saved_configs)
    snapshot = deepcopy((ctrl._gateways_cache, ctrl._routes_cache, ctrl._services))
    error = list_error(failure)
    ctrl.api.crds[plural] = error

    with pytest.raises(type(error)):
        # Same discovery-before-apply order as the reconciliation loop.
        ctrl._services = ctrl.get_services()
        ctrl.apply([], ctrl._services)

    assert fake_db.saved_configs == saved
    assert saved[-1]["SERVER_NAME"] == "owned.example.com"
    assert (ctrl._gateways_cache, ctrl._routes_cache, ctrl._services) == snapshot

    ctrl.api.crds.update(healthy)
    assert [service["SERVER_NAME"] for service in ctrl.get_services()] == ["owned.example.com"]


@pytest.mark.parametrize("plural", ALL_PLURALS)
@pytest.mark.parametrize("failure", [500, 429, "timeout"])
def test_transient_startup_list_failure_aborts_instead_of_disabling_resource(gateway_build, plural, failure):
    table = crds()
    error = list_error(failure)
    table[plural] = error

    with pytest.raises(type(error)):
        gateway_build(table, KUBERNETES_SKIP_FOREIGN_CLASSES="yes")

    # A supervisor restart after API recovery must enable the resource and its watch.
    ctrl = gateway_build(crds(), KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    assert ctrl._resource_versions[plural] == "v1"
    assert ("gatewayclass" if plural == "gatewayclasses" else plural[:-1]) in ctrl._get_watchers()


@pytest.mark.parametrize("plural", ALL_PLURALS)
def test_real_404_still_means_resource_unavailable(gateway_build, plural):
    ctrl = gateway_build()
    ctrl.api.crds[plural] = ApiException(status=404, reason="Not Found")

    assert ctrl._list_custom_objects(plural) == []


def test_successful_empty_list_can_remove_last_service(gateway_build, fake_db):
    ctrl = gateway_build(crds(gateways=[gw()], httproutes=[route(hostnames=["owned.example.com"], rules=[{"backendRefs": [backend()]}])]))
    assert ctrl.apply([], ctrl.get_services(), first=True)
    ctrl.api.crds["httproutes"] = (("v1",), [])

    assert ctrl.apply([], ctrl.get_services())
    assert fake_db.saved_configs[-1]["SERVER_NAME"] == ""

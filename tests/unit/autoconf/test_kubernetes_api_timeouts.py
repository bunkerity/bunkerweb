"""Dead Kubernetes calls must time out, and a stalled lock holder must fail liveness."""

import sys
from pathlib import Path
from socket import IPPROTO_TCP, SOL_SOCKET, SO_KEEPALIVE, TCP_USER_TIMEOUT
from threading import Thread
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _port_helpers import BASE, GATEWAY, INGRESS, K8S, bare_controller


def test_discovery_calls_have_finite_timeouts():
    controller = bare_controller()
    controller._corev1.list_pod_for_all_namespaces.return_value.items = []
    assert controller._get_controller_instances() == []
    assert controller._corev1.list_pod_for_all_namespaces.call_args.kwargs["_request_timeout"] == (10, 60)
    controller._supported_config_types = []
    controller._corev1.list_config_map_for_all_namespaces.return_value.items = []
    assert controller.get_configs() == ({}, {})
    assert controller._corev1.list_config_map_for_all_namespaces.call_args.kwargs["_request_timeout"] == (10, 60)


def test_kubernetes_clients_share_progress_tracking_and_keepalives(monkeypatch):
    monkeypatch.delenv("NAMESPACES", raising=False)
    controller = K8S.KubernetesController(api_client=Mock())
    core = K8S.client.CoreV1Api.call_args.kwargs["api_client"]
    assert core.call_api() == {"ok": True}
    options = K8S.Configuration._default.socket_options
    assert (SOL_SOCKET, SO_KEEPALIVE, 1) in options
    assert (IPPROTO_TCP, TCP_USER_TIMEOUT, 60000) in options
    # A sibling watch completing a request must not hide the holder's stalled call.
    clock = [100.0]
    monkeypatch.setattr(BASE, "monotonic", lambda: clock[0])
    with controller._internal_lock:
        clock[0] = 150.0
        worker = Thread(target=core.call_api)
        worker.start()
        worker.join(timeout=1)
        assert not worker.is_alive()
        assert controller._internal_lock.stalled_for() == 50.0
        core.call_api()
        assert controller._internal_lock.stalled_for() == 0.0


def test_only_stalled_lock_holder_drops_global_marker(monkeypatch, tmp_path):
    controller = bare_controller()
    assert hasattr(BASE, "HoldTimeLock"), "plain Lock cannot identify a stuck holder"
    controller._internal_lock = BASE.HoldTimeLock()
    controller._lock_max_hold = 600
    marker = tmp_path / "autoconf.healthy"
    marker.write_text("ok")
    clock = [100.0]
    monkeypatch.setattr(BASE, "monotonic", lambda: clock[0])
    assert controller._check_lock_hold(marker) is False
    with controller._internal_lock:
        clock[0] = 701.0
        assert controller._check_lock_hold(marker) is True
        assert not marker.exists()
    marker.write_text("ok")
    assert controller._check_lock_hold(marker) is False
    assert marker.exists()


def test_bunkerweb_api_responses_refresh_holder_progress(monkeypatch):
    controller = K8S.KubernetesController(api_client=Mock())
    assert hasattr(controller._internal_lock, "stalled_for"), "API-only applies need progress tracking too"
    clock = [100.0]
    monkeypatch.setattr(BASE, "monotonic", lambda: clock[0])
    with controller._internal_lock:
        clock[0] = 200.0
        controller._api.observer("GET", "/metadata", 0, 200)
        assert controller._internal_lock.stalled_for() == 0.0


@pytest.mark.parametrize("family", ["ingress", "gateway"])
def test_class_ownership_lookups_are_bounded(family):
    if family == "ingress":
        controller = bare_controller(INGRESS.IngressController)
        controller._ingress_classes_readable = True
        controller._ingress_controller = "ours"
        controller._networkingv1 = Mock()
        controller._networkingv1.list_ingress_class.return_value.items = []
        assert controller._foreign_ingress_classes() == set()
        call = controller._networkingv1.list_ingress_class.call_args
    else:
        controller = bare_controller(GATEWAY.GatewayController)
        controller._gateway_classes_readable = True
        controller._gateway_controller = "ours"
        controller._resource_versions = {"gatewayclasses": "v1"}
        controller._gateway_api_group = "gateway.networking.k8s.io"
        controller._gateway_api_version = "v1"
        controller._custom_objects = Mock()
        controller._custom_objects.list_cluster_custom_object.return_value = {"items": []}
        assert controller._foreign_gateway_classes() == set()
        call = controller._custom_objects.list_cluster_custom_object.call_args
    assert call.kwargs["_request_timeout"] == (10, 60)

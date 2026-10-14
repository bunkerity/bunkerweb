"""Class isolation must gate discovery and load-balancer status publication together."""

import sys
from pathlib import Path
from threading import Lock
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lb_address_call_sites import _GATEWAY, _INGRESS, _K8S_ENTRY  # noqa: E402


def _base_init(self, *, api_client):
    self._logger = Mock()
    self._corev1 = Mock()
    self._namespaces = []
    self._should_ignore_annotation = lambda annotation: False


def _ingress(name, class_name=None, annotation=None):
    return NS(
        metadata=NS(name=name, namespace="default", annotations={"kubernetes.io/ingress.class": annotation} if annotation else {}),
        spec=NS(ingress_class_name=class_name),
    )


def _ingress_controller(monkeypatch, flag="yes", selected=""):
    monkeypatch.setenv("KUBERNETES_SKIP_FOREIGN_CLASSES", flag)
    monkeypatch.setenv("KUBERNETES_INGRESS_CLASS", selected)
    monkeypatch.setenv("KUBERNETES_INGRESS_CONTROLLER", "bunkerweb.io/ingress-controller")
    monkeypatch.setattr(_K8S_ENTRY.KubernetesController, "__init__", _base_init)
    api = Mock()
    api.list_ingress_class.return_value = NS(
        items=[
            NS(metadata=NS(name="owned"), spec=NS(controller="bunkerweb.io/ingress-controller")),
            NS(metadata=NS(name="foreign", annotations={"ingressclass.kubernetes.io/is-default-class": "true"}), spec=NS(controller="example.com/foreign")),
        ]
    )
    api.list_ingress_for_all_namespaces.return_value = NS(
        items=[
            _ingress("owned", "owned"),
            _ingress("foreign", "foreign"),
            _ingress("unknown", "unknown"),
            _ingress("classless"),
            _ingress("legacy", annotation="foreign"),
            _ingress("precedence", "owned", "foreign"),
        ]
    )
    monkeypatch.setattr(_INGRESS.client, "NetworkingV1Api", lambda: api, raising=False)
    return _INGRESS.IngressController(api_client=Mock()), api


@pytest.mark.parametrize(
    "flag,selected,expected",
    [
        ("yes", "", {"owned", "unknown", "classless", "precedence"}),
        ("no", "", {"owned", "foreign", "unknown", "classless", "legacy", "precedence"}),
        ("yes", "foreign", {"foreign"}),
    ],
)
def test_ingress_discovery_and_status_share_class_scope(monkeypatch, flag, selected, expected):
    controller, api = _ingress_controller(monkeypatch, flag, selected)
    assert {i.metadata.name for i in controller._get_controller_services()} == expected
    controller._patch_controller_status(["192.0.2.1"])
    assert {c.kwargs["name"] for c in api.patch_namespaced_ingress_status.call_args_list} == expected


def _gateway_controller(monkeypatch, flag="yes", selected=""):
    monkeypatch.setenv("KUBERNETES_SKIP_FOREIGN_CLASSES", flag)
    monkeypatch.setenv("KUBERNETES_GATEWAY_CLASS", selected)
    monkeypatch.setenv("KUBERNETES_GATEWAY_CONTROLLER", "bunkerweb.io/gateway-controller")
    monkeypatch.setattr(_K8S_ENTRY.KubernetesController, "__init__", _base_init)
    gateways = [{"metadata": {"name": name, "namespace": "default"}, "spec": {"gatewayClassName": name}} for name in ("owned", "foreign", "unknown")]
    classes = [
        {"metadata": {"name": name}, "spec": {"controllerName": owner}}
        for name, owner in (
            ("owned", "bunkerweb.io/gateway-controller"),
            ("foreign", "example.com/foreign"),
        )
    ]
    routes = [
        {"kind": "HTTPRoute", "metadata": {"name": name, "namespace": "default"}, "spec": {"parentRefs": [{"name": name}]}}
        for name in ("owned", "foreign", "unknown")
    ]
    api = Mock()
    api.list_cluster_custom_object.side_effect = lambda group, version, plural, **kwargs: {
        "items": {"gatewayclasses": classes, "gateways": gateways, "httproutes": routes}.get(plural, [])
    }
    monkeypatch.setattr(_GATEWAY.client, "CustomObjectsApi", lambda: api, raising=False)
    return _GATEWAY.GatewayController(api_client=Mock()), api


@pytest.mark.parametrize(
    "flag,selected,expected",
    [
        ("yes", "", {"owned", "unknown"}),
        ("no", "", {"owned", "foreign", "unknown"}),
        ("yes", "foreign", {"foreign"}),
    ],
)
def test_gateway_routes_and_status_share_class_scope(monkeypatch, flag, selected, expected):
    controller, api = _gateway_controller(monkeypatch, flag, selected)
    assert {r["metadata"]["name"] for r in controller._get_controller_services()} == expected
    controller._patch_controller_status(["192.0.2.1"])
    assert {c.args[4] for c in api.patch_namespaced_custom_object_status.call_args_list} == expected


@pytest.mark.parametrize("family", ["ingress", "gateway"])
def test_foreign_resources_receive_no_status_patch(monkeypatch, family):
    if family == "ingress":
        controller, api = _ingress_controller(monkeypatch)
        api.list_ingress_for_all_namespaces.return_value = NS(items=[_ingress("foreign", "foreign")])
        controller._patch_controller_status(["192.0.2.1"])
        api.patch_namespaced_ingress_status.assert_not_called()
    else:
        controller, api = _gateway_controller(monkeypatch)
        controller._get_controller_services()
        controller._patch_controller_status(["192.0.2.1"])
        assert "foreign" not in {c.args[4] for c in api.patch_namespaced_custom_object_status.call_args_list}


def test_ingress_class_transfer_triggers_reconciliation(monkeypatch):
    controller, api = _ingress_controller(monkeypatch, selected="owned")
    controller._get_controller_services()
    moved = _ingress("owned", "foreign")
    assert controller._is_custom_event("Ingress", moved, {}, "default", "owned")


@pytest.mark.parametrize("family,kind,watcher", [("ingress", "IngressClass", "ingressclass"), ("gateway", "GatewayClass", "gatewayclass")])
def test_class_changes_are_watched_and_reconciled(monkeypatch, family, kind, watcher):
    controller, _ = (_ingress_controller if family == "ingress" else _gateway_controller)(monkeypatch)
    assert watcher in controller._get_watchers()
    assert controller._is_custom_event(kind, NS(), {}, None, "foreign")


@pytest.mark.parametrize("family", ["ingress", "gateway"])
@pytest.mark.parametrize("initial", [True, False])
def test_unreadable_ownership_aborts_discovery_and_status(monkeypatch, family, initial):
    controller, api = (_ingress_controller if family == "ingress" else _gateway_controller)(monkeypatch)
    if not initial:
        controller._get_controller_services()
    denial = _INGRESS.ApiException(status=403, reason="Forbidden")
    if family == "ingress":
        # A formerly adopted object changes class while the class lookup is unavailable.
        api.list_ingress_for_all_namespaces.return_value = NS(items=[_ingress("owned", "foreign")])
        api.list_ingress_class.side_effect = denial
        publisher = api.patch_namespaced_ingress_status
    else:
        original = api.list_cluster_custom_object.side_effect

        def unavailable(group, version, plural, **kwargs):
            if plural == "gatewayclasses":
                raise denial
            if plural == "gateways":
                return {"items": [{"metadata": {"name": "owned", "namespace": "default"}, "spec": {"gatewayClassName": "foreign"}}]}
            return original(group, version, plural, **kwargs)

        api.list_cluster_custom_object.side_effect = unavailable
        publisher = api.patch_namespaced_custom_object_status
    with pytest.raises(RuntimeError, match="ownership"):
        controller._get_controller_services()
    with pytest.raises(RuntimeError, match="ownership"):
        controller._patch_controller_status(["192.0.2.1"])
    publisher.assert_not_called()
    assert any("Grant get/list/watch" in str(call) for call in controller._logger.error.call_args_list)
    # Exercise the real reconciliation entry point: the failed RHS leaves the
    # previous service snapshot intact and never reaches the API apply path.
    controller._internal_lock = Lock()
    controller._pending_apply = True
    controller._log_event_summary = Mock()
    controller._update_settings = Mock()
    controller.get_instances = Mock(return_value=[])
    controller.get_services = controller._get_controller_services
    controller._services = previous = [{"SERVER_NAME": "previous.example"}]
    controller.apply_config = Mock()
    controller._trigger_apply_if_idle()
    assert controller._services is previous
    controller.apply_config.assert_not_called()


@pytest.mark.parametrize("family", ["ingress", "gateway"])
def test_unset_flag_retains_all_classes(monkeypatch, family):
    factory = _ingress_controller if family == "ingress" else _gateway_controller
    factory(monkeypatch)
    monkeypatch.delenv("KUBERNETES_SKIP_FOREIGN_CLASSES")
    module = _INGRESS if family == "ingress" else _GATEWAY
    cls = module.IngressController if family == "ingress" else module.GatewayController
    controller = cls(api_client=Mock())
    resources = controller._get_controller_services()
    names = {r.metadata.name if family == "ingress" else r["metadata"]["name"] for r in resources}
    assert "foreign" in names


def test_gateway_status_refreshes_class_transfer(monkeypatch):
    controller, api = _gateway_controller(monkeypatch)
    controller._get_controller_services()
    original = api.list_cluster_custom_object.side_effect

    def transferred(group, version, plural, **kwargs):
        if plural == "gatewayclasses":
            return {"items": [{"metadata": {"name": "owned"}, "spec": {"controllerName": "other"}}]}
        return original(group, version, plural, **kwargs)

    api.list_cluster_custom_object.side_effect = transferred
    controller._patch_controller_status(["192.0.2.1"])
    assert "owned" not in {c.args[4] for c in api.patch_namespaced_custom_object_status.call_args_list}


def test_initial_gateway_probe_denial_does_not_disable_isolation(monkeypatch):
    _, api = _gateway_controller(monkeypatch)
    original = api.list_cluster_custom_object.side_effect

    def denied(group, version, plural, **kwargs):
        if plural == "gatewayclasses":
            raise _GATEWAY.ApiException(status=403, reason="Forbidden")
        return original(group, version, plural, **kwargs)

    api.list_cluster_custom_object.side_effect = denied
    controller = _GATEWAY.GatewayController(api_client=Mock())
    with pytest.raises(RuntimeError, match="ownership"):
        controller._get_controller_services()
    with pytest.raises(RuntimeError, match="ownership"):
        controller._patch_controller_status(["192.0.2.1"])
    api.patch_namespaced_custom_object_status.assert_not_called()
    assert any("Grant get/list/watch on gatewayclasses" in str(call) for call in controller._logger.error.call_args_list)
    api.list_cluster_custom_object.side_effect = original
    assert {r["metadata"]["name"] for r in controller._get_controller_services()} == {"owned", "unknown"}


@pytest.mark.parametrize("family", ["ingress", "gateway"])
def test_configured_controller_id_changes_ownership(monkeypatch, family):
    factory = _ingress_controller if family == "ingress" else _gateway_controller
    _, api = factory(monkeypatch)
    monkeypatch.setenv(f"KUBERNETES_{family.upper()}_CONTROLLER", "example.com/foreign")
    cls = _INGRESS.IngressController if family == "ingress" else _GATEWAY.GatewayController
    resources = cls(api_client=Mock())._get_controller_services()
    names = {r.metadata.name if family == "ingress" else r["metadata"]["name"] for r in resources}
    assert "foreign" in names
    assert "owned" not in names


@pytest.mark.parametrize("family", ["ingress", "gateway"])
def test_namespace_and_annotation_filters_remain_in_force(monkeypatch, family):
    controller, api = (_ingress_controller if family == "ingress" else _gateway_controller)(monkeypatch)
    controller._namespaces = ["other"]
    assert controller._get_controller_services() == []
    controller._patch_controller_status(["192.0.2.1"])
    publisher = api.patch_namespaced_ingress_status if family == "ingress" else api.patch_namespaced_custom_object_status
    publisher.assert_not_called()
    controller._namespaces = []
    controller._should_ignore_annotation = lambda annotation: annotation == "ignore"
    if family == "ingress":
        api.list_ingress_for_all_namespaces.return_value.items[0].metadata.annotations = {"ignore": "yes"}
    else:
        original = api.list_cluster_custom_object.side_effect

        def ignored(group, version, plural, **kwargs):
            data = original(group, version, plural, **kwargs)
            if plural == "gateways":
                data["items"][0]["metadata"]["annotations"] = {"ignore": "yes"}
            return data

        api.list_cluster_custom_object.side_effect = ignored
    resources = controller._get_controller_services()
    names = {r.metadata.name if family == "ingress" else r["metadata"]["name"] for r in resources}
    assert "owned" not in names

#!/usr/bin/env python3

from pathlib import Path
from sys import path as sys_path
from unittest.mock import MagicMock
import unittest

ROOT = Path(__file__).resolve().parents[2]
for rel in ("src/autoconf", "src/common/db", "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(ROOT / rel))

from controllers.GatewayController import GatewayController  # type: ignore  # noqa: E402


def make_gateway_class(name: str, controller_name: str) -> dict:
    return {"metadata": {"name": name}, "spec": {"controllerName": controller_name}}


def make_gateway(name: str, gateway_class_name: str, namespace: str = "demo") -> dict:
    return {"metadata": {"namespace": namespace, "name": name}, "spec": {"gatewayClassName": gateway_class_name}}


ISTIO_CLASS = make_gateway_class("istio", "istio.io/gateway-controller")
BUNKERWEB_CLASS = make_gateway_class("bunkerweb", "bunkerweb.io/gateway-controller")

GW_ISTIO = make_gateway("gw-istio", "istio")
GW_BW = make_gateway("gw-bw", "bunkerweb")
GW_UNKNOWN = make_gateway("gw-unknown", "cilium")

GATEWAYS_FIXTURE = [GW_ISTIO, GW_BW, GW_UNKNOWN]
GATEWAYCLASSES_FIXTURE = [ISTIO_CLASS, BUNKERWEB_CLASS]


def make_custom_objects_mock():
    def _list_cluster_custom_object(group, version, plural, **kwargs):
        if plural == "gateways":
            return {"items": GATEWAYS_FIXTURE}
        if plural == "gatewayclasses":
            return {"items": GATEWAYCLASSES_FIXTURE}
        return {"items": []}

    mock = MagicMock()
    mock.list_cluster_custom_object.side_effect = _list_cluster_custom_object
    return mock


def new_controller(gateway_class="", skip_foreign_classes=True, readable=None) -> GatewayController:
    if readable is None:
        # Mirrors GatewayController.__init__: a class filter always disables ownership filtering.
        readable = bool(skip_foreign_classes and not gateway_class)
    ctrl = GatewayController.__new__(GatewayController)
    ctrl._custom_objects = make_custom_objects_mock()
    ctrl._gateways_cache = {}
    ctrl._gateway_class = gateway_class
    ctrl._gateway_api_group = "gateway.networking.k8s.io"
    ctrl._gateway_api_version = "v1"
    ctrl._gateway_api_available = True
    ctrl._resource_versions = {"gateways": "v1", "gatewayclasses": "v1"}
    ctrl._skip_foreign_classes = skip_foreign_classes
    ctrl._gateway_controller = "bunkerweb.io/gateway-controller"
    ctrl._gateway_classes_readable = readable
    ctrl._gateway_classes_warned = False
    ctrl._namespaces = []
    ctrl._logger = MagicMock()
    ctrl._should_ignore_annotation = lambda a: False
    return ctrl


class GatewayOwnershipTest(unittest.TestCase):
    def test_flag_yes_readable_filters_foreign_classes(self):
        ctrl = new_controller()

        gateways = ctrl._get_gateways()

        self.assertEqual(sorted(name for _, name in gateways.keys()), ["gw-bw", "gw-unknown"])

    def test_flag_no_adopts_everything_and_never_lists_gatewayclasses(self):
        ctrl = new_controller(skip_foreign_classes=False, readable=False)

        gateways = ctrl._get_gateways()

        self.assertEqual(sorted(name for _, name in gateways.keys()), ["gw-bw", "gw-istio", "gw-unknown"])
        for call in ctrl._custom_objects.list_cluster_custom_object.call_args_list:
            self.assertNotEqual(call.args[2], "gatewayclasses")

    def test_classes_not_readable_adopts_everything(self):
        ctrl = new_controller(readable=False)

        gateways = ctrl._get_gateways()

        self.assertEqual(sorted(name for _, name in gateways.keys()), ["gw-bw", "gw-istio", "gw-unknown"])
        for call in ctrl._custom_objects.list_cluster_custom_object.call_args_list:
            self.assertNotEqual(call.args[2], "gatewayclasses")

    def test_filter_set_bypasses_class_ownership(self):
        ctrl = new_controller(gateway_class="bunkerweb")

        gateways = ctrl._get_gateways()

        self.assertEqual(sorted(name for _, name in gateways.keys()), ["gw-bw"])
        for call in ctrl._custom_objects.list_cluster_custom_object.call_args_list:
            self.assertNotEqual(call.args[2], "gatewayclasses")

    def test_is_custom_event_gatewayclass_kind(self):
        ctrl = new_controller()
        self.assertTrue(ctrl._is_custom_event("GatewayClass", BUNKERWEB_CLASS, None, None, "bunkerweb"))

        ctrl_off = new_controller(skip_foreign_classes=False, readable=False)
        self.assertFalse(ctrl_off._is_custom_event("GatewayClass", BUNKERWEB_CLASS, None, None, "bunkerweb"))

    def test_is_custom_event_existing_route_kinds_unaffected(self):
        ctrl = new_controller()
        self.assertTrue(ctrl._is_custom_event("HTTPRoute", {}, None, "demo", "route"))
        self.assertFalse(ctrl._is_custom_event("ConfigMap", {}, None, "demo", "cm"))


if __name__ == "__main__":
    unittest.main()

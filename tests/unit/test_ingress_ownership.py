#!/usr/bin/env python3

from pathlib import Path
from sys import path as sys_path
from unittest.mock import MagicMock
import unittest

ROOT = Path(__file__).resolve().parents[2]
for rel in ("src/autoconf", "src/common/db", "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(ROOT / rel))

from kubernetes.client import (  # type: ignore  # noqa: E402
    V1Ingress,
    V1IngressClass,
    V1IngressClassSpec,
    V1IngressSpec,
    V1ObjectMeta,
)
from kubernetes.client.exceptions import ApiException  # type: ignore  # noqa: E402
from controllers.IngressController import IngressController  # type: ignore  # noqa: E402


def make_ingress(name: str, namespace: str = "demo", ingress_class_name=None, annotations=None) -> V1Ingress:
    return V1Ingress(
        metadata=V1ObjectMeta(name=name, namespace=namespace, annotations=annotations),
        spec=V1IngressSpec(ingress_class_name=ingress_class_name, rules=[]),
    )


def make_ingress_class(name: str, controller: str) -> V1IngressClass:
    return V1IngressClass(metadata=V1ObjectMeta(name=name), spec=V1IngressClassSpec(controller=controller))


def new_controller(ingress_class="", skip_foreign_classes=True, readable=None) -> IngressController:
    if readable is None:
        # Mirrors IngressController.__init__: a class filter always disables ownership filtering.
        readable = bool(skip_foreign_classes and not ingress_class)
    ctrl = IngressController.__new__(IngressController)
    ctrl._ingress_class = ingress_class
    ctrl._skip_foreign_classes = skip_foreign_classes
    ctrl._ingress_controller = "bunkerweb.io/ingress-controller"
    ctrl._ingress_classes_readable = readable
    ctrl._namespaces = []
    ctrl._logger = MagicMock()
    ctrl._networkingv1 = MagicMock()
    ctrl._owned_ingress_keys = set()
    ctrl._last_foreign_ingress_classes = None
    ctrl._should_ignore_annotation = lambda a: False
    return ctrl


ALB_CLASS = make_ingress_class("alb", "ingress.k8s.aws/alb")
BUNKERWEB_CLASS = make_ingress_class("bunkerweb", "bunkerweb.io/ingress-controller")

ALB_APP = make_ingress("alb-app", ingress_class_name="alb")
BW_APP = make_ingress("bw-app", ingress_class_name="bunkerweb")
PLAIN = make_ingress("plain")
LEGACY_FOREIGN = make_ingress("legacy-foreign", annotations={"kubernetes.io/ingress.class": "alb"})
LEGACY_UNKNOWN = make_ingress("legacy-unknown", annotations={"kubernetes.io/ingress.class": "traefik"})
NGINX_APP = make_ingress("nginx-app", ingress_class_name="nginx")

FIXTURE_1 = [ALB_APP, BW_APP, PLAIN, LEGACY_FOREIGN, LEGACY_UNKNOWN, NGINX_APP]


class IngressOwnershipTest(unittest.TestCase):
    def test_flag_yes_filters_foreign_classes(self):
        ctrl = new_controller()
        ctrl._networkingv1.list_ingress_for_all_namespaces.return_value = MagicMock(items=FIXTURE_1)
        ctrl._networkingv1.list_ingress_class.return_value = MagicMock(items=[ALB_CLASS, BUNKERWEB_CLASS])

        services = ctrl._get_controller_services()

        self.assertEqual([i.metadata.name for i in services], ["bw-app", "legacy-unknown", "nginx-app", "plain"])
        self.assertEqual(ctrl._owned_ingress_keys, {("demo", n) for n in ("bw-app", "legacy-unknown", "nginx-app", "plain")})

    def test_flag_no_adopts_everything_and_never_lists_classes(self):
        ctrl = new_controller(skip_foreign_classes=False, readable=False)
        ctrl._networkingv1.list_ingress_for_all_namespaces.return_value = MagicMock(items=FIXTURE_1)

        services = ctrl._get_controller_services()

        self.assertEqual(len(services), 6)
        ctrl._networkingv1.list_ingress_class.assert_not_called()

    def test_classes_not_readable_adopts_everything(self):
        ctrl = new_controller(readable=False)
        ctrl._networkingv1.list_ingress_for_all_namespaces.return_value = MagicMock(items=FIXTURE_1)

        services = ctrl._get_controller_services()

        self.assertEqual(len(services), 6)
        ctrl._networkingv1.list_ingress_class.assert_not_called()

    def test_filter_set_bypasses_class_ownership(self):
        ctrl = new_controller(ingress_class="bunkerweb")
        ctrl._networkingv1.list_ingress_for_all_namespaces.return_value = MagicMock(items=FIXTURE_1)

        services = ctrl._get_controller_services()

        self.assertEqual([i.metadata.name for i in services], ["bw-app"])
        ctrl._networkingv1.list_ingress_class.assert_not_called()

    def test_is_custom_event_uses_relist_snapshot_then_owned_keys(self):
        ctrl = new_controller()
        ctrl._networkingv1.list_ingress_for_all_namespaces.return_value = MagicMock(items=FIXTURE_1)
        ctrl._networkingv1.list_ingress_class.return_value = MagicMock(items=[ALB_CLASS, BUNKERWEB_CLASS])
        ctrl._get_controller_services()

        self.assertFalse(ctrl._is_custom_event("Ingress", ALB_APP, None, "demo", "alb-app"))

        ctrl._owned_ingress_keys.add(("demo", "alb-app"))
        self.assertTrue(ctrl._is_custom_event("Ingress", ALB_APP, None, "demo", "alb-app"))

        self.assertTrue(ctrl._is_custom_event("Ingress", PLAIN, None, "demo", "plain"))

    def test_is_custom_event_ingressclass_kind(self):
        ctrl = new_controller()
        self.assertTrue(ctrl._is_custom_event("IngressClass", ALB_CLASS, None, None, "alb"))

        ctrl_off = new_controller(skip_foreign_classes=False, readable=False)
        self.assertFalse(ctrl_off._is_custom_event("IngressClass", ALB_CLASS, None, None, "alb"))

    def test_patch_controller_status_only_patches_owned(self):
        ctrl = new_controller()
        ctrl._networkingv1.list_ingress_for_all_namespaces.return_value = MagicMock(items=FIXTURE_1)
        ctrl._networkingv1.list_ingress_class.return_value = MagicMock(items=[ALB_CLASS, BUNKERWEB_CLASS])
        ctrl._patch_ingress_status = MagicMock()

        ctrl._patch_controller_status(["1.2.3.4"])

        patched_names = sorted(call.args[0].metadata.name for call in ctrl._patch_ingress_status.call_args_list)
        self.assertEqual(patched_names, ["bw-app", "legacy-unknown", "nginx-app", "plain"])

    def test_probe_ingress_classes_warns_once_on_403(self):
        ctrl = new_controller()
        ctrl._ingress_classes_warned = False
        ctrl._networkingv1.list_ingress_class.side_effect = ApiException(status=403, reason="Forbidden")

        self.assertFalse(ctrl._probe_ingress_classes())
        self.assertFalse(ctrl._probe_ingress_classes())

        self.assertEqual(ctrl._logger.warning.call_count, 1)
        warning_message = ctrl._logger.warning.call_args[0][0]
        self.assertIn("ingressclasses", warning_message)


if __name__ == "__main__":
    unittest.main()

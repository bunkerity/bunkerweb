"""The IPv6 classification has TWO consumers, and they build different payloads from it.

`test_kubernetes_watch_health.py` covers `_is_ip_address` itself. That is one guard for one
behaviour, not one guard per code path: `IngressController._patch_ingress_status` files the result
as `{"ip": …}` / `{"hostname": …}`, while `GatewayController._patch_gateway_status` files it as
`{"type": "IPAddress"|"Hostname", "value": …}`. Reverting either call site to an IPv4-only regex
leaves the function's own tests green while that controller goes back to filing IPv6 literals as
hostnames -- which the API server rejects with a 422 that only appears in the controller's log.

So these assert the payload each call site actually produces, not that it calls the helper.
"""

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONTROLLERS = ROOT / "src" / "autoconf" / "controllers"


def _load(name: str, extra: dict):
    """Load one controller module by path with `kubernetes` and the package stubbed out.

    The real `KubernetesController` module is registered as `controllers.KubernetesController`
    first, so the class under test inherits the REAL `_is_ip_address`. Stubbing it here would
    make these tests pass against any implementation, which is the failure they exist to catch.
    """
    kubernetes = ModuleType("kubernetes")
    kubernetes.client = ModuleType("kubernetes.client")
    kubernetes.client.Configuration = object
    kubernetes.config = Mock()
    kubernetes.watch = Mock()
    exceptions = ModuleType("kubernetes.client.exceptions")

    class ApiException(Exception):
        def __init__(self, status=None, reason=None):
            super().__init__(f"{status} {reason}")
            self.status = status
            self.reason = reason

    exceptions.ApiException = ApiException
    kubernetes.client.exceptions = exceptions

    controllers = ModuleType("controllers")
    base = ModuleType("controllers.Controller")
    base.Controller = type("Controller", (), {})
    controllers.Controller = base

    stubs = {
        "kubernetes": kubernetes,
        "kubernetes.client": kubernetes.client,
        "kubernetes.client.exceptions": exceptions,
        "controllers": controllers,
        "controllers.Controller": base,
        **extra,
    }
    # RULE 16: a mutation run against a file another lane is editing must not touch the original.
    # `safe-mutate.py --copy` writes the mutant elsewhere; point this loader at it with e.g.
    # BW_CONTROLLER_GATEWAYCONTROLLER=/tmp/safe-mutate-xxxx/GatewayController.py
    source = Path(os.environ.get(f"BW_CONTROLLER_{name.upper()}", "")) if os.environ.get(f"BW_CONTROLLER_{name.upper()}") else CONTROLLERS / f"{name}.py"
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(f"bw_autoconf_{name}", source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


_K8S = _load("KubernetesController", {})
_K8S_ENTRY = ModuleType("controllers.KubernetesController")
_K8S_ENTRY.KubernetesController = _K8S.KubernetesController
_INGRESS = _load("IngressController", {"controllers.KubernetesController": _K8S_ENTRY})
_GATEWAY = _load("GatewayController", {"controllers.KubernetesController": _K8S_ENTRY})

# Both families, so a call site that silently reverts to an IPv4-only test is caught. Named so the
# floor below can assert it is still populated (RULE 13).
ADDRESSES = ["2001:db8::1", "::1", "fd00:1234:5678::abcd"]
HOSTNAMES = ["lb.example.com", "a1b2c3.elb.eu-west-1.amazonaws.com"]


def test_the_address_tables_are_populated():
    """Floor, not an exact count: growth is collaboration, another lane may add cases."""
    assert len(ADDRESSES) >= 3, "ADDRESSES emptied: both call-site tests collect nothing"
    assert len(HOSTNAMES) >= 2, "HOSTNAMES emptied: the hostname assertions collect nothing"
    assert all(":" in a for a in ADDRESSES), "ADDRESSES must stay IPv6 -- IPv4 passed the old regex too"


def _ingress():
    controller = object.__new__(_INGRESS.IngressController)
    controller._logger = Mock()
    controller._networkingv1 = Mock()
    ingress = Mock()
    ingress.metadata = Mock(name="ing", namespace="default")
    ingress.metadata.name = "ing"
    ingress.metadata.namespace = "default"
    return controller, ingress


def _gateway():
    controller = object.__new__(_GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._custom_objects = Mock()
    controller._gateway_api_group = "gateway.networking.k8s.io"
    controller._gateway_api_version = "v1"
    return controller, {"metadata": {"name": "gw", "namespace": "default"}}


def _sent_body(mock_call):
    """The two clients differ: Ingress passes `body=`, Gateway passes it as the last positional."""
    args, kwargs = mock_call.call_args
    if "body" in kwargs:
        return kwargs["body"]
    assert args, "patch called with neither a body= kwarg nor positional args"
    return args[-1]


class TestIngressCallSite:
    @pytest.mark.parametrize("address", ADDRESSES)
    def test_an_ipv6_literal_is_filed_as_an_ip(self, address):
        controller, ingress = _ingress()
        assert controller._patch_ingress_status(ingress, [address]) is True
        entries = _sent_body(controller._networkingv1.patch_namespaced_ingress_status)["status"]["loadBalancer"]["ingress"]
        assert entries == [{"ip": address}], f"{address} was filed as a hostname; the API server answers 422"

    @pytest.mark.parametrize("name", HOSTNAMES)
    def test_a_dns_name_is_still_filed_as_a_hostname(self, name):
        controller, ingress = _ingress()
        assert controller._patch_ingress_status(ingress, [name]) is True
        entries = _sent_body(controller._networkingv1.patch_namespaced_ingress_status)["status"]["loadBalancer"]["ingress"]
        assert entries == [{"hostname": name}]


class TestGatewayCallSite:
    @pytest.mark.parametrize("address", ADDRESSES)
    def test_an_ipv6_literal_is_typed_as_an_ipaddress(self, address):
        controller, gateway = _gateway()
        assert controller._patch_gateway_status(gateway, [address]) is True
        entries = _sent_body(controller._custom_objects.patch_namespaced_custom_object_status)["status"]["addresses"]
        assert entries == [{"type": "IPAddress", "value": address}], f"{address} was typed as a Hostname"

    @pytest.mark.parametrize("name", HOSTNAMES)
    def test_a_dns_name_is_still_typed_as_a_hostname(self, name):
        controller, gateway = _gateway()
        assert controller._patch_gateway_status(gateway, [name]) is True
        entries = _sent_body(controller._custom_objects.patch_namespaced_custom_object_status)["status"]["addresses"]
        assert entries == [{"type": "Hostname", "value": name}]


def test_both_families_reach_the_same_helper():
    """Mixed input in one call: the loop must classify per address, not once for the batch."""
    controller, ingress = _ingress()
    assert controller._patch_ingress_status(ingress, ["2001:db8::1", "lb.example.com", "10.0.0.1"]) is True
    entries = _sent_body(controller._networkingv1.patch_namespaced_ingress_status)["status"]["loadBalancer"]["ingress"]
    assert entries == [{"ip": "2001:db8::1"}, {"hostname": "lb.example.com"}, {"ip": "10.0.0.1"}]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

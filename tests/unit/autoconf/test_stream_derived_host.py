"""A stream service built from an Ingress or route annotated `SERVER_TYPE: stream` needs the unsuffixed `REVERSE_PROXY_HOST`.

The host the controller derives from the Ingress or route is stored unprefixed and numbered (`REVERSE_PROXY_HOST_1`).
Only `<server_name>_REVERSE_PROXY_HOST*` keys used to be converted, so the stream template found no
`REVERSE_PROXY_HOST`, rendered no backend, and left `http://...` in an unused HTTP snippet.
"""

import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _port_helpers import GATEWAY, INGRESS, bare_controller  # noqa: E402

FQDN = "app.edge.svc.cluster.local"
STREAM_KEYS = ("REVERSE_PROXY_HOST", "REVERSE_PROXY_URL")


def _gateway_controller():
    controller = object.__new__(GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._settings = {}
    controller._domain_name = "cluster.local"
    controller._service_protocol = "http"
    controller._reverse_proxy_suffix_start = 1
    controller._get_gateway_annotations = lambda svc: {}
    controller._get_listener_hostnames = lambda svc, protocols=None: []
    controller._get_listener_protocol = lambda svc, hostname, allowed_protocols=None: "HTTP"
    controller._get_listener_port = lambda *a, **kw: None
    controller._should_ignore_annotation = lambda annotation: False
    controller._api = Mock()
    controller._api.validate_setting.return_value = (True, None)
    return controller


def _http_route(port=80):
    return {
        "kind": "HTTPRoute",
        "metadata": {"name": "r", "namespace": "edge", "annotations": {"bunkerweb.io/SERVER_TYPE": "stream"}},
        "spec": {"hostnames": ["app.example.com"], "rules": [{"backendRefs": [{"name": "app", "port": port}]}]},
    }


def _ingress_controller():
    controller = bare_controller(INGRESS.IngressController)
    controller._settings = {}
    controller._reverse_proxy_suffix_start = 1
    controller._service_protocol = "http"
    controller._api = type("Api", (), {"validate_setting": staticmethod(lambda *a, **kw: (True, None))})()
    controller._corev1.list_namespaced_service.return_value.items = [NS(spec=NS(ports=[NS(name="http", port=80)]))]
    return controller


def _ingress(port=80):
    backend = NS(service=NS(name="app", port=NS(name=None, number=port)))
    return NS(
        metadata=NS(name="site", namespace="edge", annotations={"bunkerweb.io/SERVER_TYPE": "stream"}),
        spec=NS(rules=[NS(host="www.example.com", http=NS(paths=[NS(path="/", backend=backend)]))], tls=[]),
    )


def _assert_stream_backend(service, host):
    assert service["REVERSE_PROXY_HOST"] == host
    assert service["REVERSE_PROXY_URL"] == "/"
    leftovers = [key for key in service if key.startswith("REVERSE_PROXY_") and key not in STREAM_KEYS]
    assert leftovers == []


def test_gateway_derived_host_becomes_the_unsuffixed_stream_host():
    [service] = _gateway_controller()._to_services(_http_route(80))
    _assert_stream_backend(service, f"{FQDN}:80")


def test_gateway_derived_host_keeps_a_non_default_port():
    [service] = _gateway_controller()._to_services(_http_route(8080))
    _assert_stream_backend(service, f"{FQDN}:8080")


def test_ingress_derived_host_becomes_the_unsuffixed_stream_host():
    [service] = _ingress_controller()._to_services(_ingress(80))
    _assert_stream_backend(service, f"{FQDN}:80")


def test_ingress_derived_host_keeps_a_non_default_port():
    [service] = _ingress_controller()._to_services(_ingress(8080))
    _assert_stream_backend(service, f"{FQDN}:8080")


def test_gateway_extra_derived_hosts_are_dropped_with_a_warning():
    controller = _gateway_controller()
    route = _http_route(80)
    route["spec"]["rules"].append({"backendRefs": [{"name": "other", "port": 81}]})
    [service] = controller._to_services(route)
    _assert_stream_backend(service, f"{FQDN}:80")
    controller._logger.warning.assert_called()

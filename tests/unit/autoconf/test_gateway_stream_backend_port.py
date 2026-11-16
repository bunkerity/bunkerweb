"""A stream upstream needs an explicit port: nginx refuses `no port in upstream "<host>"` and the whole config with it.

`GatewayController._to_services` drops `:80` from `REVERSE_PROXY_HOST` because an HTTP upstream defaults to port 80.
That shortcut is wrong for TCPRoute, UDPRoute, TLSRoute (and an HTTPRoute attached to a TCP listener), which render
into `stream.conf`: every reload failed while the Gateway status still said `Programmed=True`.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_lb_address_call_sites import _K8S_ENTRY, _load  # noqa: E402

_GATEWAY = _load("GatewayController", {"controllers.KubernetesController": _K8S_ENTRY})

FQDN = "backend.default.svc.cluster.local"


def _controller(listener_protocol="HTTP"):
    controller = object.__new__(_GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._settings = {}
    controller._domain_name = "cluster.local"
    controller._service_protocol = "http"
    controller._reverse_proxy_suffix_start = 1
    controller._get_gateway_annotations = lambda svc: {}
    controller._get_listener_hostnames = lambda svc, protocols=None: []
    controller._get_listener_protocol = lambda svc, hostname, allowed_protocols=None: listener_protocol
    controller._get_listener_port = lambda *a, **kw: None
    return controller


def _route(kind, port):
    spec: dict = {"rules": [{"backendRefs": [{"name": "backend", "port": port}]}]}
    if kind in ("HTTPRoute", "TLSRoute"):
        spec["hostnames"] = ["app.example.com"]
    return {"kind": kind, "metadata": {"name": "r", "namespace": "default", "annotations": {}}, "spec": spec}


@pytest.mark.parametrize("kind", ["TCPRoute", "UDPRoute", "TLSRoute"])
@pytest.mark.parametrize("port", [80, 8080])
def test_a_stream_route_always_carries_the_backend_port(kind, port):
    service = _controller()._to_services(_route(kind, port))[0]
    assert service["SERVER_TYPE"] == "stream"
    assert service["REVERSE_PROXY_HOST"] == f"{FQDN}:{port}"


@pytest.mark.parametrize("port", [80, 8080])
def test_an_http_route_on_a_tcp_listener_is_a_stream_upstream(port):
    service = _controller("TCP")._to_services(_route("HTTPRoute", port))[0]
    assert service["SERVER_TYPE"] == "stream"
    assert service["REVERSE_PROXY_HOST"] == f"{FQDN}:{port}"


def test_an_http_route_on_port_80_keeps_the_implicit_port():
    service = _controller("HTTP")._to_services(_route("HTTPRoute", 80))[0]
    assert "SERVER_TYPE" not in service
    assert service["REVERSE_PROXY_HOST_1"] == f"http://{FQDN}"


def test_an_http_route_on_a_non_default_port_keeps_it():
    service = _controller("HTTP")._to_services(_route("HTTPRoute", 8080))[0]
    assert service["REVERSE_PROXY_HOST_1"] == f"http://{FQDN}:8080"


@pytest.mark.parametrize(
    "written,expected",
    [
        ("http://x.default.svc.cluster.local", "x.default.svc.cluster.local:80"),
        ("x.default.svc.cluster.local", "x.default.svc.cluster.local:80"),
        ("http://x.default.svc.cluster.local:8080", "x.default.svc.cluster.local:8080"),
        ("x.default.svc.cluster.local:9000", "x.default.svc.cluster.local:9000"),
    ],
)
def test_a_stream_host_set_by_annotation_gets_a_port_once_the_scheme_is_stripped(written, expected):
    controller = _controller()
    controller._should_ignore_annotation = lambda annotation: False
    controller._api = Mock()
    controller._api.validate_setting.return_value = (True, None)
    route = _route("HTTPRoute", 80)
    route["metadata"]["annotations"] = {"bunkerweb.io/SERVER_TYPE": "stream", "bunkerweb.io/app.example.com_REVERSE_PROXY_HOST": written}
    service = controller._to_services(route)[0]
    assert service["app.example.com_REVERSE_PROXY_HOST"] == expected

"""A stream host set by annotation must keep a port once the scheme is stripped: nginx refuses `no port in upstream`."""

from types import SimpleNamespace as NS

import pytest

from _port_helpers import INGRESS, bare_controller


@pytest.mark.parametrize(
    "written,expected",
    [
        ("http://x.edge.svc.cluster.local", "x.edge.svc.cluster.local:80"),
        ("x.edge.svc.cluster.local", "x.edge.svc.cluster.local:80"),
        ("http://x.edge.svc.cluster.local:8080", "x.edge.svc.cluster.local:8080"),
        ("x.edge.svc.cluster.local:9000", "x.edge.svc.cluster.local:9000"),
    ],
)
def test_a_stream_host_set_by_annotation_gets_a_port_once_the_scheme_is_stripped(written, expected):
    controller = bare_controller(INGRESS.IngressController)
    controller._settings = {}
    controller._reverse_proxy_suffix_start = 1
    controller._service_protocol = "http"
    controller._api = type("Api", (), {"validate_setting": staticmethod(lambda *a, **kw: (True, None))})()
    controller._corev1.list_namespaced_service.return_value.items = [NS(spec=NS(ports=[NS(name="http", port=80)]))]
    backend = NS(service=NS(name="app", port=NS(name=None, number=80)))
    ingress = NS(
        metadata=NS(
            name="site",
            namespace="edge",
            annotations={"bunkerweb.io/SERVER_TYPE": "stream", "bunkerweb.io/www.example.com_REVERSE_PROXY_HOST": written},
        ),
        spec=NS(rules=[NS(host="www.example.com", http=NS(paths=[NS(path="/", backend=backend)]))], tls=[]),
    )
    [service] = controller._to_services(ingress)
    assert service["www.example.com_REVERSE_PROXY_HOST"] == expected

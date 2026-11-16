"""An unresolved named Service port falls back to port 80 without aborting discovery."""

from types import SimpleNamespace as NS

import pytest

from _port_helpers import INGRESS, bare_controller


@pytest.mark.parametrize("ports", [None, [], [NS(name="other", port=8080)]])
def test_missing_named_service_port_falls_back_with_warning(ports):
    controller = bare_controller(INGRESS.IngressController)
    controller._settings = {}
    controller._reverse_proxy_suffix_start = 1
    controller._service_protocol = "http"
    controller._corev1.list_namespaced_service.return_value.items = [NS(spec=NS(ports=ports))]
    backend = NS(service=NS(name="app", port=NS(name="http", number=None)))
    ingress = NS(
        metadata=NS(name="site", namespace="edge", annotations={}),
        spec=NS(rules=[NS(host="www.example.com", http=NS(paths=[NS(path="/", backend=backend)]))], tls=[]),
    )
    [service] = controller._to_services(ingress)
    assert service["REVERSE_PROXY_HOST_1"] == "http://app.edge.svc.cluster.local"
    warning = " ".join(str(call) for call in controller._logger.warning.call_args_list)
    assert "edge/site" in warning
    assert "http" in warning
    assert "port 80" in warning

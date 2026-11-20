"""Named-port fallback diagnostics and Swarm instance discovery bookkeeping."""

import logging
from types import SimpleNamespace

import pytest
from _autoconf_helpers import attach_log
from kubernetes import client as k
from test_ingress_controller_services import build, ingress, meta, path, rule  # noqa: F401
from test_swarm_controller_labels import build as swarm_build, service, swarm_env  # noqa: F401


@pytest.mark.parametrize("ports", [None, [], [k.V1ServicePort(name="other", port=8080)]])
def test_missing_named_port_warns_once_and_keeps_other_ingresses(build, ports):  # noqa: F811
    ctrl = build()
    backend = k.V1Service(metadata=meta("api"), spec=k.V1ServiceSpec(ports=ports))
    ctrl._corev1.list_namespaced_service.side_effect = lambda namespace, **kw: SimpleNamespace(items=[backend])
    ctrl.networking.list_ingress_for_all_namespaces.return_value = SimpleNamespace(
        items=[
            ingress("named", rules=[rule("named.example.com", path("/", port_name="web"))]),
            ingress("numeric", rules=[rule("numeric.example.com", path("/", number=8081))]),
        ]
    )
    log = attach_log(ctrl)

    named, numeric = ctrl.get_services()

    assert named["REVERSE_PROXY_HOST_1"] == "http://api.prod.svc.cluster.local"
    assert numeric["REVERSE_PROXY_HOST_1"] == "http://api.prod.svc.cluster.local:8081"
    [warning] = log.messages(logging.WARNING)
    assert "prod/named" in warning
    assert "prod/api" in warning
    assert "web" in warning
    assert "port 80" in warning


def test_matching_named_port_80_does_not_warn(build):  # noqa: F811
    ctrl = build()
    backend = k.V1Service(metadata=meta("api"), spec=k.V1ServiceSpec(ports=[k.V1ServicePort(name="web", port=80)]))
    ctrl._corev1.list_namespaced_service.side_effect = lambda namespace, **kw: SimpleNamespace(items=[backend])
    log = attach_log(ctrl)

    [svc] = ctrl._to_services(ingress(rules=[rule("named.example.com", path("/", port_name="web"))]))

    assert svc["REVERSE_PROXY_HOST_1"] == "http://api.prod.svc.cluster.local"
    assert log.messages(logging.WARNING) == []


def test_swarm_discovery_replaces_departed_instance_ids(swarm_env):  # noqa: F811
    first = service("first", {"bunkerweb.INSTANCE": "yes"})
    second = service("second", {"bunkerweb.INSTANCE": "yes"})
    services = {"bunkerweb.INSTANCE": [first, first, second]}
    ctrl = swarm_build(services)

    ctrl.get_instances()
    assert ctrl._SwarmController__swarm_instances == [first.id, second.id]

    services["bunkerweb.INSTANCE"] = [second]
    ctrl.get_instances()
    assert ctrl._SwarmController__swarm_instances == [second.id]

    services["bunkerweb.INSTANCE"] = []
    ctrl.get_instances()
    assert ctrl._SwarmController__swarm_instances == []

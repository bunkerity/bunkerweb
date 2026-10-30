"""Regression tests for defects found while writing the autoconf controller tests (BW-542, BW-543)."""

from types import SimpleNamespace

from kubernetes import client as k
from test_ingress_controller_services import build, ingress, meta, path, rule  # noqa: F401
from test_swarm_controller_labels import build as swarm_build, service as swarm_service, swarm_env  # noqa: F401


def test_a_named_port_on_a_service_without_ports_does_not_break_the_whole_apply(build):  # noqa: F811
    ctrl = build()
    external = k.V1Service(metadata=meta("api"), spec=k.V1ServiceSpec(ports=None, type="ExternalName", external_name="x.example.com"))
    ctrl._corev1.list_namespaced_service.side_effect = lambda namespace, **kw: SimpleNamespace(items=[external])

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/", port_name="web"))]))

    assert svc["SERVER_NAME"] == "a.example.com"


def test_swarm_instance_ids_are_remembered_once(swarm_env):  # noqa: F811
    tasks = [{"ID": "t", "NodeID": "n", "DesiredState": "running", "Status": {"State": "running"}}]
    bw = swarm_service("bw", {"bunkerweb.INSTANCE": "yes"}, env=[], tasks=tasks, sid="bw1")
    ctrl = swarm_build({"bunkerweb.INSTANCE": [bw]})

    for _ in range(3):
        ctrl.get_instances()

    assert ctrl._SwarmController__swarm_instances == ["bw1"]

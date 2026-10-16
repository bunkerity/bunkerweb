"""Configuration delivery must not wait for the readiness that configuration enables."""

import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lb_address_call_sites import _K8S


def _pod():
    return NS(
        metadata=NS(name="bw", namespace="default", deletion_timestamp=None),
        spec=NS(containers=[NS(name="bunkerweb", env=[NS(name="API_HTTP_PORT", value="5000")])]),
        status=NS(
            pod_ip="10.0.0.2",
            phase="Running",
            conditions=[NS(type="Ready", status="False")],
            container_statuses=[NS(name="bunkerweb", state=NS(running=NS()))],
        ),
    )


def _instance(pod):
    controller = object.__new__(_K8S.KubernetesController)
    controller._logger = Mock()
    controller._domain_name = "cluster.local"
    controller._use_fqdn = True
    controller._get_controller_services = lambda: []
    return controller._to_instances(pod)[0]


def test_running_unready_container_can_receive_configuration():
    instance = _instance(_pod())
    assert instance["health"] is True
    assert instance["hostname"] == "10-0-0-2.default.pod.cluster.local"
    assert instance["env"] == {"API_HTTP_PORT": "5000"}


@pytest.mark.parametrize("case", ["pending", "missing-ip", "deleting", "not-running", "sidecar-only", "missing-status", "missing-container-status"])
def test_unavailable_container_is_not_healthy_even_if_ready(case):
    pod = _pod()
    pod.status.conditions[0].status = "True"
    if case == "pending":
        pod.status.phase = "Pending"
    elif case == "missing-ip":
        pod.status.pod_ip = None
    elif case == "deleting":
        pod.metadata.deletion_timestamp = "2026-10-16T00:00:00Z"
    elif case == "not-running":
        pod.status.container_statuses[0].state.running = None
    elif case == "sidecar-only":
        pod.status.container_statuses[0].name = "sidecar"
    elif case == "missing-status":
        pod.status = None
    else:
        pod.status.container_statuses = None
    assert _instance(pod)["health"] is False


@pytest.mark.parametrize("ready", ["True", "False"])
def test_legacy_container_name_keeps_readiness_discovery(ready):
    pod = _pod()
    pod.spec.containers[0].name = "legacy"
    pod.status.conditions[0].status = ready
    assert _instance(pod)["health"] is (ready == "True")

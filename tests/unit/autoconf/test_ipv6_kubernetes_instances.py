"""Pod instance hostnames follow Kubernetes DNS separator encoding."""

import pytest
from test_kubernetes_controller_core import K8s, pod


@pytest.mark.parametrize(
    ("ip", "hostname"),
    [
        ("2001:db8::1", "2001-db8--1.prod.pod.cluster.local"),
        ("2001:db8:1:2:3:4:5:6", "2001-db8-1-2-3-4-5-6.prod.pod.cluster.local"),
        ("10.0.0.5", "10-0-0-5.prod.pod.cluster.local"),
        (None, "bw-0.prod.pod.cluster.local"),
    ],
)
def test_default_pod_fqdn(k8s_env, ip, hostname):
    [instance] = K8s()._to_instances(pod(ip=ip))

    assert instance["hostname"] == hostname


def test_ipv6_pod_fqdn_uses_configured_domain(k8s_env):
    k8s_env.setenv("KUBERNETES_DOMAIN_NAME", "corp.local")

    assert K8s()._to_instances(pod(ip="2001:db8::1", namespace="edge"))[0]["hostname"] == "2001-db8--1.edge.pod.corp.local"


@pytest.mark.parametrize("ip", ["2001:db8::1", "10.0.0.5", None])
def test_raw_pod_address_is_preserved(k8s_env, ip):
    k8s_env.setenv("USE_KUBERNETES_FQDN", "no")

    assert K8s()._to_instances(pod(ip=ip))[0]["hostname"] == (ip or "bw-0")

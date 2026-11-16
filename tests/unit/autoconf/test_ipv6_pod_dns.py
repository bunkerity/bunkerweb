"""IPv6 pod DNS labels encode colons as hyphens; raw IP mode preserves addresses."""

from types import SimpleNamespace as NS

import pytest

from _port_helpers import bare_controller


@pytest.mark.parametrize(
    "ip,hostname",
    [
        ("2001:db8::1", "2001-db8--1.edge.pod.cluster.local"),
        ("2001:db8:1:2:3:4:5:6", "2001-db8-1-2-3-4-5-6.edge.pod.cluster.local"),
        ("10.0.0.2", "10-0-0-2.edge.pod.cluster.local"),
        (None, "bw-0.edge.pod.cluster.local"),
    ],
)
def test_pod_dns_name(ip, hostname):
    controller = bare_controller()
    pod = NS(metadata=NS(name="bw-0", namespace="edge"), status=NS(pod_ip=ip, conditions=[]), spec=NS(containers=[]))
    assert controller._to_instances(pod)[0]["hostname"] == hostname


def test_raw_ipv6_pod_address_is_preserved():
    controller = bare_controller()
    controller._use_fqdn = False
    pod = NS(metadata=NS(name="bw-0", namespace="edge"), status=NS(pod_ip="2001:db8::1", conditions=[]), spec=NS(containers=[]))
    assert controller._to_instances(pod)[0]["hostname"] == "2001:db8::1"

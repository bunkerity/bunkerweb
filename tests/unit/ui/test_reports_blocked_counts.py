"""Stored reports count as blocked unless security mode is detect (dev 64be0c6ac)."""

from datetime import datetime

import pytest

from app.models.instance import InstancesUtils


@pytest.mark.parametrize("status,protocol", [(400, "http"), (451, "http"), (500, "tcp"), (200, "udp"), (403, "http")])
@pytest.mark.parametrize("security_mode,blocked", [("block", 1), ("detect", 0), (None, 1)])
def test_blocked_counts_follow_security_mode(status, protocol, security_mode, blocked):
    utils = object.__new__(InstancesUtils)
    report = {
        "id": "report",
        "date": datetime.now().astimezone().timestamp(),
        "ip": "192.0.2.1",
        "country": "FR",
        "status": status,
        "protocol": protocol,
    }
    if security_mode is not None:
        report["security_mode"] = security_mode
    utils._iter_instance_api_requests = lambda: iter([report])

    result = utils._compute_home_aggregates(hours=2, top_ips_limit=10, redis_client=None)

    assert result["request_countries"] == ({"FR": {"blocked": 1}} if blocked else {})
    assert result["top_blocked_ips"] == ({"192.0.2.1": {"blocked": 1}} if blocked else {})
    assert result["blocked_unique_ips"] == blocked
    assert sum(result["time_buckets"].values()) == blocked
    assert result["request_statuses"] == {status: 1}

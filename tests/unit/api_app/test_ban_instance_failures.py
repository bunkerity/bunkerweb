"""UB4-2: ban/unban responses preserve instance failures, including across bulk targets."""

import pytest

from _api_http_helpers import ADMIN_HEADERS, router_client

from ApiCaller import ApiCaller
import app.routers.bans as bans
from app.deps import get_instances_api_caller


class Instance:
    """Only the instance transport is replaced; ApiCaller's failure aggregation stays real."""

    def __init__(self, hostname, first_status):
        self.endpoint = f"http://{hostname}:5000"
        self.first_status = first_status
        self.calls = []

    def request(self, method, path, *, data, **_):
        self.calls.append((method, path, data))
        status = self.first_status if data["ip"] == "192.0.2.1" else 200
        return status is not None, "connection refused" if status is None else "", status, {"msg": "ok" if status == 200 else "failed"}


@pytest.mark.parametrize(
    "method,path,instance_path", [("POST", "/bans", "/ban"), ("POST", "/bans/ban", "/ban"), ("DELETE", "/bans", "/unban"), ("POST", "/bans/unban", "/unban")]
)
@pytest.mark.parametrize(
    "statuses",
    [(200, 200), (500, 500), (500, 200), (200, 500), (None, None), (None, 200)],
    ids=["all-succeed", "all-http-fail", "first-http-fails", "last-http-fails", "all-unreachable", "one-unreachable"],
)
@pytest.mark.parametrize("bulk", [False, True], ids=["single-target", "failed-target-before-successful-target"])
def test_ban_and_unban_report_instance_failures(monkeypatch, method, path, instance_path, statuses, bulk):
    client = router_client(monkeypatch, bans, object())
    monkeypatch.setattr(bans, "CrowdSecClient", lambda _db: object())
    monkeypatch.setattr(bans, "find_lease", lambda *_: None)
    instances = [Instance(f"bw{index}", status) for index, status in enumerate(statuses, start=1)]
    client.app.dependency_overrides[get_instances_api_caller] = lambda: ApiCaller(instances)
    targets = [{"ip": "192.0.2.1"}, {"ip": "192.0.2.2"}] if bulk else [{"ip": "192.0.2.1"}]

    response = client.request(method, path, json=targets if bulk else targets[0], headers=ADMIN_HEADERS)

    all_ok = all(status == 200 for status in statuses)
    assert response.status_code == (200 if all_ok else 502), response.text
    assert response.json() == {"status": "success" if all_ok else "error"}
    for instance in instances:
        assert [(method, path, data["ip"], data["ban_scope"]) for method, path, data in instance.calls] == [
            ("POST", instance_path.lstrip("/"), target["ip"], "global") for target in targets
        ]

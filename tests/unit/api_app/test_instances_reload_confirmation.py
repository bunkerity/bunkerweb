"""Both reload routes keep their shape and only acknowledge confirmed readiness."""

from types import SimpleNamespace

import pytest

from ApiCaller import ApiCaller
import reload_utils
from _api_http_helpers import ADMIN_HEADERS
import app.deps as deps
import app.routers.instances as instances
import test_route_permission_matrix

api_routes = test_route_permission_matrix.api_routes


@pytest.mark.parametrize("single", [False, True])
@pytest.mark.parametrize("outcome", ["confirmed", "pending", "rejected", "poll-error", "timeout"])
def test_reload_requires_confirmation(api_routes, monkeypatch, single, outcome):
    now = [0.0]
    monkeypatch.setattr(reload_utils, "monotonic", lambda: now[0])
    monkeypatch.setattr(reload_utils, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    api = SimpleNamespace(endpoint="http://node:5000/", calls=[])
    states = ["reloading", "ok"] if outcome == "confirmed" else ["reloading"]

    def request(method, url, **kwargs):
        api.calls.append((method, url, kwargs))
        if method == "POST":
            return (True, "", 500, {"status": "error"}) if outcome == "rejected" else (True, "", 200, {"status": "success", "confirmed": False})
        if outcome == "timeout":
            now[0] += sum(kwargs["timeout"])
            raise TimeoutError("health timed out")
        if outcome == "poll-error":
            return True, "", 500, {"status": "error", "msg": "initialization failed"}
        return True, "", 200, {"status": "success", "msg": states.pop(0) if len(states) > 1 else states[0]}

    api.request = request
    application = api_routes.client.app
    application.dependency_overrides[deps.get_instances_api_caller] = lambda: ApiCaller([api])
    application.dependency_overrides[deps.get_api_for_hostname] = lambda: api
    monkeypatch.setattr(instances, "ApiCaller", ApiCaller)
    response = api_routes.client.post("/instances/node/reload" if single else "/instances/reload", headers=ADMIN_HEADERS)
    expected = "success" if outcome == "confirmed" else "pending" if outcome in {"pending", "timeout"} else "error"
    assert response.json() == {"status": expected}
    assert response.status_code == (502 if expected == "error" else 200)
    assert sum(method == "POST" for method, _, _ in api.calls) == 1
    if outcome != "rejected":
        assert any(method == "GET" for method, _, _ in api.calls)
    assert now[0] <= 5

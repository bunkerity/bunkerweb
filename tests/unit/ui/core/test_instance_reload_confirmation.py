"""UI reload messages must describe unconfirmed readiness as pending."""

from types import SimpleNamespace

import pytest

from ApiCaller import ApiCaller
import reload_utils
from test_instance_api_calls import make


@pytest.mark.parametrize("outcome", ["confirmed", "pending", "rejected", "poll-error", "timeout"])
def test_manual_reload_requires_confirmation(monkeypatch, outcome):
    now = [0.0]
    monkeypatch.setattr(reload_utils, "monotonic", lambda: now[0])
    monkeypatch.setattr(reload_utils, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    api = SimpleNamespace(endpoint="http://bw1:5000/", calls=[])
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
    message = make(ApiCaller([api])).reload()
    assert (message == "Instance bw1 has been reloaded.") is (outcome == "confirmed")
    if outcome != "confirmed":
        assert message.startswith("Can't reload")
    if outcome in {"pending", "timeout"}:
        assert "pending" in message
    assert sum(method == "POST" for method, _, _ in api.calls) == 1
    if outcome != "rejected":
        assert any(method == "GET" for method, _, _ in api.calls)
    assert now[0] <= 5

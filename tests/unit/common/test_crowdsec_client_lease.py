"""CrowdSec client additions for the lease unban flow: a per-instance request, lease removal, `refresh_ip`.

The lease reply shape is lane C's (`api.lua`): `{"status": "success", "msg": "lease <result>", "result": <result>}`."""

import pytest

from test_crowdsec_client import _API, _load_client

INSTANCE = {"hostname": "bw-one", "status": "up", "credential": "one-secret", "local_id": "a" * 64}
LEASE_ID = "0123456789abcdef"


class _Recorder:
    """An instance API that records the requests and answers with a canned reply."""

    def __init__(self, status=200, payload=None):
        self.calls = []
        self.reply = (True, "", status, payload)

    def request(self, method, path, data=None, timeout=None):
        self.calls.append((method, path, data))
        return self.reply


@pytest.fixture
def module(monkeypatch):
    return _load_client()


def _client(module, recorder, monkeypatch):
    monkeypatch.setattr(_API, "from_instance", classmethod(lambda cls, instance, *, token=None: recorder))
    db = type("DB", (), {"get_instances": lambda self, **_kwargs: [INSTANCE]})()
    return module.CrowdSecClient(db)


def test_instance_request_returns_the_listing(module, monkeypatch):
    recorder = _Recorder(payload={"status": "success", "data": [{"ip": "1.2.3.4"}]})
    assert _client(module, recorder, monkeypatch).instance_request(INSTANCE, "GET", "/bans") == [{"ip": "1.2.3.4"}]
    assert recorder.calls == [("GET", "/bans", None)]


def test_instance_request_reads_an_empty_ban_listing(module, monkeypatch):
    recorder = _Recorder(payload={"status": "success", "msg": ""})
    assert _client(module, recorder, monkeypatch).instance_request(INSTANCE, "GET", "/bans") == []


@pytest.mark.parametrize("outcome", ["removed", "absent", "changed"])
def test_remove_lease_posts_the_lease_id_and_returns_the_outcome(module, monkeypatch, outcome):
    recorder = _Recorder(payload={"status": "success", "msg": f"lease {outcome}", "result": outcome})

    result = _client(module, recorder, monkeypatch).remove_lease(INSTANCE, "1.2.3.4", "global", None, LEASE_ID)

    assert result == outcome
    assert recorder.calls == [("POST", "/unban", {"ip": "1.2.3.4", "ban_scope": "global", "lease_id": LEASE_ID})]


def test_remove_lease_for_a_service_names_the_service(module, monkeypatch):
    recorder = _Recorder(payload={"status": "success", "msg": "lease removed", "result": "removed"})
    _client(module, recorder, monkeypatch).remove_lease(INSTANCE, "1.2.3.4", "service", "app.example.com", LEASE_ID)
    assert recorder.calls == [("POST", "/unban", {"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com", "lease_id": LEASE_ID})]


@pytest.mark.parametrize(
    "payload", [{"status": "success", "result": "maybe"}, {"status": "success", "msg": "lease removed"}, {"status": "success", "msg": "ip 1.2.3.4 unbanned"}]
)
def test_remove_lease_refuses_a_reply_that_is_not_one_of_the_three_outcomes(module, monkeypatch, payload):
    # A reply from an instance that ignores `lease_id` and ran the generic unban would be mistaken for success otherwise.
    recorder = _Recorder(payload=payload)
    with pytest.raises(module.CrowdSecError):
        _client(module, recorder, monkeypatch).remove_lease(INSTANCE, "1.2.3.4", "global", None, LEASE_ID)


def test_remove_lease_surfaces_an_instance_failure(module, monkeypatch):
    recorder = _Recorder(status=500, payload={"status": "error", "msg": "boom"})
    with pytest.raises(module.CrowdSecError) as caught:
        _client(module, recorder, monkeypatch).remove_lease(INSTANCE, "1.2.3.4", "global", None, LEASE_ID)
    assert caught.value.status == 502
    assert "boom" not in str(caught.value)  # transport errors outside /crowdsec/ can carry secrets


def test_refresh_ip_is_a_known_operation(module, monkeypatch):
    recorder = _Recorder(payload={"status": "success", "data": {"refreshed": True}})
    connection_id = module.encode_connection("bw-one", INSTANCE["local_id"])

    result = _client(module, recorder, monkeypatch).query(connection_id, "refresh_ip", {"ip": "1.2.3.4"})

    assert result == {"refreshed": True}
    assert recorder.calls == [("POST", "/crowdsec/refresh_ip", {"ip": "1.2.3.4", "connection": INSTANCE["local_id"]})]

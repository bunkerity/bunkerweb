"""The public API stores a ban under the canonical spelling of its address and refuses a target that is not an address.

One IPv6 address is one ban: an expanded or upper case spelling, an IPv4-mapped IPv6 address and a zone id all reach
the instances as the one canonical text (or are refused with 422 before any instance is called). Real guard and real
router; the instances are a recorder.

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

import pytest
from _api_http_helpers import ADMIN_HEADERS, router_client  # type: ignore

import app.routers.bans as bans_mod  # noqa: E402
from app.deps import get_instances_api_caller  # noqa: E402


class Recorder:
    def __init__(self):
        self.sent = []

    def send_to_apis(self, method, path, data=None, response=False, **_):
        self.sent.append((method, path, data))
        return True, ({} if response else None)


@pytest.fixture
def client_and_recorder(monkeypatch):
    client = router_client(monkeypatch, bans_mod, object())
    # no CrowdSec lease behind any address here: an explicit unban goes straight to the instances
    monkeypatch.setattr(bans_mod, "CrowdSecClient", lambda _db: object())
    monkeypatch.setattr(bans_mod, "find_lease", lambda *_a, **_k: None)
    recorder = Recorder()
    client.app.dependency_overrides[get_instances_api_caller] = lambda: recorder
    return client, recorder


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
        ("2001:db8::1", "2001:db8::1"),
        ("::ffff:192.0.2.1", "192.0.2.1"),
        ("::FFFF:C000:201", "192.0.2.1"),
        (" 192.0.2.1 ", "192.0.2.1"),
    ],
)
def test_a_ban_reaches_the_instances_under_the_canonical_address(client_and_recorder, given, stored):
    client, recorder = client_and_recorder
    response = client.post("/bans/ban", json={"ip": given}, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    assert [(m, p, d["ip"]) for m, p, d in recorder.sent] == [("POST", "/ban", stored)]


@pytest.mark.parametrize(
    ("given", "stored"),
    [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1")],
)
def test_an_unban_reaches_the_instances_under_the_canonical_address(client_and_recorder, given, stored):
    client, recorder = client_and_recorder
    response = client.post("/bans/unban", json={"ip": given}, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    unbans = [d["ip"] for m, p, d in recorder.sent if m == "POST" and p == "/unban"]
    assert unbans == [stored]


@pytest.mark.parametrize("bad", ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::1/64"])
def test_a_target_that_is_not_a_bare_address_is_refused_before_any_instance_is_called(client_and_recorder, bad):
    client, recorder = client_and_recorder
    response = client.post("/bans/ban", json=[{"ip": "192.0.2.9"}, {"ip": bad}], headers=ADMIN_HEADERS)
    assert response.status_code == 422, response.text
    assert recorder.sent == [], "a half applied request: the valid first item was already banned"
    response = client.post("/bans/unban", json={"ip": bad}, headers=ADMIN_HEADERS)
    assert response.status_code == 422, response.text
    assert recorder.sent == []

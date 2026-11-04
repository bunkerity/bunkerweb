"""app/models/instance.py, ``Instance``: every instance action turns the API reply into the message the UI shows.

``ApiCaller`` is a scripted fake (``conftest.FakeApiCaller``), so each test pins both the request the
UI sends (method, path, payload, timeout) and the message it builds from the reply.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models.instance import Instance, decode_search_panes, encode_search_panes, _copy_home_aggregates, _parse_count

NOW = datetime(2026, 10, 26, 12, 0, 0)


def make(caller, hostname="bw1", name="bw1.local"):
    return Instance(hostname, name, "ui", "up", "static", NOW, NOW, caller)


class TestSearchPanes:
    def test_round_trip_with_separators_inside_values(self):
        panes = {"url": ["/a,b", "/c;d", "100%"], "status": ["403"]}
        encoded = encode_search_panes(panes)
        assert "," in encoded and encoded.count(";") == 1  # separators of the format only, values are percent-encoded
        assert decode_search_panes(encoded) == panes

    def test_empty_and_malformed(self):
        assert decode_search_panes("") == {}
        assert decode_search_panes("novalue;ip:1.2.3.4") == {"ip": ["1.2.3.4"]}
        assert encode_search_panes({}) == ""


class TestParseCount:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(5, 5), (5.9, 5), ("10", 10), (" 10K ", 10000), ("2m", 2000000), ("1.5k", 7), ("-3", 7), ("1e3", 7), ("", 7), (None, 7), ("k", 7)],
    )
    def test_shorthand(self, value, expected):
        assert _parse_count(value, 7) == expected

    def test_unprintable_value_falls_back(self):
        class Bad:
            def __str__(self):
                raise RuntimeError

        assert _parse_count(Bad(), 3) == 3


def test_copy_home_aggregates_is_isolated_from_the_source():
    source = {
        "request_countries": {"FR": {"blocked": 1}},
        "top_blocked_ips": {"1.1.1.1": {"blocked": 2}},
        "blocked_unique_ips": 1,
        "time_buckets": {"t": 1},
        "request_statuses": {403: 1},
    }
    copy = _copy_home_aggregates(source)
    copy["request_countries"]["FR"]["blocked"] = 99
    copy["time_buckets"]["t"] = 99
    assert source["request_countries"]["FR"]["blocked"] == 1 and source["time_buckets"]["t"] == 1
    assert _copy_home_aggregates({}) == {"request_countries": {}, "top_blocked_ips": {}, "blocked_unique_ips": 0, "time_buckets": {}, "request_statuses": {}}


class TestConstruction:
    def test_missing_caller_gets_a_default_one(self):
        assert make(None).apiCaller is not None

    def test_id_is_the_hostname(self, fake_caller):
        assert make(fake_caller()).id == "bw1"

    def test_from_hostname(self):
        db = MagicMock()
        db.get_instance.return_value = None
        assert Instance.from_hostname("nope", db) is None
        db.get_instance.return_value = {
            "hostname": "bw1",
            "server_name": "bwapi",
            "method": "scheduler",
            "status": "up",
            "type": "container",
            "creation_date": NOW,
            "last_seen": NOW,
            "port": 5000,
        }
        built = Instance.from_hostname("bw1", db)
        assert (built.hostname, built.name, built.method, built.status, built.type) == ("bw1", "bwapi", "scheduler", "up", "container")
        db.get_instance.assert_called_with("bw1")


class TestLifecycle:
    def test_reload_requests_a_tested_reload_by_default(self, fake_caller, monkeypatch):
        monkeypatch.delenv("DISABLE_CONFIGURATION_TESTING", raising=False)
        caller = fake_caller(default=(True, {}))
        assert make(caller).reload() == "Instance bw1 has been reloaded."
        method, url, kwargs = caller.calls[0]
        assert (method, url) == ("POST", "/reload?test=yes")
        assert kwargs["timeout"][0] == 5 and kwargs["timeout"][1] >= 15

    def test_reload_can_skip_configuration_testing(self, fake_caller, monkeypatch):
        monkeypatch.setenv("DISABLE_CONFIGURATION_TESTING", "YES")
        caller = fake_caller()
        make(caller).reload()
        assert caller.calls[0][1] == "/reload?test=no"

    def test_reload_failures(self, fake_caller):
        assert make(fake_caller(default=(False, {}))).reload() == "Can't reload instance bw1"
        assert make(fake_caller(default=TimeoutError("slow"))).reload() == "Can't reload instance bw1: slow"

    def test_start_is_not_implemented(self, fake_caller):
        with pytest.raises(NotImplementedError):
            make(fake_caller()).start()

    @pytest.mark.parametrize(("action", "path", "done"), [("stop", "/stop", "stopped"), ("restart", "/restart", "restarted")])
    def test_stop_and_restart(self, fake_caller, action, path, done):
        caller = fake_caller()
        assert getattr(make(caller), action)() == f"Instance bw1 has been {done}."
        assert caller.calls[0][:2] == ("POST", path)
        assert getattr(make(fake_caller(default=(False, {}))), action)() == f"Can't {action} instance bw1"
        assert getattr(make(fake_caller(default=OSError("x"))), action)() == f"Can't {action} instance bw1: x"


class TestBanUnban:
    def test_global_ban_message_and_payload(self, fake_caller):
        caller = fake_caller()
        msg = make(caller).ban("1.2.3.4", 60, "spam", "_", "global")
        assert msg == "IP 1.2.3.4 has been banned globally on instance bw1 for 60 seconds with reason: spam."
        assert caller.calls[0][2]["data"] == {"ip": "1.2.3.4", "exp": 60, "reason": "spam", "service": "_", "ban_scope": "global"}

    def test_service_scope_kept_for_a_real_service(self, fake_caller):
        caller = fake_caller()
        msg = make(caller).ban("1.2.3.4", 5, "", "www.example.com", "service")
        assert msg == "IP 1.2.3.4 has been banned for service www.example.com on instance bw1 for 5 seconds."
        assert caller.calls[0][2]["data"]["ban_scope"] == "service"

    @pytest.mark.parametrize("service", ["", None, "unknown", "Web UI", "bwcli", "default server"])
    def test_service_scope_degrades_to_global_for_missing_or_reserved_service(self, fake_caller, service):
        caller = fake_caller()
        make(caller).ban("1.2.3.4", 5, "r", service, "service")
        assert caller.calls[0][2]["data"]["ban_scope"] == "global"

    def test_invalid_scope_is_global(self, fake_caller):
        caller = fake_caller()
        make(caller).ban("1.2.3.4", 5, "r", "svc", "galaxy")
        assert caller.calls[0][2]["data"]["ban_scope"] == "global"

    def test_ban_failures(self, fake_caller):
        assert make(fake_caller(default=(False, {}))).ban("1.1.1.1", 1, "", "_") == "Can't ban 1.1.1.1 on instance bw1"
        assert make(fake_caller(default=OSError("net"))).ban("1.1.1.1", 1, "", "_") == "Can't ban 1.1.1.1 on instance bw1: net"

    def test_unban_payload_and_messages(self, fake_caller):
        caller = fake_caller()
        assert make(caller).unban("1.2.3.4") == "IP 1.2.3.4 has been unbanned on instance bw1."
        assert caller.calls[0][2]["data"] == {"ip": "1.2.3.4", "ban_scope": "global"}
        assert make(caller).unban("1.2.3.4", "svc", "service") == "IP 1.2.3.4 has been unbanned for service svc on instance bw1."
        assert caller.calls[1][2]["data"] == {"ip": "1.2.3.4", "ban_scope": "service", "service": "svc"}

    def test_unban_never_sends_a_reserved_service(self, fake_caller):
        caller = fake_caller()
        make(caller).unban("1.2.3.4", "unknown")
        assert "service" not in caller.calls[0][2]["data"]

    def test_unban_failures(self, fake_caller):
        assert make(fake_caller(default=(False, {}))).unban("1.1.1.1") == "Can't unban 1.1.1.1 on instance bw1"
        assert make(fake_caller(default=OSError("net"))).unban("1.1.1.1", "svc") == "Can't unban 1.1.1.1 for service svc on instance bw1: net"


class TestReads:
    def test_bans(self, fake_caller):
        assert make(fake_caller(default=(True, {"bw1": {"data": []}}))).bans() == ("", {"bw1": {"data": []}})
        assert make(fake_caller(default=(False, {"e": 1}))).bans() == ("Can't get bans from instance bw1", {"e": 1})
        assert make(fake_caller(default=OSError("x"))).bans() == ("Can't get bans from instance bw1: x", {})

    def test_reports_query_encodes_search_and_panes(self, fake_caller):
        caller = fake_caller()
        make(caller).reports_query(5, 20, "a b&c", "ip", "asc", "url:/x y", True)
        method, url, kwargs = caller.calls[0]
        assert method == "GET" and kwargs == {"response": True}
        assert url == "/metrics/requests/query?start=5&length=20&search=a%20b%26c&order_column=ip&order_dir=asc&search_panes=url%3A/x%20y&count_only=true"

    def test_passthrough_endpoints(self, fake_caller):
        caller = fake_caller(default=(True, {"ok": 1}))
        inst = make(caller)
        assert inst.reports() == (True, {"ok": 1})
        inst.metrics("limit")
        inst.metrics_redis()
        inst.data("jobs")
        assert [c[1] for c in caller.calls] == ["/metrics/requests", "/metrics/limit", "/redis/stats", "/jobs"]
        assert all(c[2] == {"response": True} for c in caller.calls)

    def test_ping(self, fake_caller):
        assert make(fake_caller(default=(True, {"p": 1}))).ping() == ("Instance bw1 is up", {"p": 1})
        assert make(fake_caller(default=(False, {"p": 2}))).ping() == ("Can't ping instance bw1", {"p": 2})
        assert make(fake_caller(default=OSError("x"))).ping() == ("Can't ping instance bw1: x", {})
        caller = fake_caller(default=(True, {}))
        make(caller).ping("antibot")
        assert caller.calls[0][:2] == ("POST", "/antibot/ping") and caller.calls[0][2] == {"response": True}

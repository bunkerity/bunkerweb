"""``sync-bans`` projection helpers — the half of ban convergence that writes back out.

Two things here can break the fleet quietly, so both are pinned:

* ``exp == 0`` means *permanent* on the wire (``utils.add_ban``). A ban a fraction of a second from
  expiry must never be pushed as 0, or every instance receiving it holds it forever.
* Under Redis the instances must NOT be pushed to. They materialize a Redis ban lazily on the first
  request from that IP, so "missing from the shared dict" is the healthy state; pushing anyway
  resets every ban's date on every pass and fills the 64 MB datastore.

The job is a script, not a module: importing it runs it and ends in ``sys_exit``. Only its
definitions are loaded.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "sync-bans.py"


def _load_definitions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("jobs", "logger", "API", "ApiCaller", "common_utils")}
    stubs["jobs"].Job = Mock()
    stubs["logger"].getLogger = Mock(return_value=Mock())
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["common_utils"].get_redis_client = Mock()

    module = ModuleType("bw_sync_bans")
    module.__dict__["__file__"] = str(path)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(path), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


JOB = _load_definitions(JOB_PATH)

NOW = 1704067200.0


def _ban(ip="1.2.3.4", **over):
    return {
        "ip": ip,
        "reason": "badbehavior",
        "service": "unknown",
        "date": int(NOW) - 60,
        "country": "FR",
        "ban_scope": "global",
        "exp": 3600,
        "expires_at": NOW + 3600,
        "permanent": False,
        "reason_data": {},
    } | over


def _caller(ok=True):
    caller = Mock()
    caller.send_to_apis.return_value = (ok, {})
    return caller


class TestExpForWire:
    def test_permanent_stays_zero(self):
        assert JOB.exp_for_wire(0, NOW) == 0
        assert JOB.exp_for_wire(None, NOW) == 0

    def test_almost_expired_never_rounds_to_permanent(self):
        # 0.4s left: floor() would send 0, which POST /ban reads as "never expires".
        assert JOB.exp_for_wire(NOW + 0.4, NOW) == 1

    def test_already_past_is_still_at_least_one_second(self):
        assert JOB.exp_for_wire(NOW - 30, NOW) == 1

    def test_normal_ttl_is_rounded_up(self):
        assert JOB.exp_for_wire(NOW + 3599.2, NOW) == 3600


class TestKeysAndValues:
    def test_global_key(self):
        assert JOB.ban_key(_ban()) == "bans_ip_1.2.3.4"

    def test_service_key(self):
        assert JOB.ban_key(_ban(ban_scope="service", service="app.example.com")) == "bans_service_app.example.com_ip_1.2.3.4"

    def test_redis_value_carries_every_field_lua_decodes(self):
        # utils.is_banned / ban_sync.build_snapshot read these by name; a missing `permanent`
        # silently turns a permanent ban into an expiring one.
        from json import loads

        assert set(loads(JOB.redis_value(_ban()))) == {
            "reason",
            "service",
            "date",
            "country",
            "ban_scope",
            "reason_data",
            "permanent",
            "expires_at",
        }

    def test_identity_ignores_the_service_of_a_global_ban(self):
        # Instances report a placeholder service on global bans ("unknown", "bwcli", ...), so
        # comparing it would make every global ban look missing and re-push it every pass.
        assert JOB.identity_of(_ban(service="unknown")) == JOB.identity_of(_ban(service="bwcli"))
        assert JOB.identity_of(_ban(ban_scope="service", service="app.example.com")) == ("1.2.3.4", "service", "app.example.com")


class TestProjectionUnderRedis:
    def test_writes_to_redis_and_never_to_the_instances(self):
        redis_client = Mock()
        caller = _caller()

        projected, failures = JOB.project_bans([_ban()], {"bw-1": caller}, {}, redis_client, NOW)

        assert (projected, failures) == (1, 0)
        redis_client.set.assert_called_once()
        # Pushing under a healthy Redis would reset every ban's date on every pass.
        caller.send_to_apis.assert_not_called()

    def test_stays_silent_across_repeated_passes(self):
        redis_client = Mock()
        caller = _caller()
        for _ in range(10):
            JOB.project_bans([_ban()], {"bw-1": caller}, {}, redis_client, NOW)
        assert caller.send_to_apis.call_count == 0

    def test_permanent_ban_is_written_without_a_ttl(self):
        redis_client = Mock()
        JOB.project_bans([_ban(permanent=True, expires_at=0)], {}, {}, redis_client, NOW)
        assert "ex" not in redis_client.set.call_args.kwargs

    def test_expiring_ban_carries_its_remaining_ttl(self):
        redis_client = Mock()
        JOB.project_bans([_ban()], {}, {}, redis_client, NOW)
        assert redis_client.set.call_args.kwargs["ex"] == 3600


class TestProjectionWithoutRedis:
    def test_pushes_a_ban_the_instance_does_not_have(self):
        caller = _caller()

        projected, failures = JOB.project_bans([_ban()], {"bw-1": caller}, {"bw-1": []}, None, NOW)

        assert (projected, failures) == (1, 0)
        method, path = caller.send_to_apis.call_args.args
        assert (method, path) == ("POST", "/ban")
        assert caller.send_to_apis.call_args.kwargs["data"]["exp"] == 3600

    def test_pushes_nothing_when_the_instance_already_enforces_it(self):
        caller = _caller()

        projected, _ = JOB.project_bans([_ban()], {"bw-1": caller}, {"bw-1": [_ban(service="bwcli")]}, None, NOW)

        assert projected == 0
        caller.send_to_apis.assert_not_called()

    def test_a_failed_push_is_counted_and_does_not_stop_the_others(self):
        caller = _caller(ok=False)

        projected, failures = JOB.project_bans([_ban("1.2.3.4"), _ban("5.6.7.8")], {"bw-1": caller}, {"bw-1": []}, None, NOW)

        assert (projected, failures) == (0, 2)
        assert caller.send_to_apis.call_count == 2

    def test_each_instance_is_diffed_against_its_own_report(self):
        # The restarted instance gets the whole set back; the healthy one is left alone.
        healthy, restarted = _caller(), _caller()

        JOB.project_bans([_ban()], {"ok": healthy, "restarted": restarted}, {"ok": [_ban()], "restarted": []}, None, NOW)

        healthy.send_to_apis.assert_not_called()
        restarted.send_to_apis.assert_called_once()


class TestRecordsFromRedis:
    def test_reads_both_scopes(self):
        from json import dumps

        redis_client = Mock()
        redis_client.scan_iter.side_effect = [
            [b"bans_ip_1.2.3.4"],
            [b"bans_service_app.example.com_ip_5.6.7.8"],
        ]
        redis_client.get.return_value = dumps({"reason": "manual", "date": 1, "permanent": True}).encode()

        records = JOB.records_from_redis(redis_client)

        assert [(r["ip"], r["ban_scope"], r["service"]) for r in records] == [
            ("1.2.3.4", "global", ""),
            ("5.6.7.8", "service", "app.example.com"),
        ]
        assert {r["origin"] for r in records} == {"redis"}

    def test_undecodable_value_is_skipped_not_fatal(self):
        redis_client = Mock()
        redis_client.scan_iter.side_effect = [[b"bans_ip_1.2.3.4"], []]
        redis_client.get.return_value = b"not json"

        assert JOB.records_from_redis(redis_client) == []


@pytest.mark.parametrize(
    "identity,expected",
    [
        ({"ip": "1.2.3.4", "ban_scope": "global", "service": ""}, {"ip": "1.2.3.4", "ban_scope": "global"}),
        (
            {"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com"},
            {"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com"},
        ),
    ],
)
def test_identity_payload(identity, expected):
    assert JOB.identity_payload(identity) == expected

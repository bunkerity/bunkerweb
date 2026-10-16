"""``sync-bans`` and CrowdSec ban leases (wave 25, lane X1A; X1 amendment 2, R1b).

* A lease is learned but never projected (the instance renews it on its own, a stale DB copy would
  clobber the renewal).
* A lease tombstone is replayed as ``POST /unban`` with ``lease_id`` and, in Redis, by one
  compare-and-delete ``EVAL`` on the single key; an explicit ban keeps today's generic replay.
* A key that now holds an explicit ban, or a newer lease, survives the lease replay.

The Redis arm runs against a real ``redis-server`` (skipped when the binary is missing), because the
script is Lua that only Redis can execute.
"""

import ast
import re
import runpy
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from json import dumps
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from redis.exceptions import RedisError

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "sync-bans.py"
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

LEASE_ID = "0123456789abcdef"
OTHER_ID = "fedcba9876543210"
NOW = 1704067200.0


def _load_definitions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("jobs", "logger", "API", "ApiCaller", "common_utils")}
    stubs["jobs"].Job = Mock()
    stubs["logger"].getLogger = Mock(return_value=Mock())
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["common_utils"].get_redis_client = Mock()

    module = ModuleType("bw_sync_bans_lease")
    module.__dict__["__file__"] = str(path)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(path), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


JOB = _load_definitions(JOB_PATH)


def _lease_ban(ip="1.2.3.4", **over):
    return {
        "ip": ip,
        "reason": "crowdsec",
        "service": "unknown",
        "date": int(NOW) - 5,
        "country": "FR",
        "ban_scope": "global",
        "exp": 30,
        "expires_at": NOW + 30,
        "permanent": False,
        "reason_data": {"lease": True, "lease_id": LEASE_ID},
        "kind": "crowdsec_lease",
    } | over


def _explicit_ban(ip="1.2.3.4", **over):
    return _lease_ban(ip, reason="manual", reason_data={}, kind="ban", exp=3600, expires_at=NOW + 3600) | over


def _caller(ok=True):
    caller = Mock()
    caller.send_to_apis.return_value = (ok, {})
    return caller


# ── projection ──────────────────────────────────────────────────────────────────────────────────
class TestProjectionSkipsLeases:
    def test_redis_gets_the_explicit_ban_and_not_the_lease(self):
        redis_client = Mock()
        projected, failures = JOB.project_bans([_lease_ban("1.1.1.1"), _explicit_ban("2.2.2.2")], {}, {}, redis_client, NOW)
        assert (projected, failures) == (1, 0)
        (call,) = redis_client.set.call_args_list
        assert call.args[0] == "bans_ip_2.2.2.2"

    def test_a_lease_alone_writes_nothing_to_redis(self):
        redis_client = Mock()
        assert JOB.project_bans([_lease_ban()], {}, {}, redis_client, NOW) == (0, 0)
        redis_client.set.assert_not_called()

    def test_instances_are_not_pushed_a_lease_they_lack(self):
        caller = _caller()
        projected, _ = JOB.project_bans([_lease_ban("1.1.1.1"), _explicit_ban("2.2.2.2")], {"bw-1": caller}, {"bw-1": []}, None, NOW)
        assert projected == 1
        (call,) = caller.send_to_apis.call_args_list
        assert call.kwargs["data"]["ip"] == "2.2.2.2"

    def test_a_row_without_kind_is_projected_as_before(self):
        # Rows from an older get_bans() carry no kind: they are ordinary bans.
        redis_client = Mock()
        ban = _explicit_ban()
        del ban["kind"]
        assert JOB.project_bans([ban], {}, {}, redis_client, NOW) == (1, 0)


# ── replay to the instances ─────────────────────────────────────────────────────────────────────
class TestInstanceReplay:
    def test_lease_tombstone_goes_out_with_its_lease_id(self):
        caller = _caller()
        identity = {"ip": "1.2.3.4", "ban_scope": "global", "service": "", "lease_id": LEASE_ID}
        assert JOB.replay_instance_tombstones(caller, "bw-1", [identity]) == 0
        method, path = caller.send_to_apis.call_args.args
        assert (method, path) == ("POST", "/unban")
        assert caller.send_to_apis.call_args.kwargs["data"] == {"ip": "1.2.3.4", "ban_scope": "global", "lease_id": LEASE_ID}

    def test_service_lease_tombstone_keeps_its_service(self):
        caller = _caller()
        identity = {"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com", "lease_id": LEASE_ID}
        JOB.replay_instance_tombstones(caller, "bw-1", [identity])
        assert caller.send_to_apis.call_args.kwargs["data"] == {"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com", "lease_id": LEASE_ID}

    def test_explicit_tombstone_keeps_the_generic_replay(self):
        caller = _caller()
        JOB.replay_instance_tombstones(caller, "bw-1", [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}])
        assert caller.send_to_apis.call_args.kwargs["data"] == {"ip": "1.2.3.4", "ban_scope": "global"}

    def test_failures_are_counted_and_do_not_stop_the_rest(self):
        caller = _caller(ok=False)
        identities = [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}, {"ip": "5.6.7.8", "ban_scope": "global", "service": "", "lease_id": LEASE_ID}]
        assert JOB.replay_instance_tombstones(caller, "bw-1", identities) == 2
        assert caller.send_to_apis.call_count == 2


# ── replay to Redis ─────────────────────────────────────────────────────────────────────────────
class TestRedisReplayCalls:
    def test_lease_tombstone_is_one_eval_on_one_key_and_no_plain_delete(self):
        redis_client = Mock()
        redis_client.eval.return_value = b"removed"
        JOB.replay_redis_tombstones(redis_client, [{"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com", "lease_id": LEASE_ID}])
        redis_client.eval.assert_called_once_with(JOB.REMOVE_LEASE_SCRIPT, 1, "bans_service_app.example.com_ip_1.2.3.4", LEASE_ID)
        redis_client.delete.assert_not_called()
        redis_client.get.assert_not_called()

    def test_explicit_tombstone_is_the_plain_delete(self):
        redis_client = Mock()
        JOB.replay_redis_tombstones(redis_client, [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}])
        redis_client.delete.assert_called_once_with("bans_ip_1.2.3.4")
        redis_client.eval.assert_not_called()

    @pytest.mark.parametrize("operation", ["eval", "delete"])
    def test_a_redis_error_is_logged_and_counted_without_stopping_replay(self, operation):
        redis_client = Mock()
        getattr(redis_client, operation).side_effect = [RedisError("replay unavailable"), b"removed"]
        failed = {"ip": "1.2.3.4", "ban_scope": "global", "service": ""}
        if operation == "eval":
            failed["lease_id"] = LEASE_ID
        tombstones = [
            failed,
            {"ip": "5.6.7.8", "ban_scope": "global", "service": "", "lease_id": OTHER_ID},
            {"ip": "9.10.11.12", "ban_scope": "global", "service": ""},
        ]

        with patch.object(JOB, "LOGGER") as logger:
            assert JOB.replay_redis_tombstones(redis_client, tombstones) == 1

        redis_client.eval.assert_any_call(JOB.REMOVE_LEASE_SCRIPT, 1, "bans_ip_5.6.7.8", OTHER_ID)
        redis_client.delete.assert_any_call("bans_ip_9.10.11.12")
        logger.error.assert_called_once()
        message = logger.error.call_args.args[0]
        assert "1.2.3.4" in message and "replay unavailable" in message

    @pytest.mark.parametrize("operation", ["eval", "delete"])
    def test_job_projects_and_purges_after_a_replay_error_and_exits_two(self, monkeypatch, operation):
        monkeypatch.setenv("USE_REDIS", "yes")
        redis_client = Mock()
        redis_client.scan_iter.return_value = []
        getattr(redis_client, operation).side_effect = RedisError("replay unavailable")
        tombstone = {"ip": "1.2.3.4", "ban_scope": "global", "service": ""}
        if operation == "eval":
            tombstone["lease_id"] = LEASE_ID
        ban = _explicit_ban("5.6.7.8", permanent=True, expires_at=0)
        db = Mock()
        db.get_metadata.return_value = {"scheduler_first_start": False}
        db.get_instances.return_value = []
        db.learn_bans.return_value = ([], [tombstone])
        db.get_bans.return_value = [ban]
        db.purge_bans.return_value = ""
        stubs = {name: ModuleType(name) for name in ("jobs", "logger", "API", "ApiCaller", "common_utils")}
        stubs["jobs"].Job = Mock(return_value=Mock(db=db))
        stubs["logger"].getLogger = Mock(return_value=Mock())
        stubs["API"].API = Mock()
        stubs["ApiCaller"].ApiCaller = Mock()
        stubs["common_utils"].get_redis_client = Mock(return_value=redis_client)

        with patch.dict(sys.modules, stubs), pytest.raises(SystemExit) as exc:
            runpy.run_path(str(JOB_PATH))

        redis_client.set.assert_called_once_with("bans_ip_5.6.7.8", JOB.redis_value(ban))
        db.purge_bans.assert_called_once_with()
        assert exc.value.code == 2


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def redis_server(tmp_path_factory):
    binary = shutil.which("redis-server")
    if not binary:
        pytest.skip("redis-server is not installed")
    import redis

    port = _free_port()
    workdir = tmp_path_factory.mktemp("redis")
    proc = subprocess.Popen(
        [binary, "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no", "--dir", str(workdir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(host="127.0.0.1", port=port)
    try:
        for _ in range(100):
            try:
                client.ping()
                break
            except redis.exceptions.ConnectionError:
                time.sleep(0.05)
        else:
            pytest.skip("redis-server did not start")
        yield client
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def rds(redis_server):
    redis_server.flushall()
    return redis_server


def _put(client, key, reason="crowdsec", reason_data=None, ttl=300):
    client.set(
        key,
        dumps(
            {"reason": reason, "service": "unknown", "date": 1, "ban_scope": "global", "reason_data": reason_data, "permanent": False, "expires_at": 9999999999}
        ),
        ex=ttl,
    )


class TestRedisReplayAgainstRedis:
    def test_removes_the_key_when_it_still_holds_that_lease(self, rds):
        _put(rds, "bans_ip_1.2.3.4", reason_data={"lease": True, "lease_id": LEASE_ID})
        assert JOB.remove_lease_from_redis(rds, "bans_ip_1.2.3.4", LEASE_ID) == "removed"
        assert rds.exists("bans_ip_1.2.3.4") == 0

    def test_reports_absent_for_a_missing_key(self, rds):
        assert JOB.remove_lease_from_redis(rds, "bans_ip_1.2.3.4", LEASE_ID) == "absent"

    def test_a_renewed_lease_survives(self, rds):
        _put(rds, "bans_ip_1.2.3.4", reason_data={"lease": True, "lease_id": OTHER_ID})
        assert JOB.remove_lease_from_redis(rds, "bans_ip_1.2.3.4", LEASE_ID) == "changed"
        assert rds.exists("bans_ip_1.2.3.4") == 1

    def test_an_explicit_ban_survives_even_with_the_same_lease_id_in_its_data(self, rds):
        _put(rds, "bans_ip_1.2.3.4", reason="manual", reason_data={"lease_id": LEASE_ID})
        assert JOB.remove_lease_from_redis(rds, "bans_ip_1.2.3.4", LEASE_ID) == "changed"
        assert rds.exists("bans_ip_1.2.3.4") == 1

    def test_an_explicit_ban_without_reason_data_survives(self, rds):
        _put(rds, "bans_ip_1.2.3.4", reason="badbehavior", reason_data=None)
        assert JOB.remove_lease_from_redis(rds, "bans_ip_1.2.3.4", LEASE_ID) == "changed"
        assert rds.exists("bans_ip_1.2.3.4") == 1

    def test_undecodable_value_survives(self, rds):
        rds.set("bans_ip_1.2.3.4", "not json")
        assert JOB.remove_lease_from_redis(rds, "bans_ip_1.2.3.4", LEASE_ID) == "changed"
        assert rds.exists("bans_ip_1.2.3.4") == 1

    def test_only_the_named_key_is_touched(self, rds):
        _put(rds, "bans_ip_1.2.3.4", reason_data={"lease": True, "lease_id": LEASE_ID})
        _put(rds, "bans_service_app.example.com_ip_1.2.3.4", reason="manual")
        JOB.replay_redis_tombstones(rds, [{"ip": "1.2.3.4", "ban_scope": "global", "service": "", "lease_id": LEASE_ID}])
        assert rds.exists("bans_ip_1.2.3.4") == 0
        assert rds.exists("bans_service_app.example.com_ip_1.2.3.4") == 1

    def test_explicit_tombstone_still_deletes_plainly(self, rds):
        _put(rds, "bans_ip_1.2.3.4", reason="manual")
        JOB.replay_redis_tombstones(rds, [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}])
        assert rds.exists("bans_ip_1.2.3.4") == 0


class TestEndToEndAgainstTheDatabase:
    """The R1b scenario, DB through replay: a revoked global lease must leave a manual service ban
    active in the DB, at the instance (nothing replayed) and in Redis."""

    def _setup(self, db, rds):
        past = (datetime.now(timezone.utc) - timedelta(seconds=300)).timestamp()
        lease = {
            "ip": "1.2.3.4",
            "reason": "crowdsec",
            "service": "unknown",
            "date": past,
            "country": "FR",
            "ban_scope": "global",
            "exp": 30,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp(),
            "permanent": False,
            "reason_data": {"lease": True, "lease_id": LEASE_ID, "version": 1},
        }
        manual = lease | {"reason": "manual", "reason_data": {}, "ban_scope": "service", "service": "app.example.com"}
        db.learn_bans([lease])
        assert (
            db.upsert_ban(
                "1.2.3.4", ban_scope="service", service_id="app.example.com", reason="manual", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
            )
            == ""
        )
        _put(rds, "bans_ip_1.2.3.4", reason_data={"lease": True, "lease_id": LEASE_ID})
        _put(rds, "bans_service_app.example.com_ip_1.2.3.4", reason="manual")
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        return lease, manual

    def test_manual_service_ban_survives_the_revoked_global_lease(self, db, rds):
        _, manual = self._setup(db, rds)
        caller = _caller()

        inserted, tombstoned = db.learn_bans([manual])
        assert inserted == [] and tombstoned == []
        assert JOB.replay_instance_tombstones(caller, "bw-1", tombstoned) == 0
        JOB.replay_redis_tombstones(rds, tombstoned)

        caller.send_to_apis.assert_not_called()
        assert rds.exists("bans_service_app.example.com_ip_1.2.3.4") == 1
        assert [(b["ban_scope"], b["reason"]) for b in db.get_bans()] == [("service", "manual")]

    def test_the_same_lease_is_replayed_by_id_and_a_replacing_explicit_ban_is_spared(self, db, rds):
        lease, _ = self._setup(db, rds)
        caller = _caller()

        _, tombstoned = db.learn_bans([lease])
        assert [t.get("lease_id") for t in tombstoned] == [LEASE_ID]
        JOB.replay_instance_tombstones(caller, "bw-1", tombstoned)
        assert caller.send_to_apis.call_args.kwargs["data"]["lease_id"] == LEASE_ID

        # Between the revoke and the replay an operator put an explicit ban on that key.
        _put(rds, "bans_ip_1.2.3.4", reason="manual")
        JOB.replay_redis_tombstones(rds, tombstoned)
        assert rds.exists("bans_ip_1.2.3.4") == 1

    def test_the_replayed_lease_is_removed_from_redis_when_it_is_still_there(self, db, rds):
        lease, _ = self._setup(db, rds)
        _, tombstoned = db.learn_bans([lease])
        JOB.replay_redis_tombstones(rds, tombstoned)
        assert rds.exists("bans_ip_1.2.3.4") == 0
        assert rds.exists("bans_service_app.example.com_ip_1.2.3.4") == 1


# ── the script is shared with lane C's Lua remove_lease ─────────────────────────────────────────
def _squash(text):
    return re.sub(r"\s+", "", text)


def test_the_lua_remove_lease_runs_the_same_redis_script():
    lua = UTILS_LUA.read_text(encoding="utf-8")
    if "remove_lease" not in lua:
        pytest.skip("utils.lua has no remove_lease yet (lane C): this pin arms itself once it lands")
    assert _squash(JOB.REMOVE_LEASE_SCRIPT) in _squash(lua), "utils.lua remove_lease must embed sync-bans.py REMOVE_LEASE_SCRIPT verbatim"

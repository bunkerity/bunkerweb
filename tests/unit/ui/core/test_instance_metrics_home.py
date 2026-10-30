"""app/models/instance.py: metrics aggregation (Redis first, instances second), home dashboard aggregates, ping and data."""

import json
from datetime import datetime
from time import time
from unittest.mock import MagicMock

import pytest

from _ui_core_helpers import report
from app.models import instance as instance_module
from app.models.instance import Instance, InstancesUtils

NOW = datetime(2026, 10, 26, 12, 0, 0)


def inst(hostname, caller):
    return Instance(hostname, hostname, "ui", "up", "static", NOW, NOW, caller)


def ok(host, payload):
    return (True, {host: payload})


@pytest.fixture(autouse=True)
def _clear_home_cache():
    instance_module._HOME_AGG_CACHE.clear()
    yield
    instance_module._HOME_AGG_CACHE.clear()


@pytest.fixture
def db():
    database = MagicMock()
    database.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "1000"}
    return database


@pytest.fixture
def utils(db, redis, routes_utils):
    routes_utils.client = redis
    return InstancesUtils(db)


class TestMaxBlockedRequests:
    @pytest.mark.parametrize(
        ("config", "expected"),
        [
            ({"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "2k"}, 2000),
            ({}, 10000),
            ({"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "x"}, 10000),
            ({"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "0"}, 0),
        ],
    )
    def test_value(self, db, config, expected):
        db.get_config.return_value = config
        assert InstancesUtils(db)._get_max_blocked_requests_redis() == expected

    def test_database_error_uses_the_documented_default(self, db):
        db.get_config.side_effect = RuntimeError("down")
        assert InstancesUtils(db)._get_max_blocked_requests_redis() == 10000

    def test_only_the_one_setting_is_requested(self, db):
        InstancesUtils(db)._get_max_blocked_requests_redis()
        db.get_config.assert_called_once_with(global_only=True, methods=False, filtered_settings=("METRICS_MAX_BLOCKED_REQUESTS_REDIS",))


def recent(i, **extra):
    return report(i, date=time() - 60 * i, **extra)


class TestHomeAggregates:
    def seed(self, redis, rows):
        redis.lists["requests"] = [json.dumps(r).encode() for r in rows]

    def test_aggregates_blocked_requests_in_the_window(self, utils, redis):
        rows = [
            recent(1, ip="9.9.9.9", country="FR", status=403),
            recent(2, ip="9.9.9.9", country="FR", status="429"),
            recent(3, ip="8.8.8.8", country="US", status=403),
            recent(4, ip="", country="US", status="weird"),
            recent(5, ip="7.7.7.7", security_mode="detect", status=200),
            report(6, date=time() - 3600 * 24 * 30),
            report(7, date=time() + 3600),
            report(8, date="not-a-number"),
            recent(1, ip="1.1.1.1"),  # duplicate id, ignored
        ]
        self.seed(redis, rows)
        out = utils.get_home_aggregates(hours=24, top_ips_limit=2)
        assert out["request_countries"] == {"FR": {"blocked": 2}, "US": {"blocked": 2}}
        assert out["top_blocked_ips"] == {"9.9.9.9": {"blocked": 2}, "8.8.8.8": {"blocked": 1}}
        assert out["blocked_unique_ips"] == 3  # 9.9.9.9, 8.8.8.8 and the grouped "unknown"; detect mode is not a block
        assert out["request_statuses"] == {403: 2, 429: 1, 0: 1, 200: 1}
        assert len(out["time_buckets"]) == 24 and sum(out["time_buckets"].values()) == 4

    def test_unknown_ip_is_grouped(self, utils, redis):
        self.seed(redis, [recent(1, ip=""), recent(2, ip=None)])
        assert utils.get_home_aggregates(hours=24)["top_blocked_ips"] == {"unknown": {"blocked": 2}}

    def test_top_limit_zero_means_unlimited(self, utils, redis):
        self.seed(redis, [recent(i, ip=f"1.1.1.{i}") for i in range(1, 5)])
        assert len(utils.get_home_aggregates(hours=24, top_ips_limit=0)["top_blocked_ips"]) == 4

    def test_result_is_cached_and_callers_get_copies(self, utils, redis):
        self.seed(redis, [recent(1)])
        first = utils.get_home_aggregates(hours=24)
        first["request_countries"]["FR"]["blocked"] = 99
        redis.calls.clear()
        second = utils.get_home_aggregates(hours=24)
        assert second["request_countries"]["FR"]["blocked"] == 1
        assert "lrange" not in redis.calls and "pipeline.execute" not in redis.calls

    def test_snapshot_is_shared_with_other_workers_through_redis(self, utils, redis):
        self.seed(redis, [recent(1)])
        utils.get_home_aggregates(hours=24, top_ips_limit=5)
        raw = redis.kv["metrics:home_agg:24:5"]
        assert json.loads(raw)["request_statuses"] == {"403": 1}

        instance_module._HOME_AGG_CACHE.clear()  # a second worker with a cold local cache
        redis.calls.clear()
        again = utils.get_home_aggregates(hours=24, top_ips_limit=5)
        assert again["request_statuses"] == {403: 1}  # JSON string keys are turned back into ints
        assert "pipeline.execute" not in redis.calls

    @pytest.mark.parametrize("raw", [b"{broken", b"[1]", b""])
    def test_unusable_shared_snapshot_is_recomputed(self, utils, redis, raw):
        self.seed(redis, [recent(1)])
        redis.kv["metrics:home_agg:24:10"] = raw
        assert utils.get_home_aggregates(hours=24)["blocked_unique_ips"] == 1

    def test_shared_snapshot_read_error_is_not_fatal(self, utils, redis):
        self.seed(redis, [recent(1)])
        redis.errors["get"] = ConnectionError("x")
        assert utils.get_home_aggregates(hours=24)["blocked_unique_ips"] == 1

    def test_explicit_none_client_uses_instances_and_is_not_cached(self, db, fake_caller):
        data = {"requests": [recent(1), recent(1), {"no": "id"}, "junk", recent(2, ip="3.3.3.3")]}
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "data": data})))
        utils = InstancesUtils(db)
        utils.get_instances = lambda status=None: [a]
        out = utils.get_home_aggregates(hours=24, redis_client=None)
        assert out["blocked_unique_ips"] == 2
        assert instance_module._HOME_AGG_CACHE == {}

    def test_cap_zero_reads_the_instances(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "0"}
        self.seed(redis, [recent(1, ip="redis-ip")])
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"requests": [recent(2, ip="inst-ip")]}})))
        utils.get_instances = lambda status=None: [a]
        assert list(utils.get_home_aggregates(hours=24)["top_blocked_ips"]) == ["inst-ip"]

    def test_instance_request_iterator_skips_failures(self, db, fake_caller):
        good = {"status": "success", "data": {"requests": [{"id": 1}]}}
        instances = [
            inst("boom", fake_caller(default=OSError("x"))),
            inst("down", fake_caller(default=(False, {}))),
            inst("err", fake_caller(default=ok("err", {"status": "error"}))),
            inst("nodict", fake_caller(default=ok("nodict", {"status": "success", "data": "str"}))),
            inst("nolist", fake_caller(default=ok("nolist", {"status": "success", "data": {"requests": "x"}}))),
            inst("ok", fake_caller(default=ok("ok", good))),
            inst("dup", fake_caller(default=ok("dup", good))),
        ]
        utils = InstancesUtils(db)
        utils.get_instances = lambda status=None: instances
        assert list(utils._iter_instance_api_requests()) == [{"id": 1}]


class TestGetMetricsInstances:
    def metrics(self, utils, fake_caller, replies, plugin="limit", **kwargs):
        instances = [inst(host, fake_caller(default=reply)) for host, reply in replies.items()]
        return utils.get_metrics(plugin, instances=instances, redis_client=None, **kwargs)

    def test_values_are_merged_by_type(self, utils, fake_caller):
        merged = self.metrics(
            utils,
            fake_caller,
            {
                "a": ok("a", {"status": "success", "msg": {"n": 2, "s": "x", "l": [1], "d": {"c": 1, "l": [1], "o": "a"}, "redis_nb_keys": 5}}),
                "b": ok("b", {"status": "success", "data": {"n": 3, "s": "y", "l": [2], "d": {"c": 2, "l": [2], "o": "b", "new": 1}, "redis_nb_keys": 7}}),
            },
        )
        assert merged == {"n": 5, "s": "y", "l": [1, 2], "d": {"c": 3, "l": [1, 2], "o": "b", "new": 1}, "redis_nb_keys": 5}

    def test_non_numeric_current_value_does_not_break_the_sum(self, utils, fake_caller):
        merged = self.metrics(
            utils,
            fake_caller,
            {
                "a": ok("a", {"status": "success", "msg": {"n": "5", "m": "nil", "f": "1.5", "d": {"k": "7"}}}),
                "b": ok("b", {"status": "success", "msg": {"n": 1, "m": 2, "f": 1, "d": {"k": 3}}}),
            },
        )
        assert merged["n"] == 6 and merged["m"] == 2 and merged["f"] == 2.5 and merged["d"] == {"k": 10}
        assert isinstance(merged["n"], int)

    def test_type_mismatches_are_replaced_by_the_newer_value(self, utils, fake_caller):
        merged = self.metrics(
            utils,
            fake_caller,
            {"a": ok("a", {"status": "success", "msg": {"l": "text", "d": 5}}), "b": ok("b", {"status": "success", "msg": {"l": [1], "d": {"k": 1}}})},
        )
        assert merged == {"l": [1], "d": {"k": 1}}

    def test_failing_instances_are_logged_and_skipped(self, utils, db, fake_caller):
        merged = self.metrics(
            utils,
            fake_caller,
            {
                "boom": OSError("x"),
                "down": (False, {}),
                "bad": ok("bad", {"status": "error", "msg": "nope"}),
                "good": ok("good", {"status": "success", "msg": {"n": 1}}),
            },
        )
        assert merged == {"n": 1}
        assert db.logger.warning.call_count == 3

    def test_direct_response_format_drops_status_and_msg(self, utils, fake_caller):
        merged = self.metrics(utils, fake_caller, {"a": ok("a", {"status": "success", "msg": "text", "used": 5})})
        assert merged == {"used": 5}

    def test_redis_plugin_asks_the_redis_stats_endpoint(self, utils, fake_caller):
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"k": 1}})))
        assert utils.get_metrics("redis", instances=[a], redis_client=None) == {"k": 1}
        assert a.apiCaller.calls[0][1] == "/redis/stats"

    def test_hostname_queries_only_that_instance(self, utils, fake_caller, monkeypatch):
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"k": 1}})))
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a if hostname == "a" else None))
        assert utils.get_metrics("limit", "a", redis_client=None) == {"k": 1}
        assert utils.get_metrics("limit", "zz", redis_client=None) == {}


class TestGetMetricsRedis:
    def test_requests_come_from_redis_deduplicated_and_skip_instances(self, utils, redis, fake_caller):
        redis.lists["requests"] = [json.dumps(report(i)).encode() for i in (1, 2, 1)]
        a = inst("a", fake_caller())
        out = utils.get_metrics("requests", instances=[a])
        assert [r["id"] for r in out["requests"]] == ["r1", "r2"]
        assert a.apiCaller.calls == []

    def test_requests_cap_zero_defers_to_instances(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "0"}
        redis.lists["requests"] = [json.dumps(report(1)).encode()]
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"requests": [1]}})))
        assert utils.get_metrics("requests", instances=[a]) == {"requests": [1]}

    def test_errors_counters_are_summed_across_workers(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_SAVE_TO_REDIS": "yes"}
        redis.kv.update(
            {
                "metrics:errors_counter_404:w1": b"3",
                "metrics:errors_counter_404:w2": b"4",
                "metrics:errors_counter_500:w1": b"1",
                "metrics:errors_counter_403:w1": b"x",
            }
        )
        a = inst("a", fake_caller())
        assert utils.get_metrics("errors", instances=[a]) == {"counter_404": 7, "counter_500": 1}
        assert a.apiCaller.calls == []

    def test_saving_to_redis_disabled_means_instances_only(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_SAVE_TO_REDIS": "no"}
        redis.kv["metrics:limit_hits:w1"] = b"9"
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"hits": 1}})))
        assert utils.get_metrics("limit", instances=[a]) == {"hits": 1}

    def test_plugin_keys_are_decoded_and_summed(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_SAVE_TO_REDIS": "yes"}
        redis.kv.update(
            {
                "metrics:limit_hits:w1": b"3",
                "metrics:limit_hits:w2": b"4.0",
                "metrics:limit_table:w1": b'{"a": 1}',
                "metrics:limit_name:w1": b"plain text",
            }
        )
        redis.lists["metrics:limit_rows:w1"] = [b'{"r": 1}', b"raw"]
        redis.lists["metrics:limit_rows:w2"] = [b'{"r": 2}']
        redis.key_types["metrics:limit_odd:w1"] = "zset"
        redis.kv["metrics:limit_odd:w1"] = b"1"
        a = inst("a", fake_caller())
        out = utils.get_metrics("limit", instances=[a])
        assert out == {"hits": 7, "table": {"a": 1}, "name": "plain text", "rows": [{"r": 1}, "raw", {"r": 2}]}
        assert any("Unsupported Redis data type zset for key metrics:limit_odd:w1" in c.args[0] for c in db.logger.warning.call_args_list)

    def test_garbage_worker_value_does_not_shadow_real_counts(self, utils, redis, db):
        db.get_config.return_value = {"METRICS_SAVE_TO_REDIS": "yes"}
        redis.kv["metrics:limit_hits:w1"] = b"oops"
        redis.kv["metrics:limit_hits:w2"] = b"5"
        assert utils.get_metrics("limit", instances=[]) == {"hits": 5}

    def test_redis_failure_is_logged_and_instances_answer(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_SAVE_TO_REDIS": "yes"}
        redis.errors["scan_iter"] = ConnectionError("down")
        a = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"hits": 2}})))
        assert utils.get_metrics("limit", instances=[a]) == {"hits": 2}
        assert "Failed to get metrics from Redis" in db.logger.warning.call_args_list[0].args[0]

    def test_pipeline_failure_falls_back_to_per_key_reads(self, utils, redis, db):
        db.get_config.return_value = {"METRICS_SAVE_TO_REDIS": "yes"}
        redis.kv["metrics:limit_hits:w1"] = b"3"
        redis.kv["metrics:limit_hits:w2"] = b"4"
        real_execute = type(redis.pipeline()).execute
        state = {"first": True}

        def flaky(self):
            if state["first"] and any(op[0] == "get" for op in self.ops):
                state["first"] = False
                raise RuntimeError("WRONGTYPE")
            return real_execute(self)

        from _ui_core_helpers import _FakePipeline

        original = _FakePipeline.execute
        _FakePipeline.execute = flaky
        try:
            assert utils.get_metrics("limit", instances=[]) == {"hits": 7}
        finally:
            _FakePipeline.execute = original


class TestPingAndData:
    def test_first_success_wins_and_failure_reason_is_kept(self, db, fake_caller):
        down = inst("a", fake_caller(default=ok("a", {"status": "error", "msg": "licence invalid"})))
        up = inst("b", fake_caller(default=ok("b", {"status": "success", "msg": "pong"})))
        utils = InstancesUtils(db)
        assert utils.get_ping("antibot", instances=[down, up]) == {"status": "success", "msg": "pong"}
        assert utils.get_ping("antibot", instances=[down]) == {"status": "error", "msg": "licence invalid"}

    def test_ping_ignores_broken_instances(self, db, fake_caller):
        boom = inst("a", fake_caller(default=OSError("x")))
        junk = inst("b", fake_caller(default=(True, "string")))
        wrong = inst("c", fake_caller(default=(True, {"other": {}})))
        assert InstancesUtils(db).get_ping("x", instances=[boom, junk, wrong]) == {"status": "error", "msg": ""}

    def test_get_data(self, db, fake_caller):
        good = inst("a", fake_caller(default=ok("a", {"status": "success", "msg": {"k": 1}})))
        err = inst("b", fake_caller(default=ok("b", {"status": "error"})))
        down = inst("c", fake_caller(default=(False, {})))
        boom = inst("d", fake_caller(default=OSError("x")))
        assert InstancesUtils(db).get_data("jobs", instances=[good, err, down, boom]) == [
            {"a": {"k": 1}},
            {"b": {"status": "error"}},
            {"c": {"status": "error"}},
            {"d": {"status": "error"}},
        ]

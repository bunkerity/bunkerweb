"""app/models/instance.py, ``InstancesUtils``: fleet fan-out, report lookup and the paged reports query.

Redis is the in-memory ``conftest.FakeRedis`` holding the exact keys the metrics writer produces
(``requests`` list, ``requests:facets:initialized`` certificate, one facet hash per pane field), so
the fast page, the streaming fallback and the instance fallback are all exercised for real.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models import instance as instance_module
from app.models.instance import Instance, InstancesUtils
from _ui_core_helpers import FIELDS, report, seed
from redis_keys import facet_key, initialized_key, requests_key  # type: ignore

NOW = datetime(2026, 10, 26, 12, 0, 0)


def inst(hostname, caller, status="up"):
    return Instance(hostname, hostname + ".local", "ui", status, "static", NOW, NOW, caller)


@pytest.fixture
def db():
    database = MagicMock()
    database.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "100"}
    return database


@pytest.fixture
def utils(db, redis, routes_utils):
    routes_utils.client = redis
    return InstancesUtils(db)


class TestFleetOperations:
    def test_get_instances_filters_by_status_and_builds_api_clients(self, db):
        base = {"method": "ui", "type": "static", "creation_date": NOW, "last_seen": NOW}
        db.get_instances.return_value = [
            {"hostname": "a", "name": "A", "status": "up", **base},
            {"hostname": "b", "name": "B", "status": "down", **base},
        ]
        utils = InstancesUtils(db)
        assert [i.hostname for i in utils.get_instances()] == ["a", "b"]
        assert [i.hostname for i in utils.get_instances(status="up")] == ["a"]
        assert utils.get_instances()[0].apiCaller is not None

    def test_reload_reports_down_and_failing_instances(self, db, fake_caller):
        ok = inst("ok", fake_caller(default=(True, {})))
        bad = inst("bad", fake_caller(default=(False, {})))
        down = inst("dn", fake_caller(), status="down")
        utils = InstancesUtils(db)
        assert utils.reload_instances(instances=[ok, bad, down]) == ["bad.local", "dn.local"]
        assert utils.reload_instances(instances=[ok]) == "Successfully reloaded instances"

    def test_ban_and_unban_return_the_failing_instance_names(self, db, fake_caller):
        ok = inst("ok", fake_caller(default=(True, {})))
        bad = inst("bad", fake_caller(default=(False, {})))
        utils = InstancesUtils(db)
        assert utils.ban("1.1.1.1", 1, "", "_", instances=[ok, bad]) == ["bad.local"]
        assert utils.ban("1.1.1.1", 1, "", "_", instances=[ok]) == ""
        assert utils.unban("1.1.1.1", instances=[ok, bad]) == ["bad.local"]
        assert utils.unban("1.1.1.1", instances=[ok]) == ""

    def test_gather_runs_one_instance_inline_and_many_in_parallel(self):
        gather = InstancesUtils._gather_from_instances
        assert gather([], lambda i: [1]) == []
        assert gather(["a"], lambda i: [i]) == ["a"]
        assert sorted(gather(["a", "b", "c"], lambda i: [i, i.upper()])) == ["A", "B", "C", "a", "b", "c"]


class TestBans:
    def make_instance(self, fake_caller, hostname, bans):
        return inst(hostname, fake_caller(default=(True, {hostname: {"data": bans}})))

    def test_duplicates_collapse_to_the_earliest_expiry_and_scope_is_inferred(self, db, fake_caller):
        a = self.make_instance(fake_caller, "a", [{"ip": "1.1.1.1", "exp": 50, "service": "_"}, {"ip": "2.2.2.2", "exp": 10, "service": "svc"}])
        b = self.make_instance(fake_caller, "b", [{"ip": "1.1.1.1", "exp": 20, "service": "_"}, {"ip": "1.1.1.1", "exp": 5, "kind": "lease"}])
        bans = InstancesUtils(db).get_bans(instances=[a, b])
        by_key = {(x["ip"], x["ban_scope"], x.get("kind", "ban")): x["exp"] for x in bans}
        assert by_key == {("1.1.1.1", "global", "ban"): 20, ("2.2.2.2", "service", "ban"): 10, ("1.1.1.1", "global", "lease"): 5}

    def test_explicit_ban_scope_is_kept(self, db, fake_caller):
        a = self.make_instance(fake_caller, "a", [{"ip": "1.1.1.1", "exp": 1, "service": "svc", "ban_scope": "global"}])
        assert InstancesUtils(db).get_bans(instances=[a])[0]["ban_scope"] == "global"

    def test_failing_instance_contributes_nothing(self, db, fake_caller):
        bad = inst("bad", fake_caller(default=(False, {})))
        assert InstancesUtils(db).get_bans(instances=[bad]) == []

    def test_single_hostname(self, db, fake_caller, monkeypatch):
        a = self.make_instance(fake_caller, "a", [{"ip": "1.1.1.1", "exp": 1}])
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a if hostname == "a" else None))
        utils = InstancesUtils(db)
        assert [b["ip"] for b in utils.get_bans("a")] == ["1.1.1.1"]
        assert utils.get_bans("missing") == []


class TestGetReports:
    def test_reports_from_all_instances_newest_first(self, db, fake_caller):
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": 1, "date": 5}, {"id": 2, "date": 9}]}}})))
        b = inst("b", fake_caller(default=(True, {"b": {"msg": None}})))
        c = inst("c", fake_caller(default=(False, {})))
        assert [r["id"] for r in InstancesUtils(db).get_reports(instances=[a, b, c])] == [2, 1]

    def test_single_hostname(self, db, fake_caller, monkeypatch):
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": 1, "date": 1}]}}})))
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a if hostname == "a" else None))
        utils = InstancesUtils(db)
        assert utils.get_reports("a") == [{"id": 1, "date": 1}]
        assert utils.get_reports("zz") == []


class TestGetReportData:
    def test_redis_hit_returns_the_data_of_the_newest_occurrence(self, utils, redis):
        seed(redis, [report(1, data={"v": "old"}), report(2), report(1, data={"v": "new"})])
        assert utils.get_report_data("r1") == {"v": "new"}

    def test_empty_id_is_none(self, utils):
        assert utils.get_report_data("") is None

    def test_redis_miss_falls_back_to_instances_picking_the_latest_match(self, utils, redis, fake_caller):
        seed(redis, [report(2)])
        old = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": "x", "date": 1, "data": "old"}]}}})))
        new = inst(
            "b", fake_caller(default=(True, {"b": {"msg": {"requests": [{"id": "x", "date": 9, "data": "new"}, {"id": "y", "date": 99, "data": "no"}]}}}))
        )
        assert utils.get_report_data("x", instances=[old, new]) == "new"
        assert utils.get_report_data("nope", instances=[old, new]) is None

    def test_redis_error_is_logged_and_instances_answer(self, utils, redis, fake_caller):
        redis.errors["llen"] = ConnectionError("down")
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": "x", "date": 1, "data": "inst"}]}}})))
        assert utils.get_report_data("x", instances=[a]) == "inst"

    def test_hostname_that_is_not_an_instance_searches_all(self, utils, redis, fake_caller, monkeypatch):
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: None))
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": "x", "date": 1, "data": "inst"}]}}})))
        assert utils.get_report_data("x", hostname="www.example.com", instances=[a]) == "inst"

    def test_hostname_that_is_an_instance_is_queried_directly(self, utils, fake_caller, monkeypatch):
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": "x", "date": 1, "data": "direct"}]}}})))
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a))
        assert utils.get_report_data("x", hostname="a") == "direct"

    def test_cap_zero_ignores_redis_entirely(self, utils, redis, db, fake_caller):
        db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "0"}
        seed(redis, [report(1, data="redis")])
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [{"id": "r1", "date": 1, "data": "inst"}]}}})))
        assert utils.get_report_data("r1", instances=[a]) == "inst"
        assert "lrange" not in redis.calls

    def test_broken_instances_are_skipped(self, utils, fake_caller):
        boom = inst("a", fake_caller(default=OSError("x")))
        junk = inst("b", fake_caller(default=(True, {"b": {"msg": {"requests": "not-a-list"}}})))
        down = inst("c", fake_caller(default=(False, {})))
        assert utils.get_report_data("x", instances=[boom, junk, down]) is None


class TestBanEvidence:
    EVIDENCE = {"ban_id": "b:1", "server_name": "svc", "score": 9, "events": [{"n": 1}, {"n": 2}]}

    def run(self, utils, data, redis=None, instances=None):
        return utils._resolve_ban_evidence(data, redis, instances=instances)

    def test_non_ban_data_is_returned_untouched(self, utils):
        assert self.run(utils, {"a": 1}) == {"a": 1}
        assert self.run(utils, "text") == "text"

    @pytest.mark.parametrize("ban_id", [5, "bad id with spaces", "x" * 300, ""])
    def test_invalid_ban_ids_are_marked_missing(self, utils, ban_id):
        assert self.run(utils, {"ban_id": ban_id}) == {"ban_id": ban_id, "evidence_missing": True}

    def test_evidence_from_redis_is_flattened_per_event(self, utils, redis):
        redis.kv[f"{requests_key(False)}:ban_evidence:b:1"] = json.dumps(self.EVIDENCE).encode()
        assert self.run(utils, {"ban_id": "b:1"}, redis) == [{"n": 1, "ban_id": "b:1", "score": 9}, {"n": 2, "ban_id": "b:1", "score": 9}]

    @pytest.mark.parametrize(
        "payload",
        [{"ban_id": "other", "events": [{"n": 1}]}, {"ban_id": "b:1", "events": []}, {"ban_id": "b:1", "events": ["str"]}, {"ban_id": "b:1"}, [1]],
    )
    def test_malformed_evidence_is_rejected(self, utils, redis, payload):
        redis.kv[f"{requests_key(False)}:ban_evidence:b:1"] = json.dumps(payload).encode()
        assert self.run(utils, {"ban_id": "b:1"}, redis, instances=[]) == {"ban_id": "b:1", "evidence_missing": True}

    def test_instances_answer_when_redis_has_nothing(self, utils, redis, fake_caller):
        caller = fake_caller(default=(True, {"a": {"msg": self.EVIDENCE}}))
        result = self.run(utils, {"ban_id": "b:1"}, redis, instances=[inst("a", caller)])
        assert [e["n"] for e in result] == [1, 2]
        assert caller.calls[0][1] == "/metrics/badbehavior/ban/b%3A1"

    def test_redis_error_and_instance_errors_end_as_missing(self, utils, redis, fake_caller):
        redis.errors["get"] = ConnectionError("down")
        boom = inst("a", fake_caller(default=OSError("x")))
        bad = inst("b", fake_caller(default=(False, {})))
        assert self.run(utils, {"ban_id": "b:1"}, redis, instances=[boom, bad]) == {"ban_id": "b:1", "evidence_missing": True}

    def test_report_data_resolves_evidence_through_the_lookup(self, utils, redis):
        redis.kv[f"{requests_key(False)}:ban_evidence:b:1"] = json.dumps(self.EVIDENCE).encode()
        seed(redis, [report(1, data={"ban_id": "b:1"})])
        redis.kv[f"{requests_key(False)}:ban_evidence:b:1"] = json.dumps(self.EVIDENCE).encode()
        assert [e["n"] for e in utils.get_report_data("r1")] == [1, 2]


class TestPaneCounts:
    def test_complete_facets_are_used_directly(self, utils, redis):
        seed(redis, [report(1), report(2), report(3)])
        counts = utils.get_reports_pane_counts()
        assert counts["country"] == {"FR": {"total": 2, "count": 2}, "US": {"total": 1, "count": 1}}
        assert set(counts) == set(FIELDS)

    def test_uncertified_list_streams_the_reports(self, utils, redis):
        seed(redis, [report(1), report(1), report(2)], certified=False)
        counts = utils.get_reports_pane_counts()
        assert counts["status"] == {"403": {"total": 2, "count": 2}}  # the duplicated id counts once

    def test_a_field_with_inconsistent_facets_is_streamed_and_the_certificate_dropped(self, utils, redis):
        seed(redis, [report(1), report(2)])
        redis.hashes[facet_key(False, "country")] = {b"FR": b"5"}  # sums to 5, certificate says 2 valid
        counts = utils.get_reports_pane_counts()
        assert counts["country"] == {"FR": {"total": 1, "count": 1}, "US": {"total": 1, "count": 1}}
        assert counts["status"] == {"403": {"total": 2, "count": 2}}
        assert initialized_key(False) not in redis.kv  # the next metrics timer rebuilds it

    def test_instance_fallback_without_redis(self, db, routes_utils, fake_caller):
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [report(1), report(2)]}}})))
        counts = InstancesUtils(db).get_reports_pane_counts(instances=[a])
        assert counts["ip"]["10.0.0.1"] == {"total": 1, "count": 1}

    def test_hostname_scope_bypasses_redis(self, utils, redis, fake_caller, monkeypatch):
        seed(redis, [report(1)])
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"requests": [report(7, country="DE")]}}})))
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a))
        assert "DE" in utils.get_reports_pane_counts("a")["country"]

    def test_calculate_pane_counts_counts_filtered_ids(self, utils):
        all_reports = [report(1), report(2), report(3, country="FR")]
        counts = utils._calculate_pane_counts(all_reports, [all_reports[0], all_reports[2]])
        assert counts["country"] == {"FR": {"total": 2, "count": 2}, "US": {"total": 1, "count": 0}}
        assert utils._calculate_pane_counts([{"id": 1}], [])["method"] == {"N/A": {"total": 1, "count": 0}}


class TestReportsQueryRedis:
    @pytest.fixture
    def many(self, redis):
        seed(redis, [report(i) for i in range(1, 8)])

    def test_fast_page_newest_first(self, utils, many):
        out = utils.get_reports_query(start=0, length=3)
        assert [r["id"] for r in out["data"]] == ["r7", "r6", "r5"]
        assert (out["total"], out["filtered"]) == (7, 7)
        assert out["pane_counts"]["country"]["FR"]["total"] == 4  # facets cover the whole retained list

    def test_fast_page_ascending_with_offset(self, utils, many):
        out = utils.get_reports_query(start=2, length=2, order_dir="asc")
        assert [r["id"] for r in out["data"]] == ["r3", "r4"]

    def test_fast_page_past_the_end_is_empty(self, utils, many):
        out = utils.get_reports_query(start=50, length=5)
        assert out["data"] == [] and out["total"] == 7

    def test_window_is_capped_by_the_configured_maximum(self, utils, many, db):
        db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "3"}
        out = utils.get_reports_query(start=0, length=10)
        assert [r["id"] for r in out["data"]] == ["r7", "r6", "r5"] and out["total"] == 3

    def test_count_only_uses_the_certificate(self, utils, many, redis):
        out = utils.get_reports_query(count_only=True)
        assert (out["total"], out["filtered"], out["data"]) == (7, 7, [])
        assert "lrange" not in redis.calls

    def test_search_filters_and_counts(self, utils, many):
        out = utils.get_reports_query(search="P3", length=10)
        assert [r["id"] for r in out["data"]] == ["r3"]
        assert (out["total"], out["filtered"]) == (7, 1)
        assert out["pane_counts"]["country"]["FR"] == {"total": 4, "count": 1}

    def test_search_is_case_insensitive_across_fields(self, utils, many):
        assert utils.get_reports_query(search="CURL", length=-1)["filtered"] == 7
        assert utils.get_reports_query(search="nothing-matches", length=-1)["data"] == []

    def test_pane_filter_restricts_rows(self, utils, many):
        panes = instance_module.encode_search_panes({"country": ["FR"]})
        out = utils.get_reports_query(search_panes=panes, length=-1)
        assert sorted(r["id"] for r in out["data"]) == ["r1", "r3", "r5", "r7"]
        assert out["filtered"] == 4 and out["total"] == 7

    def test_sort_by_another_column(self, utils, many):
        out = utils.get_reports_query(order_column="url", order_dir="asc", length=3)
        assert [r["url"] for r in out["data"]] == ["/p1", "/p2", "/p3"]

    def test_length_minus_one_returns_everything(self, utils, many):
        out = utils.get_reports_query(length=-1, order_dir="asc")
        assert [r["id"] for r in out["data"]] == [f"r{i}" for i in range(1, 8)]

    def test_heap_pagination_matches_full_sort(self, utils, many):
        out = utils.get_reports_query(start=2, length=3, search="p")
        assert [r["id"] for r in out["data"]] == ["r5", "r4", "r3"]

    def test_pane_counts_can_be_switched_off(self, utils, many):
        out = utils.get_reports_query(length=2, include_pane_counts=False)
        assert out["pane_counts"] == {} and len(out["data"]) == 2

    def test_uncertified_list_is_streamed_and_deduplicated(self, utils, redis):
        seed(redis, [report(1), report(2), report(1), report(3)], certified=False)
        out = utils.get_reports_query(length=10)
        assert [r["id"] for r in out["data"]] == ["r3", "r2", "r1"] and out["total"] == 3

    def test_streaming_count_only_still_counts_filtered_rows(self, utils, redis):
        seed(redis, [report(1), report(2)], certified=False)
        out = utils.get_reports_query(search="p2", count_only=True)
        assert (out["total"], out["filtered"], out["data"]) == (2, 1, [])
        assert out["pane_counts"]["country"]["US"] == {"total": 1, "count": 1}

    def test_nonfast_list_streams_instead_of_paging(self, utils, redis):
        seed(redis, [report(1), report(2)], nonfast=1)
        out = utils.get_reports_query(length=1)
        assert [r["id"] for r in out["data"]] == ["r2"]
        assert out["pane_counts"]["country"]["FR"] == {"total": 1, "count": 1}

    def test_corrupt_page_falls_back_to_streaming(self, utils, redis):
        seed(redis, [report(1), report(2), report(3)])
        redis.lists[requests_key(False)][1] = b"{broken"
        redis.kv[initialized_key(False)] = json.dumps({"version": 2, "length": 3, "valid": 3, "nonfast": 0}).encode()
        out = utils.get_reports_query(length=10, include_pane_counts=False)
        assert [r["id"] for r in out["data"]] == ["r3", "r1"]

    def test_redis_failure_falls_back_to_the_instances(self, utils, redis, fake_caller):
        redis.errors["llen"] = ConnectionError("down")
        redis.errors["pipeline.execute"] = ConnectionError("down")
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"data": [report(9)], "total": 1}}})))
        out = utils.get_reports_query(instances=[a], length=5)
        assert [r["id"] for r in out["data"]] == ["r9"]


class TestReportsQueryInstances:
    def instance(self, fake_caller, name, data, total):
        return inst(name, fake_caller(default=(True, {name: {"msg": {"data": data, "total": total}}})))

    def test_aggregated_across_instances_deduplicated_and_sorted(self, db, routes_utils, fake_caller):
        a = self.instance(fake_caller, "a", [report(1), report(2)], 2)
        b = self.instance(fake_caller, "b", [report(2), report(3)], 5)
        out = InstancesUtils(db).get_reports_query(start=0, length=2, instances=[a, b])
        assert [r["id"] for r in out["data"]] == ["r3", "r2"]
        assert (out["total"], out["filtered"]) == (5, 3)
        assert out["pane_counts"]["country"]["FR"]["total"] == 2

    def test_length_minus_one_and_count_only(self, db, routes_utils, fake_caller):
        a = self.instance(fake_caller, "a", [report(1), report(2)], 2)
        utils = InstancesUtils(db)
        assert len(utils.get_reports_query(length=-1, instances=[a])["data"]) == 2
        counted = utils.get_reports_query(count_only=True, instances=[a])
        assert counted["data"] == [] and counted["filtered"] == 2 and counted["pane_counts"]["method"]["GET"]["total"] == 2
        assert utils.get_reports_query(count_only=True, include_pane_counts=False, instances=[a])["pane_counts"] == {}

    def test_every_instance_is_asked_for_everything(self, db, routes_utils, fake_caller):
        a = self.instance(fake_caller, "a", [], 0)
        InstancesUtils(db).get_reports_query(start=5, length=5, search="x", order_column="ip", instances=[a])
        url = a.apiCaller.calls[0][1]
        assert "start=0" in url and "length=-1" in url and "order_dir=desc" in url and "search=x" in url and "order_column=ip" in url

    def test_hostname_delegates_to_that_instance(self, db, routes_utils, fake_caller, monkeypatch):
        a = inst("a", fake_caller(default=(True, {"a": {"msg": {"total": 4, "filtered": 4, "data": [report(1)], "pane_counts": {}}}})))
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a))
        out = InstancesUtils(db).get_reports_query(hostname="a", start=3, length=1)
        assert out["total"] == 4 and a.apiCaller.calls[0][1].startswith("/metrics/requests/query?start=3&length=1")

    def test_unknown_hostname_or_bad_reply_is_empty(self, db, routes_utils, fake_caller, monkeypatch):
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: None))
        empty = {"total": 0, "filtered": 0, "data": [], "pane_counts": {}}
        assert InstancesUtils(db).get_reports_query(hostname="zz") == empty
        a = inst("a", fake_caller(default=(False, {})))
        monkeypatch.setattr(Instance, "from_hostname", staticmethod(lambda hostname, database: a))
        assert InstancesUtils(db).get_reports_query(hostname="a") == empty


class TestHelpers:
    def test_apply_report_filters(self, utils):
        rows = [report(1), report(2), report(3)]
        assert [r["id"] for r in utils._apply_report_filters(rows, "P2", "")] == ["r2"]
        panes = instance_module.encode_search_panes({"country": ["FR"], "status": ["403"]})
        assert [r["id"] for r in utils._apply_report_filters(rows, "", panes)] == ["r1", "r3"]
        assert utils._apply_report_filters(rows, "", "") == rows

    def test_sort_reports(self, utils):
        rows = [{"date": "3", "ip": "b"}, {"date": None, "ip": "c"}, {"date": 2.5, "ip": "a"}]
        assert [r["ip"] for r in utils._sort_reports(rows, "date", "desc")] == ["b", "a", "c"]
        assert [r["ip"] for r in utils._sort_reports(rows, "ip", "asc")] == ["a", "b", "c"]

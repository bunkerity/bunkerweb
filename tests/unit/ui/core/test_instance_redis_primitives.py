"""app/models/instance.py, Redis readers: report decoding, certificate checks, facet scans and list iterators."""

import json
from unittest.mock import MagicMock

import pytest

from app.models.instance import InstancesUtils
from redis_keys import facet_key, initialized_key, requests_key  # type: ignore
from _ui_core_helpers import report, seed

REQ = requests_key(False)
INIT = initialized_key(False)


@pytest.fixture
def utils():
    return InstancesUtils(MagicMock())


def certificate(redis, length, valid=None, nonfast=0, version=2):
    redis.kv[INIT] = json.dumps({"version": version, "length": length, "valid": length if valid is None else valid, "nonfast": nonfast}).encode()


class TestDecodeReport:
    @pytest.mark.parametrize(
        "raw",
        [b"{broken", b"[1]", b'{"id": [1]}', b'{"id": "a", "date": "abc"}', b'{"id": "a", "date": Infinity}', b'{"id": "a", "date": NaN}', None],
    )
    def test_rejected(self, raw):
        assert InstancesUtils._decode_redis_report(raw) is None

    @pytest.mark.parametrize("raw", [b'{"id": "a", "date": 5}', b'{"date": 1.5}', b'{"id": 7}', b'{"id": "a", "date": null}'])
    def test_accepted(self, raw):
        assert InstancesUtils._decode_redis_report(raw) == json.loads(raw)

    def test_decode_text(self):
        assert InstancesUtils._decode_redis_text(b"abc\xc3\xa9") == "abc\u00e9"
        assert InstancesUtils._decode_redis_text(b"\xff") == "�"
        assert InstancesUtils._decode_redis_text(5) == "5"


class TestRequestState:
    def test_valid_certificate(self, utils, redis):
        seed(redis, [report(1), report(2)])
        assert utils._get_redis_request_state(redis) == {"version": 2, "length": 2, "valid": 2, "nonfast": 0}

    @pytest.mark.parametrize("mutate", ["no-cert", "old-version", "length-mismatch", "garbage", "list"])
    def test_invalid_certificates_are_none(self, utils, redis, mutate):
        seed(redis, [report(1), report(2)])
        if mutate == "no-cert":
            del redis.kv[INIT]
        elif mutate == "old-version":
            certificate(redis, 2, version=1)
        elif mutate == "length-mismatch":
            certificate(redis, 5)
        elif mutate == "garbage":
            redis.kv[INIT] = b"{nope"
        else:
            redis.kv[INIT] = b"[1]"
        assert utils._get_redis_request_state(redis) is None

    def test_scan_window(self, utils, redis):
        seed(redis, [report(i) for i in range(10)])
        assert utils._get_redis_scan_window(redis, 4) == (6, 10)
        assert utils._get_redis_scan_window(redis, 100) == (0, 10)
        assert utils._get_redis_scan_window(redis, 0) == (0, 10)
        redis.errors["llen"] = ConnectionError("x")
        assert utils._get_redis_scan_window(redis, 4) == (0, None)


class TestIterHash:
    def test_small_hash_uses_hgetall(self, utils, redis):
        redis.hashes["h"] = {b"a": b"1", b"b": b"2"}
        assert dict(utils._iter_redis_hash(redis, "h")) == {b"a": b"1", b"b": b"2"}
        assert "hscan" not in redis.calls

    @pytest.mark.parametrize("mode", ["large", "hlen-error"])
    def test_cursor_loop_for_large_or_unmeasurable_hash(self, utils, redis, monkeypatch, mode):
        redis.hashes["h"] = {b"a": b"1", b"b": b"2", b"c": b"3", b"d": b"4", b"e": b"5"}
        if mode == "large":
            monkeypatch.setattr(InstancesUtils, "_FACET_HGETALL_MAX", 1)
        else:
            redis.errors["hlen"] = ConnectionError("x")
        assert dict(utils._iter_redis_hash(redis, "h")) == redis.hashes["h"]
        assert redis.calls.count("hscan") == 3 and "hgetall" not in redis.calls


class TestFacets:
    def test_counts_are_ranked_by_count_then_value_and_capped(self, utils, redis, monkeypatch):
        rows = [report(1, country="FR"), report(2, country="FR"), report(3, country="DE"), report(4, country="US"), report(5, country="")]
        seed(redis, rows)
        monkeypatch.setattr(InstancesUtils, "_REPORT_PANE_MAX_VALUES", 2)
        counts = utils._get_redis_pane_counts_from_facets(redis, ["country"])
        assert list(counts["country"]) == ["FR", "US"]  # DE/US/N-A tie on 1: highest value wins the heap
        assert counts["country"]["FR"] == {"total": 2, "count": 2}

    def test_empty_value_is_shown_as_na(self, utils, redis):
        seed(redis, [report(1, country="")])
        assert utils._get_redis_pane_counts_from_facets(redis, ["country"])["country"] == {"N/A": {"total": 1, "count": 1}}

    def test_no_certificate_no_counts(self, utils, redis):
        seed(redis, [report(1)], certified=False)
        assert utils._get_redis_pane_counts_from_facets(redis, ["country"]) is None

    @pytest.mark.parametrize("bad", [b"0", b"-2", b"abc"])
    def test_corrupt_facet_drops_just_that_field_and_the_certificate(self, utils, redis, bad):
        seed(redis, [report(1)])
        redis.hashes[facet_key(False, "country")] = {b"FR": bad}
        counts = utils._get_redis_pane_counts_from_facets(redis, ["country", "method"])
        assert set(counts) == {"method"}
        assert INIT not in redis.kv

    def test_certificate_is_kept_when_a_newer_generation_replaced_it(self, utils, redis):
        seed(redis, [report(1)])
        state = utils._get_redis_request_state(redis)
        redis.hashes[facet_key(False, "country")] = {b"FR": b"9"}
        original_get = redis.get

        def get_then_swap(key):
            if key == INIT and redis.calls.count("get") >= 3:
                certificate(redis, 1, valid=1, nonfast=0, version=2)  # same generation: eval deletes
            return original_get(key)

        redis.get = get_then_swap
        utils._get_redis_pane_counts_from_facets(redis, ["country"], state=state)
        assert redis.evals and redis.evals[0][2][0] == INIT

    def test_generation_change_during_the_scan_invalidates_the_snapshot(self, utils, redis):
        seed(redis, [report(1), report(2)])
        original = redis.hgetall

        def hgetall_and_push(key):
            result = original(key)
            redis.lists[REQ].append(json.dumps(report(3)).encode())
            return result

        redis.hgetall = hgetall_and_push
        assert utils._get_redis_pane_counts_from_facets(redis, ["country"]) is None


class TestFastPage:
    def page(self, utils, redis, **kwargs):
        defaults = dict(max_requests=100, start=0, length=3, order_dir="desc")
        defaults.update(kwargs)
        return utils._get_redis_requests_fast_page(redis, **defaults)

    def test_requires_a_clean_certificate_and_a_positive_length(self, utils, redis):
        seed(redis, [report(i) for i in range(1, 5)])
        assert self.page(utils, redis, length=0) is None
        certificate(redis, 4, nonfast=1)
        assert self.page(utils, redis) is None
        del redis.kv[INIT]
        assert self.page(utils, redis) is None

    def test_empty_list(self, utils, redis):
        seed(redis, [])
        certificate(redis, 0)
        assert self.page(utils, redis) == (0, [])

    def test_descending_and_ascending_pages(self, utils, redis):
        seed(redis, [report(i) for i in range(1, 6)])
        total, rows = self.page(utils, redis, start=1, length=2)
        assert (total, [r["id"] for r in rows]) == (5, ["r4", "r3"])
        total, rows = self.page(utils, redis, start=1, length=2, order_dir="asc")
        assert [r["id"] for r in rows] == ["r2", "r3"]

    def test_cap_limits_the_window(self, utils, redis):
        seed(redis, [report(i) for i in range(1, 6)])
        total, rows = self.page(utils, redis, max_requests=2, length=5)
        assert (total, [r["id"] for r in rows]) == (2, ["r5", "r4"])
        assert self.page(utils, redis, max_requests=2, start=2) == (2, [])

    def test_duplicate_id_or_undecodable_row_disqualifies_the_list(self, utils, redis):
        seed(redis, [report(1), report(1), report(2)])
        assert self.page(utils, redis) is None
        seed(redis, [report(1), report(2)])
        redis.lists[REQ][0] = b"{broken"
        assert self.page(utils, redis) is None

    def test_truncated_list_disqualifies_the_page(self, utils, redis):
        seed(redis, [report(i) for i in range(1, 6)])
        redis.lists[REQ] = redis.lists[REQ][:2]  # certificate still says 5
        assert self.page(utils, redis) is None

    def test_generation_change_between_reads_is_retried_then_given_up(self, utils, redis):
        seed(redis, [report(i) for i in range(1, 4)])
        original = redis.lrange
        state = {"n": 0}

        def lrange_and_bump(key, start, end):
            state["n"] += 1
            result = original(key, start, end)
            certificate(redis, 3, valid=state["n"] + 100)  # a different certificate every read
            return result

        redis.lrange = lrange_and_bump
        assert self.page(utils, redis) is None
        assert state["n"] == InstancesUtils._FAST_PAGE_ATTEMPTS


class TestIterators:
    def seeded(self, redis, n):
        redis.lists[REQ] = [json.dumps({"id": i, "date": i}).encode() for i in range(n)]

    def test_forward_iteration_spans_chunks_and_batches(self, utils, redis):
        self.seeded(redis, 7)
        assert [r["id"] for r in utils._iter_redis_requests(redis, chunk_size=2, pipeline_batch=2)] == list(range(7))

    def test_start_index_and_total_bound_the_scan(self, utils, redis):
        self.seeded(redis, 7)
        assert [r["id"] for r in utils._iter_redis_requests(redis, chunk_size=3, start_index=4, total=7)] == [4, 5, 6]
        assert list(utils._iter_redis_requests(redis, start_index=9, total=7)) == []

    def test_undecodable_rows_are_skipped(self, utils, redis):
        self.seeded(redis, 3)
        redis.lists[REQ][1] = b"{x"
        assert [r["id"] for r in utils._iter_redis_requests(redis, chunk_size=10)] == [0, 2]

    def test_llen_failure_falls_back_to_chunk_termination(self, utils, redis):
        self.seeded(redis, 5)
        redis.errors["llen"] = ConnectionError("x")
        assert [r["id"] for r in utils._iter_redis_requests(redis, chunk_size=2)] == list(range(5))

    def test_reverse_iteration_is_newest_first(self, utils, redis):
        self.seeded(redis, 5)
        assert [r["id"] for r in utils._iter_redis_requests_reverse(redis, chunk_size=2)] == [4, 3, 2, 1, 0]
        assert [r["id"] for r in utils._iter_redis_requests_reverse(redis, chunk_size=2, start_index=3, total=5)] == [4, 3]

    def test_reverse_stops_quietly_on_redis_errors(self, utils, redis):
        self.seeded(redis, 5)
        redis.errors["llen"] = ConnectionError("x")
        assert list(utils._iter_redis_requests_reverse(redis)) == []
        del redis.errors["llen"]
        redis.errors["lrange"] = ConnectionError("x")
        assert list(utils._iter_redis_requests_reverse(redis)) == []

    def test_reverse_skips_bad_rows_and_stops_on_empty_chunk(self, utils, redis):
        self.seeded(redis, 3)
        redis.lists[REQ][2] = b"{x"
        assert [r["id"] for r in utils._iter_redis_requests_reverse(redis)] == [1, 0]
        redis.lists[REQ] = []
        assert list(utils._iter_redis_requests_reverse(redis, total=9)) == []

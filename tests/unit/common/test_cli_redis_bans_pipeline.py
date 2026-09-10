"""`bwcli bans` cost three Redis round trips per ban plus one per ten keys.

Port of dev c58b69e07. `scan_iter` without `count` leaves Redis on its `COUNT=10` default, so
key discovery alone was one round trip per ten bans, and each key then paid a `GET` and a
`TTL` of its own. `__collect_redis_bans` collapses both: one `SCAN` cursor at `count=1000`,
one pipelined `GET`/`TTL` pass.

The decoding is what must not have changed with them — the permanent-ban TTL override, the
`service`/`ban_scope` split, and the raw-value fallback for a payload that is not JSON.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT / "src" / "common" / "cli", _ROOT / "src" / "common" / "api", _ROOT / "src" / "common" / "utils", _ROOT / "src" / "common" / "db"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from CLI import CLI  # noqa: E402


class _Pipe:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def get(self, key):
        self.ops.append(("get", key))

    def ttl(self, key):
        self.ops.append(("ttl", key))

    def execute(self):
        self.redis.pipelines += 1
        self.redis.round_trips += 1
        out = [self.redis.values.get(key) if op == "get" else self.redis.ttls.get(key, -1) for op, key in self.ops]
        self.ops = []
        return out


class _Redis:
    def __init__(self, values, ttls=None):
        self.values = values
        self.ttls = ttls or {}
        self.scan_kwargs = []
        self.pipelines = 0
        self.round_trips = 0

    def scan_iter(self, pattern, **kwargs):
        self.scan_kwargs.append((pattern, kwargs))
        self.round_trips += 1
        prefix = pattern.rstrip("*").split("*")[0]
        for key in self.values:
            if key.startswith(prefix) and ("_ip_" in key if "service" in pattern else not key.startswith("bans_service_")):
                yield key

    def pipeline(self, transaction=True):
        assert transaction is False, "a read-only fan-out must not open a MULTI"
        return _Pipe(self)

    def get(self, key):  # pragma: no cover - the per-key path is what this port removes
        raise AssertionError("bans() must not issue a GET per key any more")

    def ttl(self, key):  # pragma: no cover
        raise AssertionError("bans() must not issue a TTL per key any more")


def _cli(redis):
    cli = object.__new__(CLI)
    cli._CLI__redis = redis
    cli._CLI__logger = Mock()
    return cli


# --------------------------------------------------------------------------------------
# The round trips
# --------------------------------------------------------------------------------------
def test_a_hundred_bans_cost_two_round_trips_not_three_hundred():
    values = {f"bans_ip_10.0.0.{i}": b'{"reason": "test", "date": 1}' for i in range(100)}
    redis = _Redis(values, {key: 60 for key in values})

    bans = _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global")

    assert len(bans) == 100
    assert redis.round_trips == 2, "one SCAN pass plus one pipelined GET/TTL pass"
    assert redis.pipelines == 1


def test_the_scan_no_longer_runs_on_the_ten_key_default():
    redis = _Redis({"bans_ip_10.0.0.1": b'{"reason": "x", "date": 1}'})

    _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global")

    assert redis.scan_kwargs[0][1].get("count") == 1000


def test_an_empty_pattern_never_opens_a_pipeline():
    redis = _Redis({})

    assert _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global") == []
    assert redis.pipelines == 0


# --------------------------------------------------------------------------------------
# The decoding, unchanged
# --------------------------------------------------------------------------------------
def test_a_global_ban_keeps_its_ip_and_scope():
    redis = _Redis({"bans_ip_10.0.0.1": b'{"reason": "manual", "date": 7}'}, {"bans_ip_10.0.0.1": 120})

    (ban,) = _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global")

    assert ban["ip"] == "10.0.0.1"
    assert ban["ban_scope"] == "global"
    assert ban["exp"] == 120


def test_a_service_ban_splits_the_service_out_of_the_key():
    key = "bans_service_www.example.com_ip_10.0.0.2"
    redis = _Redis({key: b'{"reason": "manual", "date": 7}'}, {key: 30})

    (ban,) = _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_service_*_ip_*", "service")

    assert (ban["ip"], ban["service"], ban["ban_scope"]) == ("10.0.0.2", "www.example.com", "service")


def test_a_permanent_ban_still_overrides_the_ttl():
    key = "bans_ip_10.0.0.3"
    redis = _Redis({key: b'{"reason": "manual", "date": 7, "permanent": true}'}, {key: 900})

    (ban,) = _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global")

    assert ban["exp"] == 0


def test_a_payload_that_is_not_json_falls_back_to_the_raw_reason():
    key = "bans_ip_10.0.0.4"
    redis = _Redis({key: b"legacy-plain-reason"}, {key: 60})
    cli = _cli(redis)

    (ban,) = cli.__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global")

    assert ban["reason"] == "legacy-plain-reason"
    assert ban["ban_scope"] == "global"
    cli._CLI__logger.warning.assert_called_once()


def test_a_key_that_vanished_between_the_scan_and_the_pipeline_is_skipped():
    """SCAN is a cursor, not a snapshot: a ban can expire before the GET lands."""
    redis = _Redis({"bans_ip_10.0.0.5": None}, {})

    assert _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global") == []


@pytest.mark.parametrize("raw", [b'{"reason": "x", "date": 1}', '{"reason": "x", "date": 1}'])
def test_both_a_bytes_and_a_str_reply_decode(raw):
    """`decode_responses` is a client-level setting the operator can flip."""
    key = "bans_ip_10.0.0.6"
    redis = _Redis({key: raw}, {key: 5})

    (ban,) = _cli(redis).__getattribute__("_CLI__collect_redis_bans")("bans_ip_*", "global")

    assert ban["reason"] == "x"

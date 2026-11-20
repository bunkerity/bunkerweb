"""app/models/resilient_session.py: sessions keep working while Redis refuses or cannot be reached.

Redis is a scripted ``redis.Redis`` subclass (so the parent interface keeps it) and the fallback
is a real cachelib ``SimpleCache``: the assertions read where a session lives after each failure.
"""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from cachelib import SimpleCache
from flask import Flask, g, session
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, ResponseError

from app.models import resilient_session as rs
from app.models.resilient_session import ResilientRedisSessionInterface, _TOMBSTONE_KEY, _UNREADABLE_KEY


class ScriptedRedis(Redis):
    """Stores values in a dict; ``fail`` makes the named commands raise the given error."""

    def __init__(self):
        super().__init__()
        self.store = {}
        self.fail = {}
        self.calls = []

    def _gate(self, name):
        self.calls.append(name)
        if name in self.fail:
            raise self.fail[name]

    def get(self, name):
        self._gate("get")
        return self.store.get(name)

    def set(self, name, value, ex=None, **kwargs):
        self._gate("set")
        self.store[name] = value
        return True

    def delete(self, *names):
        self._gate("delete")
        for name in names:
            self.store.pop(name, None)
        return len(names)


class BrokenCache(SimpleCache):
    def set(self, *args, **kwargs):
        return False

    def delete(self, *args, **kwargs):
        return False


@pytest.fixture
def parts(monkeypatch):
    app = Flask("resilient")
    app.secret_key = "k"
    app.permanent_session_lifetime = timedelta(hours=1)
    clock = {"now": 100.0}
    monkeypatch.setattr(rs, "monotonic", lambda: clock["now"])
    redis, fallback, logger = ScriptedRedis(), SimpleCache(), MagicMock()
    interface = ResilientRedisSessionInterface(app, client=redis, fallback=fallback, logger=logger, breaker_seconds=10.0)
    app.session_interface = interface

    class P:
        pass

    p = P()
    p.app, p.redis, p.fallback, p.logger, p.interface, p.clock = app, redis, fallback, logger, interface, clock
    p.session = lambda data=None: interface.session_class(data or {"a": 1}, sid="s")
    return p


UNREACHABLE = RedisConnectionError("down")
REFUSED = ResponseError("OOM command not allowed when used memory > 'maxmemory'")


def test_parent_keeps_the_given_client(parts):
    assert parts.interface.client is parts.redis


class TestWrite:
    def test_healthy_redis_owns_the_session(self, parts):
        parts.fallback.set("p:s", {"stale": 1})
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert "p:s" in parts.redis.store
        assert parts.fallback.get("p:s") is None  # the local copy is dropped once Redis owns it

    def test_unreachable_redis_falls_back_and_opens_the_breaker(self, parts):
        parts.redis.fail["set"] = UNREACHABLE
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert parts.fallback.get("p:s") == {"a": 1}
        assert parts.interface.redis_available is False
        assert parts.logger.warning.call_count == 1

        parts.redis.calls.clear()
        parts.interface._upsert_session(timedelta(hours=1), parts.session({"b": 2}), "p:s")
        assert "set" not in parts.redis.calls  # breaker open: Redis is not even asked
        assert parts.fallback.get("p:s") == {"b": 2}

    def test_breaker_closes_after_the_window(self, parts):
        parts.redis.fail["set"] = UNREACHABLE
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        parts.clock["now"] += 11
        assert parts.interface.redis_available is True

    def test_outage_is_reported_once_even_across_breaker_windows(self, parts):
        parts.redis.fail["set"] = UNREACHABLE
        for _ in range(3):
            parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
            parts.clock["now"] += 11
        assert parts.logger.warning.call_count == 1

    def test_recovery_rearms_the_outage_report(self, parts):
        parts.redis.fail["set"] = UNREACHABLE
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        parts.redis.fail.clear()
        parts.clock["now"] += 11
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        parts.redis.fail["set"] = UNREACHABLE
        parts.clock["now"] += 11
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert parts.logger.warning.call_count == 2

    def test_refused_write_keeps_the_breaker_closed_and_discards_the_stale_redis_copy(self, parts):
        parts.redis.store["p:s"] = b"old"
        parts.redis.fail["set"] = REFUSED
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert parts.interface.redis_available is True
        assert parts.fallback.get("p:s") == {"a": 1}
        assert "p:s" not in parts.redis.store  # otherwise the older payload would win the next read

    def test_refusal_log_is_throttled(self, parts):
        parts.redis.fail["set"] = REFUSED
        for _ in range(4):
            parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert parts.logger.warning.call_count == 1
        parts.clock["now"] += 11
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert parts.logger.warning.call_count == 2

    def test_failed_local_write_leaves_the_redis_copy_alone(self, parts):
        parts.interface.fallback = BrokenCache()
        parts.redis.store["p:s"] = b"old"
        parts.redis.fail["set"] = REFUSED
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        assert parts.redis.store["p:s"] == b"old"

    def test_fallback_exception_never_escapes(self, parts):
        parts.interface.fallback = MagicMock()
        parts.interface.fallback.set.side_effect = OSError("disk full")
        parts.redis.fail["set"] = UNREACHABLE
        parts.interface._upsert_session(timedelta(hours=1), parts.session(), "p:s")
        parts.logger.exception.assert_called_once()
        assert parts.logger.exception.call_args.args[1] == "write"


class TestRead:
    def test_reads_from_redis(self, parts):
        parts.redis.store["p:s"] = parts.interface.serializer.encode(parts.session({"k": "v"}))
        assert parts.interface._retrieve_session_data("p:s") == {"k": "v"}

    def test_missing_in_redis_is_none(self, parts):
        assert parts.interface._retrieve_session_data("p:none") is None

    def test_local_copy_wins_over_redis_and_is_written_back(self, parts):
        parts.redis.store["p:s"] = parts.interface.serializer.encode(parts.session({"k": "stale"}))
        parts.fallback.set("p:s", {"k": "fresh"})
        assert parts.interface._retrieve_session_data("p:s") == {"k": "fresh"}
        assert parts.interface.serializer.decode(parts.redis.store["p:s"]) == {"k": "fresh"}
        assert parts.fallback.get("p:s") is None

    def test_local_copy_stays_when_redis_still_refuses_the_write_back(self, parts):
        parts.fallback.set("p:s", {"k": "fresh"})
        parts.redis.fail["set"] = REFUSED
        assert parts.interface._retrieve_session_data("p:s") == {"k": "fresh"}
        assert parts.fallback.get("p:s") == {"k": "fresh"}

    def test_local_copy_stays_while_the_breaker_is_open(self, parts):
        parts.fallback.set("p:s", {"k": "fresh"})
        parts.interface._breaker_until = parts.clock["now"] + 5
        assert parts.interface._retrieve_session_data("p:s") == {"k": "fresh"}
        assert "set" not in parts.redis.calls and parts.fallback.get("p:s") == {"k": "fresh"}

    def test_unencodable_local_copy_is_still_served(self, parts):
        parts.fallback.set("p:s", {"k": object()})
        assert "k" in parts.interface._retrieve_session_data("p:s")
        assert "Could not encode" in parts.logger.exception.call_args.args[0]

    def test_tombstone_hides_the_session_and_reconciles_the_delete(self, parts):
        parts.redis.store["p:s"] = b"zombie"
        parts.fallback.set("p:s", {_TOMBSTONE_KEY: True})
        assert parts.interface._retrieve_session_data("p:s") is None
        assert "p:s" not in parts.redis.store and parts.fallback.get("p:s") is None

    def test_tombstone_survives_while_redis_cannot_confirm(self, parts):
        parts.fallback.set("p:s", {_TOMBSTONE_KEY: True})
        parts.redis.fail["delete"] = UNREACHABLE
        assert parts.interface._retrieve_session_data("p:s") is None
        assert parts.fallback.get("p:s") == {_TOMBSTONE_KEY: True}

    def test_unreachable_read_is_remembered_for_logout(self, parts):
        parts.redis.fail["get"] = UNREACHABLE
        with parts.app.app_context():
            assert parts.interface._retrieve_session_data("p:s") is None
            assert getattr(g, _UNREADABLE_KEY) == "p:s"
        assert parts.interface.redis_available is False

    def test_read_failure_outside_an_app_context_is_none(self, parts):
        parts.redis.fail["get"] = UNREACHABLE
        assert parts.interface._retrieve_session_data("p:s") is None


class TestDelete:
    def test_confirmed_delete_leaves_nothing_behind(self, parts):
        parts.redis.store["p:s"] = b"x"
        parts.fallback.set("p:s", {"a": 1})
        parts.interface._delete_session("p:s")
        assert "p:s" not in parts.redis.store and parts.fallback.get("p:s") is None

    def test_unconfirmed_delete_leaves_a_tombstone(self, parts):
        parts.redis.fail["delete"] = UNREACHABLE
        parts.interface._delete_session("p:s")
        assert parts.fallback.get("p:s") == {_TOMBSTONE_KEY: True}

    def test_open_breaker_skips_redis_delete(self, parts):
        parts.interface._breaker_until = parts.clock["now"] + 5
        parts.interface._delete_session("p:s")
        assert "delete" not in parts.redis.calls and parts.fallback.get("p:s") == {_TOMBSTONE_KEY: True}

    def test_uncleared_local_copy_is_reported(self, parts):
        parts.interface.fallback = BrokenCache()
        parts.interface._drop_local_copy("p:s")
        assert "kept a copy" in parts.logger.warning.call_args.args[0]


class TestSaveSession:
    def test_logout_revokes_the_id_redis_could_not_read(self, parts):
        parts.redis.store["p:old"] = b"still-valid"
        sess = parts.interface.session_class({"x": 1}, sid="new")
        sess.clear()
        sess.pop("_permanent")
        sess.modified = True
        with parts.app.test_request_context("/"):
            setattr(g, _UNREADABLE_KEY, "p:old")
            parts.interface.save_session(parts.app, sess, parts.app.response_class())
        assert "p:old" not in parts.redis.store

    def test_unmodified_empty_session_does_not_revoke(self, parts):
        parts.redis.store["p:old"] = b"still-valid"
        sess = parts.interface.session_class({}, sid="new")
        with parts.app.test_request_context("/"):
            setattr(g, _UNREADABLE_KEY, "p:old")
            parts.interface.save_session(parts.app, sess, parts.app.response_class())
        assert "p:old" in parts.redis.store

    def test_full_request_cycle_round_trip(self, parts):
        parts.app.add_url_rule("/set", "set", lambda: session.__setitem__("u", "alice") or "ok")
        parts.app.add_url_rule("/get", "get", lambda: session.get("u", "none"))
        client = parts.app.test_client()
        parts.redis.fail["set"] = UNREACHABLE
        assert client.get("/set").data == b"ok"
        assert client.get("/get").data == b"alice"  # served from the local store
        assert len(parts.redis.store) == 0

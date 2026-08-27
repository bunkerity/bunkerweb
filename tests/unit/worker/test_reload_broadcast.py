"""The reload debounce must coalesce reloads without dropping anyone's cache push.

It used to return before ``send_files`` whenever another job held the lock. At boot a dozen
jobs finish inside five seconds, so all but the first had their output silently withheld from
the instances -- a downloaded blocklist or a fresh certificate sitting in the worker's
``/var/cache/bunkerweb`` while the instance's stayed empty, with every job recorded a success.
``tests/core/blacklist.yml::ip_urls`` is the integration test that catches it end to end;
these pin the mechanism.
"""

from types import ModuleType
from unittest.mock import Mock, patch

from test_delivery_guarantees import BROKER, LOGGER, TASKS


class _LockRedis:
    """Enough Redis for the debounce: SETNX semantics, DEL returning how many keys went.

    Plus the set operations the deferred-acknowledgement queue uses: a job that writes files and
    asks for a reload leaves its change acknowledgement here, and the reload applies it only once
    the push has actually landed.
    """

    def __init__(self, held=None, pending_acks=None):
        self.keys = dict(held or {})
        self.sets = {"bw:reload_pending_acks": set(pending_acks or ())}
        self.expirations = []
        self.ops = []

    def smembers(self, key):
        self.ops.append(("smembers", key))
        return set(self.sets.get(key, ()))

    def srem(self, key, *members):
        self.ops.append(("srem", key))
        target = self.sets.setdefault(key, set())
        removed = 0
        for member in members:
            if member in target:
                target.discard(member)
                removed += 1
        return removed

    def sadd(self, key, *members):
        self.ops.append(("sadd", key))
        self.sets.setdefault(key, set()).update(members)
        return len(members)

    def set(self, key, value, nx=False, ex=None):
        self.ops.append(("set", key))
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True

    def delete(self, key):
        self.ops.append(("delete", key))
        return 1 if self.keys.pop(key, None) is not None else 0

    def expire(self, key, ttl):
        self.expirations.append((key, ttl))

    def eval(self, _script, _numkeys, lock, dirty):
        """redis-py's EVAL -- Lua run by the Redis server, not Python's builtin.

        Stands in for RELEASE_IF_CLEAN: release only while nothing is flagged.
        """
        self.ops.append(("eval", lock))
        if dirty in self.keys:
            return 0
        self.keys.pop(lock, None)
        return 1


def _apis():
    apis = Mock()
    apis.send_files = Mock(return_value=True)
    apis.send_to_apis = Mock(return_value=(True, {}))
    return apis


def _with_redis(client):
    module = ModuleType("redis")
    module.Redis = Mock()
    module.Redis.from_url = Mock(return_value=client)
    return patch.dict("sys.modules", {"redis": module})


def test_the_api_token_falls_back_to_the_stored_config(monkeypatch):
    """API_TOKEN is a BunkerWeb setting, so a split deployment sets it on the instances and the
    API rather than on the worker container. Reading only the environment built tokenless
    callers, and every push was refused with 444 "missing API token" -- invisibly.
    """
    monkeypatch.delenv("API_TOKEN", raising=False)
    db = Mock()
    db.get_config.return_value = {"API_TOKEN": "from-the-database"}

    assert TASKS._api_token(db, LOGGER) == "from-the-database"

    monkeypatch.setenv("API_TOKEN", "from-the-env")
    assert TASKS._api_token(db, LOGGER) == "from-the-env"


def test_the_holder_pushes_the_cache_then_reloads():
    client = _LockRedis()
    apis = _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    apis.send_files.assert_called_once_with("/var/cache/bunkerweb", "/cache")
    apis.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30))
    # Held for the next job to take, not left behind to block it for a minute.
    assert TASKS.RELOAD_LOCK_KEY not in client.keys


def test_a_job_that_loses_the_lock_flags_the_run_instead_of_pushing():
    client = _LockRedis({TASKS.RELOAD_LOCK_KEY: "1"})
    apis = _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    assert client.keys.get(TASKS.RELOAD_DIRTY_KEY) == "1"
    # One push per window, not one per job: the holder's tar carries this job's files, which
    # were written before it asked for the reload.
    apis.send_files.assert_not_called()


def test_the_flag_goes_up_before_the_lock_is_contested():
    """Lost wakeup, closed by ordering. Flagging only after a failed acquisition leaves a window
    where the holder has already made its last check: it releases, the flag goes up behind it,
    and nothing pushes. Raising the flag first means the holder either claims it (and pushes
    after) or cannot release.
    """
    client = _LockRedis()
    with _with_redis(client):
        TASKS._request_reload_debounced(_apis(), BROKER, LOGGER)

    sets = [key for op, key in client.ops if op == "set"]
    assert sets.index(TASKS.RELOAD_DIRTY_KEY) < sets.index(TASKS.RELOAD_LOCK_KEY)


def test_the_holder_cannot_release_while_a_job_is_flagged():
    """The release is one atomic step for the same reason: checking then deleting lets a flag
    land in between."""
    client = _LockRedis()
    client.keys[TASKS.RELOAD_DIRTY_KEY] = "1"
    assert client.eval(TASKS.RELEASE_IF_CLEAN, 2, TASKS.RELOAD_LOCK_KEY, TASKS.RELOAD_DIRTY_KEY) == 0
    assert "if redis.call('exists', KEYS[2]) == 1 then return 0 end" in TASKS.RELEASE_IF_CLEAN


def test_a_job_that_finishes_during_the_push_earns_another_round():
    """The regression. Files written after the holder built its tar are not in it, so a second
    reload alone would reload the same stale tree -- the holder has to push again."""
    client = _LockRedis()
    apis = _apis()
    flagged = []

    def push(*_args):
        if not flagged:
            flagged.append(True)
            client.set(TASKS.RELOAD_DIRTY_KEY, "1")
        return True

    apis.send_files = Mock(side_effect=push)
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    assert apis.send_files.call_count == 2
    assert apis.send_to_apis.call_count == 2
    assert client.expirations == [(TASKS.RELOAD_LOCK_KEY, TASKS.RELOAD_LOCK_TTL)]


def test_a_steady_stream_of_dirty_jobs_cannot_pin_the_worker():
    class _AlwaysDirty(_LockRedis):
        def delete(self, key):
            if key == TASKS.RELOAD_DIRTY_KEY:
                return 1
            return super().delete(key)

    client = _AlwaysDirty()
    apis = _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    assert apis.send_to_apis.call_count == TASKS.MAX_RELOAD_ROUNDS
    assert TASKS.RELOAD_LOCK_KEY not in client.keys


def test_a_failed_push_releases_the_lock():
    """It raises, and the job is recorded failed -- but leaving the lock behind would mute
    every other job's reload until the TTL expired."""
    client = _LockRedis()
    apis = _apis()
    apis.send_files = Mock(return_value=False)
    with _with_redis(client):
        try:
            TASKS._request_reload_debounced(apis, BROKER, LOGGER)
        except RuntimeError:
            pass

    assert TASKS.RELOAD_LOCK_KEY not in client.keys

"""Regression tests for ResilientRedisSessionInterface (src/ui/app/models/resilient_session.py).

A session written to the local fallback while Redis is unreachable/refusing must never be
rolled back to a stale Redis copy once Redis recovers, and a delete performed during an
outage must not resurrect the pre-delete Redis copy either. Run against the unfixed module,
the rollback cases below fail; against the fixed module, everything passes.

Uses a real Flask app, real Flask-Session machinery (the real ResilientRedisSessionInterface,
never mocked), a real SafeFileSystemCache in a temp dir, and a fake Redis client implementing
get/set/delete that can be switched to raise a timeout (unreachable) or a response error
(refused, e.g. OOM -- which only ever rejects writes, never reads or deletes).

Some routes flip the fake client into failure mode from *inside* the view function, after
Flask-Session's open_session() has already read the session but before save_session() writes
it back. That reproduces the actual race: Redis answers the read and dies before the save,
which is the only way to hit a failed write/delete without also losing the session id (a read
miss makes Flask-Session mint a brand new id, which is a separate, pre-existing property of
open_session() and not what these tests are about).

Cookies are propagated explicitly with client.set_cookie(), never via a raw "Cookie" header:
Werkzeug's test client owns cookies through its own jar and silently ignores a hand-written
Cookie header, so a request meant to replay a specific session id (a second worker, or a
stale tab replaying a cookie the server told it to delete) must go through set_cookie().
"""

import shutil
import sys
import tempfile
import unittest
from datetime import timedelta
from http.cookies import SimpleCookie
from logging import NullHandler, getLogger
from pathlib import Path
from time import monotonic, sleep

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "ui"))

from unittest.mock import MagicMock

from flask import Flask, session  # noqa: E402
from redis.cluster import RedisCluster  # noqa: E402
from redis.exceptions import ClusterDownError, ResponseError, SlotNotCoveredError, TimeoutError as RedisTimeoutError  # noqa: E402

from app.models.resilient_session import ResilientRedisSessionInterface  # noqa: E402
from app.models.safe_session_cache import SafeFileSystemCache  # noqa: E402

BREAKER_SECONDS = 0.05
RECOVERY_SETTLE = 0.1  # > BREAKER_SECONDS, so a just-opened breaker is always closed again by then
COOKIE_NAME = "session"


class FakeRedisClient:
    """Minimal get/set/delete stand-in for redis.Redis with two switchable failure modes.

    fail_mode="unreachable" raises the same exception a dead/paused Redis raises (a timeout)
    on every command. fail_mode="refused" raises what a Redis at maxmemory raises, and only
    for writes: reads and deletes still succeed, same as a real Redis at maxmemory.
    """

    def __init__(self):
        self.store = {}
        self.fail_mode = None

    def _maybe_raise(self, op):
        if self.fail_mode == "unreachable":
            raise RedisTimeoutError(f"simulated Redis timeout during {op}")
        if self.fail_mode == "cluster_down":
            raise ClusterDownError(f"simulated Redis Cluster down during {op}")
        if self.fail_mode == "slot_not_covered":
            raise SlotNotCoveredError(f"simulated slot not covered during {op}")
        if self.fail_mode == "refused" and op == "set":
            raise ResponseError("OOM command not allowed when used memory > 'maxmemory'.")

    def get(self, name):
        self._maybe_raise("get")
        return self.store.get(name)

    def set(self, name, value, ex=None):
        self._maybe_raise("set")
        self.store[name] = value
        return True

    def delete(self, name):
        self._maybe_raise("delete")
        return 1 if self.store.pop(name, None) is not None else 0


def _sid_from_response(resp, cookie_name=COOKIE_NAME):
    for header in resp.headers.get_all("Set-Cookie"):
        jar = SimpleCookie()
        jar.load(header)
        if cookie_name in jar:
            return jar[cookie_name].value
    raise AssertionError("response did not set a session cookie")


class ResilientSessionTestCase(unittest.TestCase):
    KEY_PREFIX = "test_session:"

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp(prefix="bw-ui-session-test-")
        self.redis = FakeRedisClient()

    def tearDown(self):
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def _make_app(self, lifetime_seconds=5, redis_client=None, cache_dir=None):
        redis_client = redis_client if redis_client is not None else self.redis

        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test-secret"
        app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=lifetime_seconds)
        app.config["SESSION_REFRESH_EACH_REQUEST"] = True

        logger = getLogger(f"test.resilient_session.{id(app)}")
        logger.addHandler(NullHandler())
        logger.propagate = False

        fallback = SafeFileSystemCache(cache_dir=cache_dir or self.cache_dir, threshold=0, default_timeout=lifetime_seconds)
        app.session_interface = ResilientRedisSessionInterface(
            app,
            client=redis_client,
            fallback=fallback,
            logger=logger,
            breaker_seconds=BREAKER_SECONDS,
            key_prefix=self.KEY_PREFIX,
            use_signer=False,
            permanent=True,
            sid_length=32,
        )

        @app.route("/set/<value>")
        def set_value(value):
            session["v"] = value
            return "ok"

        @app.route("/get")
        def get_value():
            return session.get("v", "")

        @app.route("/logout")
        def logout():
            session.clear()
            return "ok"

        @app.route("/fail_then_set/<value>")
        def fail_then_set(value):
            # The session is already loaded (open_session ran before this view): only the
            # save that follows this view sees the failure, exactly like Redis dying mid-request.
            redis_client.fail_mode = "unreachable"
            session["v"] = value
            return "ok"

        @app.route("/fail_then_logout")
        def fail_then_logout():
            redis_client.fail_mode = "unreachable"
            session.clear()
            return "ok"

        @app.route("/fail_then_rotate")
        def fail_then_rotate():
            redis_client.fail_mode = "unreachable"
            app.session_interface.regenerate(session)
            return "ok"

        @app.route("/cluster_down_then_set/<value>")
        def cluster_down_then_set(value):
            redis_client.fail_mode = "cluster_down"
            session["v"] = value
            return "ok"

        @app.route("/slot_not_covered_then_set/<value>")
        def slot_not_covered_then_set(value):
            redis_client.fail_mode = "slot_not_covered"
            session["v"] = value
            return "ok"

        return app

    def _store_id(self, sid):
        return self.KEY_PREFIX + sid

    @staticmethod
    def _replay(client, sid):
        """Force `client`'s next request to present `sid`, regardless of its cookie jar --
        a second worker's client that never had it, or a tab replaying a cookie the server
        already told it to delete."""
        client.set_cookie(COOKIE_NAME, sid)

    # 1. write timeout during outage, then recovery: reads return "newer"; Redis ends up
    # holding "newer" (reconciled) and the local copy is gone.
    def test_write_timeout_then_recovery_reconciles_to_redis(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)
        self.assertIsNotNone(self.redis.get(store_id))  # redis holds "original"

        client.get("/fail_then_set/newer")
        # write failed against redis: only the local fallback has "newer", and the stale
        # "original" in redis was left alone (discard is skipped while redis is unreachable).
        self.assertEqual(interface.fallback.get(store_id).get("v"), "newer")
        self.assertIsNotNone(self.redis.store.get(store_id))

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        resp3 = client.get("/get")
        self.assertEqual(resp3.data, b"newer")

        # reconciled: redis now holds "newer", local copy is gone
        redis_value = interface.serializer.decode(self.redis.get(store_id))
        self.assertEqual(redis_value.get("v"), "newer")
        self.assertIsNone(interface.fallback.get(store_id))

    # 2. read timeout: the local copy is served.
    def test_read_timeout_serves_local_copy(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)

        client.get("/fail_then_set/newer")

        # Still unreachable while reading (fail_then_set left fail_mode set).
        resp2 = client.get("/get")
        self.assertEqual(resp2.data, b"newer")
        self.assertIsNotNone(interface.fallback.get(store_id))

    # 2b. Redis Cluster raising ClusterDownError behaves like any other unreachable
    # backend: the write falls back locally and a read while still down serves it.
    def test_cluster_down_error_serves_local_copy(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)

        client.get("/cluster_down_then_set/newer")

        # Still down while reading (cluster_down_then_set left fail_mode set).
        resp2 = client.get("/get")
        self.assertEqual(resp2.data, b"newer")
        self.assertIsNotNone(interface.fallback.get(store_id))

    # 2c. SlotNotCoveredError (raised during a cluster failover window) does not subclass
    # RedisError, unlike every other exception these tests cover: it must still be handled
    # as unreachable, not escape as a 500.
    def test_slot_not_covered_serves_local_copy(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)

        client.get("/slot_not_covered_then_set/newer")

        # Still down while reading (slot_not_covered_then_set left fail_mode set).
        resp2 = client.get("/get")
        self.assertEqual(resp2.data, b"newer")
        self.assertIsNotNone(interface.fallback.get(store_id))

    # A RedisCluster client must be kept as-is: the parent interface only recognizes
    # plain redis.Redis and would otherwise silently swap it for a localhost client.
    def test_cluster_client_stored_as_is(self):
        cluster_client = MagicMock(spec=RedisCluster)
        app = self._make_app(redis_client=cluster_client)
        self.assertIs(app.session_interface.client, cluster_client)

    # 3. refused write (OOM): local copy served and the stale Redis copy is deleted.
    def test_refused_write_discards_stale_redis_copy(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)
        self.assertIsNotNone(self.redis.get(store_id))

        # A refused write never blocks reads, so no fail_then_* trick is needed here.
        self.redis.fail_mode = "refused"
        client.get("/set/newer")
        self.assertEqual(interface.fallback.get(store_id).get("v"), "newer")
        self.assertIsNone(self.redis.get(store_id))  # discarded immediately, not on next read

        self.redis.fail_mode = None
        resp3 = client.get("/get")
        self.assertEqual(resp3.data, b"newer")

    # 4. delete during outage then recovery: session is gone from both stores, a read returns None.
    def test_delete_during_outage_then_recovery_removes_both_copies(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)
        self.assertIsNotNone(self.redis.get(store_id))

        client.get("/fail_then_logout")
        # the delete could not reach redis: a stale copy is still there, tombstoned locally
        self.assertIsNotNone(self.redis.store.get(store_id))
        self.assertIsInstance(interface.fallback.get(store_id), dict)

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        self._replay(client, sid)  # logout told the client to delete its cookie; force a replay
        resp2 = client.get("/get")
        self.assertEqual(resp2.data, b"")

        self.assertIsNone(self.redis.get(store_id))
        self.assertIsNone(interface.fallback.get(store_id))

    # 5. logout path during an outage: a stale cookie replayed after recovery must not
    # resurrect the session (a revocation must not be silently undone).
    def test_logout_during_outage_does_not_resurrect_on_recovery(self):
        app = self._make_app()
        client = app.test_client()

        resp = client.get("/set/secret")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)

        client.get("/fail_then_logout")

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        # a stale browser tab / bookmark replays the pre-logout cookie once Redis recovers
        self._replay(client, sid)
        resp2 = client.get("/get")
        self.assertEqual(resp2.data, b"")
        self.assertIsNone(self.redis.get(store_id))

    # 6. expiry: a tombstone and a local copy both expire with the session lifetime.
    def test_tombstone_and_local_copy_expire_with_session_lifetime(self):
        app = self._make_app(lifetime_seconds=1)
        interface = app.session_interface

        # local-copy branch: a brand new session, born entirely during the outage.
        client1 = app.test_client()
        self.redis.fail_mode = "unreachable"
        resp = client1.get("/set/newer")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)
        self.assertIsInstance(interface.fallback.get(store_id), dict)

        sleep(1.2)
        self.assertIsNone(interface.fallback.get(store_id))
        resp2 = client1.get("/get")
        self.assertEqual(resp2.data, b"")  # local copy expired, redis still unreachable

        # That last read found the local copy gone and, still seeing fail_mode set, tripped
        # the breaker again: let it expire before relying on redis_available below.
        sleep(RECOVERY_SETTLE)

        # tombstone branch: a fresh client, so this session gets its own new id (unrelated to
        # the expired one above, which this app's fallback/redis still remember nothing useful of).
        client2 = app.test_client()
        self.redis.fail_mode = None
        resp3 = client2.get("/set/original2")
        sid2 = _sid_from_response(resp3)
        store_id2 = self._store_id(sid2)
        self.assertIsNotNone(self.redis.get(store_id2))

        client2.get("/fail_then_logout")
        self.assertIsInstance(interface.fallback.get(store_id2), dict)

        sleep(1.2)
        self.assertIsNone(interface.fallback.get(store_id2))

    # 7. process restart: a brand-new interface instance over the same fallback dir stays authoritative.
    def test_local_copy_survives_process_restart(self):
        app = self._make_app()
        client = app.test_client()

        resp = client.get("/set/original")
        sid = _sid_from_response(resp)

        client.get("/fail_then_set/newer")

        # Redis recovers, and separately, this worker restarts: a fresh interface with no
        # memory of the outage, over the same fallback directory.
        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        app2 = self._make_app()
        client2 = app2.test_client()
        self._replay(client2, sid)  # client2 never saw this cookie on its own
        resp2 = client2.get("/get")
        self.assertEqual(resp2.data, b"newer")

    # 8. two interface instances sharing one fallback dir (multi-worker on one host) agree.
    def test_two_instances_sharing_fallback_dir_agree(self):
        app1 = self._make_app()
        app2 = self._make_app()  # same self.cache_dir, same self.redis: shared state
        client1 = app1.test_client()
        client2 = app2.test_client()

        resp = client1.get("/set/original")
        sid = _sid_from_response(resp)
        store_id = self._store_id(sid)

        client1.get("/fail_then_set/newer")

        # worker 2 sees the same local copy right away, without ever having contacted redis.
        self._replay(client2, sid)
        resp2 = client2.get("/get")
        self.assertEqual(resp2.data, b"newer")

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        resp3 = client2.get("/get")
        self.assertEqual(resp3.data, b"newer")
        self.assertIsNone(app1.session_interface.fallback.get(store_id))

        # worker 1 now reads the reconciled value back from redis.
        resp4 = client1.get("/get")
        self.assertEqual(resp4.data, b"newer")

    # 12. Redis is already down when the request starts: the session read fails, so the request
    # carries a session it cannot see. Logging out must still revoke the id the cookie names.
    def test_logout_with_unreadable_session_during_outage_is_not_undone(self):
        app = self._make_app()
        client = app.test_client()

        sid = _sid_from_response(client.get("/set/secret"))
        store_id = self._store_id(sid)

        self.redis.fail_mode = "unreachable"
        self._replay(client, sid)
        client.get("/logout")
        self.assertIsNotNone(self.redis.store.get(store_id))  # the stale copy is still in Redis

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        self._replay(client, sid)
        self.assertEqual(client.get("/get").data, b"")
        self.assertIsNone(self.redis.get(store_id))

    # 13. Same, with the breaker already open: the read is skipped rather than failed.
    def test_logout_with_breaker_open_is_not_undone(self):
        app = self._make_app()
        client = app.test_client()
        interface = app.session_interface

        sid = _sid_from_response(client.get("/set/secret"))
        store_id = self._store_id(sid)

        self.redis.fail_mode = "unreachable"
        interface._breaker_until = monotonic() + 60
        self._replay(client, sid)
        client.get("/logout")

        self.redis.fail_mode = None
        interface._breaker_until = 0.0
        self._replay(client, sid)
        self.assertEqual(client.get("/get").data, b"")
        self.assertIsNone(self.redis.get(store_id))

    # 14. A plain request during the outage is not a logout: the session must survive it.
    def test_unreadable_session_read_only_request_keeps_the_session(self):
        app = self._make_app()
        client = app.test_client()

        sid = _sid_from_response(client.get("/set/secret"))

        self.redis.fail_mode = "unreachable"
        self._replay(client, sid)
        client.get("/get")

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        self._replay(client, sid)
        self.assertEqual(client.get("/get").data, b"secret")

    # 15. Session id rotation while Redis dies: the old id is refused after recovery and the
    # rotated session is still served.
    def test_rotation_during_outage_is_not_undone(self):
        app = self._make_app()
        client = app.test_client()

        old_sid = _sid_from_response(client.get("/set/secret"))
        old_store_id = self._store_id(old_sid)

        new_sid = _sid_from_response(client.get("/fail_then_rotate"))
        self.assertNotEqual(old_sid, new_sid)
        self.assertEqual(client.get("/get").data, b"secret")  # served from the local store

        self.redis.fail_mode = None
        sleep(RECOVERY_SETTLE)
        self._replay(client, old_sid)
        self.assertEqual(client.get("/get").data, b"")
        self.assertIsNone(self.redis.get(old_store_id))

        self._replay(client, new_sid)
        self.assertEqual(client.get("/get").data, b"secret")


if __name__ == "__main__":
    unittest.main()

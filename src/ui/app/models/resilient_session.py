from time import monotonic
from typing import Any, Optional

from cachelib.base import BaseCache
from flask_session.redis import RedisSessionInterface
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError, TimeoutError as RedisTimeoutError

# Only these are worth leaving Redis alone for. A command rejected because Redis is at
# maxmemory comes back instantly and says nothing about the next one: reads and deletes are
# still served, so skipping them would hide live sessions and leave logged-out ones behind.
UNREACHABLE_ERRORS = (RedisConnectionError, RedisTimeoutError)


def _total_seconds(lifetime) -> int:
    return int(lifetime.total_seconds())


class ResilientRedisSessionInterface(RedisSessionInterface):
    """Redis-backed sessions that survive Redis refusing commands after startup.

    The backend is picked once per worker, so a Redis that dies or fills up later leaves the
    worker pinned to it and every session read or write raises. Sessions then fall back to a
    local cache until Redis answers again.

    An eviction is invisible here: Redis reports success and simply no longer holds the key,
    so only connection failures and rejected writes are covered.
    """

    def __init__(self, app, *, client, fallback: BaseCache, logger, breaker_seconds: float = 10.0, **kwargs):
        self.fallback = fallback
        self.logger = logger
        self.breaker_seconds = breaker_seconds
        self._breaker_until = 0.0
        self._next_log_at = 0.0
        self._reported_unreachable = False
        super().__init__(app, client=client, **kwargs)
        # The parent silently swaps any client that is not a redis.Redis for a new one on
        # localhost, which would send sessions somewhere nobody configured.
        self.client = client

    @property
    def redis_available(self) -> bool:
        return monotonic() >= self._breaker_until

    def _handle_failure(self, action: str, exc: BaseException) -> None:
        """Record a failed Redis operation, and stop asking only if Redis is unreachable.

        An unreachable Redis costs REDIS_TIMEOUT per operation, which stalls the whole UI, so
        it is worth skipping for a while. A rejected command is not: see UNREACHABLE_ERRORS.
        """
        now = monotonic()
        if isinstance(exc, UNREACHABLE_ERRORS):
            # Once per outage, not once per breaker window: the breaker reopens every few
            # seconds to probe, and an operator has to be able to tell one long outage from
            # a flapping Redis.
            if not self._reported_unreachable:
                self._reported_unreachable = True
                self.logger.warning("Redis is unreachable (%s), skipping it for %d seconds at a time", exc, int(self.breaker_seconds))
            self._breaker_until = now + self.breaker_seconds
            return

        # Throttled, because a Redis at maxmemory rejects a write on every single save.
        if now >= self._next_log_at:
            self._next_log_at = now + self.breaker_seconds
            self.logger.warning("Redis refused the session %s (%s), using the local session store", action, exc)

    def _note_redis_answered(self) -> None:
        """Arm the unreachable report again, so the next outage is announced."""
        self._reported_unreachable = False

    def _fallback_call(self, action: str, call, default=None):
        """Never let the local store raise: it is what the failing Redis falls back to."""
        try:
            return call()
        except Exception as e:
            self.logger.exception("Local session store failed to %s (%s)", action, e)
            return default

    def _discard_stale_redis_copy(self, store_id: str) -> None:
        """Remove what Redis still holds for a session it just refused to update.

        Left there, the older payload keeps winning the read, which strands a multi-step flow
        such as 2FA on its pre-refusal state for as long as Redis stays full. DEL frees memory
        so it is not rejected at maxmemory, and it only runs once the local copy exists.
        """
        if not self.redis_available:
            return
        try:
            self.client.delete(store_id)
        except RedisError as e:
            self._handle_failure("delete", e)
        else:
            self._note_redis_answered()

    def _retrieve_session_data(self, store_id: str) -> Optional[dict]:
        if self.redis_available:
            try:
                serialized_session_data = self.client.get(store_id)
                self._note_redis_answered()
                if serialized_session_data:
                    return self.serializer.decode(serialized_session_data)
            except RedisError as e:
                self._handle_failure("read", e)

        # A session written while Redis was refusing commands only exists locally, so a miss
        # upstream must not end it. Same payload shape as the cachelib interface: a plain dict.
        local_session_data = self._fallback_call("read", lambda: self.fallback.get(store_id))
        return local_session_data if isinstance(local_session_data, dict) else None

    def _upsert_session(self, session_lifetime, session: Any, store_id: str) -> None:
        storage_time_to_live = _total_seconds(session_lifetime)

        if self.redis_available:
            try:
                self.client.set(name=store_id, value=self.serializer.encode(session), ex=storage_time_to_live)
            except RedisError as e:
                self._handle_failure("write", e)
            else:
                self._note_redis_answered()
                # Drop the local copy once Redis owns the session again, otherwise expiry in
                # Redis would resurrect the stale local one on the next read.
                self._fallback_call("delete", lambda: self.fallback.delete(store_id))
                return

        # cachelib reports a failed write by returning False rather than raising, so the result
        # is what says the session is safe. Dropping the Redis copy without it would leave the
        # session in no store at all, which a full disk alone would be enough to cause.
        # ponytail: last writer wins across workers, so a peer that succeeds against a recovered
        # Redis in this window can still have its copy deleted here. Costs a login, not access.
        if self._fallback_call("write", lambda: self.fallback.set(store_id, dict(session), timeout=storage_time_to_live)):
            self._discard_stale_redis_copy(store_id)

    def _delete_session(self, store_id: str) -> None:
        if self.redis_available:
            try:
                self.client.delete(store_id)
            except RedisError as e:
                self._handle_failure("delete", e)
            else:
                self._note_redis_answered()

        # Always both: a logout or an id rotation must not leave a usable copy behind.
        self._fallback_call("delete", lambda: self.fallback.delete(store_id))

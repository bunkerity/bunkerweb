from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from logging import getLogger
from time import perf_counter, time

from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError as RequestsConnectionError, RetryError, Timeout
from urllib3.util.retry import Retry

# The id of the request being served, propagated to the API so one page render can be followed
# across both services' logs. A ContextVar rather than an attribute: the client is a shared
# singleton and the UI serves requests on threads.
REQUEST_ID: ContextVar[str] = ContextVar("bw_request_id", default="")

# Per-request memo for idempotent GETs, opened by the caller for the span of one request (see
# `src/ui/app/perf.py`). One page render asks several times for the same metadata, global
# settings or instance list, because the shared context and the route each need them and
# neither can see the other's answer.
#
# Scoped to a single request on purpose. A cross-request cache would need invalidation on every
# mutation path in the product; this one cannot go stale, because nothing outside the request
# can change while it is open — and any non-GET the request itself makes empties it.
#
# Entries are copied in and out. Callers treat what they get back as theirs and edit it in place
# (`Config.get_plugins` used to pop the `id` off every plugin), which without a copy hands the
# next caller in the same request a payload the first one has already taken apart. On the
# largest response in the product, 212 KB of plugin schemas, a copy costs 2.9 ms against the
# 27 ms round trip it replaces; on the 2 KB metadata that is actually fetched twice per render,
# it costs nothing worth measuring.
REQUEST_CACHE: ContextVar = ContextVar("bw_request_cache", default=None)


def _cache_key(path: str, kwargs: dict):
    """A GET is identified by its path and its query. Lists are ordered by the caller, so they
    are compared as given rather than sorted — `filtered_settings=[a, b]` and `[b, a]` are two
    different requests as far as the API is concerned."""
    params = kwargs.get("params") or {}
    return (path, tuple(sorted((key, tuple(value) if isinstance(value, list) else value) for key, value in params.items())))


class ApiClientError(Exception):
    """API returned a 4xx error."""

    def __init__(self, message, status_code=None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ApiUnavailableError(Exception):
    """API unreachable or returned 5xx."""

    def __init__(self, message="API unavailable"):
        self.message = message
        super().__init__(message)


class BaseApiClient:
    """Shared HTTP client base class for BunkerWeb API consumers.

    Provides connection pooling, Bearer token auth, error handling, and TTL-cached
    readonly check. Subclass this to add domain-specific API methods.
    """

    def __init__(self, base_url: str, api_token: str, timeout=30, logger_name: str = "API_CLIENT"):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._logger = getLogger(logger_name)

        self.session = Session()
        self.session.headers["Authorization"] = f"Bearer {api_token}"
        self.session.headers["Content-Type"] = "application/json"

        # Connection pooling with 1 retry on 5xx/connection errors.
        # respect_retry_after_header is OFF on purpose: urllib3 retries 429 whenever the response
        # carries a Retry-After (429 is in Retry.RETRY_AFTER_STATUS_CODES), and it *sleeps* for the
        # value the server sent. The API's rate limiter answers with the remaining window, so a
        # single 429 blocked the calling thread for up to a minute inside a request handler --
        # long enough for BunkerWeb's own 60s proxy read timeout to kill the browser connection.
        # Surfacing the 429 immediately as ApiClientError is the honest failure.
        retry = Retry(total=1, backoff_factor=0.5, status_forcelist=[502, 503, 504], respect_retry_after_header=False)
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._readonly_cache = None
        self._readonly_cache_ttl = 5  # seconds
        self._readonly_cache_time = 0
        self._expect_errors = False  # When True, log failures at WARNING instead of ERROR

        # Optional (method, path, duration_ms, status) callback, set by the caller that wants
        # to account for its own fan-out — see `src/ui/app/perf.py`. Left None everywhere else,
        # which is why this costs nothing to the scheduler and the autoconf.
        self.observer = None

    @contextmanager
    def expect_errors(self):
        """Context manager to temporarily downgrade error logs to WARNING.

        Use when failures are expected (e.g., initial API connectivity checks).
        """
        self._expect_errors = True
        try:
            yield
        finally:
            self._expect_errors = False

    # ── Core request methods ─────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs):
        """Central request method with error handling.

        Returns the parsed JSON response dict on success.
        Raises ApiClientError on 4xx, ApiUnavailableError on 5xx/network errors.
        """
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)

        log = self._logger.warning if self._expect_errors else self._logger.error

        request_id = REQUEST_ID.get()
        if request_id:
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("X-Request-ID", request_id)
            kwargs["headers"] = headers

        cache = REQUEST_CACHE.get()
        cached = method == "GET" and cache is not None and "data" not in kwargs and "json" not in kwargs
        if cached:
            key = _cache_key(path, kwargs)
            if key in cache:
                # Counted as a hit rather than a call: the point of the memo is that the number
                # in `Server-Timing` goes down, and a hit costs no round trip to hide.
                self._observe(method, path, perf_counter(), "memo")
                return deepcopy(cache[key])

        started = perf_counter()
        try:
            resp = self.session.request(method, url, **kwargs)
        except (RequestsConnectionError, Timeout, RetryError) as e:
            # `RetryError` belongs here, not with the status handling below. The retry policy has
            # `status_forcelist=[502, 503, 504]`, and once those retries are spent requests does not
            # *return* the response — urllib3 raises `MaxRetryError` and requests re-raises
            # `RetryError`, which subclasses `RequestException` and not `ConnectionError`. Leaving
            # it out made the `status_code >= 500` branch below dead for exactly the three statuses
            # it exists for, and let a raw requests exception escape the client: every caller wraps
            # these calls in `except (ApiClientError, ApiUnavailableError)`, so a degraded API
            # turned every UI page into a 500 instead of an "API unavailable" flash.
            #
            # Timed and counted like any other call: a page that is slow because the API is
            # unreachable has to look slow in the accounting too.
            self._observe(method, path, started, None)
            log(f"API unreachable ({method} {path}): {e}")
            raise ApiUnavailableError(f"Cannot reach API at {self.base_url}: {e}") from e

        self._observe(method, path, started, resp.status_code)

        # A write invalidates everything: cheaper and safer than tracking which read each
        # endpoint could have affected, and a request that writes then reads is rare.
        if cache is not None and method != "GET":
            cache.clear()

        if resp.status_code >= 500:
            msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
            log(f"API returned {resp.status_code} ({method} {path}): {msg}")
            raise ApiUnavailableError(f"API returned {resp.status_code}")

        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("message", body.get("msg", resp.text[:500]))
            except Exception:
                msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
            raise ApiClientError(msg, status_code=resp.status_code)

        # 204 No Content or empty body
        if resp.status_code == 204 or not resp.content:
            payload = {"status": "success"}
        else:
            try:
                payload = resp.json()
            except Exception:
                payload = {"status": "success", "data": resp.text}

        # Only successful GETs are memoised — the error paths above raise before reaching here,
        # so a failure is retried by the next caller rather than remembered.
        if cached:
            cache[key] = deepcopy(payload)
        return payload

    def _observe(self, method: str, path: str, started: float, status):
        """Hand one call to the observer, if there is one. Never lets it break a request:
        accounting that can take the page down with it is worse than no accounting."""
        if self.observer is None:
            return
        try:
            self.observer(method, path, (perf_counter() - started) * 1000, status)
        except BaseException as e:  # noqa: B902
            self._logger.debug(f"API call observer failed: {e}")

    def _get(self, path: str, **kwargs):
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs):
        return self._request("POST", path, **kwargs)

    def _put(self, path: str, **kwargs):
        return self._request("PUT", path, **kwargs)

    def _patch(self, path: str, **kwargs):
        return self._request("PATCH", path, **kwargs)

    def _delete(self, path: str, **kwargs):
        return self._request("DELETE", path, **kwargs)

    def _raw_request(self, method: str, path: str, **kwargs):
        """Like _request but returns the raw Response object (for binary downloads)."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)

        try:
            resp = self.session.request(method, url, **kwargs)
        except (RequestsConnectionError, Timeout, RetryError) as e:
            # Same hole as in `_request`, on the path that serves binary downloads: plugin
            # tarballs, log downloads, config and service exports. Same session, same retry
            # policy, so a retried 502/503/504 escapes here too unless `RetryError` is caught.
            raise ApiUnavailableError(f"Cannot reach API at {self.base_url}: {e}") from e

        if resp.status_code >= 500:
            raise ApiUnavailableError(f"API returned {resp.status_code}")
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("message", resp.text[:500])
            except Exception:
                msg = resp.text[:500]
            raise ApiClientError(msg, status_code=resp.status_code)

        return resp

    # ── System ──────────────────────────────────────────────────────────

    @property
    def readonly(self) -> bool:
        """Check if the database is in readonly mode. Cached with short TTL."""
        now = time()
        if self._readonly_cache is not None and (now - self._readonly_cache_time) < self._readonly_cache_ttl:
            return bool(self._readonly_cache)

        try:
            data = self._get("/system/readonly")
            self._readonly_cache = bool(data.get("readonly", False))
        except (ApiClientError, ApiUnavailableError):
            self._readonly_cache = True

        self._readonly_cache_time = now
        return bool(self._readonly_cache)

    def ping(self) -> dict:
        """Call GET /ping and return the response dict."""
        return self._get("/ping")

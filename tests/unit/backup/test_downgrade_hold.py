"""The writer hold: taking it, keeping it, giving it back -- and who actually honours it.

The key itself holds nothing. What stops the writers is `GET /system/readonly`, which the
scheduler, the autoconf, the UI and the API all consult, so the two halves are tested together:
the CLI side that takes the hold, and the endpoint side that turns it into read-only.

The endpoint FAILS OPEN on a broker it cannot read -- a Valkey blip must not freeze every write
fleet-wide with no operator action that clears it -- so the refusal lives on the CLI side
instead, in `hold_observed_by_api`. Both properties are asserted below; dropping either one
turns a safe pair into an outage or into theatre.
"""

import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from json import loads
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKUP = _REPO_ROOT / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import downgrade  # noqa: E402
from downgrade import (  # noqa: E402
    HOLD_KEY,
    acquire_hold,
    api_url,
    broker_state,
    broker_url,
    drain,
    hold_observed_by_api,
    hold_status,
    hold_ttl,
    refresh_hold,
    release_hold,
)

_SYSTEM_ROUTER = _REPO_ROOT / "src" / "api" / "app" / "routers" / "system.py"
_SHIM = "_bw_api_under_test"


class FakeRedis:
    """Just enough Redis: SET NX EX, GET, DEL, EXISTS, EXPIRE, LLEN, HLEN, SCARD, and EVAL.

    EVAL interprets the two scripts by identity rather than running Lua. That is the honest
    limit of this fake: it proves the compare-and-delete SEMANTICS the callers depend on, not
    the three lines of Lua themselves, which only a real broker can execute.
    """

    def __init__(self, now=0.0):
        self.data = {}
        self.expiry = {}
        self.now = now
        self.fail = None

    def _check(self):
        if self.fail:
            raise self.fail

    def _live(self, key):
        if key in self.expiry and self.expiry[key] <= self.now:
            self.data.pop(key, None)
            self.expiry.pop(key, None)
        return key in self.data

    def ping(self):
        self._check()
        return True

    def set(self, key, value, nx=False, ex=None):
        self._check()
        if nx and self._live(key):
            return None
        self.data[key] = value.encode() if isinstance(value, str) else value
        if ex:
            self.expiry[key] = self.now + ex
        return True

    def get(self, key):
        self._check()
        return self.data.get(key) if self._live(key) else None

    def delete(self, key):
        self._check()
        return 1 if self.data.pop(key, None) is not None else 0

    def exists(self, key):
        self._check()
        return 1 if self._live(key) else 0

    def ttl(self, key):
        self._check()
        if not self._live(key):
            return -2
        if key not in self.expiry:
            return -1
        return int(self.expiry[key] - self.now)

    def expire(self, key, ttl):
        self._check()
        if not self._live(key):
            return 0
        self.expiry[key] = self.now + int(ttl)
        return 1

    def llen(self, key):
        self._check()
        return len(self.data.get(key, []))

    def hlen(self, key):
        self._check()
        return len(self.data.get(key, {}))

    def scard(self, key):
        self._check()
        return len(self.data.get(key, set()))

    def eval(self, script, _numkeys, key, *args):
        self._check()
        current = self.get(key)
        expected = args[0].encode() if isinstance(args[0], str) else args[0]
        if current != expected:
            return 0
        if script is downgrade._RELEASE_IF_MINE:
            return self.delete(key)
        if script is downgrade._REFRESH_IF_MINE:
            return self.expire(key, args[1])
        raise AssertionError(f"unknown script handed to EVAL: {script!r}")


@pytest.fixture
def client():
    return FakeRedis()


class TestTakingTheHold:
    def test_the_first_attempt_takes_it(self, client):
        handle, existing = acquire_hold(client, "1.6.12", ttl=900)
        assert handle
        assert existing is None
        assert hold_status(client)["target"] == "1.6.12"

    def test_a_second_attempt_refuses_rather_than_interleaving(self, client):
        first, _ = acquire_hold(client, "1.6.12")
        second, existing = acquire_hold(client, "1.6.11")
        assert first
        assert second == "", "the second downgrade attempt took the hold as well"
        assert existing["target"] == "1.6.12", "the refusal must name who is holding it"

    def test_the_hold_expires_by_itself_when_the_holder_dies(self, client):
        acquire_hold(client, "1.6.12", ttl=900)
        client.now += 901
        assert hold_status(client) is None
        # ... and the next operator can take it.
        assert acquire_hold(client, "1.6.12")[0]

    def test_a_hold_holding_something_unparsable_is_still_reported(self, client):
        client.set(HOLD_KEY, "not json")
        assert hold_status(client) == {"raw": "not json"}

    def test_the_stored_payload_carries_no_secret(self, client):
        acquire_hold(client, "1.6.12")
        stored = loads(client.get(HOLD_KEY))
        assert set(stored) == {"token", "target", "started_at"}


class TestGivingItBack:
    def test_the_holder_releases_its_own_hold(self, client):
        handle, _ = acquire_hold(client, "1.6.12")
        assert release_hold(client, handle)
        assert hold_status(client) is None

    def test_a_stale_holder_cannot_delete_someone_else_s_hold(self, client):
        """The failure this prevents: a holder blocked past its TTL comes back and releases the
        hold a SECOND operator legitimately took, unfreezing a fleet mid-downgrade."""
        stale, _ = acquire_hold(client, "1.6.12", ttl=900)
        client.now += 901
        fresh, _ = acquire_hold(client, "1.6.11", ttl=900)

        assert not release_hold(client, stale)
        assert hold_status(client)["target"] == "1.6.11"
        assert release_hold(client, fresh)

    def test_force_releases_a_hold_whose_holder_is_gone(self, client):
        acquire_hold(client, "1.6.12")
        assert release_hold(client, "", force=True)
        assert hold_status(client) is None

    def test_releasing_without_a_handle_does_nothing(self, client):
        acquire_hold(client, "1.6.12")
        assert not release_hold(client, "")
        assert hold_status(client) is not None


class TestDefaultEndpoints:
    """The Linux packages are the case these defaults exist for."""

    def test_the_broker_default_matches_the_product(self, monkeypatch):
        """`src/linux/scripts/bunkerweb-scheduler.sh` exports API_URL but never
        CELERY_BROKER_URL, and bwcli runs from a plain shell. With no default, quiesce exited 1 and
        check_writers degraded to restore_only on every Linux install, forever."""
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        assert broker_url() == downgrade.DEFAULT_BROKER_URL
        # Same literal src/worker/app.py:17 and src/worker/tasks.py:382 use.
        assert downgrade.DEFAULT_BROKER_URL == "redis://127.0.0.1:6379/0"

    def test_an_explicit_broker_url_still_wins(self, monkeypatch):
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://broker:6379/2")
        assert broker_url() == "redis://broker:6379/2"

    def test_bwcli_s_own_api_convention_comes_first(self, monkeypatch):
        """`src/common/cli/CLI.py:62,257` reads BWCLI_API_URL; the scheduler and the Linux unit
        export API_URL."""
        monkeypatch.setenv("BWCLI_API_URL", "http://bwcli:9000")
        monkeypatch.setenv("API_URL", "http://elsewhere:8888")
        assert api_url() == "http://bwcli:9000"

    def test_it_falls_back_to_the_scheduler_s_api_url(self, monkeypatch):
        monkeypatch.delenv("BWCLI_API_URL", raising=False)
        monkeypatch.setenv("API_URL", "http://bw-api:8888/")
        assert api_url() == "http://bw-api:8888"

    def test_the_last_resort_is_the_linux_socket(self, monkeypatch):
        """src/linux/scripts/bunkerweb-scheduler.sh:264 -- 127.0.0.1:8888, not bw-api:5000."""
        monkeypatch.delenv("BWCLI_API_URL", raising=False)
        monkeypatch.delenv("API_URL", raising=False)
        assert api_url() == "http://127.0.0.1:8888"


class TestKeepingIt:
    def test_a_refresh_pushes_the_ttl_out(self, client):
        handle, _ = acquire_hold(client, "1.6.12", ttl=900)
        client.now += 800
        assert refresh_hold(client, handle, ttl=900)
        client.now += 800
        assert hold_status(client) is not None, "the refresh did not extend the hold"

    def test_a_refresh_fails_once_the_hold_is_someone_else_s(self, client):
        stale, _ = acquire_hold(client, "1.6.12", ttl=900)
        client.now += 901
        acquire_hold(client, "1.6.11", ttl=900)
        assert not refresh_hold(client, stale, ttl=900)

    def test_a_refresh_fails_when_the_hold_is_gone(self, client):
        handle, _ = acquire_hold(client, "1.6.12", ttl=900)
        release_hold(client, handle)
        assert not refresh_hold(client, handle, ttl=900)

    def test_the_remaining_ttl_is_readable(self, client):
        """`--release` shows it, so an operator confirming a steal can see the hold is live."""
        acquire_hold(client, "1.6.12", ttl=900)
        assert hold_ttl(client) == 900
        client.now += 300
        assert hold_ttl(client) == 600

    def test_an_absent_hold_has_no_ttl(self, client):
        assert hold_ttl(client) == -2


class TestBrokerStateAndDrain:
    def test_an_idle_broker_reads_as_idle(self, client):
        state = broker_state(client=client, url="redis://127.0.0.1:6379/0")
        assert state["reachable"] and state["queued"] == 0 and state["unacked"] == 0

    def test_a_broker_error_never_raises_and_never_leaks_the_url(self, client):
        client.fail = RuntimeError("auth failed for redis://user:sup3rsecret@broker:6379/0")
        state = broker_state(client=client, url="redis://user:sup3rsecret@broker:6379/0")
        assert state["reachable"] is False
        assert "sup3rsecret" not in state["error"]

    def test_no_broker_url_is_reported_not_raised(self):
        state = broker_state(client=None, url="")
        assert state["reachable"] is False and state["error"]

    def test_the_drain_refuses_to_call_the_fleet_idle_with_acks_outstanding(self, client):
        """A deferred acknowledgement is material a job WROTE that has not reached the instances.
        An empty queue with acks outstanding is exactly the "discovered halfway through" case, and
        `check_writers` already refuses on it -- the drain must agree or the two disagree about
        what "idle" means."""
        client.data[downgrade.RELOAD_ACK_PENDING_KEY] = {"one change"}
        ticks = iter([0, 1, 2, 3, 4, 5, 6, 99])
        drained, state = drain(client, timeout=5, poll=1, sleeper=lambda _: None, clock=lambda: next(ticks))
        assert not drained
        assert state["pending_acks"] == 1

    def test_the_drain_returns_once_the_acks_have_been_delivered(self, client):
        client.data[downgrade.RELOAD_ACK_PENDING_KEY] = set()
        drained, _ = drain(client, timeout=10, poll=1, sleeper=lambda _: None, clock=lambda: 0)
        assert drained

    def test_the_drain_returns_as_soon_as_the_queue_is_empty(self, client):
        drained, _ = drain(client, timeout=10, poll=1, sleeper=lambda _: None, clock=lambda: 0)
        assert drained

    def test_the_drain_is_bounded_rather_than_freezing_the_system(self, client):
        """A drain that waits forever is a freeze: the caller has to be able to give the system
        back instead of sitting on it."""
        client.data["default"] = ["a job"]
        ticks = iter([0, 1, 2, 3, 4, 5, 6, 99])
        drained, state = drain(client, timeout=5, poll=1, sleeper=lambda _: None, clock=lambda: next(ticks))
        assert not drained
        assert state["queued"] == 1


class TestTheApiIsWhatActuallyHolds:
    """`hold_observed_by_api` is the refusal the fail-open endpoint deliberately does not make."""

    class FakeApi:
        def __init__(self, *answers):
            self.answers = list(answers)

        def _get(self, _path):
            answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
            if isinstance(answer, BaseException):
                raise answer
            return {"readonly": answer}

    def test_a_fleet_reported_read_only_is_observed(self):
        observed, reason = hold_observed_by_api(client=self.FakeApi(True), timeout=0, sleeper=lambda _: None, clock=lambda: 0)
        assert observed and reason == ""

    def test_a_still_writable_fleet_is_refused(self):
        observed, reason = hold_observed_by_api(client=self.FakeApi(False), timeout=0, sleeper=lambda _: None, clock=lambda: 0)
        assert not observed
        assert "still writable" in reason

    def test_an_unreachable_api_is_refused_not_assumed_held(self):
        """`BaseApiClient.readonly` answers True when the API is unreachable, which is exactly
        the case that must refuse -- so this path must not go through it."""
        observed, reason = hold_observed_by_api(client=self.FakeApi(ConnectionError("no route")), timeout=0, sleeper=lambda _: None, clock=lambda: 0)
        assert not observed
        assert "could not be asked" in reason

    def test_it_waits_for_the_endpoint_to_catch_up(self):
        """The endpoint's answer is cached for 5 s in every client, so the first poll can still
        say writable without meaning the hold failed."""
        ticks = iter([0, 1, 2, 3])
        observed, _ = hold_observed_by_api(client=self.FakeApi(False, True), timeout=10, poll=1, sleeper=lambda _: None, clock=lambda: next(ticks))
        assert observed


# ── The endpoint side ───────────────────────────────────────────────────────────────────────


class FakeDb:
    def __init__(self, readonly=False):
        self.readonly = readonly


@pytest.fixture
def system_router(monkeypatch):
    """Load src/api/app/routers/system.py under a private package name.

    Not `app`: `tests/unit/ui/conftest.py` needs `import app` to resolve uniquely to the UI's
    package, and putting the API's there would break the whole suite at collection time.
    """
    redis_module = types.ModuleType("redis")
    holder = {"client": FakeRedis(), "db": FakeDb()}

    holder["from_url_calls"] = 0

    class _Redis:
        @staticmethod
        def from_url(_url, **_kwargs):
            holder["from_url_calls"] += 1
            return holder["client"]

    redis_module.Redis = _Redis
    monkeypatch.setitem(sys.modules, "redis", redis_module)

    package = types.ModuleType(_SHIM)
    package.__path__ = [str(_SYSTEM_ROUTER.parents[1])]
    auth = types.ModuleType(f"{_SHIM}.auth")
    auth.__path__ = []
    guard = types.ModuleType(f"{_SHIM}.auth.guard")
    guard.guard = lambda: None
    utils = types.ModuleType(f"{_SHIM}.utils")
    utils.LOGGER = _RecordingLogger()
    utils.get_db = lambda: holder["db"]
    routers = types.ModuleType(f"{_SHIM}.routers")
    routers.__path__ = [str(_SYSTEM_ROUTER.parent)]

    for name, module in (
        (_SHIM, package),
        (f"{_SHIM}.auth", auth),
        (f"{_SHIM}.auth.guard", guard),
        (f"{_SHIM}.utils", utils),
        (f"{_SHIM}.routers", routers),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    spec = spec_from_file_location(f"{_SHIM}.routers.system", _SYSTEM_ROUTER)
    module = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, f"{_SHIM}.routers.system", module)
    spec.loader.exec_module(module)

    module._holder = holder
    module._logger = utils.LOGGER
    return module


class _RecordingLogger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def error(self, message):
        self.errors.append(str(message))

    def warning(self, message):
        pass

    def info(self, message):
        self.infos.append(str(message))


def _readonly(module) -> bool:
    return loads(module.check_readonly().body)["readonly"]


class TestTheReadOnlyEndpoint:
    def test_the_key_name_has_not_drifted_from_the_cli(self, system_router):
        """The two literals cannot be shared -- the core plugins are not on the API image's
        import path -- and a drift would not error anywhere: the CLI would set a key nobody
        reads and the hold would be silently inert."""
        assert system_router.DOWNGRADE_HOLD_KEY == HOLD_KEY

    def test_a_hold_makes_the_fleet_read_only(self, system_router, monkeypatch):
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        acquire_hold(system_router._holder["client"], "1.6.12")
        assert _readonly(system_router) is True

    def test_releasing_the_hold_gives_the_fleet_back(self, system_router, monkeypatch):
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        client = system_router._holder["client"]
        handle, _ = acquire_hold(client, "1.6.12")
        release_hold(client, handle)
        assert _readonly(system_router) is False

    def test_an_expired_hold_gives_the_fleet_back(self, system_router, monkeypatch):
        """The bound that saves an operator whose terminal died mid-downgrade."""
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        client = system_router._holder["client"]
        acquire_hold(client, "1.6.12", ttl=900)
        client.now += 901
        assert _readonly(system_router) is False

    def test_an_unreachable_broker_falls_back_to_the_boot_time_state_and_says_so(self, system_router, monkeypatch):
        """FAIL OPEN. Freezing every write fleet-wide on a Valkey blip would read as a permanent
        read-only outage with no operator action that clears it."""
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://user:sup3rsecret@broker:6379/0")
        system_router._holder["client"].fail = RuntimeError("connection refused to redis://user:sup3rsecret@broker:6379/0")

        assert _readonly(system_router) is False
        assert system_router._logger.errors, "an unreadable broker must be logged, not swallowed"
        assert "sup3rsecret" not in system_router._logger.errors[0], "the broker password reached the log"

    def test_the_boot_time_read_only_still_wins_on_its_own(self, system_router, monkeypatch):
        """Additive only: DATABASE_URI_READONLY keeps meaning exactly what it meant."""
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        system_router._holder["db"] = FakeDb(readonly=True)
        assert _readonly(system_router) is True

    def test_no_broker_configured_is_not_a_hold(self, system_router, monkeypatch):
        """No default here, matching app/celery_app.py: an API with no broker has no Celery either.
        The Linux unit exports one (src/linux/scripts/bunkerweb-api.sh:241), so the packages are
        covered without this endpoint inventing a URL of its own."""
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        assert _readonly(system_router) is False


class TestTheEndpointUnderPolling:
    """Scheduler, autoconf and every UI worker poll this endpoint. It has to be cheap and quiet."""

    def test_the_broker_client_is_built_once_not_once_per_request(self, system_router, monkeypatch):
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        for _ in range(5):
            _readonly(system_router)
        assert system_router._holder["from_url_calls"] == 1, "a ConnectionPool and a TCP connect per poll"

    def test_a_changed_broker_url_rebuilds_the_client(self, system_router, monkeypatch):
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        _readonly(system_router)
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://elsewhere:6379/0")
        _readonly(system_router)
        assert system_router._holder["from_url_calls"] == 2

    def test_an_outage_logs_once_not_once_per_poll(self, system_router, monkeypatch):
        """The scenario fail-open exists for. One ERROR per poll per process, forever, is what the
        per-request version produced."""
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        system_router._holder["client"].fail = RuntimeError("connection refused")

        for _ in range(10):
            assert _readonly(system_router) is False

        assert len(system_router._logger.errors) == 1, f"logged {len(system_router._logger.errors)} times for one outage"

    def test_recovery_is_logged_and_the_hold_is_honoured_again(self, system_router, monkeypatch):
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        client = system_router._holder["client"]
        acquire_hold(client, "1.6.12")

        client.fail = RuntimeError("connection refused")
        assert _readonly(system_router) is False
        client.fail = None

        assert _readonly(system_router) is True
        assert any("readable again" in line for line in system_router._logger.infos)

    def test_a_second_outage_after_a_recovery_logs_again(self, system_router, monkeypatch):
        """Log-on-change, not log-once-ever: a new outage is news."""
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        client = system_router._holder["client"]

        client.fail = RuntimeError("first")
        _readonly(system_router)
        client.fail = None
        _readonly(system_router)
        client.fail = RuntimeError("second")
        _readonly(system_router)

        assert len(system_router._logger.errors) == 2

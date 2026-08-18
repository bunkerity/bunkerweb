"""The healthcheck must re-push a configuration to an instance stuck in the loading state.

A container restart brings the instance back reachable while it still serves ``IS_LOADING=yes``.
Nine core plugins gate ``is_needed()`` on that state, so the instance keeps serving traffic while
enforcing no client certificates, no basic auth, no blacklist and no rate limit, and the
timer-driven work (bad-behavior counting, metrics flush, sessions cleanup) stops too. It answers
healthchecks as ``up`` throughout. ModSecurity/CRS, antibot and country filtering do not read the
flag and keep enforcing. The old healthcheck only re-pushed on a ``down``/``failover`` -> ``up``
transition, which a ~15s restart slips past.

``main`` is loaded under an alias here: its plain module name would collide with
``src/api/app/main.py`` in the same test session (see this package's conftest).
"""

import importlib.util
import sys
from unittest.mock import Mock, patch
from pathlib import Path

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"


@pytest.fixture(scope="module")
def scheduler_main():
    spec = importlib.util.spec_from_file_location("bw_scheduler_main", _MAIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bw_scheduler_main"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("bw_scheduler_main", None)


class FakeApiClient:
    """Just the four calls healthcheck_job makes."""

    def __init__(self, instances, health):
        self._instances = instances
        self._health = health
        self.status_updates = []

    def get_instances(self):
        return self._instances

    def get_instance_health(self, hostname):
        return self._health.get(hostname)

    def update_instance(self, hostname, status):
        self.status_updates.append((hostname, status))
        return ""


class FakeScheduler:
    def __init__(self):
        self.dispatched = []

    def run_single(self, name):
        self.dispatched.append(name)
        return True


@pytest.fixture
def harness(scheduler_main, monkeypatch):
    """Wire the module globals healthcheck_job reads, and reset the loading set."""

    def _install(instances, health):
        api_client = FakeApiClient(instances, health)
        scheduler = FakeScheduler()
        monkeypatch.setattr(scheduler_main, "API_CLIENT", api_client)
        monkeypatch.setattr(scheduler_main, "SCHEDULER", scheduler)
        scheduler_main.APPLYING_CHANGES.clear()
        scheduler_main.HEALTHCHECK_EVENT.clear()
        scheduler_main.LOADING_INSTANCES.clear()
        return api_client, scheduler

    return _install


def test_up_instance_reporting_loading_triggers_a_push(harness, scheduler_main):
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == ["push-configs"]
    assert scheduler_main.LOADING_INSTANCES == {"bw": 1}


def _run_passes(scheduler_main, count):
    for _ in range(count):
        scheduler_main.HEALTHCHECK_EVENT.clear()
        scheduler_main.healthcheck_job()


def test_the_first_passes_retry_rather_than_latching(harness, scheduler_main):
    """Deliberately not once-per-episode -- that was the original design and it was wrong.

    A dispatch can report success without landing (a read-only database makes run_single return
    True without queueing anything), so one attempt is no guarantee that anything was tried, and
    the instance is meanwhile serving traffic with mTLS, basic auth, blacklist and rate limiting
    inactive.
    """
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})

    _run_passes(scheduler_main, scheduler_main.LOADING_FAST_RETRIES)

    assert scheduler.dispatched == ["push-configs"] * scheduler_main.LOADING_FAST_RETRIES
    assert scheduler_main.LOADING_INSTANCES == {"bw": scheduler_main.LOADING_FAST_RETRIES}


def test_a_stuck_instance_stops_reloading_the_fleet_every_pass(harness, scheduler_main):
    """The other half: retrying is not free, so it must not run forever at full rate.

    The instance is marked up before this branch, so each dispatch is a complete push-configs --
    render, upload, fleet reload. `/health` also fails toward "loading", so a datastore hiccup
    lands here too. After the fast attempts the cadence drops to one in LOADING_SLOW_RETRY_EVERY.
    """
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})

    _run_passes(scheduler_main, scheduler_main.LOADING_SLOW_RETRY_EVERY)

    # The fast attempts, plus exactly one when the streak hits the slow interval.
    assert len(scheduler.dispatched) == scheduler_main.LOADING_FAST_RETRIES + 1
    assert scheduler_main.LOADING_INSTANCES == {"bw": scheduler_main.LOADING_SLOW_RETRY_EVERY}


def test_the_loading_streak_escalates_to_an_error(harness, scheduler_main):
    """A stuck instance must become loud rather than scroll past as a repeated warning."""
    _api, _scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})
    logger = Mock()
    with patch.object(scheduler_main, "HEALTHCHECK_LOGGER", logger):
        _run_passes(scheduler_main, scheduler_main.LOADING_SLOW_RETRY_EVERY)

    assert logger.warning.call_count == scheduler_main.LOADING_FAST_RETRIES, "every fast attempt says it is dispatching"
    assert logger.error.call_count == 1, "the slow-interval attempt escalates"
    assert "needs an operator" in logger.error.call_args[0][0]


def test_a_healthy_instance_pushes_nothing(harness, scheduler_main):
    api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "ok"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []
    assert api.status_updates == [("bw", "up")]
    assert scheduler_main.LOADING_INSTANCES == {}


def test_reloading_is_not_treated_as_loading(harness, scheduler_main):
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "reloading"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []


def test_unreachable_instance_goes_down_and_leaves_the_loading_set(harness, scheduler_main):
    api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})

    scheduler_main.healthcheck_job()
    assert scheduler_main.LOADING_INSTANCES == {"bw": 1}

    # Same instance, now unreachable: it must not stay remembered as loading, otherwise it would
    # never earn a push again when it comes back.
    api._health = {}
    scheduler_main.HEALTHCHECK_EVENT.clear()
    scheduler_main.healthcheck_job()

    assert api.status_updates[-1] == ("bw", "down")
    assert scheduler_main.LOADING_INSTANCES == {}


def test_recovery_from_down_still_pushes(harness, scheduler_main):
    _api, scheduler = harness([{"hostname": "bw", "status": "down"}], {"bw": "ok"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == ["push-configs"]

"""The healthcheck must re-push a configuration to an instance stuck in the loading state.

A container restart brings the instance back reachable while it still serves ``IS_LOADING=yes``,
and in that state both Lua timer loops return early -- no bad-behavior counting, no metrics
flush, no sessions cleanup -- while the instance keeps serving traffic. The old healthcheck only
re-pushed on a ``down``/``failover`` -> ``up`` transition, which a ~15s restart slips past.

``main`` is loaded under an alias here: its plain module name would collide with
``src/api/app/main.py`` in the same test session (see this package's conftest).
"""

import importlib.util
import sys
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
    assert scheduler_main.LOADING_INSTANCES == {"bw"}


def test_a_still_loading_instance_is_pushed_only_once(harness, scheduler_main):
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})

    scheduler_main.healthcheck_job()
    scheduler_main.HEALTHCHECK_EVENT.clear()
    scheduler_main.healthcheck_job()

    # push-configs is what clears the loading state; an instance still loading after one push is
    # broken for another reason and must not earn a dispatch on every pass.
    assert scheduler.dispatched == ["push-configs"]


def test_a_healthy_instance_pushes_nothing(harness, scheduler_main):
    api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "ok"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []
    assert api.status_updates == [("bw", "up")]
    assert scheduler_main.LOADING_INSTANCES == set()


def test_reloading_is_not_treated_as_loading(harness, scheduler_main):
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "reloading"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []


def test_unreachable_instance_goes_down_and_leaves_the_loading_set(harness, scheduler_main):
    api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "loading"})

    scheduler_main.healthcheck_job()
    assert scheduler_main.LOADING_INSTANCES == {"bw"}

    # Same instance, now unreachable: it must not stay remembered as loading, otherwise it would
    # never earn a push again when it comes back.
    api._health = {}
    scheduler_main.HEALTHCHECK_EVENT.clear()
    scheduler_main.healthcheck_job()

    assert api.status_updates[-1] == ("bw", "down")
    assert scheduler_main.LOADING_INSTANCES == set()


def test_recovery_from_down_still_pushes(harness, scheduler_main):
    _api, scheduler = harness([{"hostname": "bw", "status": "down"}], {"bw": "ok"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == ["push-configs"]

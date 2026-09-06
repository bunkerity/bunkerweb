"""The post-migration config-apply stall on the mariadb/mysql upgrade arms.

CI run 33528164796 (branch 1.7, ``d898d5c66``) timed out two upgrade arms with a healthy fleet and
an unapplied configuration. The autoconf/mysql arm is the readable one, three log lines apart::

    16:44:14 [JOBS.PUSH-CONFIGS] All 1 registered BunkerWeb instance(s) are down; leaving the
                                 changes pending for a later run
    16:44:15 [SCHEDULER]         All BunkerWeb instances are up
    16:49:16 [SCHEDULER]         Configuration changes are still pending 300s after the last
                                 dispatch; the job that should have applied them never completed.

Two independent defects put those lines in that order, and this file pins both:

1. **Ordering.** The scheduler refreshed the instances' ``status`` column *after* dispatching
   push-configs. push-configs filters on that column and defers when every instance reads "down",
   so on an upgrade -- where the column still holds whatever the pre-upgrade process left -- the
   first push after the migration deferred against a fleet that had been serving for 22 seconds.
2. **No recovery.** Nothing re-examined that deferral. ``healthcheck_job`` re-dispatched only on a
   ``down``/``failover`` -> ``up`` edge, and the scheduler's own boot pass had already consumed
   that edge by marking the instance up. The 300s ``APPLY_RETRY_INTERVAL`` re-arm was the only way
   back -- and the harness health window is also 300s, which is why the retry landed at 16:49:17,
   one second after the arm was declared dead.

``main`` is imported under an alias with ``Path.mkdir`` sandboxed; see
``test_healthcheck_loading`` for why that is necessary rather than decorative.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"

_REAL_MKDIR = Path.mkdir


def _sandboxed_mkdir(sandbox):
    def _mkdir(self, *args, **kwargs):
        target = self if self.is_relative_to(sandbox) else (sandbox.joinpath(*self.parts[1:]) if self.is_absolute() else self)
        if target.is_absolute() and not target.is_relative_to(sandbox):
            raise PermissionError(13, "Permission denied", str(target))
        return _REAL_MKDIR(target, *args, **kwargs)

    return _mkdir


@pytest.fixture(scope="module")
def scheduler_main(tmp_path_factory):
    sandbox = tmp_path_factory.mktemp("apply-stall-sandbox")
    spec = importlib.util.spec_from_file_location("bw_scheduler_main_stall", _MAIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bw_scheduler_main_stall"] = module
    with patch.object(Path, "mkdir", _sandboxed_mkdir(sandbox)):
        spec.loader.exec_module(module)
    yield module
    sys.modules.pop("bw_scheduler_main_stall", None)


PENDING = {
    "pro_plugins_changed": False,
    "last_pro_plugins_change": None,
    "external_plugins_changed": False,
    "last_external_plugins_change": None,
    "custom_configs_changed": True,
    "last_custom_configs_change": "2026-09-01T16:43:39",
    "plugins_config_changed": {},
    "instances_changed": True,
    "last_instances_change": "2026-09-01T16:43:39",
    "certificates_changed": False,
    "last_certificates_change": None,
}

IDLE = PENDING | {"custom_configs_changed": False, "instances_changed": False}


class FakeApiClient:
    readonly = False

    def __init__(self, instances, health, metadata, reachable=True):
        self._instances = instances
        self._health = health
        self._metadata = metadata
        self._reachable = reachable
        self.status_updates = []
        self.pings = []

    def get_instances(self):
        return self._instances

    def get_instance_health(self, hostname):
        return self._health.get(hostname)

    def ping_instance(self, hostname):
        self.pings.append(hostname)
        return self._reachable

    def update_instance(self, hostname, status):
        self.status_updates.append((hostname, status))
        return ""

    def get_metadata(self):
        return self._metadata


class FakeScheduler:
    def __init__(self):
        self.dispatched = []

    def run_single(self, name):
        self.dispatched.append(name)
        return True


@pytest.fixture
def install(scheduler_main, monkeypatch):
    def _install(instances, health=None, metadata=None, reachable=True):
        api_client = FakeApiClient(instances, health or {}, IDLE if metadata is None else metadata, reachable)
        scheduler = FakeScheduler()
        monkeypatch.setattr(scheduler_main, "API_CLIENT", api_client)
        monkeypatch.setattr(scheduler_main, "SCHEDULER", scheduler)
        scheduler_main.APPLYING_CHANGES.clear()
        scheduler_main.HEALTHCHECK_EVENT.clear()
        scheduler_main.LOADING_INSTANCES.clear()
        scheduler_main.PENDING_REDISPATCH_PASSES = 0
        return api_client, scheduler

    return _install


# --------------------------------------------------------------------------------------------
# Defect 1 -- the ordering
# --------------------------------------------------------------------------------------------


def test_the_status_refresh_runs_before_push_configs_is_dispatched(scheduler_main):
    """The whole bug in one assertion: which of the two happens first.

    Source order rather than behaviour, because the pass this guards lives inside
    ``if __name__ == "__main__":`` and is not reachable from a test. Both markers are asserted to
    exist so a rename cannot make this pass by finding nothing.
    """
    # Scoped to the apply pass: healthcheck_job dispatches push-configs too, earlier in the file,
    # and an unscoped search would compare against that one instead.
    apply_pass = _MAIN_PATH.read_text(encoding="utf-8").split('if __name__ == "__main__":', 1)
    assert len(apply_pass) == 2, "could not find the __main__ block"
    source = apply_pass[1]

    refresh = source.index("success = refresh_instance_statuses()")
    # BOTH dispatch sites, because the one CI actually died on is the boot path:
    # `SCHEDULER.reload(...)` -> run_once -> push-configs, which does not go through run_single.
    # Guarding only run_single leaves a hole where moving the refresh between the two keeps this
    # test green and restores the exact bug.
    dispatch = min(source.index('run_single("push-configs")'), source.index("SCHEDULER.reload("))

    assert refresh < dispatch, (
        "the instance status refresh must precede the push-configs dispatch: push-configs filters "
        "the registered instances on the status column this writes, and defers when they all read "
        "'down'. Refreshing afterwards hands the worker the previous process's statuses."
    )


def test_refresh_marks_a_reachable_instance_up(install, scheduler_main):
    api, _scheduler = install([{"hostname": "bw", "status": "down"}], reachable=True)

    assert scheduler_main.refresh_instance_statuses() is True
    assert api.pings == ["bw"]
    assert api.status_updates == [("bw", "up")]


def test_refresh_marks_an_unreachable_instance_down_and_reports_failure(install, scheduler_main):
    api, _scheduler = install([{"hostname": "bw", "status": "up"}], reachable=False)

    assert scheduler_main.refresh_instance_statuses() is False
    assert api.status_updates == [("bw", "down")]


def test_refresh_never_raises_into_the_apply_pass(install, scheduler_main, monkeypatch):
    """It feeds ``failover`` metadata and the dispatch decision; an exception must not abort them."""
    api, _scheduler = install([{"hostname": "bw", "status": "up"}])
    monkeypatch.setattr(api, "get_instances", lambda: (_ for _ in ()).throw(RuntimeError("db gone")))

    assert scheduler_main.refresh_instance_statuses() is False


# --------------------------------------------------------------------------------------------
# Defect 2 -- the missing recovery path
# --------------------------------------------------------------------------------------------


def test_pending_changes_on_a_healthy_fleet_re_dispatch_push_configs(install, scheduler_main):
    """The regression the mysql arm died of.

    The instance is ``up`` and stays ``up`` -- no transition for the recovery branch to catch --
    but the change flags are still raised because push-configs deferred. Before the fix this pass
    dispatched nothing and the configuration waited out the full 300s re-arm.
    """
    _api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata=PENDING)

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == ["push-configs"]


def test_an_idle_scheduler_dispatches_nothing(install, scheduler_main):
    """The other half: no flags raised means the apply landed, so there is nothing to re-push."""
    _api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata=IDLE)

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []


def test_a_down_instance_does_not_trigger_a_re_dispatch(install, scheduler_main):
    """While an instance is genuinely down the flags are *supposed* to stay raised.

    Re-dispatching would only defer again, once every HEALTHCHECK_INTERVAL forever. The
    ``down`` -> ``up`` branch picks it up when it comes back.
    """
    _api, scheduler = install([{"hostname": "bw", "status": "down"}], {"bw": None}, metadata=PENDING)

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []


def test_one_unreachable_instance_suppresses_the_re_dispatch_for_the_whole_fleet(install, scheduler_main):
    """``fleet_reachable`` is fleet-wide on purpose: a partial push defers just the same."""
    instances = [{"hostname": "bw-1", "status": "up"}, {"hostname": "bw-2", "status": "up"}]
    _api, scheduler = install(instances, {"bw-1": "up", "bw-2": None}, metadata=PENDING)

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []


def test_a_loading_instance_keeps_its_backoff(install, scheduler_main):
    """The re-dispatch must not defeat the loading branch's deliberate rate limit.

    An instance that is up but still loading is loading *because* the push never landed, so
    pending flags are its normal companion. The loading branch backs off to one attempt every
    LOADING_SLOW_RETRY_EVERY passes because each dispatch is a full render + upload + fleet
    reload; on the passes it skips, `recovered` is False and the fleet is reachable, so an
    unguarded pending-changes branch would re-dispatch on every one of them and undo the backoff.
    """
    _api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "loading"}, metadata=PENDING)

    for _ in range(scheduler_main.LOADING_SLOW_RETRY_EVERY):
        scheduler_main.HEALTHCHECK_EVENT.clear()
        scheduler_main.healthcheck_job()

    assert len(scheduler.dispatched) == scheduler_main.LOADING_FAST_RETRIES + 1


def test_a_push_that_keeps_failing_backs_off(install, scheduler_main):
    """The re-dispatch is not self-limiting, so it needs the same backoff as the loading branch.

    push-configs exits 2 at the render step on a broken template, which is upstream of the
    per-instance upload and of the failover marking: every status stays ``up``, nothing reports
    loading, the flags stay raised. Unbounded, this branch would re-render the whole configuration
    tree on the heavy queue every pass — ten times more often than the 300 s re-arm it improves on.
    """
    _api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata=PENDING)

    for _ in range(scheduler_main.PENDING_REDISPATCH_SLOW_RETRY_EVERY):
        scheduler_main.HEALTHCHECK_EVENT.clear()
        scheduler_main.healthcheck_job()

    # The first observation, plus exactly one when the streak reaches the slow interval.
    assert len(scheduler.dispatched) == 2


def test_the_backoff_resets_once_the_changes_land(install, scheduler_main):
    """A later deferral must get its immediate retry back, not inherit the previous streak."""
    api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata=PENDING)

    scheduler_main.healthcheck_job()
    assert len(scheduler.dispatched) == 1

    api._metadata = IDLE  # the push landed and acknowledged
    scheduler_main.HEALTHCHECK_EVENT.clear()
    scheduler_main.healthcheck_job()
    assert len(scheduler.dispatched) == 1

    api._metadata = PENDING  # a fresh change defers again
    scheduler_main.HEALTHCHECK_EVENT.clear()
    scheduler_main.healthcheck_job()
    assert len(scheduler.dispatched) == 2, "the counter did not reset, so the retry was throttled"


def test_a_readonly_database_does_not_re_dispatch(install, scheduler_main, monkeypatch):
    """`run_single` returns True without queueing on a read-only DB, so the flags never clear.

    Re-dispatching would log a warning and an error every pass, forever, and queue nothing.
    """
    api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata=PENDING)
    monkeypatch.setattr(api, "readonly", True)

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == []


def test_a_broken_metadata_read_does_not_break_the_healthcheck(install, scheduler_main, monkeypatch):
    """The API returns its errors as a plain string, and the call can also just raise."""
    _api, scheduler = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata="database is locked")

    scheduler_main.healthcheck_job()
    assert scheduler.dispatched == []

    api2, scheduler2 = install([{"hostname": "bw", "status": "up"}], {"bw": "up"}, metadata=PENDING)
    monkeypatch.setattr(api2, "get_metadata", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    scheduler_main.healthcheck_job()
    assert scheduler2.dispatched == []


# --------------------------------------------------------------------------------------------
# The shared flag list
# --------------------------------------------------------------------------------------------


def test_every_change_flag_counts_as_pending(scheduler_main):
    """Both callers read this one list; a flag missing from it is a silently unapplied change.

    ``plugins_config_changed`` is the one that matters: it is a ``{plugin_id: timestamp}`` dict,
    not a bool, and it has already gone missing once from one of two hand-maintained copies of
    this list in autoconf.
    """
    for flag in scheduler_main.PENDING_CHANGE_FLAGS:
        raised = IDLE | {flag: {"blacklist": "2026-09-01T16:43:39"} if flag == "plugins_config_changed" else True}
        assert scheduler_main.has_pending_changes(raised), f"{flag} was not treated as a pending change"

    assert not scheduler_main.has_pending_changes(IDLE)
    assert "plugins_config_changed" in scheduler_main.PENDING_CHANGE_FLAGS

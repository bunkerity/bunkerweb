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

Importing it is not free: ``src/scheduler/main.py`` calls ``Path.mkdir`` at module level on
``/etc/bunkerweb/configs`` (:63, plus one per entry of ``CUSTOM_CONFIGS_DIRS`` at :77),
``/etc/bunkerweb/plugins`` (:83), ``/etc/bunkerweb/pro/plugins`` (:86) and ``/var/tmp/bunkerweb``
(:89). That is correct behaviour inside the scheduler's container and is not this file's business
to change — but it means the import writes to ``/etc``. On a developer box with a permissive
``/etc/bunkerweb`` the import happens to succeed; on a CI runner it does not, and every test here
errored with ``PermissionError: [Errno 13] Permission denied: '/etc/bunkerweb'`` (run 32470372717,
branch 1.7, 2026-08-21). The ambient filesystem was supplying the answer.

So the import runs with ``Path.mkdir`` re-rooted into a per-module sandbox, and the same patch
**refuses** any target that is still absolute-and-outside it — i.e. it behaves exactly like the
runner's ``/etc``. Remove the re-rooting and the import raises ``PermissionError`` here too, on
any host. ``test_the_import_writes_nothing_outside_the_sandbox`` asserts that directly.
"""

import importlib.util
import sys
from unittest.mock import Mock, patch
from pathlib import Path

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"

_REAL_MKDIR = Path.mkdir


def _sandboxed_mkdir(sandbox, created):
    """A ``Path.mkdir`` that cannot write outside ``sandbox``, and says so the way a runner does.

    An absolute target is re-rooted under ``sandbox`` (``/etc/bunkerweb/configs`` ->
    ``<sandbox>/etc/bunkerweb/configs``); a relative one is left alone. Anything that ends up
    absolute and outside the sandbox raises ``PermissionError(13)`` — the exact failure CI gets for
    ``/etc``. Both halves matter: the re-rooting is the fix, the refusal is what proves the fix is
    doing the work rather than a writable ``/etc/bunkerweb`` on the host.
    """

    def _reroot(path):
        """The fix itself, isolated so a mutant can neuter exactly this and nothing else."""
        return sandbox.joinpath(*path.parts[1:]) if path.is_absolute() else path

    def _mkdir(self, *args, **kwargs):
        # `parents=True` makes pathlib recurse via `self.parent.mkdir(...)`, which comes back
        # through this same patch — so a path already inside the sandbox must be left alone, or
        # each parent would be re-rooted a second time.
        target = self if self.is_relative_to(sandbox) else _reroot(self)
        if target.is_absolute() and not target.is_relative_to(sandbox):
            raise PermissionError(13, "Permission denied", str(target))
        created.append(str(target))
        return _REAL_MKDIR(target, *args, **kwargs)

    return _mkdir


@pytest.fixture(scope="module")
def scheduler_import(tmp_path_factory):
    """Import ``src/scheduler/main.py`` with every module-level ``mkdir`` confined to a sandbox.

    Returns ``(module, sandbox, created)``. ``created`` is every directory the import asked for,
    already re-rooted — the evidence the guard test reads.
    """
    sandbox = tmp_path_factory.mktemp("scheduler-import-sandbox")
    created = []

    spec = importlib.util.spec_from_file_location("bw_scheduler_main", _MAIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bw_scheduler_main"] = module
    with patch.object(Path, "mkdir", _sandboxed_mkdir(sandbox, created)):
        spec.loader.exec_module(module)
    yield module, sandbox, created
    sys.modules.pop("bw_scheduler_main", None)


@pytest.fixture(scope="module")
def scheduler_main(scheduler_import):
    return scheduler_import[0]


def test_the_import_writes_nothing_outside_the_sandbox(scheduler_import):
    """RULE 17: the host's ``/etc`` must not be what makes this file pass.

    The floor is not decoration — ``all(...)``/``== []`` over an empty list is vacuously true, so a
    run where the import created nothing at all would otherwise read as a pass.
    """
    _module, sandbox, created = scheduler_import

    assert len(created) >= 1, "the import created no directory at all — this guard proves nothing"
    outside = [path for path in created if not path.startswith(str(sandbox))]
    assert outside == [], f"the import wrote outside the sandbox: {outside}"

    # The three /etc trees main.py builds at import really were requested, and really landed in the
    # sandbox: proof the paths were redirected rather than the calls skipped.
    for expected in ("etc/bunkerweb/configs", "etc/bunkerweb/plugins", "etc/bunkerweb/pro/plugins"):
        assert (sandbox / expected).is_dir(), f"{expected} was not created under the sandbox"


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


def test_a_restart_that_kept_its_config_still_earns_a_push(harness, scheduler_main):
    """`needs_config` is the safe half of the old behaviour.

    A restart used to force `IS_LOADING=yes`, which disabled nine plugins for a configuration the
    instance already had. It now keeps enforcing and reports this state instead — but it still owes
    the scheduler a fresh configuration, so it must still earn a push.
    """
    _api, scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "needs_config"})

    scheduler_main.healthcheck_job()

    assert scheduler.dispatched == ["push-configs"]
    assert scheduler_main.LOADING_INSTANCES == {"bw": 1}


def test_the_two_waiting_states_are_logged_differently(harness, scheduler_main):
    """One is an exposure, the other is routine — the log must not conflate them.

    Claiming access controls are inactive when they are enforcing would send an operator chasing a
    bypass that does not exist.
    """
    _api, _scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "needs_config"})
    logger = Mock()
    with patch.object(scheduler_main, "HEALTHCHECK_LOGGER", logger):
        scheduler_main.healthcheck_job()

    assert logger.warning.call_count == 0, "a preserved configuration is not a warning"
    assert "configuration preserved" in logger.info.call_args[0][0]


def test_a_stuck_needs_config_escalates_without_claiming_a_bypass(harness, scheduler_main):
    _api, _scheduler = harness([{"hostname": "bw", "status": "up"}], {"bw": "needs_config"})
    logger = Mock()
    with patch.object(scheduler_main, "HEALTHCHECK_LOGGER", logger):
        _run_passes(scheduler_main, scheduler_main.LOADING_SLOW_RETRY_EVERY)

    assert logger.error.call_count == 1
    message = logger.error.call_args[0][0]
    assert "traffic is protected" in message
    assert "inactive" not in message, "this state does not disable anything"


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

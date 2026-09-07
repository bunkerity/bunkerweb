"""A reload-flagged job whose cache nobody can receive yet must say so, and be carried later.

`if ret == 1 and apis:` had no `else`. On a cold boot the local instance has not registered in the
DB yet and `BUNKERWEB_INSTANCES` is empty, so `_get_apis()` returns None: the job wrote its files,
exited 1 to ask for them to be shipped, and the push plus the reload were skipped with no log line,
no deferral reason and a plain-success run row. The instances then serve the previous configuration
until some *later* job happens to change something -- which for an `every: once` job is never.
Reproduced on a live all-in-one (`.cache/results-2026-09-06-wave13/f2-repro.log`): three jobs
dropped inside the first 17 seconds of the first boot.

Loading technique is `test_execute_job_deferral_reason.py`'s: celery/redis are not in the unit venv,
so `src/worker/tasks.py` is loaded for real with its `worker.*` imports stubbed.
"""

import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from jobs import JOB_DEFERRAL_PREFIX, drain_deferral_reason, note_deferral
from test_execute_job_deferral_reason import BROKER, JOB, LOGGER, TASKS, _Self
from test_reload_broadcast import _LockRedis, _apis, _with_redis


@pytest.fixture(autouse=True)
def _clean():
    drain_deferral_reason()
    yield
    drain_deferral_reason()


@pytest.fixture
def runtime(monkeypatch):
    """`execute_job` with everything but the reload decision stubbed out.

    Returns a small handle: set `.ret` (the job's exit code) and `.apis`, run it, read the row it
    recorded and the broker state it left behind.
    """
    logger_module = ModuleType("logger")
    logger_module.setup_logger = Mock(return_value=LOGGER)
    monkeypatch.setitem(sys.modules, "logger", logger_module)
    monkeypatch.setattr(TASKS, "_load_job_config_env", lambda db, logger: {})
    monkeypatch.setenv("CELERY_BROKER_URL", BROKER)

    executor = Mock()
    monkeypatch.setattr(TASKS, "JobExecutor", Mock(return_value=executor))
    db = Mock(add_job_run=Mock(return_value=None))
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
    monkeypatch.setattr(TASKS, "_delivery_attempt", lambda *_args: 1)

    class _Runtime:
        client = _LockRedis()
        apis = None
        reloaded = []

        def run(self, ret=1):
            executor.run = Mock(return_value=ret)
            monkeypatch.setattr(TASKS, "_get_apis", lambda *_args: self.apis)
            monkeypatch.setattr(TASKS, "_request_reload_debounced", Mock(side_effect=lambda apis, *_a: self.reloaded.append(apis)))
            with _with_redis(self.client):
                TASKS.execute_job(_Self(), dict(JOB))
            return db.add_job_run.call_args

    return _Runtime()


class TestNoInstanceYet:
    def test_the_run_records_a_deferral_instead_of_a_plain_success(self, runtime):
        call = runtime.run(ret=1)

        assert call.args[1] is True, "a deferral is not a failure"
        assert call.kwargs["error"] == f"{JOB_DEFERRAL_PREFIX}no reachable instance yet -- reload deferred"

    def test_the_operator_is_told(self, runtime):
        LOGGER.warning.reset_mock()

        runtime.run(ret=1)

        said = " ".join(str(c.args[0]) for c in LOGGER.warning.call_args_list)
        assert "no BunkerWeb instance is reachable yet" in said
        assert "jobs/push-configs" in said, "the warning has to name the job whose output is waiting"

    def test_the_push_is_remembered_as_owed(self, runtime):
        runtime.run(ret=1)

        assert runtime.client.keys.get(TASKS.RELOAD_OWED_KEY), "a debt, carrying the token that identifies it"

    def test_the_owed_marker_never_expires(self, runtime):
        """A cold boot can outlast any TTL worth setting, and the marker's whole job is to survive
        until an instance shows up. RELOAD_DIRTY_KEY's 60s is why it could not be reused.

        `client.ttls` and not `client.expirations`: the fake used to accept `set(..., ex=)` and throw
        it away, so this assertion could not fail and `set(RELOAD_OWED_KEY, token, ex=60)` shipped
        green past it.
        """
        runtime.run(ret=1)

        assert runtime.client.keys.get(TASKS.RELOAD_OWED_KEY)
        assert TASKS.RELOAD_OWED_KEY not in runtime.client.ttls

    def test_a_fresh_debt_starts_with_a_full_retry_budget(self, runtime):
        """The counter means consecutive failures to *settle* a debt, and a job that found no
        instance never attempted one. Inheriting an older debt's count drops a brand-new cold-boot
        debt straight into the slow window -- ~14 job runs before anything carries it."""
        runtime.client.keys[TASKS.RELOAD_OWED_ATTEMPTS_KEY] = 99

        runtime.run(ret=1)

        assert TASKS.RELOAD_OWED_ATTEMPTS_KEY not in runtime.client.keys

    def test_no_instance_costs_no_carry_budget(self, runtime):
        """The trigger reads `apis and (ret == 1 or _reload_is_owed(...))` and the order is
        load-bearing. Reversed, every job of a cold boot consults a debt it demonstrably cannot
        settle -- there is nobody to push to -- and burns the fast window doing it, so the first
        instance to register meets a debt already backed off to one carry in twenty."""
        runtime.client.keys[TASKS.RELOAD_OWED_KEY] = "raised-earlier"

        runtime.run(ret=0)

        assert TASKS.RELOAD_OWED_ATTEMPTS_KEY not in runtime.client.keys
        assert runtime.reloaded == []

    def test_a_job_that_changed_nothing_owes_nothing(self, runtime):
        """Anti-vacuity: exit 0 asks for no push, so an unreachable fleet is not a deferral."""
        call = runtime.run(ret=0)

        assert call.kwargs["error"] is None
        assert TASKS.RELOAD_OWED_KEY not in runtime.client.keys

    def test_the_job_s_own_deferral_reason_is_kept_alongside_ours(self, runtime):
        """Two different preconditions can hold at once and the operator needs both."""
        note_deferral("every instance down")

        call = runtime.run(ret=1)

        assert call.kwargs["error"] == f"{JOB_DEFERRAL_PREFIX}every instance down; no reachable instance yet -- reload deferred"


class TestTheOwedPushIsCarried:
    def test_a_later_run_that_changed_nothing_still_pushes(self, runtime):
        """The push ships the whole /var/cache/bunkerweb tree, so the run that settles it does not
        have to be the run that wrote the files -- which matters, because the job that did is
        `every: once` and will not run again."""
        runtime.client.keys[TASKS.RELOAD_OWED_KEY] = "1"
        runtime.apis = _apis()

        runtime.run(ret=0)

        assert runtime.reloaded == [runtime.apis]

    def test_nothing_owed_means_no_reload(self, runtime):
        """Anti-vacuity for the branch above: without it every exit-0 job would reload the fleet."""
        runtime.apis = _apis()

        runtime.run(ret=0)

        assert runtime.reloaded == []

    def test_a_changed_run_with_an_instance_pushes_and_defers_nothing(self, runtime):
        runtime.apis = _apis()

        call = runtime.run(ret=1)

        assert runtime.reloaded == [runtime.apis]
        assert call.kwargs["error"] is None
        assert TASKS.RELOAD_OWED_KEY not in runtime.client.keys


class TestADebtThatWillNotSettleBacksOff:
    """A push that keeps failing must not re-ship the whole cache tree on every job forever.

    `apis` stays truthy while a push fails -- a failed `send_files` marks nobody down -- and
    `send_to_apis` is all-or-nothing, so one wedged instance in a healthy fleet would otherwise pin a
    full-tree transfer plus a fleet reload on every minute-cadence job, indefinitely. Same shape and
    same numbers as the scheduler's own two slow-retry paths (`src/scheduler/main.py:583`, `:639`).
    """

    def _consult(self, client, times):
        with _with_redis(client):
            return [TASKS._reload_is_owed(BROKER, LOGGER) for _ in range(times)]

    def test_the_first_few_carries_go_through(self):
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1"})

        assert self._consult(client, TASKS.RELOAD_OWED_FAST_RETRIES) == [True] * TASKS.RELOAD_OWED_FAST_RETRIES

    def test_then_it_backs_off(self):
        fast, slow = TASKS.RELOAD_OWED_FAST_RETRIES, TASKS.RELOAD_OWED_SLOW_RETRY_EVERY
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1"})

        answers = self._consult(client, slow - 1)

        assert answers[fast:] == [False] * (slow - 1 - fast)

    def test_but_the_debt_is_never_abandoned(self):
        """Giving up would be the silent loss this whole change exists to close -- so it keeps
        retrying, slowly, and says out loud that a human is needed."""
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1"})
        LOGGER.error.reset_mock()

        answers = self._consult(client, TASKS.RELOAD_OWED_SLOW_RETRY_EVERY * 2)

        assert answers[TASKS.RELOAD_OWED_SLOW_RETRY_EVERY - 1] is True
        assert answers[TASKS.RELOAD_OWED_SLOW_RETRY_EVERY * 2 - 1] is True
        assert client.keys.get(TASKS.RELOAD_OWED_KEY) == "1", "the debt itself is kept until a push settles it"
        assert "needs an operator" in " ".join(str(c.args[0]) for c in LOGGER.error.call_args_list)

    def test_nothing_owed_costs_no_budget(self):
        """Anti-vacuity: the counter must not tick on the overwhelmingly common path, or an
        untroubled deployment would exhaust the fast window before it ever owed anything."""
        client = _LockRedis()

        assert self._consult(client, 5) == [False] * 5
        assert TASKS.RELOAD_OWED_ATTEMPTS_KEY not in client.keys

    def test_a_settled_debt_gives_the_budget_back(self):
        """It counts consecutive failures to settle, not lifetime ones: a deployment that owed a
        push once at boot must not start the next one already backed off."""
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1", TASKS.RELOAD_OWED_ATTEMPTS_KEY: 99})
        with _with_redis(client):
            TASKS._request_reload_debounced(_apis(), BROKER, LOGGER)

        assert TASKS.RELOAD_OWED_ATTEMPTS_KEY not in client.keys


class TestTheApisAreResolvedAfterTheJob:
    def test_an_instance_that_registers_while_the_job_runs_is_used(self, runtime, monkeypatch):
        """`_get_apis()` used to be called before the job. A job takes seconds to minutes, and on a
        cold boot the instance registers inside that window -- the answer was stale before the
        decision that reads it."""
        registered = _apis()
        state = {"ran": False}

        def _ran(_data):
            state["ran"] = True
            return 1

        monkeypatch.setattr(TASKS, "_get_apis", lambda *_args: registered if state["ran"] else None)
        monkeypatch.setattr(TASKS, "_request_reload_debounced", Mock(side_effect=lambda apis, *_a: runtime.reloaded.append(apis)))
        TASKS.JobExecutor.return_value.run = Mock(side_effect=_ran)
        with _with_redis(runtime.client):
            TASKS.execute_job(_Self(), dict(JOB))

        assert runtime.reloaded == [registered]

    def test_a_failure_resolving_the_instances_does_not_cost_the_run_row(self, runtime, monkeypatch):
        """It now runs after the work: a raise here used to waste a dispatch that had done nothing,
        and would now lose the row and re-run a job that already ran."""
        monkeypatch.setattr(TASKS, "_get_apis", Mock(side_effect=RuntimeError("db is gone")))
        monkeypatch.setattr(TASKS, "_request_reload_debounced", Mock())
        TASKS.JobExecutor.return_value.run = Mock(return_value=1)
        with _with_redis(runtime.client):
            TASKS.execute_job(_Self(), dict(JOB))

        assert TASKS.get_worker_db().add_job_run.called

    def test_a_resolution_failure_is_not_reported_as_an_empty_fleet(self, runtime, monkeypatch):
        """`_get_apis()` raising is not the same operator problem as an empty fleet -- a broken
        import or a malformed instance row leaves nothing to look for in a fleet that may be
        perfectly healthy.

        Deliberately narrow: a database that *refuses* is swallowed inside `_get_apis` (its own
        `except Exception: db_instances = []`), falls through to `BUNKERWEB_INSTANCES` and returns
        None, so it still reads as an empty fleet. Only a raise that escapes `_get_apis` gets this
        wording.
        """
        monkeypatch.setattr(TASKS, "_get_apis", Mock(side_effect=RuntimeError("db is gone")))
        monkeypatch.setattr(TASKS, "_request_reload_debounced", Mock())
        TASKS.JobExecutor.return_value.run = Mock(return_value=1)
        with _with_redis(runtime.client):
            TASKS.execute_job(_Self(), dict(JOB))

        call = TASKS.get_worker_db().add_job_run.call_args
        assert call.kwargs["error"] == f"{JOB_DEFERRAL_PREFIX}could not resolve any reachable instance -- reload deferred"


class TestTheReloadPathSettlesTheDebt:
    def test_a_debt_raised_while_the_push_was_in_flight_survives_it(self):
        """Settling is a compare-and-delete, not a blind one.

        Another job finishes on the other queue while this push is building its tar, finds no
        reachable instance, and records a debt for material this tar cannot contain. It raises no
        dirty flag doing it -- that path never enters `_request_reload_debounced` -- so nothing makes
        the holder go round again, and RELEASE_IF_CLEAN sees a clean run. A blind delete here erases
        that debt and drops that job's material in silence: this suite's own defect, reintroduced in
        a narrower window.
        """
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "claimed-by-this-round"})
        apis = _apis()

        def _another_job_finds_no_instance(*_args, **_kwargs):  # DEV-2b3: send_files now carries a timeout
            client.keys[TASKS.RELOAD_OWED_KEY] = "raised-while-the-tar-was-built"
            return True

        apis.send_files = Mock(side_effect=_another_job_finds_no_instance)
        with _with_redis(client), patch.object(TASKS, "_broker_client", return_value=client):
            TASKS._request_reload_debounced(apis, BROKER, LOGGER)

        assert client.keys.get(TASKS.RELOAD_OWED_KEY) == "raised-while-the-tar-was-built"
        # The fake cannot run Lua, so the script's body is pinned by source the way RELEASE_IF_CLEAN
        # is (`test_reload_broadcast.py::test_the_holder_cannot_release_while_a_job_is_flagged`).
        # Without this, inverting `~=` to `==` passes every test in this file and, in production,
        # never settles the debt this push carried while deleting the one it did not.
        assert "if redis.call('get', KEYS[1]) ~= ARGV[1] then return 0 end" in TASKS.SETTLE_OWED_IF_UNCHANGED

    def test_a_re_arm_that_cannot_reach_the_broker_says_so(self):
        """It was the last broker write in the change made under a bare `suppress(BaseException)`,
        in a change whose whole subject is writes that failed in silence."""

        class _RefusesToRecordTheDebt(_LockRedis):
            def set(self, key, value, nx=False, ex=None):
                if key == TASKS.RELOAD_OWED_KEY:
                    raise ConnectionError("broker is gone")
                return super().set(key, value, nx=nx, ex=ex)

        client = _RefusesToRecordTheDebt()
        apis = _apis()
        apis.send_files = Mock(return_value=False)
        LOGGER.error.reset_mock()
        with _with_redis(client), patch.object(TASKS, "_broker_client", return_value=client):
            with pytest.raises(RuntimeError):
                TASKS._request_reload_debounced(apis, BROKER, LOGGER)

        assert "still owed" in " ".join(str(c.args[0]) for c in LOGGER.error.call_args_list)
        assert TASKS.RELOAD_LOCK_KEY not in client.keys, "the lock still goes, or nothing reloads again"

    def test_a_successful_push_clears_what_was_owed(self):
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1"})
        with _with_redis(client):
            TASKS._request_reload_debounced(_apis(), BROKER, LOGGER)

        assert TASKS.RELOAD_OWED_KEY not in client.keys

    def test_the_debt_is_raised_before_the_lock_is_released(self):
        """Release first and another worker takes the lock, pushes, clears the debt -- and then this
        frame raises it again behind it, for one fleet reload nobody owed."""
        client = _LockRedis()
        apis = _apis()
        apis.send_files = Mock(return_value=False)
        with _with_redis(client), patch.object(TASKS, "_broker_client", return_value=client):
            with pytest.raises(RuntimeError):
                TASKS._request_reload_debounced(apis, BROKER, LOGGER)

        ordered = [(op, key) for op, key in client.ops if key in (TASKS.RELOAD_OWED_KEY, TASKS.RELOAD_LOCK_KEY)]
        assert ordered.index(("set", TASKS.RELOAD_OWED_KEY)) < ordered.index(("delete", TASKS.RELOAD_LOCK_KEY))

    def test_a_failed_push_leaves_it_owed(self):
        """The other half of the same defect: a push that fails logs an error and, before this,
        waited for the next job that *changed* something rather than the next job at all."""
        client = _LockRedis()
        apis = _apis()
        apis.send_files = Mock(return_value=False)
        with _with_redis(client), patch.object(TASKS, "_broker_client", return_value=client):
            with pytest.raises(RuntimeError):
                TASKS._request_reload_debounced(apis, BROKER, LOGGER)

        assert client.keys.get(TASKS.RELOAD_OWED_KEY)

    def test_the_bound_leaves_it_owed_too(self):
        """Still dirty after MAX_RELOAD_ROUNDS: the holder gives up on purpose, so somebody else
        has to pick the tree up."""

        class _AlwaysDirty(_LockRedis):
            def delete(self, key):
                if key == TASKS.RELOAD_DIRTY_KEY:
                    return 1
                return super().delete(key)

        client = _AlwaysDirty()
        with _with_redis(client), patch.object(TASKS, "_broker_client", return_value=client):
            TASKS._request_reload_debounced(_apis(), BROKER, LOGGER)

        assert client.keys.get(TASKS.RELOAD_OWED_KEY)


class TestTheDeferralPillClearsWhenThePushLands:
    """The debt is fleet-global, the pill is per-job.

    `jobs.html` renders "Deferred" from `last_run['error']`. When run B carries the push run A could
    not deliver, A's row still says "no reachable instance yet -- reload deferred" and nothing ever
    overwrites it: A is `every: once` (`crowdsec-conf`, `certbot-new`) and `JobScheduler.setup()`
    does not schedule it again. Material delivered, pill yellow forever.

    The rule the clear has to respect is the one the whole ack chain rests on -- a marker may only
    clear once the material it speaks for has REACHED the instances -- so most of what is asserted
    here is when it must NOT fire.
    """

    def _carry(self, client, apis=None, db=None):
        apis = apis or _apis()
        with _with_redis(client), patch.object(TASKS, "_broker_client", return_value=client):
            with patch.object(TASKS, "get_worker_db", return_value=db):
                TASKS._request_reload_debounced(apis, BROKER, LOGGER)
        return apis

    def test_a_carried_push_clears_the_pill_of_the_job_it_delivered_for(self):
        db = Mock(clear_deferred_job_runs=Mock(return_value=""))

        self._carry(_LockRedis({TASKS.RELOAD_OWED_KEY: "1"}), db=db)

        call = db.clear_deferred_job_runs.call_args
        assert call.args == TASKS.RELOAD_DEFERRAL_PREFIXES
        assert isinstance(call.kwargs["before"], datetime)

    def test_nothing_owed_clears_nothing(self):
        """Anti-vacuity, and the load-bearing half of it: with no debt outstanding nothing deferred,
        and a debt the broker LOST is one whose material may genuinely never have shipped -- there
        the stale pill is the truth and clearing it is the lie."""
        db = Mock(clear_deferred_job_runs=Mock(return_value=""))

        self._carry(_LockRedis(), db=db)

        db.clear_deferred_job_runs.assert_not_called()

    def test_a_failed_push_leaves_the_pill_up(self):
        """Nothing reached the instances, so nothing is delivered and the row is still true."""
        db = Mock(clear_deferred_job_runs=Mock(return_value=""))
        apis = _apis()
        apis.send_files = Mock(return_value=False)

        with pytest.raises(RuntimeError):
            self._carry(_LockRedis({TASKS.RELOAD_OWED_KEY: "1"}), apis=apis, db=db)

        db.clear_deferred_job_runs.assert_not_called()

    def test_a_failed_reload_leaves_the_pill_up_too(self):
        """The files are on the instances but nothing is serving them yet -- the ack chain counts a
        reload, not a transfer (`_apply_deferred_acks` sits behind the same two gates)."""
        db = Mock(clear_deferred_job_runs=Mock(return_value=""))
        apis = _apis()
        apis.send_to_apis = Mock(return_value=(False, {}))

        with pytest.raises(RuntimeError):
            self._carry(_LockRedis({TASKS.RELOAD_OWED_KEY: "1"}), apis=apis, db=db)

        db.clear_deferred_job_runs.assert_not_called()

    def test_the_cutoff_is_read_before_the_tar_is_built(self):
        """A job that defers while this push is building its tar wrote files the push cannot carry.
        Its row is younger than the cutoff, so it keeps its pill -- the same reasoning that makes
        settling the debt a compare-and-delete, applied to the marker instead of the key."""
        db = Mock(clear_deferred_job_runs=Mock(return_value=""))
        seen = []
        apis = _apis()
        apis.send_files = Mock(side_effect=lambda *_a, **_kw: seen.append(datetime.now().astimezone()) or True)  # DEV-2b3

        self._carry(_LockRedis({TASKS.RELOAD_OWED_KEY: "1"}), apis=apis, db=db)

        assert db.clear_deferred_job_runs.call_args.kwargs["before"] <= seen[0]

    def test_a_database_that_refuses_costs_the_pill_and_not_the_push(self):
        """The push and the reload have already succeeded when this runs. Raising from here would
        report the whole round as failed and re-raise a debt for material already on the instances,
        so the failure is logged and swallowed -- but it IS logged."""
        db = Mock(clear_deferred_job_runs=Mock(side_effect=RuntimeError("db is gone")))
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1"})
        LOGGER.warning.reset_mock()

        self._carry(client, db=db)

        assert "deferral marker" in " ".join(str(c.args[0]) for c in LOGGER.warning.call_args_list)
        assert TASKS.RELOAD_OWED_KEY not in client.keys, "the debt this push carried is still settled"
        assert TASKS.RELOAD_LOCK_KEY not in client.keys, "the lock still goes, or nothing reloads again"

    def test_a_worker_without_a_database_carries_on(self):
        """`get_worker_db()` returns None on a worker started without DATABASE_URI."""
        client = _LockRedis({TASKS.RELOAD_OWED_KEY: "1"})

        self._carry(client, db=None)

        assert TASKS.RELOAD_OWED_KEY not in client.keys

    def test_the_prefixes_are_the_reasons_execute_job_actually_records(self, runtime, monkeypatch):
        """Drift pin. The prefixes are literals in one place and the reasons are literals in
        another; rewording a reason would not error, it would just stop clearing and leave the pill
        up forever, which is the exact defect this change closes.
        """
        recorded = [runtime.run(ret=1).kwargs["error"]]

        # Not through `runtime.run`: it re-patches `_get_apis` itself, so a patch set here would be
        # overwritten and both reasons would come out identical -- half of this pin, silently.
        monkeypatch.setattr(TASKS, "_get_apis", Mock(side_effect=RuntimeError("db is gone")))
        monkeypatch.setattr(TASKS, "_request_reload_debounced", Mock())
        TASKS.JobExecutor.return_value.run = Mock(return_value=1)
        with _with_redis(runtime.client):
            TASKS.execute_job(_Self(), dict(JOB))
        recorded.append(TASKS.get_worker_db().add_job_run.call_args.kwargs["error"])

        assert len(set(recorded)) == len(TASKS.RELOAD_DEFERRAL_PREFIXES), recorded
        for reason in recorded:
            assert reason.startswith(TASKS.RELOAD_DEFERRAL_PREFIXES), reason

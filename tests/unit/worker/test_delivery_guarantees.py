"""At-least-once delivery: the ack settings and the bound that makes them safe.

``task_acks_late`` used to be False, so the broker acked a job on RECEIPT and a worker killed
mid-job lost it silently -- the scheduler recorded nothing and believed it ran. Turning it on
(plus ``task_reject_on_worker_lost``) buys a retry, and costs Celery's own protection against a
task that loops forever by killing its worker every time. ``_delivery_attempt`` is what replaces
that protection, so these tests cover both halves together.

Celery, redis and kombu are not installed in the unit venv, so every one of them is stubbed
through ``sys.modules`` -- the same approach ``test_app.py`` uses.
"""

import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


class _Conf(dict):
    __getattr__ = dict.get

    def __setattr__(self, name, value):
        self[name] = value


class _Celery:
    def __init__(self, *_args, **_kwargs):
        self.conf = _Conf()


class _Signal:
    def connect(self, function):
        return function


def _load_app():
    """Load ``src/worker/app.py`` with Celery stubbed, exposing the real conf dict."""
    celery = ModuleType("celery")
    signals = ModuleType("celery.signals")
    kombu = ModuleType("kombu")
    celery.Celery = _Celery
    signals.worker_process_init = _Signal()
    signals.worker_process_shutdown = _Signal()
    kombu.Queue = lambda name: name
    modules = {"celery": celery, "celery.signals": signals, "kombu": kombu}
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("bw_worker_app_delivery", ROOT / "src" / "worker" / "app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class _StubApp:
    """Stands in for the Celery app. ``task`` records its options and returns the raw function.

    Keeping the undecorated function is what lets the tests call ``execute_job(self, data)``
    directly, and keeping the options is what lets them assert on ``acks_late`` -- the value
    that actually governs the running worker, because a decorator argument beats ``app.conf``.
    """

    def task(self, **options):
        def decorator(function):
            function.task_options = options
            return function

        return decorator


def _load_tasks():
    """Load ``src/worker/tasks.py`` with its ``worker.*`` imports stubbed out."""
    worker_pkg = ModuleType("worker")
    worker_app = ModuleType("worker.app")
    worker_executor = ModuleType("worker.executor")
    worker_app.app = _StubApp()
    worker_app.get_worker_db = lambda: None
    worker_executor.JobExecutor = Mock()
    modules = {"worker": worker_pkg, "worker.app": worker_app, "worker.executor": worker_executor}
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("bw_worker_tasks", ROOT / "src" / "worker" / "tasks.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


APP = _load_app()
TASKS = _load_tasks()


class _FakeRedis:
    def __init__(self, counts=None, raises=False):
        self.counts = counts if counts is not None else {}
        self.raises = raises
        self.expirations = []

    def incr(self, key):
        if self.raises:
            raise RuntimeError("broker unreachable")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, ttl):
        self.expirations.append((key, ttl))


def _with_redis(client):
    """Install a stub ``redis`` module whose ``Redis.from_url`` yields ``client``."""
    module = ModuleType("redis")
    module.Redis = Mock()
    module.Redis.from_url = Mock(return_value=client)
    return patch.dict(sys.modules, {"redis": module})


LOGGER = Mock()
BROKER = "redis://broker:6379/0"


def test_worker_requests_instance_credentials(monkeypatch):
    db = Mock()
    db.get_instances.return_value = [{"hostname": "bw-1", "status": "up", "credential": "instance-token"}]
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)

    caller = TASKS._get_apis()

    db.get_instances.assert_called_once_with(with_credential=True)
    assert len(caller.apis) == 1


class TestAckSettings:
    def test_delivery_is_at_least_once(self):
        """The whole point of the change: nothing may ack a job before it has run."""
        assert APP.app.conf["task_acks_late"] is True
        assert APP.app.conf["task_reject_on_worker_lost"] is True

    def test_the_decorator_does_not_contradict_the_app_config(self):
        """``@app.task(acks_late=...)`` beats ``app.conf``, so a stale decorator silently wins.

        That is exactly how this shipped: ``app.conf`` could have said True while the task kept
        early-acking, and no test would have noticed. Assert the two agree rather than that
        either one has a particular value.
        """
        assert TASKS.execute_job.task_options["acks_late"] is APP.app.conf["task_acks_late"]

    def test_removing_celerys_loop_protection_comes_with_our_own_bound(self):
        """``reject_on_worker_lost`` disables Celery's "ack a signal-killed task" guard.

        Celery keeps that guard on by default precisely so a task that segfaults cannot be
        requeued forever. Turning it off is only safe while a finite bound exists here.
        """
        assert APP.app.conf["task_reject_on_worker_lost"] is True
        assert TASKS.MAX_DELIVERY_ATTEMPTS >= 1

    def test_the_visibility_timeout_covers_a_task_plus_the_time_it_waits_reserved(self):
        """Redelivery is driven by the visibility timeout; a task still pending when it expires
        is handed to a SECOND worker while the first is mid-write.

        Beating ``task_time_limit`` is the weak half of the property. Under acks_late the
        visibility clock starts at DELIVERY, not at execution, and with prefetch on, a message
        sits *reserved* behind the tasks the worker is already running -- so the budget has to
        cover the queue wait as well as the run. ``entrypoint.sh`` defaults to
        ``--concurrency=2``, so up to two tasks can be in front of a reserved one.
        """
        conf = APP.app.conf
        reserved_depth = 2 * conf["worker_prefetch_multiplier"]
        assert conf["broker_transport_options"]["visibility_timeout"] >= conf["task_time_limit"] * (reserved_depth + 1)


class TestBrokerClient:
    """The counter runs on the job's critical path, so it must never be able to block one."""

    def _from_url_kwargs(self, call):
        module = ModuleType("redis")
        module.Redis = Mock()
        with patch.dict(sys.modules, {"redis": module}):
            call()
        return module.Redis.from_url.call_args.kwargs

    def test_the_broker_client_cannot_block_forever(self):
        """redis-py defaults to ``socket_timeout=None``. A black-holed broker -- the netsplit
        that caused the worker loss in the first place -- would hang the job until
        ``task_time_limit``, and a time-limit kill ACKs the message: silent loss, which is the
        bug at-least-once delivery exists to fix.
        """
        kwargs = self._from_url_kwargs(lambda: TASKS._broker_client(BROKER))
        assert kwargs.get("socket_timeout")
        assert kwargs.get("socket_connect_timeout")

    def test_the_reload_path_goes_through_the_same_guarded_client(self, monkeypatch):
        """``_request_reload_debounced`` had the same bare client and the same exposure. Pin
        that it shares the helper rather than growing its own connection again."""
        seen = []
        monkeypatch.setattr(TASKS, "_broker_client", lambda url: seen.append(url) or Mock())
        apis = Mock()
        apis.send_files = Mock(return_value=True)
        apis.send_to_apis = Mock(return_value=(True, {}))
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)
        assert seen == [BROKER]


class TestDeliveryAttempt:
    def test_first_delivery_counts_one_and_sets_a_ttl(self):
        client = _FakeRedis()
        with _with_redis(client):
            assert TASKS._delivery_attempt("run-1", BROKER, LOGGER) == 1
        assert client.expirations == [("bw:job_attempt:run-1", 86400)]

    def test_redeliveries_of_the_same_dispatch_accumulate(self):
        client = _FakeRedis()
        with _with_redis(client):
            attempts = [TASKS._delivery_attempt("run-1", BROKER, LOGGER) for _ in range(3)]
        assert attempts == [1, 2, 3]
        # The TTL is set once, on the key's creation -- re-arming it on every delivery would let
        # a job that is redelivered forever keep its counter alive forever too.
        assert len(client.expirations) == 1

    def test_a_different_dispatch_of_the_same_job_starts_over(self):
        """The key is the task id, which the API mints per dispatch. This bounds retries of ONE
        dispatch; it must never accumulate across a job's scheduled runs and eventually refuse
        to run a perfectly healthy daily job."""
        client = _FakeRedis()
        with _with_redis(client):
            TASKS._delivery_attempt("run-1", BROKER, LOGGER)
            TASKS._delivery_attempt("run-1", BROKER, LOGGER)
            assert TASKS._delivery_attempt("run-2", BROKER, LOGGER) == 1

    def test_an_unreachable_broker_fails_open(self):
        """Losing the counter must cost visibility, never work: returning 0 runs the job."""
        with _with_redis(_FakeRedis(raises=True)):
            assert TASKS._delivery_attempt("run-1", BROKER, LOGGER) == 0

    def test_no_task_id_never_touches_the_broker(self):
        client = _FakeRedis()
        with _with_redis(client):
            assert TASKS._delivery_attempt("", BROKER, LOGGER) == 0
        assert client.counts == {}


class _Request:
    def __init__(self, task_id):
        self.id = task_id


class _Self:
    def __init__(self, task_id="run-1"):
        self.request = _Request(task_id)


JOB = {"name": "certbot-renew", "plugin_id": "letsencrypt", "run_id": "run-1", "file": "certbot-renew.py", "path": "/x"}


@pytest.fixture
def stub_runtime(monkeypatch):
    """Neutralize everything ``execute_job`` reaches for except the code under test."""
    logger_module = ModuleType("logger")
    logger_module.setup_logger = Mock(return_value=LOGGER)
    monkeypatch.setitem(sys.modules, "logger", logger_module)
    monkeypatch.setattr(TASKS, "_get_apis", lambda: None)
    monkeypatch.setattr(TASKS, "_load_job_config_env", lambda db, logger: {})
    monkeypatch.setenv("CELERY_BROKER_URL", BROKER)
    executor = Mock()
    executor.run = Mock(return_value=0)
    monkeypatch.setattr(TASKS, "JobExecutor", Mock(return_value=executor))
    return executor


class TestAbandonment:
    def test_a_job_within_the_limit_runs(self, stub_runtime, monkeypatch):
        db = Mock()
        db.add_job_run = Mock(return_value=None)
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
        with _with_redis(_FakeRedis(counts={"bw:job_attempt:run-1": TASKS.MAX_DELIVERY_ATTEMPTS - 1})):
            result = TASKS.execute_job(_Self(), dict(JOB))
        stub_runtime.run.assert_called_once()
        assert result["success"] is True
        assert "abandoned_after_attempts" not in result

    def test_a_job_past_the_limit_is_dropped_without_running(self, stub_runtime, monkeypatch):
        """The failure mode this bound exists for: an OOM-killing job requeued forever. It must
        stop EXECUTING, not merely stop logging -- assert the executor was never invoked."""
        db = Mock()
        db.add_job_run = Mock(return_value=None)
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
        with _with_redis(_FakeRedis(counts={"bw:job_attempt:run-1": TASKS.MAX_DELIVERY_ATTEMPTS})):
            result = TASKS.execute_job(_Self(), dict(JOB))
        stub_runtime.run.assert_not_called()
        assert result["success"] is False
        assert result["abandoned_after_attempts"] == TASKS.MAX_DELIVERY_ATTEMPTS + 1

    def test_abandoning_still_records_a_failed_run(self, stub_runtime, monkeypatch):
        """Silence is what the old early-ack behaviour produced. Giving up must be visible in
        the job history rather than reproducing the bug at the limit."""
        db = Mock()
        db.add_job_run = Mock(return_value=None)
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
        with _with_redis(_FakeRedis(counts={"bw:job_attempt:run-1": TASKS.MAX_DELIVERY_ATTEMPTS})):
            TASKS.execute_job(_Self(), dict(JOB))
        db.add_job_run.assert_called_once()
        recorded_name, recorded_success = db.add_job_run.call_args[0][0], db.add_job_run.call_args[0][1]
        assert recorded_name == "certbot-renew"
        assert recorded_success is False
        assert isinstance(db.add_job_run.call_args[0][2], datetime)

    def test_a_dead_database_does_not_stop_the_job_being_dropped(self, stub_runtime, monkeypatch):
        """Recording the give-up is best-effort; failing to record it must not raise back into
        Celery, which would reject the message and restart the very loop this bound ends."""
        db = Mock()
        db.add_job_run = Mock(side_effect=RuntimeError("db gone"))
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
        with _with_redis(_FakeRedis(counts={"bw:job_attempt:run-1": TASKS.MAX_DELIVERY_ATTEMPTS})):
            result = TASKS.execute_job(_Self(), dict(JOB))
        assert result["success"] is False
        stub_runtime.run.assert_not_called()

    def test_an_unreachable_broker_does_not_block_the_job(self, stub_runtime, monkeypatch):
        """Fail-open, end to end: no counter must mean the job runs, not that it is abandoned."""
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: None)
        with _with_redis(_FakeRedis(raises=True)):
            result = TASKS.execute_job(_Self(), dict(JOB))
        stub_runtime.run.assert_called_once()
        assert result["success"] is True


class TestLeaseBroker:
    """The broker URL a leased job needs, and the strip that has to keep holding for everyone else.

    ``SENSITIVE_ENV_KEYS`` removes ``CELERY_BROKER_URL`` from every job's environment. That left
    push-configs' distributed lease inert in split-container deployments: no Redis on localhost,
    so the acquisition raised and the job's except branch pushed anyway, uncoordinated, on every
    dispatch. The lease worked only in all-in-one -- the one topology with nothing to coordinate.
    """

    @staticmethod
    def _env_seen_by(job_name, stub_runtime, monkeypatch):
        """Run one job and return the environment its executor actually saw."""
        seen = {}
        stub_runtime.run = Mock(side_effect=lambda _data: seen.update(os.environ) or 0)
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: None)
        with _with_redis(_FakeRedis()):
            TASKS.execute_job(_Self(), dict(JOB, name=job_name))
        return seen

    def test_a_leased_job_can_reach_the_broker(self, stub_runtime, monkeypatch):
        seen = self._env_seen_by("push-configs", stub_runtime, monkeypatch)
        assert seen.get("CELERY_BROKER_URL") == BROKER

    def test_every_other_job_still_cannot(self, stub_runtime, monkeypatch):
        """The exception is an allowlist, not a removal: a third-party plugin job must not gain
        read access to the broker credentials because one core job needed a lease."""
        seen = self._env_seen_by("certbot-renew", stub_runtime, monkeypatch)
        assert "CELERY_BROKER_URL" not in seen

    def test_the_hmac_secret_is_stripped_from_a_leased_job_too(self, stub_runtime, monkeypatch):
        """Only the broker URL is excepted. Widening it to the whole set would be a real leak."""
        monkeypatch.setenv("JOBS_HMAC_SECRET", "s3cret")
        seen = self._env_seen_by("push-configs", stub_runtime, monkeypatch)
        assert "JOBS_HMAC_SECRET" not in seen

    def test_nothing_is_invented_when_the_worker_has_no_broker_either(self, stub_runtime, monkeypatch):
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        seen = self._env_seen_by("push-configs", stub_runtime, monkeypatch)
        assert "CELERY_BROKER_URL" not in seen

    def test_the_worker_env_is_restored_afterwards(self, stub_runtime, monkeypatch):
        self._env_seen_by("push-configs", stub_runtime, monkeypatch)
        assert os.environ.get("CELERY_BROKER_URL") == BROKER

    def test_every_leased_job_names_a_job_that_exists(self):
        """The set is matched against job_data["name"], so a typo disables the lease silently."""
        jobs = {path.stem for path in (ROOT / "src" / "common" / "core").glob("*/jobs/*.py")}
        assert TASKS.LEASE_JOBS <= jobs, sorted(TASKS.LEASE_JOBS - jobs)

    def test_a_job_that_takes_a_lease_is_in_the_set(self):
        """The other direction: a job reading the lease key without being listed here is back to
        having no broker, which is the bug this closes."""
        for path in (ROOT / "src" / "common" / "core").glob("*/jobs/*.py"):
            if "acquire_lease(" in path.read_text(encoding="utf-8"):
                assert path.stem in TASKS.LEASE_JOBS, path.stem

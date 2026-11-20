"""BW-2211: scheduled jobs run once, through JobScheduler's runner, on a fresh module each time.

The registry helpers fall back to the default ``schedule`` registry, so the same tests run against a copy of the
scheduler from before the change (``BW_SCHEDULER_SRC``) and fail there for the behaviour, not for a missing attribute.
"""

import ast
import asyncio
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import schedule

import test_jobscheduler_jobs as jobs_tests
from test_jobscheduler_jobs import EXIT, FakeDb, job

make_scheduler = jobs_tests.make_scheduler  # the fixture, shared

MAIN_PY = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"
if "BW_SCHEDULER_SRC" in os.environ:
    MAIN_PY = Path(os.environ["BW_SCHEDULER_SRC"]) / "main.py"


def registry(sched):
    return getattr(sched, "scheduler", schedule)


def make_due(sched):
    for scheduled in registry(sched).jobs:
        scheduled.next_run = datetime.now() - timedelta(seconds=1)


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class Trace:
    """Stands in for a module the job bodies import: records when each job ran and on which thread."""

    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def run(self, name, nap=0.0):
        start = time.monotonic()
        time.sleep(nap)
        end = time.monotonic()
        with self.lock:
            self.events.append((name, start, end, threading.current_thread().name))

    def of(self, name):
        return [event for event in self.events if event[0] == name]

    def count(self, name):
        return len(self.of(name))


@pytest.fixture
def trace(monkeypatch):
    recorded = Trace()
    monkeypatch.setitem(sys.modules, "bw_trace", recorded)
    return recorded


@pytest.fixture(autouse=True)
def clean_default_registry():
    schedule.clear()
    yield
    schedule.clear()


def traced(name, nap=0.0):
    return f"import sys, bw_trace\nbw_trace.run({name!r}, {nap})\nsys.exit(0)\n"


def batch(sched, mode):
    """Run one batch the way production does and return what escaped it, so a test can assert the behaviour first."""
    try:
        if mode == "run_once":
            sched.run_once()
        else:
            sched.setup()
            make_due(sched)
            sched.run_pending()
    except (Exception, asyncio.CancelledError) as e:  # noqa: BLE001
        return e
    return None


class RecoveringDb(FakeDb):
    """A database whose primary is down until ``fail`` is cleared; every retry stamps ``last_connection_retry`` like the real one."""

    def __init__(self):
        super().__init__()
        self.fail: Exception | None = None
        self.retries = 0

    def retry_connection(self, **kwargs):
        self.last_connection_retry = datetime.now().astimezone()
        self.retries += 1
        if self.fail and not kwargs.get("fallback"):
            raise self.fail


# --- T1 (S1): one runner ------------------------------------------------------------------------------------------


def test_the_tick_runs_the_healthcheck_once_and_plugin_jobs_through_the_runner(make_scheduler, sched_main, monkeypatch, trace, caplog):
    sched = make_scheduler([("plug", [job("a", "a.py", "minute")], {"a.py": traced("a")})])
    monkeypatch.setattr(sched_main, "SCHEDULER", sched)
    sched.setup()
    health = []
    healthcheck = schedule.every(1).hours.do(lambda: health.append(1))
    healthcheck.next_run = datetime.now() - timedelta(seconds=1)
    make_due(sched)
    healthcheck.next_run = datetime.now() - timedelta(seconds=1)

    with caplog.at_level(logging.INFO):
        sched_main.scheduler_tick(True)

    assert len(health) == 1
    assert trace.count("a") == 1
    assert sched.generation_pending is True
    assert "All scheduled jobs have been executed" in caplog.text
    assert not [key for key in sys.modules if key.startswith("bw_job_")], "the batch cleanup did not run"
    assert schedule.jobs == [healthcheck], "a plugin job sits on the default registry, where the library runs it off the runner"

    sched_main.scheduler_tick(False)
    assert len(health) == 1 and trace.count("a") == 1, "nothing is due on the next tick"


def test_the_main_loop_calls_the_tick_and_nothing_else_runs_schedules():
    tree = ast.parse(MAIN_PY.read_text())
    tick = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "scheduler_tick"), None)
    assert tick is not None, "main.py has no scheduler_tick()"
    inside = {id(n) for n in ast.walk(tick)}

    def runs_schedules(call):
        func = call.func
        return (isinstance(func, ast.Name) and func.id == "run_pending") or (
            isinstance(func, ast.Attribute) and func.attr == "run_pending" and isinstance(func.value, ast.Name) and func.value.id == "SCHEDULER"
        )

    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert [c for c in calls if runs_schedules(c) and id(c) not in inside] == [], "a run_pending() call outside scheduler_tick()"
    assert any(isinstance(c.func, ast.Name) and c.func.id == "scheduler_tick" for c in calls), "the main loop never calls scheduler_tick()"
    assert sum(runs_schedules(c) for c in calls if id(c) in inside) == 2, "scheduler_tick() must run both the healthcheck and the job runner"


# --- T2 (S3): a fresh module every run ----------------------------------------------------------------------------


def test_consecutive_batches_and_run_single_never_warn_about_reloading(make_scheduler, trace, caplog):
    sched = make_scheduler([("plug", [job("a", "a.py", "minute")], {"a.py": traced("a")})])
    sched.setup()
    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            make_due(sched)
            assert sched.run_pending() is True
        assert sched.run_single("a") is True
        make_due(sched)
        assert sched.run_pending() is True
    assert trace.count("a") == 4
    assert "Failed to reload" not in caplog.text


def test_a_rewrite_with_the_same_size_and_mtime_runs_the_new_source(make_scheduler, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    marker = tmp_path / "marker"
    body = "import sys\nopen({marker!r}, 'w').write({text!r})\nsys.exit(0)\n"
    sched = make_scheduler([("plug", [job("a", "a.py", "minute")], {"a.py": body.format(marker=str(marker), text="one")})])
    script = Path(next(iter(sched._JobScheduler__jobs["plug"]))["path"]) / "jobs" / "a.py"
    sched.setup()
    make_due(sched)
    sched.run_pending()
    assert marker.read_text() == "one"

    stat = script.stat()
    script.write_text(body.format(marker=str(marker), text="two"), encoding="utf-8")
    os.utime(script, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert script.stat().st_size == stat.st_size and script.stat().st_mtime_ns == stat.st_mtime_ns

    make_due(sched)
    sched.run_pending()
    assert marker.read_text() == "two"


def test_a_job_module_keeps_its_job_name_and_real_path(make_scheduler, tmp_path):
    marker = tmp_path / "marker"
    body = f"import sys\nopen({str(marker)!r}, 'w').write(__name__ + '|' + __file__)\nsys.exit(0)\n"
    sched = make_scheduler([("plug", [job("the-job", "a.py")], {"a.py": body})])
    script = Path(next(iter(sched._JobScheduler__jobs["plug"]))["path"]) / "jobs" / "a.py"
    sched.run_single("the-job")
    assert marker.read_text() == f"the-job|{script.resolve()}"
    sched.run_single("the-job")
    assert marker.read_text() == f"the-job|{script.resolve()}"


# --- T3 (S2): the run_once concurrency model ----------------------------------------------------------------------


def test_scheduled_jobs_run_serially_per_plugin_in_parallel_across_plugins_and_async_alone(make_scheduler, trace, monkeypatch):
    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "6")
    sched = make_scheduler(
        [
            (
                "alpha",
                [job("a1", "a1.py", "minute"), job("a2", "a2.py", "minute"), job("a3", "a3.py", "minute", **{"async": True})],
                {"a1.py": traced("a1", 0.3), "a2.py": traced("a2", 0.05), "a3.py": traced("a3", 0.3)},
            ),
            ("beta", [job("b1", "b1.py", "minute")], {"b1.py": traced("b1", 0.3)}),
        ]
    )
    assert batch(sched, "run_pending") is None
    a1, a2, a3, b1 = (trace.of(name)[0] for name in ("a1", "a2", "a3", "b1"))
    assert a2[1] >= a1[2], "jobs of one plugin overlapped"
    assert b1[1] < a1[2] and a1[1] < b1[2], "plugins did not run in parallel"
    assert a3[1] < a1[2] and a1[1] < a3[2], "the async job waited for its plugin"
    assert a1[3] == a2[3], "one plugin's jobs should share a task"
    assert threading.current_thread().name not in {e[3] for e in trace.events}, "a job ran on the calling thread"


# --- T4 (S4): one healthcheck ---------------------------------------------------------------------------------------


def test_a_reload_leaves_exactly_one_healthcheck(make_scheduler, sched_main, trace):
    sched = make_scheduler([("plug", [job("a", "a.py", "minute")], {"a.py": traced("a")})])

    def healthchecks():
        return [j for j in schedule.jobs if j.job_func.func is sched_main.healthcheck_job]

    sched_main.schedule_healthcheck()
    assert len(healthchecks()) == 1
    assert sched.reload({}) is True
    assert len(healthchecks()) == 1, "reload() wiped the healthcheck from the default registry"
    for _ in range(3):
        assert sched.reload({}) is True
        sched_main.schedule_healthcheck()
    assert len(healthchecks()) == 1


# --- T5 (S5): one failure record per failing job ------------------------------------------------------------------


FAILING = {
    "exc.py": "raise RuntimeError('boom')\n",
    "two.py": EXIT.format(code=2),
    "three.py": EXIT.format(code=3),
}
FAILING_JOBS = [job("exc", "exc.py", "minute"), job("two", "two.py", "minute"), job("three", "three.py", "minute")]


@pytest.mark.parametrize("mode", ["run_once", "run_pending"])
def test_every_failing_job_of_a_batch_is_recorded_once(make_scheduler, caplog, mode):
    sched = make_scheduler([("plug", FAILING_JOBS, FAILING)])
    published = []
    if mode == "run_pending":
        sched._JobScheduler__publish_pending = lambda: published.append(True) or True
    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, mode)
    wait_for(lambda: len(sched.fake_db.job_runs) >= 3, timeout=1.0)
    time.sleep(0.1)

    assert sorted(sched.failed_jobs) == ["plug/exc", "plug/three", "plug/two"]
    assert sorted(sched.fake_db.job_runs) == [("exc", False), ("three", False), ("two", False)]
    for name in ("exc", "two", "three"):
        lines = [r for r in caplog.records if r.levelno >= logging.ERROR and f"'{name}'" in r.getMessage()]
        assert len(lines) == 1, f"{name}: {[r.getMessage() for r in lines]}"
    if mode == "run_pending":
        assert published == [True], "exit 3 must still request the publication"
    else:
        assert sched.consume_pending_publication()[0] is True
    assert escaped is None


# --- T6 (S6): batches wait for every task, raising callbacks are contained -----------------------------------------


def raising_wrapper(sched, raising, attempts, exc=RuntimeError):
    """Make the scheduled callable itself raise (past the entrypoint, which __job_wrapper already catches)."""
    real = sched._JobScheduler__job_wrapper

    def wrapper(path, plugin, name, file):
        attempts.append(name)
        if name in raising:
            raise exc(f"bookkeeping failed for {name}")
        return real(path, plugin, name, file)

    sched._JobScheduler__job_wrapper = wrapper


def test_a_raising_task_does_not_end_the_batch_early_or_get_resubmitted(make_scheduler, trace, caplog):
    sched = make_scheduler(
        [
            ("first", [job("r", "r.py", "minute")], {"r.py": traced("r")}),
            ("second", [job("s", "s.py", "minute")], {"s.py": traced("s", 0.6)}),
        ]
    )
    attempts = []
    raising_wrapper(sched, {"r"}, attempts)
    cleanups = []
    real_cleanup = sched.cleanup_modules
    sched.cleanup_modules = lambda: (cleanups.append(time.monotonic()), real_cleanup())[1]

    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, "run_pending")
    assert trace.count("s") == 1, "the batch ended while a sibling job was still running"
    assert cleanups and cleanups[0] >= trace.of("s")[0][2], "cleanup started while a sibling job was still running"
    assert "Exception while running job 'r'" in caplog.text
    assert sched.failed_jobs == ["first/r"]
    assert all(j.next_run > datetime.now() for j in registry(sched).jobs), "a job of the batch is still due"
    assert escaped is None

    assert sched.run_pending() is True
    assert attempts == ["r", "s"] or sorted(attempts) == ["r", "s"], "a due slot was submitted twice"
    assert trace.count("s") == 1


@pytest.mark.parametrize("mode", ["run_once", "run_pending"])
def test_a_raising_job_does_not_skip_the_next_job_of_its_plugin(make_scheduler, trace, caplog, mode):
    sched = make_scheduler([("plug", [job("A", "a.py", "minute"), job("B", "b.py", "minute")], {"a.py": traced("A"), "b.py": traced("B")})])
    attempts = []
    raising_wrapper(sched, {"A"}, attempts)
    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, mode)
    wait_for(lambda: len(sched.fake_db.job_runs) >= 2, timeout=1.0)
    time.sleep(0.1)

    assert trace.count("B") == 1
    assert sched.failed_jobs == ["plug/A"]
    assert sorted(sched.fake_db.job_runs) == [("A", False), ("B", True)]
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR and "'A'" in r.getMessage()]) == 1
    assert escaped is None


def test_the_reschedule_after_a_raising_callback_uses_the_vendored_schedule_api():
    assert callable(getattr(schedule.Job, "_schedule_next_run", None))
    scheduled = schedule.every(1).hours.do(lambda: None)
    before = scheduled.next_run
    scheduled.last_run = datetime.now()
    time.sleep(0.01)
    scheduled._schedule_next_run()
    assert scheduled.next_run > before


# --- C1: a cancelled job is a failed run, like a raised exception ---------------------------------------------------

CANCELLED = {"c.py": "import asyncio\nraise asyncio.CancelledError()\n", "n.py": traced("N")}
CANCELLED_JOBS = [job("c", "c.py", "minute"), job("n", "n.py", "minute")]


@pytest.mark.parametrize("mode", ["run_once", "run_pending"])
def test_a_cancelled_job_is_a_failed_run_like_a_raised_exception(make_scheduler, trace, caplog, mode):
    sched = make_scheduler([("plug", CANCELLED_JOBS, CANCELLED)])
    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, mode)
    wait_for(lambda: len(sched.fake_db.job_runs) >= 2, timeout=1.0)
    time.sleep(0.1)

    assert escaped is None
    assert trace.count("N") == 1, "the next job of the plugin was skipped"
    assert sched.failed_jobs == ["plug/c"]
    assert sorted(sched.fake_db.job_runs) == [("c", False), ("n", True)]
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR and "'c'" in r.getMessage()]) == 1
    if mode == "run_pending":
        assert all(j.next_run > datetime.now() for j in registry(sched).jobs), "the cancelled job is still due"
        assert sched.run_pending() is True
        assert trace.count("N") == 1 and len(sched.fake_db.job_runs) == 2, "a due slot ran twice"


@pytest.mark.parametrize("mode", ["run_once", "run_pending"])
def test_a_cancellation_escaping_the_callable_does_not_skip_the_next_job_or_stay_due(make_scheduler, trace, caplog, mode):
    sched = make_scheduler([("plug", [job("A", "a.py", "minute"), job("B", "b.py", "minute")], {"a.py": traced("A"), "b.py": traced("B")})])
    raising_wrapper(sched, {"A"}, [], exc=asyncio.CancelledError)
    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, mode)
    wait_for(lambda: len(sched.fake_db.job_runs) >= 2, timeout=1.0)
    time.sleep(0.1)

    assert escaped is None
    assert trace.count("B") == 1
    assert sched.failed_jobs == ["plug/A"]
    assert sorted(sched.fake_db.job_runs) == [("A", False), ("B", True)]
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR and "'A'" in r.getMessage()]) == 1
    if mode == "run_pending":
        assert all(j.next_run > datetime.now() for j in registry(sched).jobs), "the cancelled job is still due"


# --- F2-F4: logging an exception must not evaluate its truth value or let its text raise ----------------------------------


class BoolRaises(Exception):
    def __bool__(self):
        raise RuntimeError("__bool__ must not be evaluated")


class BoolRaisesStr(str):
    def __bool__(self):
        raise RuntimeError("__bool__ must not be evaluated")


class StrBoolRaises(Exception):
    """__str__ returns a str subclass whose __bool__ raises."""

    def __str__(self):
        return BoolRaisesStr(super().__str__())


class StrRaises(Exception):
    def __str__(self):
        raise RuntimeError("__str__ must not be evaluated")


class FormatRaisesStr(str):
    def __format__(self, spec):
        raise RuntimeError("__format__ must not be evaluated")

    def __bool__(self):
        raise RuntimeError("__bool__ must not be evaluated")


class NamedMeta(type):
    """The class name is a str subclass that raises when formatted or truth-tested."""

    @property
    def __name__(cls):
        return FormatRaisesStr("NamedBoom")


class NamedBoom(Exception, metaclass=NamedMeta):
    def __str__(self):
        raise RuntimeError("__str__ must not be evaluated")


class NoNameMeta(type):
    @property
    def __name__(cls):
        raise RuntimeError("__name__ must not be evaluated")


class NoNameBoom(Exception, metaclass=NoNameMeta):
    def __str__(self):
        raise RuntimeError("__str__ must not be evaluated")


class StrExit(Exception):
    def __str__(self):
        raise SystemExit("__str__ must not be evaluated")


class StrInterrupt(Exception):
    def __str__(self):
        raise KeyboardInterrupt("__str__ must not be evaluated")


class NameExitMeta(type):
    @property
    def __name__(cls):
        raise SystemExit("__name__ must not be evaluated")


class NameExitBoom(Exception, metaclass=NameExitMeta):
    def __str__(self):
        raise SystemExit("__str__ must not be evaluated")


NAME_HEAD = (
    "class S(str):\n    def __format__(self, spec):\n        raise RuntimeError('__format__ must not be evaluated')\n"
    "    def __bool__(self):\n        raise RuntimeError('__bool__ must not be evaluated')\n\n"
)
BOOL_RAISES_SOURCES = {
    "named": NAME_HEAD
    + "class M(type):\n    @property\n    def __name__(cls):\n        return S('NamedBoom')\n\n"
    + "class NamedBoom(Exception, metaclass=M):\n    def __str__(self):\n        raise RuntimeError('__str__ must not be evaluated')\n\nraise NamedBoom('boom')\n",
    "noname": (
        "class M(type):\n    @property\n    def __name__(cls):\n        raise RuntimeError('__name__ must not be evaluated')\n\n"
        "class NoNameBoom(Exception, metaclass=M):\n    def __str__(self):\n        raise RuntimeError('__str__ must not be evaluated')\n\nraise NoNameBoom('boom')\n"
    ),
    "str_exit": "class StrExit(Exception):\n    def __str__(self):\n        raise SystemExit('__str__ must not be evaluated')\n\nraise StrExit('boom')\n",
    "str_interrupt": (
        "class StrInterrupt(Exception):\n    def __str__(self):\n        raise KeyboardInterrupt('__str__ must not be evaluated')\n\nraise StrInterrupt('boom')\n"
    ),
    "name_exit": (
        "class M(type):\n    @property\n    def __name__(cls):\n        raise SystemExit('__name__ must not be evaluated')\n\n"
        "class NameExitBoom(Exception, metaclass=M):\n    def __str__(self):\n        raise SystemExit('__str__ must not be evaluated')\n\nraise NameExitBoom('boom')\n"
    ),
    "bool": "class E(Exception):\n    def __bool__(self):\n        raise RuntimeError('__bool__ must not be evaluated')\n\nraise E('boom')\n",
    "str": (
        "class S(str):\n    def __bool__(self):\n        raise RuntimeError('__bool__ must not be evaluated')\n\n"
        "class E(Exception):\n    def __str__(self):\n        return S(super().__str__())\n\nraise E('boom')\n"
    ),
    "raises": "class StrRaises(Exception):\n    def __str__(self):\n        raise RuntimeError('__str__ must not be evaluated')\n\nraise StrRaises('boom')\n",
}
BOOL_RAISES_EXC = {
    "bool": BoolRaises,
    "str": StrBoolRaises,
    "raises": StrRaises,
    "named": NamedBoom,
    "noname": NoNameBoom,
    "str_exit": StrExit,
    "str_interrupt": StrInterrupt,
    "name_exit": NameExitBoom,
}


@pytest.mark.parametrize("mode", ["run_once", "run_pending"])
@pytest.mark.parametrize("where", ["entrypoint", "callable"])
@pytest.mark.parametrize("kind", ["bool", "str", "raises", "named", "noname", "str_exit", "str_interrupt", "name_exit"])
def test_an_exception_that_breaks_its_own_formatting_is_a_failed_run_not_an_escape(make_scheduler, trace, caplog, mode, where, kind):
    sched = make_scheduler(
        [
            (
                "plug",
                [job("A", "a.py", "minute"), job("B", "b.py", "minute")],
                {"a.py": BOOL_RAISES_SOURCES[kind], "b.py": traced("B")} if where == "entrypoint" else {"a.py": traced("A"), "b.py": traced("B")},
            )
        ]
    )
    if where == "callable":
        raising_wrapper(sched, {"A"}, [], exc=BOOL_RAISES_EXC[kind])
    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, mode)
    wait_for(lambda: len(sched.fake_db.job_runs) >= 2, timeout=1.0)
    time.sleep(0.1)

    assert escaped is None
    assert trace.count("B") == 1, "the next job of the plugin was skipped"
    assert sched.failed_jobs == ["plug/A"]
    assert sorted(sched.fake_db.job_runs) == [("A", False), ("B", True)]
    lines = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR and "'A'" in r.getMessage()]
    assert len(lines) == 1
    # the log line carries the job's own error: a __bool__ evaluated inside the except block replaces it with the __bool__ error
    for evaluated in ("__bool__", "__str__", "__format__", "__name__"):
        assert f"{evaluated} must not be evaluated" not in lines[0]
    if kind == "raises":
        assert "StrRaises" in lines[0], "a __str__ that raises falls back to the class name"
    elif kind in ("str_exit", "str_interrupt"):
        assert lines[0].endswith(("StrExit", "StrInterrupt")), "a __str__ that raises SystemExit or KeyboardInterrupt falls back to the class name"
    elif kind == "name_exit":
        assert lines[0].endswith("unprintable error"), "a class name getter that raises SystemExit gets the fixed message"
    elif kind == "named":
        assert lines[0].endswith("NamedBoom"), "the exact str copy of the class name is logged"
    elif kind == "noname":
        assert lines[0].endswith("unprintable error"), "a class name that cannot be read gets a fixed message"
    else:
        assert ("boom" if where == "entrypoint" else "bookkeeping failed for A") in lines[0]


# --- F5: a SystemExit code the job controls never reaches a comparison --------------------------------------------------

EXIT_CODE_SOURCES = {
    "code_raises": ("class X(SystemExit):\n    @property\n    def code(self):\n        raise RuntimeError('code must not be read')\n\nraise X()\n"),
    "code_exit": "class X(SystemExit):\n    @property\n    def code(self):\n        raise SystemExit('code must not be read')\n\nraise X()\n",
    "code_interrupt": ("class X(SystemExit):\n    @property\n    def code(self):\n        raise KeyboardInterrupt('code must not be read')\n\nraise X()\n"),
    "int_raises": (
        "class C(int):\n"
        + "".join(
            f"    def {op}(self, other):\n        raise RuntimeError('comparison must not be evaluated')\n"
            for op in ("__eq__", "__lt__", "__ge__", "__index__")
        )
        + "    def __int__(self):\n        raise RuntimeError('__int__ must not be called')\n\nraise SystemExit(C(2))\n"
    ),
}


@pytest.mark.parametrize("mode", ["run_once", "run_pending", "run_single"])
@pytest.mark.parametrize("kind", ["code_raises", "code_exit", "code_interrupt", "int_raises"])
def test_a_system_exit_whose_code_misbehaves_is_a_failed_run_not_an_escape(make_scheduler, trace, caplog, mode, kind):
    jobs = [job("A", "a.py", "minute")] + ([job("B", "b.py", "minute")] if mode != "run_single" else [])
    files = {"a.py": EXIT_CODE_SOURCES[kind], "b.py": traced("B")}
    sched = make_scheduler([("plug", jobs, files)])
    escaped = None
    with caplog.at_level(logging.ERROR):
        if mode == "run_single":
            try:
                assert sched.run_single("A") is False
            except (Exception, asyncio.CancelledError) as e:  # noqa: BLE001
                escaped = e
        else:
            escaped = batch(sched, mode)
    expected = [("A", False)] if mode == "run_single" else [("A", False), ("B", True)]
    wait_for(lambda: len(sched.fake_db.job_runs) >= len(expected), timeout=1.0)
    time.sleep(0.1)

    assert escaped is None
    if mode != "run_single":
        assert trace.count("B") == 1, "the next job of the plugin was skipped"
    assert sched.failed_jobs == ["plug/A"]
    assert sorted(sched.fake_db.job_runs) == expected
    lines = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR and "'A'" in r.getMessage()]
    assert len(lines) == 1, lines


@pytest.mark.parametrize(
    "code, ok, reload_pending",
    [
        (0, True, False),
        (1, True, True),
        (2, False, False),
        (3, False, True),
        (-1, False, False),
        (None, True, True),
        (True, True, True),
        (False, True, False),
        ("msg", True, True),
    ],
)
def test_every_normal_exit_code_keeps_its_meaning(make_scheduler, code, ok, reload_pending):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=repr(code))})])
    assert sched.run_single("j") is ok
    wait_for(lambda: len(sched.fake_db.job_runs) >= 1, timeout=1.0)
    time.sleep(0.1)
    assert sched.fake_db.job_runs == [("j", ok)]
    assert sched.failed_jobs == ([] if ok else ["plug/j"])
    assert sched.consume_pending_publication() == (reload_pending, False)


CLASS_CLAIM_SOURCES = {
    "claims_int": "class W:\n    @property\n    def __class__(self):\n        return int\n\nraise SystemExit(W())\n",
    "class_raises": "class W:\n    @property\n    def __class__(self):\n        raise RuntimeError('__class__ must not be read')\n\nraise SystemExit(W())\n",
}


@pytest.mark.parametrize("kind", ["claims_int", "class_raises"])
def test_a_system_exit_code_that_fakes_its_class_keeps_the_non_int_meaning(make_scheduler, kind):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": CLASS_CLAIM_SOURCES[kind]})])
    assert sched.run_single("j") is True
    wait_for(lambda: len(sched.fake_db.job_runs) >= 1, timeout=1.0)
    time.sleep(0.1)
    assert sched.fake_db.job_runs == [("j", True)]
    assert sched.failed_jobs == []
    assert sched.consume_pending_publication() == (True, False), "a non-int code is ret 1: success with a reload pending, like 'msg'"


@pytest.mark.parametrize("exc", [SystemExit, KeyboardInterrupt])
def test_a_system_exit_or_interrupt_escaping_the_callable_still_propagates(make_scheduler, trace, exc):
    sched = make_scheduler([("plug", [job("A", "a.py", "minute")], {"a.py": traced("A")})])
    raising_wrapper(sched, {"A"}, [], exc=exc)
    sched.setup()
    make_due(sched)
    with pytest.raises(exc):
        sched.run_pending()


# --- C2: two job names sharing one file get their own module ---------------------------------------------------------


def test_two_jobs_sharing_one_file_are_cached_apart_and_both_cleaned_up(make_scheduler, trace):
    sched = make_scheduler([("plug", [job("one", "shared.py", "minute"), job("two", "shared.py", "minute")], {"shared.py": traced("S")})])
    cached = []
    real_cleanup = sched.cleanup_modules
    sched.cleanup_modules = lambda: (cached.append(len(sched._JobScheduler__module_cache)), real_cleanup())[1]

    sched.run_once()

    assert trace.count("S") == 2
    assert cached and cached[0] == 2, "the second job overwrote the first one's cache entry"
    assert [k for k in sys.modules if k.startswith("bw_job_")] == []


# --- T7 (S7): read-only recovery keeps retrying ---------------------------------------------------------------------


def test_an_overdue_job_runs_once_after_a_read_only_database_recovers(make_scheduler, sched_main, monkeypatch, trace):
    db = RecoveringDb()
    sched = make_scheduler([("plug", [job("a", "a.py", "minute")], {"a.py": traced("a")})], db=db)
    monkeypatch.setattr(sched_main, "SCHEDULER", sched)
    sched.setup()
    make_due(sched)

    db.write_error = OSError("read-only")
    db.fail = ConnectionError("primary down")
    sched_main.scheduler_tick(False)
    assert db.readonly is True and trace.count("a") == 0

    sched_main.scheduler_tick(False)
    assert db.retries > 0 and trace.count("a") == 0

    # Past the first window the primary is back: the overdue job must run, once, with no config change.
    db.last_connection_retry = datetime.now().astimezone() - timedelta(seconds=31)
    db.write_error = None
    db.fail = None
    sched_main.scheduler_tick(False)
    assert db.readonly is False
    assert trace.count("a") == 1
    sched_main.scheduler_tick(False)
    assert trace.count("a") == 1


def test_a_read_only_database_is_retried_at_most_every_thirty_seconds(make_scheduler, sched_main, monkeypatch, trace):
    db = RecoveringDb()
    sched = make_scheduler([("plug", [job("a", "a.py", "minute")], {"a.py": traced("a")})], db=db)
    monkeypatch.setattr(sched_main, "SCHEDULER", sched)
    sched.setup()
    make_due(sched)
    db.write_error = OSError("read-only")
    db.fail = ConnectionError("primary down")
    sched_main.scheduler_tick(False)
    sched_main.scheduler_tick(False)
    retries = db.retries
    assert retries > 0
    sched_main.scheduler_tick(False)
    sched_main.scheduler_tick(False)
    assert db.retries == retries, "the primary was retried again inside the 30 s window"
    db.last_connection_retry = datetime.now().astimezone() - timedelta(seconds=31)
    sched_main.scheduler_tick(False)
    assert db.retries > retries
    assert trace.count("a") == 0


@pytest.mark.parametrize("mode", ["run_once", "run_pending"])
def test_a_negative_exit_status_is_a_failed_run_recorded_once(make_scheduler, caplog, mode):
    sched = make_scheduler([("plug", [job("neg", "neg.py", "minute")], {"neg.py": EXIT.format(code=-1)})])
    with caplog.at_level(logging.ERROR):
        escaped = batch(sched, mode)
    wait_for(lambda: len(sched.fake_db.job_runs) >= 1, timeout=1.0)
    time.sleep(0.1)

    assert sched.failed_jobs == ["plug/neg"]
    assert sched.fake_db.job_runs == [("neg", False)]
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR and "'neg'" in r.getMessage()]) == 1
    assert escaped is None

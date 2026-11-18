"""BW-2210: a job closes the Database it built when it ends, so MariaDB never logs "Aborted connection".

Job modules are dropped from sys.modules after every batch, which turns whatever they built into cyclic garbage. The
cyclic GC then runs ``Database.__del__`` after it has already cleared the weakrefs a TLS socket needs, so the COM_QUIT
write fails and the server sees the socket vanish. ``JobScheduler`` therefore closes, itself and deterministically,
every Database a job built, whatever way the job ends. A Database the job was handed, and the scheduler's own, stay open.
"""

import sys
import threading
from types import SimpleNamespace

import pytest

import test_jobscheduler_jobs as jobs

make_scheduler = jobs.make_scheduler
job = jobs.job

JOB_BODY = """
import logging
import sys
from os import getenv

from Database import Database

LOGGER = logging.getLogger("bw-job-under-test")
DB = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"), log=False)
{tail}
"""


@pytest.fixture
def tracked(tmp_path, monkeypatch, quiet_logger):
    """Record every Database built and every close(), without changing what either does."""
    import Database as database_module

    created, closed, events = [], [], []
    real_init, real_close = database_module.Database.__init__, database_module.Database.close
    lock = threading.Lock()

    def init(self, *args, **kwargs):
        with lock:
            created.append(self)
            events.append(("built", id(self), threading.get_ident()))
        real_init(self, *args, **kwargs)

    def close(self):
        # Database.__del__ also calls close(): only an explicit call counts as the scope's own.
        explicit = sys._getframe(1).f_code.co_name != "__del__"
        with lock:
            closed.append(self)
            if explicit:
                events.append(("close", id(self), threading.get_ident()))
        real_close(self)

    monkeypatch.setattr(database_module.Database, "__init__", init)
    monkeypatch.setattr(database_module.Database, "close", close)
    monkeypatch.setenv("DATABASE_URI", f"sqlite:///{tmp_path / 'job.sqlite3'}")
    return SimpleNamespace(
        created=created,
        closed=closed,
        events=events,
        module=database_module,
        logger=quiet_logger,
        new=lambda path: database_module.Database(quiet_logger, sqlalchemy_string=f"sqlite:///{path}", log=False),
    )


def is_closed(tracked, database):
    return any(database is c for c in tracked.closed)


@pytest.mark.parametrize(
    "tail",
    [
        "sys.exit(0)",
        "sys.exit(2)",
        "raise RuntimeError('job crashed after opening its database')",
        "raise SystemExit(1)",
    ],
    ids=["exit-0", "exit-2", "exception", "system-exit"],
)
def test_a_database_the_job_built_is_closed_however_the_job_ends(make_scheduler, tracked, tail):
    sched = make_scheduler([("plug", [job("work", "work.py")], {"work.py": JOB_BODY.format(tail=tail)})])
    built_before = len(tracked.created)

    sched.run_once()

    built = tracked.created[built_before:]
    assert len(built) == 1
    assert is_closed(tracked, built[0])


def test_every_database_a_job_built_is_closed_not_just_the_one_in_a_module_variable(make_scheduler, tracked):
    body = JOB_BODY.format(
        tail="OTHER = Database(LOGGER, sqlalchemy_string=getenv('DATABASE_URI'), log=False)\ndef main():\n    local = Database(LOGGER, sqlalchemy_string=getenv('DATABASE_URI'), log=False)\n    return local\nmain()\nsys.exit(0)"
    )
    sched = make_scheduler([("plug", [job("work", "work.py")], {"work.py": body})])
    built_before = len(tracked.created)

    sched.run_once()

    built = tracked.created[built_before:]
    assert len(built) == 3
    assert all(is_closed(tracked, db) for db in built)


def test_the_database_a_job_was_handed_is_never_closed(make_scheduler, tracked, tmp_path):
    shared = tracked.new(tmp_path / "shared.sqlite3")
    sys.modules["bw_unit_shared_db"] = SimpleNamespace(DB=shared)
    try:
        body = "import sys\nfrom bw_unit_shared_db import DB\nDB.get_metadata()\nsys.exit(0)\n"
        sched = make_scheduler([("plug", [job("borrow", "borrow.py")], {"borrow.py": body})])

        sched.run_once()

        assert not is_closed(tracked, shared)
        assert shared.get_metadata() is not None  # still usable
    finally:
        del sys.modules["bw_unit_shared_db"]
        shared.close()


def test_job_closes_the_database_it_created_and_not_the_one_it_was_passed(make_scheduler, tracked, tmp_path, monkeypatch):
    import jobs

    monkeypatch.setattr(jobs, "sep", str(tmp_path / "root"))
    shared = tracked.new(tmp_path / "shared.sqlite3")
    sys.modules["bw_unit_shared_db"] = SimpleNamespace(DB=shared)
    try:
        own = 'import logging\nimport sys\nfrom jobs import Job\nJOB = Job(logging.getLogger("bw-job-under-test"), __file__, deprecated=True)\nsys.exit(0)\n'
        passed = 'import logging\nimport sys\nfrom jobs import Job\nfrom bw_unit_shared_db import DB\nJOB = Job(logging.getLogger("bw-job-under-test"), __file__, DB, deprecated=True)\nsys.exit(0)\n'
        sched = make_scheduler(
            [
                ("ownplug", [job("own", "own.py")], {"own.py": own}),
                ("passplug", [job("passed", "passed.py")], {"passed.py": passed}),
            ]
        )
        built_before = len(tracked.created)

        sched.run_once()

        built = tracked.created[built_before:]
        assert len(built) == 1, "only Job(...) without db= builds a Database"
        assert is_closed(tracked, built[0])
        assert not is_closed(tracked, shared)
    finally:
        del sys.modules["bw_unit_shared_db"]
        shared.close()


def test_the_scheduler_own_database_is_untouched(make_scheduler, tracked, tmp_path):
    own = tracked.new(tmp_path / "scheduler.sqlite3")
    try:
        sched = make_scheduler([("plug", [job("work", "work.py")], {"work.py": JOB_BODY.format(tail="sys.exit(0)")})], db=own)

        sched.run_once()
        sched.reload({}, [])

        assert not is_closed(tracked, own)
        assert own.get_metadata() is not None
    finally:
        own.close()


def test_concurrent_jobs_each_close_only_their_own_database(make_scheduler, tracked, tmp_path):
    own = tracked.new(tmp_path / "scheduler.sqlite3")
    tail = (
        "import threading\nimport time\nfrom bw_unit_events import events\ntime.sleep(0.2)\nevents.append(('done', id(DB), threading.get_ident()))\nsys.exit(0)"
    )
    body = JOB_BODY.format(tail=tail)
    plugins = [(f"plug{i}", [job(f"work{i}", f"work{i}.py")], {f"work{i}.py": body}) for i in range(4)]
    sys.modules["bw_unit_events"] = SimpleNamespace(events=tracked.events)
    try:
        sched = make_scheduler(plugins, db=own)
        built_before = len(tracked.created)
        events_before = len(tracked.events)

        sched.run_once()

        built = tracked.created[built_before:]
        assert len(built) == 4
        assert not is_closed(tracked, own)
        events = tracked.events[events_before:]
        owners = {e[1]: e[2] for e in events if e[0] == "built"}
        assert len(set(owners.values())) > 1, "the jobs did not run on several threads"
        for db in built:
            ident = id(db)
            closes = [(i, e) for i, e in enumerate(events) if e[0] == "close" and e[1] == ident]
            done = [i for i, e in enumerate(events) if e[0] == "done" and e[1] == ident]
            assert len(closes) == 1, "each Database is closed exactly once by the scope"
            assert len(done) == 1
            assert closes[0][1][2] == owners[ident], "closed by a thread other than the one that built it"
            assert closes[0][0] > done[0], "closed before its own job body finished"
    finally:
        del sys.modules["bw_unit_events"]
        own.close()


def test_close_created_databases_restores_the_outer_scope(tracked, tmp_path):
    outer, inner = [], []
    with tracked.module.close_created_databases():
        a = tracked.new(tmp_path / "a.sqlite3")
        with tracked.module.close_created_databases():
            b = tracked.new(tmp_path / "b.sqlite3")
        inner.append(is_closed(tracked, b))
        outer.append(is_closed(tracked, a))
    assert inner == [True]
    assert outer == [False]
    assert is_closed(tracked, a)


def test_stop_closes_the_scheduler_database_before_exiting_whatever_the_status(sched_main, sandbox, fake_sched, monkeypatch):
    """_exit skips every finaliser, so the stop(1) error paths must close the scheduler's own connections themselves."""
    seen = []

    class Exited(BaseException):
        pass

    def fake_exit(status):
        seen.append((status, ("close",) in fake_sched.db.calls))
        raise Exited(status)  # the real _exit never returns

    monkeypatch.setattr(sched_main, "SCHEDULER_TASKS_EXECUTOR", SimpleNamespace(shutdown=lambda wait=True: None))
    monkeypatch.setattr(sched_main, "_exit", fake_exit)

    with pytest.raises(Exited):
        sched_main.stop(1)

    assert seen == [(1, True)], "(status, close already called when _exit ran)"


def test_a_fatal_init_exit_closes_the_databases_this_job_already_built(tracked, tmp_path, monkeypatch):
    """_exit skips the finally of close_created_databases(), so fail() must close what the job built before it."""
    seen = []

    class Exited(BaseException):
        pass

    with tracked.module.close_created_databases():
        a = tracked.new(tmp_path / "a.sqlite3")

        def fake_exit(status):
            seen.append((status, is_closed(tracked, a)))
            raise Exited(status)  # the real _exit never returns

        monkeypatch.setattr(tracked.module, "_exit", fake_exit)
        with pytest.raises(Exited):
            tracked.module.Database(tracked.logger, sqlalchemy_string="bogus://nowhere", log=False)

    assert seen == [(1, True)], "(status, A already closed when _exit ran)"


def test_a_fatal_exit_closes_every_active_scope_innermost_first(tracked, tmp_path, monkeypatch):
    """With nested scopes a fatal _exit(1) skips every finally, so it must drain the outer scope's Databases too."""
    seen = []

    class Exited(BaseException):
        pass

    with tracked.module.close_created_databases():
        a = tracked.new(tmp_path / "a.sqlite3")
        with tracked.module.close_created_databases():
            b = tracked.new(tmp_path / "b.sqlite3")

            def fake_exit(status):
                order = [db for db in tracked.closed if db is a or db is b]
                seen.append((status, is_closed(tracked, a), is_closed(tracked, b), order == [b, a]))
                raise Exited(status)  # the real _exit never returns

            monkeypatch.setattr(tracked.module, "_exit", fake_exit)
            with pytest.raises(Exited):
                tracked.module.Database(tracked.logger, sqlalchemy_string="bogus://nowhere", log=False)

    assert seen == [(1, True, True, True)], "(status, A closed, B closed, B closed before A)"


def test_a_fatal_init_exit_without_a_scope_only_exits(tracked, monkeypatch):
    def fake_exit(status):
        raise SystemExit(status)

    monkeypatch.setattr(tracked.module, "_exit", fake_exit)
    with pytest.raises(SystemExit) as exc:
        tracked.module.Database(tracked.logger, sqlalchemy_string="bogus://nowhere", log=False)
    assert exc.value.code == 1


FROZEN_HEAD = """
from dataclasses import dataclass

from Database import Database
from os import getenv
import logging

DB = Database(logging.getLogger("bw-job-under-test"), sqlalchemy_string=getenv("DATABASE_URI"), log=False)

@dataclass(frozen=True)
class {cls}({base}):
    {field}: {kind}

raise {cls}({arg})
"""

FROZEN_JOBS = {
    "frozen-error": (FROZEN_HEAD.format(cls="Boom", base="Exception", field="detail", kind="str", arg="'frozen boom detail'"), False, "frozen boom detail"),
    "frozen-exit-0": (FROZEN_HEAD.format(cls="Quit", base="SystemExit", field="code", kind="int", arg="0"), True, None),
    "frozen-exit-2": (
        FROZEN_HEAD.format(cls="Quit", base="SystemExit", field="code", kind="int", arg="2"),
        False,
        "Error while executing job 'work' from plugin 'plug'",
    ),
}


@pytest.mark.parametrize("mode", ["run_once", "run_single"])
@pytest.mark.parametrize("kind", list(FROZEN_JOBS))
def test_a_frozen_exception_leaves_the_job_scope_untouched(make_scheduler, tracked, caplog, mode, kind):
    """contextlib's generator __exit__ writes exc.__traceback__, which a frozen exception rejects and which replaced the job's own outcome."""
    import logging

    body, success, text = FROZEN_JOBS[kind]
    sched = make_scheduler([("plug", [job("work", "work.py")], {"work.py": body})])
    built_before = len(tracked.created)

    with caplog.at_level(logging.ERROR):
        assert (sched.run_once() if mode == "run_once" else sched.run_single("work")) is success

    jobs.wait_until(lambda: len(sched.fake_db.job_runs) >= 1)
    assert sched.fake_db.job_runs == [("work", success)]
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR and "'work'" in r.getMessage()]
    assert not any("FrozenInstanceError" in line or "__traceback__" in line for line in errors), errors
    if kind == "frozen-exit-2":
        # A plain nonzero exit, not an exception run: the wrapper's own ret >= 2 line, and no "Exception while executing job".
        assert not any("Exception while executing job" in line for line in errors), errors
    if text:
        assert len(errors) == 1 and text in errors[0], errors
    built = tracked.created[built_before:]
    assert len(built) == 1
    assert is_closed(tracked, built[0])

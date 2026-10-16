"""The scheduler tick reads the metadata under the backup `flock`, and never touches a lock it does not hold.

`db.lock` is a kernel `flock` since the backup lock moved to it (`common_utils.acquire_db_lock`).
The tick still ran the marker protocol: wait while the file is younger than 30 s, then `unlink()` it
on every pass. With a `flock` file that waits up to 30 s after each finished backup (the file always
exists), and the `unlink` removes the file under a live holder, so a second backup then locks a
fresh inode while the first is still running.

`main.py` cannot be imported here and its loop never ends, so the tick is cut out of the syntax
tree (the statements between the garbage-collection counter and the `isinstance(db_metadata, str)`
check) and executed against a fake client, a fake clock and a real lock file.
"""

import ast
import fcntl
import os
from pathlib import Path

import pytest

import common_utils  # type: ignore
from common_utils import DatabaseLockBusy, acquire_db_lock, release_db_lock  # type: ignore

MAIN = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"
START = 1000.0


def _tick_source() -> str:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        block = getattr(node, "body", None)
        if not isinstance(block, list):
            continue
        starts = [i for i, stmt in enumerate(block) if isinstance(stmt, ast.If) and "_gc_counter >= " in ast.unparse(stmt.test)]
        ends = [i for i, stmt in enumerate(block) if isinstance(stmt, ast.If) and "isinstance(db_metadata, str)" in ast.unparse(stmt.test)]
        if starts and ends:
            return ast.unparse(ast.Module(body=block[starts[0] + 1 : ends[0]], type_ignores=[]))
    raise AssertionError("the scheduler tick was not found in main.py")


class _Api:
    def __init__(self, lock_file, fail=False):
        self.lock_file = lock_file
        self.fail = fail
        self.calls = 0
        self.held_during_call = None

    def get_metadata(self):
        self.calls += 1
        self.held_during_call = _is_locked(self.lock_file)
        if self.fail:
            raise RuntimeError("API down")
        return {"ok": True}


class _Logger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(str(message))

    def debug(self, message):
        pass


def _is_locked(path) -> bool:
    """Whether another open file description holds the lock on `path`."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


@pytest.fixture
def lock(tmp_path):
    return tmp_path / "db.lock"


@pytest.fixture
def tick(lock, monkeypatch):
    """Run the tick once; returns (namespace, fake clock). `continue` is legal: the source runs in a one-pass loop."""
    clock = {"t": START}

    def _sleep(seconds):
        clock["t"] += seconds
        if clock["t"] - START > 300:
            raise AssertionError("the tick waited far past its 30s bound")

    monkeypatch.setattr(common_utils, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(common_utils, "sleep", _sleep)

    source = "for _pass in (0,):\n" + "\n".join("    " + line for line in _tick_source().splitlines())

    def run(api, logger=None):
        namespace = {
            "DB_LOCK_FILE": lock,
            "API_CLIENT": api,
            "LOGGER": logger or _Logger(),
            "acquire_db_lock": acquire_db_lock,
            "release_db_lock": release_db_lock,
            "DatabaseLockBusy": DatabaseLockBusy,
            # the marker protocol's names, so the unfixed tick runs under the same fake clock and fails on its behaviour
            "monotonic": lambda: clock["t"],
            "sleep": _sleep,
            "time": lambda: lock.stat().st_ctime if lock.exists() else 0.0,
            "collect": lambda: None,
            "run_pending": lambda: None,
            "SCHEDULER": type("S", (), {"run_pending": lambda self: None})(),
            "_gc_counter": 0,
            "errors": 0,
        }
        exec(compile(source, str(MAIN), "exec"), namespace)
        return namespace

    return run, clock


def test_a_lock_held_by_a_live_caller_skips_the_tick_and_stays_locked(tick, lock):
    run, clock = tick
    holder = acquire_db_lock(lock)
    api, logger = _Api(lock), _Logger()

    run(api, logger)

    assert api.calls == 0, "the tick read the metadata while a backup held the lock"
    assert logger.warnings and "skipping this scheduler tick" in logger.warnings[0]
    assert clock["t"] - START == pytest.approx(30, abs=1)
    assert lock.is_file(), "the tick removed a lock file a live caller holds"
    assert _is_locked(lock), "the tick took the lock away from its holder"
    release_db_lock(holder)


def test_a_lock_file_nobody_holds_costs_no_wait_and_stays(tick, lock):
    run, clock = tick
    lock.write_text("12345")  # what a finished backup leaves behind
    api = _Api(lock)

    run(api)

    assert clock["t"] == START, "the tick waited for a lock nobody holds"
    assert api.calls == 1
    assert lock.is_file(), "the tick removed the lock file"


def test_the_metadata_is_read_while_the_lock_is_held_and_released_after(tick, lock):
    run, _clock = tick
    api = _Api(lock)

    namespace = run(api)

    assert api.held_during_call is True
    assert namespace["db_metadata"] == {"ok": True}
    assert not _is_locked(lock), "the tick kept the lock after reading"


def test_a_failing_read_still_releases_the_lock(tick, lock):
    run, _clock = tick
    api = _Api(lock, fail=True)

    with pytest.raises(RuntimeError, match="API down"):
        run(api)

    assert not _is_locked(lock)

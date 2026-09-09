"""`acquire_db_lock` — the 30s the log line promises has to be a real bound.

The wait used to compare two frozen values: `st_ctime`, which nothing rewrites, against a
`datetime.now()` snapshot taken before the loop. Neither operand could move, so a lock younger
than 30s parked the caller until a third party deleted the file. Jobs run in the scheduler's
own thread pool and the scheduler main loop is the only reaper, so the backup job waiting on an
orphan blocked the loop that would have freed it: no `scheduler.healthy`, no config push, no
renewal, until an operator removed /var/lib/bunkerweb/db.lock by hand.

The clock is faked here rather than slept through, so the three cases cost nothing. The fake
`sleep` raises once the loop has run far past its bound, which is what turns the unfixed code
into a failure instead of a hung suite.
"""

import sys
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402

START = 1000.0


@pytest.fixture
def clock(monkeypatch):
    """A monotonic clock that only `sleep` advances, and that refuses to run away."""
    now = {"t": START}

    def _sleep(seconds):
        now["t"] += seconds
        if now["t"] - START > 300:
            raise AssertionError("acquire_db_lock() never returned")

    # raising=False so the unfixed module, which imports neither name, still runs the
    # loop under the fake clock and fails on its bound rather than on a missing attribute.
    monkeypatch.setattr(backup, "monotonic", lambda: now["t"], raising=False)
    monkeypatch.setattr(backup, "sleep", _sleep)
    return now


@pytest.fixture
def lock(tmp_path, monkeypatch):
    path = tmp_path / "db.lock"
    monkeypatch.setattr(backup, "DB_LOCK_FILE", path)
    return path


def _age(monkeypatch, lock, seconds):
    """Make the wall clock read `seconds` after the lock file was created."""
    monkeypatch.setattr(backup, "time", lambda: lock.stat().st_ctime + seconds, raising=False)


def test_a_lock_taken_a_moment_ago_is_taken_over_after_30s(clock, lock, monkeypatch):
    lock.touch()
    _age(monkeypatch, lock, 0)

    backup.acquire_db_lock()

    assert clock["t"] - START == pytest.approx(30, abs=1)
    assert lock.is_file()


def test_a_lock_already_older_than_30s_costs_no_wait(clock, lock, monkeypatch):
    lock.touch()
    _age(monkeypatch, lock, 120)

    backup.acquire_db_lock()

    assert clock["t"] == START
    assert lock.is_file()


def test_no_lock_at_all_costs_no_wait(clock, lock, monkeypatch):
    monkeypatch.setattr(backup, "time", lambda: 0.0, raising=False)

    backup.acquire_db_lock()

    assert clock["t"] == START
    assert lock.is_file()

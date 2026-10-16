"""`acquire_db_lock` -- the 30s the log line promises has to be a real bound, and a real lock.

The lock used to be a marker file: a caller waited while the file was younger than 30s and then
took it over whatever its holder was doing, so a second backup, restore or scheduler tick could
run next to a live one, and two callers could both pass the check before either touched the file.
Before that the wait compared two frozen values (`st_ctime` against a `now()` snapshot taken
before the loop), so a lock younger than 30s parked the caller until a third party deleted the
file, and the backup job waiting on an orphan blocked the scheduler loop that would have freed it.

The lock is a kernel `flock` now: the kernel drops it when its holder dies, a live holder is never
displaced, and a caller that cannot get it within 30s is told so (`DatabaseLockBusy`) instead of
taking it. The clock is faked here rather than slept through, so the cases cost nothing. The fake
`sleep` raises once the loop has run far past its bound, which is what turns an unbounded wait into
a failure instead of a hung suite.
"""

import os
import sys
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402
import common_utils  # noqa: E402

from common_utils import DatabaseLockBusy  # noqa: E402

START = 1000.0


@pytest.fixture
def clock(monkeypatch):
    """A monotonic clock that only `sleep` advances, and that refuses to run away."""
    now = {"t": START}

    def _sleep(seconds):
        now["t"] += seconds
        if now["t"] - START > 300:
            raise AssertionError("acquire_db_lock() never returned")

    # raising=False so an implementation that keeps either name in another module still runs
    # the loop under the fake clock and fails on its bound rather than on a missing attribute.
    for module in (backup, common_utils):
        monkeypatch.setattr(module, "monotonic", lambda: now["t"], raising=False)
        monkeypatch.setattr(module, "sleep", _sleep, raising=False)
    return now


@pytest.fixture
def lock(tmp_path, monkeypatch):
    path = tmp_path / "db.lock"
    monkeypatch.setattr(backup, "DB_LOCK_FILE", path)
    return path


def test_a_lock_held_by_a_live_caller_is_refused_after_30s(clock, lock):
    holder = backup.acquire_db_lock()

    with pytest.raises(DatabaseLockBusy, match=str(os.getpid())):
        backup.acquire_db_lock()

    assert clock["t"] - START == pytest.approx(30, abs=1)
    backup.release_db_lock(holder)


def test_a_wall_clock_jump_does_not_displace_a_live_holder(clock, lock, monkeypatch):
    holder = backup.acquire_db_lock()
    monkeypatch.setattr(backup, "time", lambda: lock.stat().st_ctime + 3600, raising=False)

    with pytest.raises(DatabaseLockBusy):
        backup.acquire_db_lock()

    backup.release_db_lock(holder)


def test_a_lock_file_nobody_holds_costs_no_wait(clock, lock):
    lock.write_text("999999")  # the pid a dead holder left behind

    handle = backup.acquire_db_lock()

    assert clock["t"] == START
    backup.release_db_lock(handle)


def test_no_lock_file_at_all_costs_no_wait(clock, lock):
    handle = backup.acquire_db_lock()

    assert clock["t"] == START
    assert lock.is_file()
    backup.release_db_lock(handle)


def test_a_released_lock_is_free_again_and_its_file_stays(clock, lock):
    backup.release_db_lock(backup.acquire_db_lock())

    assert lock.is_file(), "releasing the lock removed its file: a caller could then lock a new inode next to a live holder"
    handle = backup.acquire_db_lock()

    assert clock["t"] == START
    assert lock.is_file()
    backup.release_db_lock(handle)


def test_a_lock_file_the_caller_cannot_write_can_still_be_locked(clock, lock):
    if os.geteuid() == 0:
        pytest.skip("root can write to any file")
    lock.write_text("1")
    lock.chmod(0o444)  # created by root, then used by the scheduler's user

    handle = backup.acquire_db_lock()

    assert clock["t"] == START
    backup.release_db_lock(handle)

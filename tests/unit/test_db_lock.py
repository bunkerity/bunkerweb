#!/usr/bin/env python3
"""Regression tests for the backup plugin's database lock (F6).

Exercises `src/common/core/backup/backup.py`'s `acquire_db_lock` /
`release_db_lock` / `DatabaseLockBusy` with REAL, independent OS processes
(multiprocessing "spawn", never "fork") so the lock is proven across process
boundaries, not just across threads of one interpreter.

Before the fix, `acquire_db_lock()` was an age-based marker: after 30s it
unlinked the "holder"'s file and touched its own, so a second process would
silently enter the protected section while the first was still alive and
using the database. These tests prove real mutual exclusion (fcntl.flock)
replaced that marker protocol.
"""

import multiprocessing as mp
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from time import monotonic, sleep

REPO_ROOT = Path(__file__).resolve().parents[2]
for rel in ("src/common/utils", "src/common/db", "src/common/core/backup"):
    path = str(REPO_ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

import backup  # type: ignore  # noqa: E402

# --- worker entry points (top-level so they are picklable for "spawn") ---


def _holder_take_and_hold(lock_path: str, ready_event, release_event, hold_seconds: float, result_queue) -> None:
    backup.DB_LOCK_FILE = Path(lock_path)
    handle = backup.acquire_db_lock(timeout=5)
    result_queue.put(("holder", "acquired", None))
    ready_event.set()
    release_event.wait(hold_seconds)
    backup.release_db_lock(handle)
    result_queue.put(("holder", "released", None))


def _holder_take_and_wait_forever(lock_path: str, ready_event, result_queue) -> None:
    backup.DB_LOCK_FILE = Path(lock_path)
    backup.acquire_db_lock(timeout=5)
    result_queue.put(("holder", "acquired", None))
    ready_event.set()
    while True:  # killed by the test with SIGKILL; never releases on purpose
        sleep(1)


def _waiter_try_acquire(lock_path: str, start_event, timeout: float, result_queue) -> None:
    backup.DB_LOCK_FILE = Path(lock_path)
    start_event.wait(10)
    start = monotonic()
    try:
        handle = backup.acquire_db_lock(timeout=timeout)
        elapsed = monotonic() - start
        result_queue.put(("waiter", "acquired", elapsed))
        backup.release_db_lock(handle)
    except backup.DatabaseLockBusy as e:
        elapsed = monotonic() - start
        result_queue.put(("waiter", "busy", elapsed, str(e)))


def _lifecycle_participant(lock_path: str, acquired_event, released_once_event, stale_release_done_event, may_release_event, result_queue) -> None:
    """A: acquire, release, wait for B to take it, then release the (already
    closed) handle a second time -- a stale/double release."""
    backup.DB_LOCK_FILE = Path(lock_path)
    handle = backup.acquire_db_lock(timeout=5)
    result_queue.put(("A", "acquired", None))
    acquired_event.set()
    backup.release_db_lock(handle)
    result_queue.put(("A", "released", None))
    released_once_event.set()
    may_release_event.wait(10)
    backup.release_db_lock(handle)  # stale double-release, must be a no-op
    result_queue.put(("A", "stale_release_done", None))
    stale_release_done_event.set()


def _hold_until_signalled(lock_path: str, wait_event, acquired_event, may_exit_event, result_queue) -> None:
    """B: wait until A released, then acquire and hold until told to exit."""
    backup.DB_LOCK_FILE = Path(lock_path)
    wait_event.wait(10)
    handle = backup.acquire_db_lock(timeout=5)
    result_queue.put(("B", "acquired", None))
    acquired_event.set()
    may_exit_event.wait(10)
    backup.release_db_lock(handle)
    result_queue.put(("B", "released", None))


def _probe_busy(lock_path: str, wait_event, timeout: float, result_queue) -> None:
    """C: probe while B holds; must fail LOCK_NB."""
    backup.DB_LOCK_FILE = Path(lock_path)
    wait_event.wait(10)
    try:
        handle = backup.acquire_db_lock(timeout=timeout)
        result_queue.put(("C", "acquired", None))
        backup.release_db_lock(handle)
    except backup.DatabaseLockBusy:
        result_queue.put(("C", "busy", None))


class TestDbLock(unittest.TestCase):
    def setUp(self):
        self._orig_db_lock_file = backup.DB_LOCK_FILE
        self.tmp_dir = tempfile.mkdtemp(prefix="bw-db-lock-test-")
        self.lock_path = Path(self.tmp_dir) / "db.lock"
        self.ctx = mp.get_context("spawn")

    def tearDown(self):
        backup.DB_LOCK_FILE = self._orig_db_lock_file
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _drain(self, q, n):
        items = []
        for _ in range(n):
            items.append(q.get(timeout=60))
        return items

    def test_busy_holder_blocks_for_the_full_timeout_without_being_stolen(self):
        ready = self.ctx.Event()
        release = self.ctx.Event()
        q = self.ctx.Queue()

        holder = self.ctx.Process(target=_holder_take_and_hold, args=(str(self.lock_path), ready, release, 40, q))
        holder.start()
        self.assertTrue(ready.wait(10), "holder did not acquire the lock in time")
        self.assertEqual(q.get(timeout=10)[:2], ("holder", "acquired"))

        waiter = self.ctx.Process(target=_waiter_try_acquire, args=(str(self.lock_path), ready, 32, q))
        waiter_start = monotonic()
        waiter.start()
        waiter.join(45)
        self.assertFalse(waiter.is_alive(), "waiter process did not finish")

        role, status, elapsed, *rest = q.get(timeout=10)
        waiter_wall_time = monotonic() - waiter_start

        self.assertTrue(holder.is_alive(), "holder must still be alive: the timeout must never steal a live holder's lock")
        self.assertEqual((role, status), ("waiter", "busy"), "the waiter must raise DatabaseLockBusy, never silently enter")
        self.assertGreaterEqual(elapsed, 32, "the waiter must wait the full timeout, not steal early")
        self.assertGreaterEqual(waiter_wall_time, 32)
        self.assertTrue(self.lock_path.is_file(), "the lock file must never be unlinked")

        release.set()
        holder.join(10)
        self.assertEqual(q.get(timeout=10)[:2], ("holder", "released"))

    def test_dead_holder_is_recovered_quickly(self):
        ready = self.ctx.Event()
        q = self.ctx.Queue()

        holder = self.ctx.Process(target=_holder_take_and_wait_forever, args=(str(self.lock_path), ready, q))
        holder.start()
        self.assertTrue(ready.wait(10), "holder did not acquire the lock in time")
        self.assertEqual(q.get(timeout=10)[:2], ("holder", "acquired"))

        holder.kill()  # SIGKILL: the kernel must drop the flock on process exit
        holder.join(10)
        self.assertFalse(holder.is_alive())

        backup.DB_LOCK_FILE = self.lock_path
        start = monotonic()
        handle = backup.acquire_db_lock(timeout=10)
        elapsed = monotonic() - start
        backup.release_db_lock(handle)

        self.assertLess(elapsed, 2.0, "a dead holder's lock must be recovered within ~2s, not the full timeout")
        self.assertTrue(self.lock_path.is_file(), "the lock file must never be unlinked")

    def test_waiter_acquires_once_holder_releases_before_deadline(self):
        ready = self.ctx.Event()
        release = self.ctx.Event()
        q = self.ctx.Queue()

        holder = self.ctx.Process(target=_holder_take_and_hold, args=(str(self.lock_path), ready, release, 3, q))
        holder.start()
        self.assertTrue(ready.wait(10))
        self.assertEqual(q.get(timeout=10)[:2], ("holder", "acquired"))

        waiter = self.ctx.Process(target=_waiter_try_acquire, args=(str(self.lock_path), ready, 30, q))
        waiter.start()

        release.set()  # holder releases almost immediately (well before the 30s deadline)
        holder.join(10)
        self.assertEqual(q.get(timeout=10)[:2], ("holder", "released"))

        waiter.join(35)
        self.assertFalse(waiter.is_alive())
        role, status, elapsed, *_ = q.get(timeout=10)
        self.assertEqual((role, status), ("waiter", "acquired"))
        self.assertLess(elapsed, 30)

    def test_stale_or_double_release_never_breaks_a_new_owners_exclusivity(self):
        acquired_a = self.ctx.Event()
        released_once = self.ctx.Event()
        stale_release_done = self.ctx.Event()
        may_release_a = self.ctx.Event()
        acquired_b = self.ctx.Event()
        may_exit_b = self.ctx.Event()
        q = self.ctx.Queue()

        proc_a = self.ctx.Process(
            target=_lifecycle_participant,
            args=(str(self.lock_path), acquired_a, released_once, stale_release_done, may_release_a, q),
        )
        proc_b = self.ctx.Process(target=_hold_until_signalled, args=(str(self.lock_path), released_once, acquired_b, may_exit_b, q))
        proc_c = self.ctx.Process(target=_probe_busy, args=(str(self.lock_path), acquired_b, 2, q))

        proc_a.start()
        self.assertTrue(acquired_a.wait(10))
        self.assertEqual(q.get(timeout=10)[:2], ("A", "acquired"))
        self.assertEqual(q.get(timeout=10)[:2], ("A", "released"))

        proc_b.start()
        self.assertTrue(acquired_b.wait(10))
        self.assertEqual(q.get(timeout=10)[:2], ("B", "acquired"))

        # A performs the stale double-release now that B owns a fresh handle on the same path.
        may_release_a.set()
        self.assertTrue(stale_release_done.wait(10))
        self.assertEqual(q.get(timeout=10)[:2], ("A", "stale_release_done"))
        proc_a.join(10)

        proc_c.start()
        proc_c.join(10)
        self.assertEqual(q.get(timeout=10)[:2], ("C", "busy"), "B's exclusivity must survive A's stale release")

        may_exit_b.set()
        proc_b.join(10)
        self.assertEqual(q.get(timeout=10)[:2], ("B", "released"))

        self.assertTrue(self.lock_path.is_file(), "the lock file must never be unlinked")

    def test_parent_directory_is_created_on_demand(self):
        nested = Path(self.tmp_dir) / "nested" / "does" / "not" / "exist" / "db.lock"
        backup.DB_LOCK_FILE = nested
        self.assertFalse(nested.parent.exists())
        handle = backup.acquire_db_lock(timeout=5)
        try:
            self.assertTrue(nested.is_file())
        finally:
            backup.release_db_lock(handle)


if __name__ == "__main__":
    unittest.main()

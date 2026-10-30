"""install_guard keeps the generator's install out of reloads of the nginx that reads the output, and fails closed.

Run: python3 tests/unit/test_gen_install_guard.py   (GEN_DIR points at another copy of src/common/gen)
"""

import logging
import subprocess
import sys
import textwrap
import unittest
from unittest import mock
from fcntl import LOCK_EX, LOCK_NB, LOCK_SH, flock
from inspect import signature
from importlib.util import module_from_spec, spec_from_file_location
from os import O_CREAT, O_RDONLY, close, environ, getpid, open as os_open, utime
from pathlib import Path
from signal import SIGKILL
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep, time

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = Path(environ.get("GEN_DIR", REPO_ROOT / "src/common/gen"))

spec = spec_from_file_location("sync_tree_under_test", GEN_DIR / "sync_tree.py")
module = module_from_spec(spec)
spec.loader.exec_module(module)

LOGGER = logging.getLogger("guard-test")


class NeverRaised(Exception):
    """Stands in for InstallBlocked on a copy that predates it, so the tests fail on their assertions."""


InstallBlocked = getattr(module, "InstallBlocked", NeverRaised)


def lock_is_free(path: Path) -> bool:
    """Probe the way the reload handler does: a shared, non-blocking lock on a fresh open."""
    fd = os_open(path, O_RDONLY)
    try:
        flock(fd, LOCK_SH | LOCK_NB)
        return True
    except BlockingIOError:
        return False
    finally:
        close(fd)


HOLDER = textwrap.dedent("""
    import sys, time
    from fcntl import LOCK_EX, flock
    fd = open(sys.argv[1], "a+")
    flock(fd, LOCK_EX)
    print("locked", flush=True)
    time.sleep(60)
    """)

WORKER = textwrap.dedent("""
    import inspect, logging, os, sys, time
    from pathlib import Path
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("sync_tree_worker", sys.argv[1])
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    tmp = sys.argv[2]
    log = logging.getLogger("worker")
    violations = 0
    if hasattr(module, "_lock_holder"):
        # A design that checks a lock for staleness and then removes it: widen the gap between the two the way a descheduled process would
        real_holder = module._lock_holder

        def slow_holder(path):
            holder = real_holder(path)
            time.sleep(0.05 + 0.005 * int(sys.argv[5]))
            return holder

        module._lock_holder = slow_holder
    while time.time() < float(sys.argv[4]):
        pass
    extra = {"nginx_pid": Path(tmp, "nginx.pid")} if "nginx_pid" in inspect.signature(module.install_guard).parameters else {}
    for _ in range(int(sys.argv[3])):
        with module.install_guard(log, reloading=Path(tmp, "reloading"), generating=Path(tmp, "generating"), wait=30, poll=0.005, **extra):
            try:
                os.mkdir(tmp + "/inside")
            except FileExistsError:
                violations += 1
            else:
                time.sleep(0.02)
                os.rmdir(tmp + "/inside")
    print(violations)
    """)


class InstallGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.reloading = Path(self._tmp.name, "reloading")
        self.generating = Path(self._tmp.name, "generating")
        self.nginx_pid = Path(self._tmp.name, "nginx.pid")
        self.uptime = b"1000.25 100.00\n"
        read_bytes = Path.read_bytes

        def read_uptime(path, *args, **kwargs):
            if path == Path("/proc/uptime"):
                if self.uptime is None:
                    raise PermissionError("uptime unavailable")
                return self.uptime
            return read_bytes(path, *args, **kwargs)

        patch = mock.patch.object(Path, "read_bytes", read_uptime)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(module, "time", return_value=1000, create=True)
        self.wall_time = patch.start()
        self.addCleanup(patch.stop)

    def guard(self, wait=5.0):
        extra = {"nginx_pid": self.nginx_pid} if "nginx_pid" in signature(module.install_guard).parameters else {}
        return module.install_guard(LOGGER, reloading=self.reloading, generating=self.generating, wait=wait, poll=0.02, **extra)

    def master_running(self):
        self.nginx_pid.write_text(f"{getpid()}\n")

    def later(self, delay, action):
        def run():
            sleep(delay)
            action()

        thread = Thread(target=run)
        thread.start()
        self.addCleanup(thread.join)

    def holder(self):
        peer = subprocess.Popen([sys.executable, "-c", HOLDER, self.generating.as_posix()], stdout=subprocess.PIPE, text=True)
        self.addCleanup(peer.stdout.close)
        self.addCleanup(peer.wait)
        self.addCleanup(peer.kill)
        self.assertEqual(peer.stdout.readline().strip(), "locked")
        return peer

    def test_default_paths_use_the_writable_runtime_directory(self):
        parameters = signature(module.install_guard).parameters
        self.assertEqual(parameters["reloading"].default, Path("/var/tmp/bunkerweb/reloading"))
        self.assertEqual(parameters["generating"].default, Path("/var/tmp/bunkerweb/generating"))

    def test_the_lock_is_held_during_the_install_and_released_after(self):
        with self.guard():
            self.assertFalse(lock_is_free(self.generating))
        self.assertTrue(lock_is_free(self.generating))
        # The file stays: its inode is what the lock is attached to
        self.assertTrue(self.generating.is_file())

    def test_the_lock_is_released_when_the_install_fails(self):
        with self.assertRaises(RuntimeError):
            with self.guard():
                raise RuntimeError("install failed")
        self.assertTrue(lock_is_free(self.generating))

    def test_waits_for_a_reload_in_flight_and_gives_the_lock_back_meanwhile(self):
        self.reloading.write_text("1")
        self.master_running()
        self.later(0.5, self.reloading.unlink)
        free_while_waiting = []
        self.later(0.25, lambda: free_while_waiting.append(lock_is_free(self.generating)))
        start = monotonic()
        with self.guard():
            self.assertGreaterEqual(monotonic() - start, 0.45)
            self.assertFalse(lock_is_free(self.generating))
        self.assertEqual(free_while_waiting, [True])

    def test_a_marker_still_there_at_the_deadline_blocks_the_install_and_is_kept(self):
        self.reloading.write_text("1")
        self.master_running()
        entered = False
        start = monotonic()
        with self.assertRaises(InstallBlocked) as caught:
            with self.guard(wait=0.5):
                entered = True
        self.assertGreaterEqual(monotonic() - start, 0.45)
        self.assertFalse(entered)
        self.assertTrue(self.reloading.exists(), "the marker of a reload that may be in flight was removed")
        self.assertIn(str(self.reloading), str(caught.exception))
        self.assertIn("current configuration is kept", str(caught.exception))
        self.assertTrue(lock_is_free(self.generating), "the lock outlived the blocked install")

    def test_a_stale_token_with_a_live_master_is_removed(self):
        self.master_running()
        self.reloading.write_text("1000.1.699")
        with self.assertLogs(LOGGER, level="WARNING") as logs:
            with self.guard(wait=0.1):
                self.assertFalse(self.reloading.exists())
        self.assertEqual(len(logs.output), 1)
        self.assertIn("orphaned reload marker", logs.output[0])

    def test_fresh_future_and_boundary_tokens_keep_blocking_even_with_an_old_mtime(self):
        self.master_running()
        for offset in (-10, 60, -300):
            with self.subTest(offset=offset):
                self.reloading.write_text(f"{1000 + offset}.1.{1000 + offset}")
                old = time() - 3600
                utime(self.reloading, (old, old))
                with mock.patch.object(module, "time", return_value=1000, create=True):
                    with self.assertRaises(InstallBlocked):
                        with self.guard(wait=0.05):
                            self.fail("install entered with a current marker")
                self.assertTrue(self.reloading.exists())

    def test_a_forward_wall_clock_step_does_not_expire_a_one_second_old_marker(self):
        self.master_running()
        self.wall_time.return_value = 1600
        self.reloading.write_text("1000.1.999")
        with self.assertRaises(InstallBlocked):
            with self.guard(wait=0.05):
                self.fail("install entered after a wall clock step")
        self.assertEqual(self.reloading.read_text(), "1000.1.999")

    def test_legacy_empty_and_malformed_tokens_keep_blocking_even_with_an_old_mtime(self):
        self.master_running()
        for content in ("699.1", "", "garbled", "1.1.bad", "1.1.1.1", "1.1.1\n"):
            with self.subTest(content=content):
                self.reloading.write_text(content)
                old = 1
                utime(self.reloading, (old, old))
                with self.assertRaises(InstallBlocked):
                    with self.guard(wait=0.05):
                        self.fail("install entered without a valid monotonic stamp")
                self.assertEqual(self.reloading.read_text(), content)

    def test_an_unavailable_or_malformed_uptime_keeps_the_marker(self):
        self.master_running()
        for uptime in (None, b"", b"invalid\n"):
            with self.subTest(uptime=uptime):
                self.uptime = uptime
                self.reloading.write_text("1.1.1")
                with self.assertRaises(InstallBlocked):
                    with self.guard(wait=0.05):
                        self.fail("install entered without a readable uptime")
                self.assertEqual(self.reloading.read_text(), "1.1.1")

    def test_a_token_replaced_during_the_stale_check_is_kept(self):
        self.master_running()
        stale = "1000.1.699"
        fresh = "1000.2.1000"
        self.reloading.write_text(stale)
        read_bytes = Path.read_bytes
        reads = 0

        def replace_after_read(path, *args, **kwargs):
            nonlocal reads
            content = read_bytes(path, *args, **kwargs)
            if path == self.reloading:
                reads += 1
                if reads == 1:
                    path.write_text(fresh)
            return content

        with mock.patch.object(Path, "read_bytes", replace_after_read):
            with self.assertRaises(InstallBlocked):
                with self.guard(wait=0.05):
                    self.fail("install entered after a fresh token replaced the stale one")
        self.assertEqual(self.reloading.read_text(), fresh)

    def test_a_marker_with_no_pid_file_is_removed_and_the_install_goes_ahead(self):
        self.reloading.write_text("1")
        start = monotonic()
        with self.guard():
            self.assertLess(monotonic() - start, 1.0)
            self.assertFalse(self.reloading.exists())

    def test_a_marker_with_a_dead_master_is_removed_and_the_install_goes_ahead(self):
        peer = subprocess.Popen([sys.executable, "-c", "pass"])
        peer.wait()
        self.nginx_pid.write_text(f"{peer.pid}\n")
        self.reloading.write_text("1")
        with self.guard():
            self.assertFalse(self.reloading.exists())

    def test_a_marker_with_an_unreadable_pid_file_is_not_removed(self):
        self.nginx_pid.write_text("")
        self.reloading.write_text("1")
        with self.assertRaises(InstallBlocked):
            with self.guard(wait=0.3):
                pass
        self.assertTrue(self.reloading.exists())

    def test_a_live_holder_blocks_the_install_past_the_wait(self):
        self.holder()
        entered = False
        start = monotonic()
        with self.assertRaises(InstallBlocked) as caught:
            with self.guard(wait=0.5):
                entered = True
        self.assertGreaterEqual(monotonic() - start, 0.45)
        self.assertFalse(entered)
        self.assertIn(str(self.generating), str(caught.exception))

    def test_a_holder_that_finishes_in_time_is_waited_for(self):
        peer = self.holder()
        self.later(0.4, peer.kill)
        start = monotonic()
        with self.guard():
            self.assertGreaterEqual(monotonic() - start, 0.35)

    def test_a_killed_holder_frees_the_lock_with_nothing_to_reclaim(self):
        peer = self.holder()
        with self.assertRaises(InstallBlocked):
            with self.guard(wait=0.2):
                pass
        peer.send_signal(SIGKILL)
        peer.wait()
        start = monotonic()
        with self.guard():
            self.assertLess(monotonic() - start, 0.5)
            self.assertFalse(lock_is_free(self.generating))

    def test_a_lock_file_left_with_garbage_or_an_old_date_blocks_nothing(self):
        # The content is irrelevant now: only the kernel lock counts
        self.generating.write_text("12345 1")
        start = monotonic()
        with self.guard():
            self.assertLess(monotonic() - start, 0.5)

    def test_two_real_processes_never_hold_the_lock_at_once(self):
        # Every round starts from a lock file a dead generator left behind, and releases eight workers at the same instant
        violations = 0
        for _ in range(10):
            self.generating.write_text("99999999 1")
            start_at = time() + 0.4
            workers = [
                subprocess.Popen(
                    [sys.executable, "-c", WORKER, (GEN_DIR / "sync_tree.py").as_posix(), self._tmp.name, "3", str(start_at), str(index)],
                    stdout=subprocess.PIPE,
                    text=True,
                )
                for index in range(8)
            ]
            for worker in workers:
                out, _ = worker.communicate(timeout=120)
                self.assertEqual(worker.returncode, 0)
                violations += int(out.strip())
        self.assertEqual(violations, 0, "two processes were inside the install at the same time")

    def test_an_unusable_lock_location_blocks_the_install(self):
        self.generating = Path(self._tmp.name, "missing", "generating")
        entered = False
        with self.assertRaises(InstallBlocked) as caught:
            with self.guard():
                entered = True
        self.assertFalse(entered)
        self.assertIn("current configuration is kept", str(caught.exception))

    def test_the_lock_is_the_only_thing_that_makes_the_probe_fail(self):
        # Sanity for the probe used above: free when nobody holds it, busy while an exclusive lock exists
        self.generating.write_text("")
        self.assertTrue(lock_is_free(self.generating))
        fd = os_open(self.generating, O_RDONLY | O_CREAT)
        self.addCleanup(close, fd)
        flock(fd, LOCK_EX | LOCK_NB)
        self.assertFalse(lock_is_free(self.generating))


if __name__ == "__main__":
    unittest.main()

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(environ.get("SYNC_TREE_MODULE", REPO_ROOT / "src/common/gen/sync_tree.py"))

spec = spec_from_file_location("sync_tree_under_test", MODULE)
module = module_from_spec(spec)
spec.loader.exec_module(module)
sync_tree = module.sync_tree
SENTINEL = ".bw-install-incomplete"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class SyncTreeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name, "nginx")
        self.stage = self.out / ".bw-gen.1"
        write(self.out / "variables.env", "A=1\n")
        write(self.out / "nginx.conf", "old\n")
        write(self.out / "http" / "keep.conf", "keep\n")
        write(self.out / "http" / "stale.conf", "stale\n")
        write(self.out / "gone" / "x.conf", "x\n")
        write(self.out / ".bw-staging.9" / "tree", "push in flight\n")

        write(self.stage / "variables.env", "A=1\n")
        write(self.stage / "nginx.conf", "new\n")
        write(self.stage / "http" / "keep.conf", "keep\n")
        write(self.stage / "http" / "added.conf", "added\n")

    def test_destination_matches_render(self):
        sync_tree(self.stage, self.out)
        self.assertEqual((self.out / "nginx.conf").read_text(), "new\n")
        self.assertEqual((self.out / "http" / "added.conf").read_text(), "added\n")
        self.assertFalse((self.out / "http" / "stale.conf").exists())
        self.assertFalse((self.out / "gone").exists())

    def test_reserved_entries_survive(self):
        sync_tree(self.stage, self.out)
        self.assertTrue((self.out / ".bw-staging.9" / "tree").is_file())

    def test_unchanged_file_is_not_touched(self):
        before = (self.out / "variables.env").stat().st_ino
        sync_tree(self.stage, self.out)
        self.assertEqual((self.out / "variables.env").stat().st_ino, before)

    def test_mode_change_is_installed(self):
        (self.out / "nginx.conf").write_text("same\n")
        (self.stage / "nginx.conf").write_text("same\n")
        (self.out / "nginx.conf").chmod(0o750)
        (self.stage / "nginx.conf").chmod(0o644)
        sync_tree(self.stage, self.out)
        self.assertEqual((self.out / "nginx.conf").stat().st_mode & 0o777, 0o644)

    def test_before_change_runs_once_and_only_on_change(self):
        calls = []
        self.assertTrue(sync_tree(self.stage, self.out, lambda: calls.append(1)))
        self.assertEqual(calls, [1])
        write(self.stage / "variables.env", "A=1\n")
        write(self.stage / "nginx.conf", "new\n")
        write(self.stage / "http" / "keep.conf", "keep\n")
        write(self.stage / "http" / "added.conf", "added\n")
        self.assertFalse(sync_tree(self.stage, self.out, lambda: calls.append(2)))
        self.assertEqual(calls, [1])

    def test_type_change(self):
        (self.out / "http").rename(self.out / "swap")
        write(self.out / "http", "now a file\n")
        sync_tree(self.stage, self.out)
        self.assertTrue((self.out / "http" / "keep.conf").is_file())

    def test_complete_install_leaves_no_sentinel(self):
        sync_tree(self.stage, self.out)
        self.assertFalse((self.out / SENTINEL).exists())

    def test_install_that_changes_nothing_creates_no_sentinel(self):
        sync_tree(self.stage, self.out)
        write(self.stage / "variables.env", "A=1\n")
        write(self.stage / "nginx.conf", "new\n")
        write(self.stage / "http" / "keep.conf", "keep\n")
        write(self.stage / "http" / "added.conf", "added\n")
        seen = []
        self.assertFalse(sync_tree(self.stage, self.out, lambda: seen.append(1)))
        self.assertEqual(seen, [])
        self.assertFalse((self.out / SENTINEL).exists())

    def interrupt_after(self, swaps):
        calls = []
        real = module.replace

        def flaky(source, target):
            if len(calls) >= swaps:
                raise KeyboardInterrupt("cut short")
            calls.append(target)
            real(source, target)

        return patch.object(module, "replace", flaky)

    def test_interrupted_install_leaves_the_sentinel(self):
        with self.interrupt_after(1), self.assertRaises(KeyboardInterrupt):
            sync_tree(self.stage, self.out)
        self.assertTrue((self.out / SENTINEL).is_file())

    def test_sentinel_is_in_place_before_the_first_change(self):
        states = []
        sync_tree(self.stage, self.out, lambda: states.append((self.out / SENTINEL).exists()))
        self.assertEqual(states, [True])

    def test_sentinel_is_in_place_when_the_first_swap_is_cut_short(self):
        with self.interrupt_after(0), self.assertRaises(KeyboardInterrupt):
            sync_tree(self.stage, self.out)
        self.assertTrue((self.out / SENTINEL).is_file())

    def test_complete_install_clears_a_stale_sentinel(self):
        (self.out / SENTINEL).touch()
        sync_tree(self.stage, self.out)
        self.assertFalse((self.out / SENTINEL).exists())

    def test_variables_env_never_missing_while_syncing(self):
        missing = Event()
        stop = Event()

        def watch():
            while not stop.is_set():
                if not (self.out / "variables.env").is_file():
                    missing.set()

        watcher = Thread(target=watch)
        watcher.start()
        try:
            sync_tree(self.stage, self.out)
        finally:
            stop.set()
            watcher.join()
        self.assertFalse(missing.is_set(), "variables.env was missing while the render was installed")


if __name__ == "__main__":
    unittest.main()

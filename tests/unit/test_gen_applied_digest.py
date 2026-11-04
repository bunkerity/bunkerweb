"""Exercise production generator invalidation, including its lock and pre-change ordering."""

from fcntl import LOCK_EX, LOCK_NB, flock
from pathlib import Path
from re import sub
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

from test_gen_render_failure import GeneratorMainTest


def install_generated(root: Path) -> None:
    case = GeneratorMainTest("test_a_complete_render_is_installed")
    case.setUp()
    try:
        case.tmp, case.out = root, root / "nginx"
        case.marker, case.nginx_pid = root / "reloading", root / "nginx.pid"
        for name in ("settings.json", "vars.env"):
            (root / name).write_text("{}")
        for name in ("confs", "core", "plugins", "pro"):
            (root / name).mkdir(exist_ok=True)
        marker = root / "state/applied"
        key = sub(r"[^A-Za-z0-9]+", "_", case.out.as_posix()) + ".applied"
        real_unlink = Path.unlink
        seen = []

        def unlink(path, *args, **kwargs):
            if path == Path("/var/tmp/bunkerweb/pushswap", key):
                with (root / "generating").open() as lock:
                    case.assertRaises(BlockingIOError, flock, lock, LOCK_EX | LOCK_NB)
                case.assertEqual((case.out / "variables.env").read_text(), "push")
                seen.append(path)
                return real_unlink(marker, *args, **kwargs)
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", unlink):
            case.assertEqual(case.run_main([]), 0)
        case.assertEqual(len(seen), 1)
        case.assertFalse(marker.exists())
        print("PASS production generator invalidates external digest under flock before changing tree", flush=True)
    finally:
        case.doCleanups()


class GeneratorDigestTest(TestCase):
    def test_sequential_generation_invalidates_push_digest(self):
        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "nginx").mkdir()
            (root / "nginx/variables.env").write_text("push")
            (root / "state").mkdir()
            (root / "state/applied").write_text("archive-A\n")
            install_generated(root)


if __name__ == "__main__":
    main()

"""A template that fails to render must stop the generator before it touches the output.

Run: .venv/bin/python tests/unit/test_gen_render_failure.py   (GEN_DIR points at another copy of src/common/gen)
"""

import hashlib
import sys
import types
import unittest
from functools import partial
from importlib.util import module_from_spec, spec_from_file_location
from inspect import signature
from os import environ, getpid
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = Path(environ.get("GEN_DIR", REPO_ROOT / "src/common/gen"))
sys.path[:0] = [str(REPO_ROOT / "src/common/utils"), str(GEN_DIR)]


def tree_digest(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


class TemplatorFailureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.templates = tmp / "confs"
        (self.templates / "server-http").mkdir(parents=True)
        (self.templates / "nginx.conf").write_text("worker_processes 1;\n")
        (self.templates / "server-http" / "ok.conf").write_text("# ok\n")
        for name in ("core", "plugins", "pro", "out"):
            (tmp / name).mkdir()
        self.tmp = tmp

        spec = spec_from_file_location("templator_under_test", GEN_DIR / "Templator.py")
        self.module = module_from_spec(spec)
        # The batches are pickled by class reference, so the module has to be importable by name.
        sys.modules[spec.name] = self.module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(self.module)
        real_path = self.module.Path
        cache = tmp / "jinja_cache"

        def path(*parts):
            if parts[:4] == ("/", "var", "cache", "bunkerweb"):
                return real_path(cache, *parts[4:])
            return real_path(*parts)

        patcher = patch.object(self.module, "Path", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def render(self):
        config = {"SERVER_NAME": "a.example.com", "MULTISITE": "no"}
        templator = self.module.Templator(
            self.templates.as_posix(),
            (self.tmp / "core").as_posix(),
            (self.tmp / "plugins").as_posix(),
            (self.tmp / "pro").as_posix(),
            (self.tmp / "out").as_posix(),
            "/etc/nginx",
            config,
            config,
            config,
        )
        return templator.render()

    def test_a_complete_render_reports_no_failure(self):
        self.assertEqual(self.render() or [], [])

    def test_a_failing_template_is_reported(self):
        (self.templates / "server-http" / "bad.conf").write_text("{{ 1 // 0 }}\n")
        failures = self.render()
        self.assertEqual(failures, ["a.example.com/server-http/bad.conf"])
        self.assertTrue((self.tmp / "out" / "ok.conf").is_file())

    def test_a_failing_global_template_is_reported(self):
        (self.templates / "http").mkdir()
        (self.templates / "http" / "bad.conf").write_text("{{ 1 // 0 }}\n")
        self.assertEqual(self.render(), ["http/bad.conf"])


class GeneratorMainTest(unittest.TestCase):
    """main.py with the rendering faked: only what it does with the outcome is under test."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.out = tmp / "nginx"
        (self.out / "http").mkdir(parents=True)
        (self.out / "variables.env").write_text("SERVER_NAME=old.example.com\n")
        (self.out / "http" / "old-security.conf").write_text("# deny\n")
        for name in ("settings.json", "vars.env"):
            (tmp / name).write_text("{}")
        for name in ("confs", "core", "plugins", "pro"):
            (tmp / name).mkdir()
        self.tmp = tmp
        self.marker = tmp / "reloading"
        self.nginx_pid = tmp / "nginx.pid"
        self.before = tree_digest(self.out)

    def run_main(self, failures):
        out = self.out

        class FakeTemplator:
            def __init__(self, templates, core, plugins, pro, output, *args):
                self.output = Path(output)

            def render(self):
                (self.output / "variables.env").write_text("SERVER_NAME=new.example.com\n")
                (self.output / "http").mkdir()
                (self.output / "http" / "new.conf").write_text("# new\n")
                return failures

        class FakeConfigurator:
            def __init__(self, *args):
                pass

            def get_config(self, db):
                return {"SERVER_NAME": "new.example.com"}

        fakes = {
            "Templator": types.SimpleNamespace(Templator=FakeTemplator),
            "Configurator": types.SimpleNamespace(Configurator=FakeConfigurator),
            "modsecurity_audit": types.SimpleNamespace(validate_audit_log_settings=lambda config: None),
            "env_file": types.SimpleNamespace(parse_env_file=lambda path: {}),
        }
        argv = [
            "main.py",
            "--settings", str(self.tmp / "settings.json"),
            "--templates", str(self.tmp / "confs"),
            "--core", str(self.tmp / "core"),
            "--plugins", str(self.tmp / "plugins"),
            "--pro-plugins", str(self.tmp / "pro"),
            "--output", str(out),
            "--target", str(out),
            "--variables", str(self.tmp / "vars.env"),
        ]  # fmt: skip
        # The guard works on files under /var/tmp, which a test must not touch
        import sync_tree

        paths = {"reloading": self.marker, "generating": self.tmp / "generating", "wait": 0.4, "poll": 0.02}
        if "nginx_pid" in signature(sync_tree.install_guard).parameters:
            paths["nginx_pid"] = self.nginx_pid
        guard = partial(sync_tree.install_guard, **paths)
        with patch.dict(sys.modules, {name: module for name, module in fakes.items()}), patch.object(sys, "argv", argv), patch.object(
            sync_tree, "install_guard", guard
        ):
            try:
                run_path((GEN_DIR / "main.py").as_posix(), run_name="__main__")
            except SystemExit as e:
                return e.code
        return 0

    def test_a_failed_render_exits_non_zero_and_leaves_the_output_untouched(self):
        self.assertEqual(self.run_main(["a.example.com/server-http/security.conf"]), 1)
        self.assertEqual(tree_digest(self.out), self.before)
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".bw-")], [])
        self.assertFalse((self.out / ".bw-install-incomplete").exists())

    def test_an_install_cut_short_leaves_the_sentinel_for_the_next_start(self):
        import sync_tree

        with patch.object(sync_tree, "replace", side_effect=OSError("disk gone")):
            self.assertEqual(self.run_main([]), 1)
        self.assertTrue((self.out / ".bw-install-incomplete").is_file())

    def test_a_reload_marker_that_does_not_clear_exits_non_zero_and_keeps_the_marker_and_the_output(self):
        self.marker.write_text("1")
        self.nginx_pid.write_text(f"{getpid()}\n")
        self.assertEqual(self.run_main([]), 1)
        self.assertEqual(tree_digest(self.out), self.before)
        self.assertTrue(self.marker.exists(), "the marker of a reload that may be in flight was removed")
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".bw-")], [])

    def test_a_marker_without_an_nginx_master_is_removed_and_the_render_is_installed(self):
        self.marker.write_text("1")
        self.assertEqual(self.run_main([]), 0)
        self.assertFalse(self.marker.exists())
        self.assertEqual((self.out / "variables.env").read_text(), "SERVER_NAME=new.example.com\n")

    def test_a_complete_render_is_installed(self):
        self.assertEqual(self.run_main([]), 0)
        self.assertEqual((self.out / "variables.env").read_text(), "SERVER_NAME=new.example.com\n")
        self.assertFalse((self.out / "http" / "old-security.conf").exists())
        self.assertTrue((self.out / "http" / "new.conf").is_file())
        self.assertFalse((self.out / ".bw-install-incomplete").exists())


if __name__ == "__main__":
    unittest.main()

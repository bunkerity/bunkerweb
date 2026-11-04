"""Tests for the plugin hook handling done by main.py: a raising before_request hook and a plugin whose hooks fail to load both deny the request.

main.py builds the whole Web UI at import time, so the units under test are lifted from its source.
UI_MAIN_PATH points the test at another copy of main.py (used to run it against the unfixed file).
"""

import ast
import sys
import tempfile
import unittest
from contextlib import suppress
from importlib.util import module_from_spec, spec_from_file_location
from itertools import chain
from logging import getLogger
from os import getpid, environ
from os.path import abspath
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

MAIN = Path(environ.get("UI_MAIN_PATH") or Path(__file__).resolve().parents[2] / "src/ui/main.py")
LOGGER = getLogger("test_ui_hooks_fail_closed")
tree = ast.parse(MAIN.read_text(encoding="utf-8"))
nodes = {getattr(n, "name", None): n for n in tree.body}


def lift(names, namespace, extra=()):
    exec(compile(ast.Module([nodes[n] for n in names if n in nodes] + list(extra), []), str(MAIN), "exec"), namespace)
    return namespace


# The unfixed main.py runs the hooks inline at the end of before_request: lift that loop as the function under test
if "run_before_request_hooks" not in nodes:
    loop = [n for n in nodes["before_request"].body if isinstance(n, ast.For)][-1]
    runner = ast.FunctionDef("run_before_request_hooks", ast.arguments([], [], None, [], [], None, []), [loop], [], None, lineno=1)
    ast.fix_missing_locations(runner)
    HOOK_EXTRA = [runner]
else:
    HOOK_EXTRA = []


class FakeData(dict):
    def load_from_file(self):
        pass


class BeforeRequestHooksTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask("test_ui_hooks_fail_closed")
        self.executed = []

        @self.app.route("/secret")
        def secret():
            self.executed.append("route")
            return "secret"

        namespace = lift(["run_before_request_hooks"], {"app": self.app, "LOGGER": LOGGER, "_internal_error_response": lambda: ("denied", 500)}, HOOK_EXTRA)
        self.app.before_request(namespace["run_before_request_hooks"])
        self.client = self.app.test_client()

    def test_raising_hook_returns_500_and_skips_the_route(self):
        def broken():
            raise RuntimeError("partial plugin update")

        self.app.config["BEFORE_REQUEST_HOOKS"] = [broken]
        response = self.client.get("/secret")
        self.assertEqual((response.status_code, response.get_data(as_text=True)), (500, "denied"))
        self.assertEqual(self.executed, [])

    def test_hook_response_and_clean_pass_through_keep_working(self):
        self.app.config["BEFORE_REQUEST_HOOKS"] = [lambda: None, lambda: ("blocked", 403)]
        self.assertEqual(self.client.get("/secret").status_code, 403)
        self.assertEqual(self.executed, [])

        self.app.config["BEFORE_REQUEST_HOOKS"] = [lambda: None]
        self.assertEqual(self.client.get("/secret").status_code, 200)
        self.assertEqual(self.executed, ["route"])


class HooksFailingToLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("sibling", "hooks"):
            self.addCleanup(sys.modules.pop, name, None)
        root = Path(self.tmp.name)
        self.ui = root / "pro/demo/ui"
        self.ui.mkdir(parents=True)
        self.ui.joinpath("hooks.py").write_text("from sibling import VALUE\n\n\ndef before_request():\n    return VALUE\n", encoding="utf-8")
        self.write_sibling("ok")
        for sub in ("core", "ext"):
            root.joinpath(sub).mkdir()

        self.app = SimpleNamespace(config={}, blueprints={})
        namespace = {
            "app": self.app,
            "LOGGER": LOGGER,
            "DATA": FakeData(),
            "HOOKS": {"before_request": {"key": "BEFORE_REQUEST_HOOKS", "log_prefix": "Before-request"}},
            "BLUEPRINTS": (),
            "CORE_PLUGINS_PATH": root / "core",
            "EXTERNAL_PLUGINS_PATH": root / "ext",
            "PRO_PLUGINS_PATH": root / "pro",
            "_internal_error_response": lambda: ("denied", 500),
            "register_plugin_blueprints": lambda app, registry: None,
            "read_plugin_version": lambda path: "0",
            "Blueprint": object,
            "abspath": abspath,
            "chain": chain,
            "suppress": suppress,
            "getpid": getpid,
            "sys_path": sys.path,
            "sys_modules": sys.modules,
            "spec_from_file_location": spec_from_file_location,
            "module_from_spec": module_from_spec,
        }
        self.refresh = lift(["deny_plugin_requests", "refresh_app_context"], namespace)["refresh_app_context"]

    def write_sibling(self, value):
        self.ui.joinpath("sibling.py").write_text(f"VALUE = {value!r}\n", encoding="utf-8")

    def test_plugin_loading_cleanly_keeps_its_own_hook(self):
        self.refresh()
        (hook,) = self.app.config["BEFORE_REQUEST_HOOKS"]
        self.assertEqual(hook(), "ok")

    def test_plugin_whose_hooks_fail_to_import_gets_a_denying_stub(self):
        self.ui.joinpath("sibling.py").write_text("raise ImportError('partial plugin update')\n", encoding="utf-8")
        self.refresh()
        (hook,) = self.app.config["BEFORE_REQUEST_HOOKS"]
        self.assertEqual(hook(), ("denied", 500))


if __name__ == "__main__":
    unittest.main()

"""Scheduler fixes: interpreter used for child scripts, read-only change detection, UI reload flag.

src/scheduler/main.py runs the whole scheduler at import time, so the units under test are
pulled out of its AST and executed in a small namespace instead of importing the module.
"""

import ast
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
MAIN = REPO / "src" / "scheduler" / "main.py"

for path in (REPO / "src" / "common" / "db", REPO / "src" / "common" / "utils", REPO / "src" / "common" / "gen"):
    sys.path.insert(0, str(path))

from Configurator import Configurator  # noqa: E402
from Database import Database  # noqa: E402

SOURCE = MAIN.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def function_source(name):
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(SOURCE, node)
    raise AssertionError(f"{name} not found in main.py")


def branch_guarding(needle):
    """The innermost `if` whose body contains `needle`."""
    matches = [n for n in ast.walk(TREE) if isinstance(n, ast.If) and needle in "\n".join(ast.get_source_segment(SOURCE, b) for b in n.body)]
    if not matches:
        raise AssertionError(f"{needle} not found in main.py")
    return min(matches, key=lambda n: n.end_lineno - n.lineno)


class SubprocessInterpreterTest(unittest.TestCase):
    def test_every_script_child_is_launched_with_the_scheduler_interpreter(self):
        spawned = []
        for node in ast.walk(TREE):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "subprocess_run":
                cmd = node.args[0]
                self.assertIsInstance(cmd, ast.List)
                segments = [ast.get_source_segment(SOURCE, elt) for elt in cmd.elts]
                script = next((seg for seg in segments if '"gen"' in seg), None)
                if script:
                    spawned.append(node.lineno)
                    self.assertEqual(segments[0], "sys_executable", f"line {node.lineno} runs {script} through its shebang")
        self.assertEqual(len(spawned), 4, spawned)


class ReadOnlyPluginsConfigTest(unittest.TestCase):
    """Drive the real `plugins_config_changed` branch of the main loop with a read-only database."""

    def setUp(self):
        changes_assign = next(
            n
            for n in ast.walk(TREE)
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "changes" and isinstance(n.value, ast.Dict) and n.value.keys
        )
        branch = branch_guarding("Plugins config changed, generating")
        self.build_changes = compile(ast.Expression(changes_assign.value), "changes", "eval")
        self.condition = compile(ast.Expression(branch.test), "condition", "eval")

    def evaluate(self, metadata, old_changes, readonly):
        changes = eval(self.build_changes, {"db_metadata": metadata})
        scheduler = SimpleNamespace(db=SimpleNamespace(readonly=readonly))
        return bool(eval(self.condition, {"changes": changes, "old_changes": old_changes, "SCHEDULER": scheduler})), changes

    def metadata(self, plugins_config_changed):
        return {
            key: value
            for key, value in {
                "pro_plugins_changed": False,
                "last_pro_plugins_change": None,
                "external_plugins_changed": False,
                "last_external_plugins_change": None,
                "custom_configs_changed": False,
                "last_custom_configs_change": None,
                "plugins_config_changed": plugins_config_changed,
                "instances_changed": False,
                "last_instances_change": None,
            }.items()
        }

    def test_readonly_first_tick_with_pending_plugin_config_does_not_raise(self):
        triggered, _ = self.evaluate(self.metadata({"antibot": "t1"}), {}, readonly=True)
        self.assertTrue(triggered)

    def test_readonly_unchanged_plugin_config_is_not_regenerated(self):
        metadata = self.metadata({"antibot": "t1"})
        _, old = self.evaluate(metadata, {}, readonly=True)
        triggered, _ = self.evaluate(metadata, old, readonly=True)
        self.assertFalse(triggered)

    def test_readonly_new_plugin_config_change_is_regenerated(self):
        _, old = self.evaluate(self.metadata({"antibot": "t1"}), {}, readonly=True)
        triggered, _ = self.evaluate(self.metadata({"antibot": "t2"}), old, readonly=True)
        self.assertTrue(triggered)

    def test_read_write_pending_plugin_config_always_triggers(self):
        triggered, _ = self.evaluate(self.metadata({"antibot": "t1"}), {"plugins_config_changed": {"antibot": "t1"}}, readonly=False)
        self.assertTrue(triggered)


class ClaimChangesKeepsUiFlagTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bw-test-claim-changes-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmpdir, ignore_errors=True))
        logger = logging.getLogger("claim-changes-test")
        self.db = Database(logger, sqlalchemy_string=f"sqlite:///{os.path.join(self.tmpdir, 'db.sqlite3')}")
        configurator = Configurator(
            str(REPO / "src/common/settings.json"), str(REPO / "src/common/core"), [], [], {"SERVER_NAME": "", "MULTISITE": "yes"}, logger
        )
        ret, err = self.db.init_tables([configurator.get_settings(), configurator.get_plugins("core"), [], []])
        self.assertFalse(err, err)
        self.assertEqual(self.db.initialize_db("1.6.16~rc4", "Docker"), "")
        namespace = {
            "SCHEDULER": SimpleNamespace(db=self.db),
            "LOGGER": logger,
            "getenv": os.getenv,
            "Optional": __import__("typing").Optional,
            "List": list,
            "Dict": dict,
            "Any": object,
        }
        exec(function_source("claim_changes"), namespace)
        self.claim_changes = namespace["claim_changes"]

    def flag(self):
        return bool(self.db.get_metadata()["reload_ui_plugins"])

    def test_scheduler_claim_leaves_the_ui_plugins_flag_for_the_ui(self):
        self.assertEqual(self.db.checked_changes(["ui_plugins"], value=True), "")
        self.assertTrue(self.flag())
        self.claim_changes(plugins_changes="all")
        self.assertTrue(self.flag(), "the scheduler cleared the flag only the UI may consume")

    def test_scheduler_claim_with_empty_changes_leaves_the_flag(self):
        self.db.checked_changes(["ui_plugins"], value=True)
        self.claim_changes([])
        self.assertTrue(self.flag())

    def test_ui_can_still_clear_its_own_flag(self):
        self.db.checked_changes(["ui_plugins"], value=True)
        self.assertEqual(self.db.checked_changes(["ui_plugins"]), "")
        self.assertFalse(self.flag())

    def test_default_set_requests_a_ui_plugins_reload(self):
        self.assertFalse(self.flag())
        self.assertEqual(self.db.checked_changes(plugins_changes="all", value=True), "")
        self.assertTrue(self.flag(), "a default-list set (restore, migration import) must request a UI plugin reload")

    def test_default_clear_keeps_a_pending_ui_plugins_flag(self):
        self.db.checked_changes(["ui_plugins"], value=True)
        self.assertEqual(self.db.checked_changes(value=False), "")
        self.assertTrue(self.flag())

    def test_explicit_ui_plugins_clear_still_clears(self):
        self.db.checked_changes(value=True)
        self.assertTrue(self.flag())
        self.assertEqual(self.db.checked_changes(["ui_plugins"], value=False), "")
        self.assertFalse(self.flag())

    def test_scheduler_claim_still_clears_scheduler_flags(self):
        self.db.checked_changes(["instances", "external_plugins"], value=True)
        self.claim_changes(plugins_changes="all")
        metadata = self.db.get_metadata()
        self.assertFalse(metadata["instances_changed"])
        self.assertFalse(metadata["external_plugins_changed"])


if __name__ == "__main__":
    unittest.main()

"""A bulk delete skips a file-managed config with a dotted name instead of failing the whole selection."""

import sys
import unittest
from json import dumps
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[2]
for path in ("src/ui", "src/common/utils", "src/common/db", "src/common/api"):
    sys.path.insert(0, str(REPO / path))

from flask import Flask  # noqa: E402

# app.dependencies builds the database at import time: replace it for the import only
deps = ModuleType("app.dependencies")
for name in ("BW_CONFIG", "BW_INSTANCES_UTILS", "DB", "DATA", "CONFIG_TASKS_EXECUTOR"):
    setattr(deps, name, MagicMock())
with patch.dict(sys.modules, {"app.dependencies": deps}):
    import app.routes.configs as configs_module  # noqa: E402


class FakeDB:
    readonly = False

    def __init__(self):
        self.calls = []

    def delete_custom_configs(self, keys):
        self.calls.append(set(keys))
        deleted = {key for key in keys if key[2] == "ui_one"}
        return "", deleted, set(keys) - deleted


class ConfigsBulkDeleteDottedTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.errors = []
        self.data = MagicMock()
        run_now = lambda task, *args: task(*args)  # noqa: E731
        for p in (
            patch.object(configs_module, "DB", self.db),
            patch.object(configs_module, "DATA", self.data),
            patch.object(configs_module, "submit_config_task", run_now),
            patch.object(configs_module, "wait_applying", lambda: None),
            patch.object(configs_module, "handle_error", lambda message, *a, **kw: self.errors.append(message) or ("error", 302)),
        ):
            p.start()
            self.addCleanup(p.stop)
        app = Flask("cfg-delete-test", template_folder=str(REPO / "src" / "ui" / "app" / "templates"))
        app.secret_key = "test"
        app.config["LOGIN_DISABLED"] = True
        app.register_blueprint(configs_module.configs)
        app.add_url_rule("/loading", "loading", lambda: "")
        app.add_url_rule("/home", "home", lambda: "")
        self.client = app.test_client()

    def delete(self, selection):
        return self.client.post("/configs/delete", data={"configs": dumps(selection)})

    def test_dotted_file_managed_row_is_skipped_not_fatal(self):
        self.delete([{"name": "ui_one", "type": "http"}, {"name": "a.b", "type": "http"}])
        self.assertEqual(self.errors, [])
        self.assertEqual(self.db.calls, [{(None, "http", "ui_one"), (None, "http", "a.b")}])
        flashed = [call.args[0]["content"] for call in self.data["TO_FLASH"].append.call_args_list]
        self.assertTrue(any("http/a.b is not a UI/API custom config" in c for c in flashed), flashed)

    def test_malformed_input_still_rejected(self):
        for bad in (
            [{"name": "x\ny", "type": "http"}],
            [{"name": "", "type": "http"}],
            [{"name": "n" * 256, "type": "http"}],
            [{"name": "a", "type": "nope"}],
            [],
        ):
            self.errors.clear()
            self.delete(bad)
            self.assertEqual(self.errors, ["Invalid configs parameter on /configs/delete."], bad)
        self.assertEqual(self.db.calls, [])


if __name__ == "__main__":
    unittest.main()

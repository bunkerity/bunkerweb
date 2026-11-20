"""A custom config name is one identity: the name accepted on create is the name edit looks up and renames to."""

import sys
import unittest
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
    GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR = ""

    def __init__(self):
        self.rows = {}
        self.lookups = []

    def upsert_custom_config(self, config_type, name, config, service_id=None, new=False):
        if new and (service_id, config_type, name) in self.rows:
            return "The custom config already exists"
        self.rows.pop((service_id, config_type, name), None)
        self.rows[(config.get("service_id"), config["type"], config["name"])] = {
            "type": config["type"],
            "name": config["name"],
            "service_id": config.get("service_id"),
            "data": config["data"].encode(),
            "method": "ui",
            "is_draft": config["is_draft"],
            "template": None,
        }

    def get_custom_config(self, config_type, name, service_id=None, with_data=False):
        self.lookups.append(name)
        row = self.rows.get((service_id, config_type, name))
        return dict(row) if row else None


def make_client(db):
    app = Flask("cfg-name-test", template_folder=str(REPO / "src" / "ui" / "app" / "templates"))
    app.secret_key = "test"
    app.config["LOGIN_DISABLED"] = True
    app.register_blueprint(configs_module.configs)
    app.add_url_rule("/loading", "loading", lambda: "")
    app.add_url_rule("/home", "home", lambda: "")
    return app


class ConfigNameIdentityTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.errors = []
        self.rendered = []

        def run_now(task, *args):
            task(*args)

        patches = [
            patch.object(configs_module, "DB", self.db),
            patch.object(configs_module, "DATA", MagicMock()),
            patch.object(configs_module, "BW_CONFIG", MagicMock(get_config=lambda **_: {"SERVER_NAME": "svc-a"})),
            patch.object(configs_module, "submit_config_task", run_now),
            patch.object(configs_module, "wait_applying", lambda: None),
            patch.object(configs_module, "handle_error", lambda message, *a, **kw: self.errors.append(message) or ("error", 302)),
            patch.object(configs_module, "render_template", lambda template, **ctx: self.rendered.append(ctx) or "ok"),
            patch.object(configs_module, "_use_modsecurity_global_crs", lambda: False),
            patch.object(configs_module, "flash", lambda *a, **kw: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = make_client(self.db).test_client()

    def create(self, name):
        return self.client.post("/configs/new", data={"service": "global", "type": "HTTP", "name": name, "value": "x"})

    def edit_get(self, name):
        return self.client.get(f"/configs/global/http/{name}")

    def test_created_names_open_under_the_same_name(self):
        for name in ("_x", "x_", "café", "plain-name_1"):
            with self.subTest(name=name):
                self.errors.clear()
                self.rendered.clear()
                self.create(name)
                self.assertIn((None, "http", name), self.db.rows, "create did not store the typed name")
                self.edit_get(name)
                self.assertEqual(self.errors, [])
                self.assertEqual(self.rendered[-1]["name"], name)

    def test_edit_does_not_open_a_different_config_of_the_rewritten_name(self):
        self.create("x")
        self.create("_x")
        self.rendered.clear()
        self.edit_get("_x")
        self.assertEqual(self.rendered[-1]["name"], "_x")

    def test_rename_keeps_the_typed_name(self):
        self.create("old")
        self.client.post("/configs/global/http/old", data={"service": "global", "type": "HTTP", "name": "_new_", "value": "y"})
        self.assertIn((None, "http", "_new_"), self.db.rows)
        self.assertNotIn((None, "http", "new"), self.db.rows)

    def test_separators_are_refused_everywhere(self):
        self.create("old")
        for bad in ("a/b", "..", "../x", "a b", "x\n"):
            with self.subTest(bad=bad):
                self.errors.clear()
                self.create(bad)
                self.assertTrue(self.errors, "create accepted " + repr(bad))
                self.assertNotIn((None, "http", bad), self.db.rows)
                before = len(self.db.lookups)
                self.errors.clear()
                self.client.post("/configs/global/http/old", data={"service": "global", "type": "HTTP", "name": bad, "value": "z"})
                self.assertTrue(self.errors, "rename accepted " + repr(bad))
                self.assertNotIn((None, "http", bad), self.db.rows)
                self.assertGreaterEqual(len(self.db.lookups), before)
        for bad in ("..", "a%0Ab", "a%20b"):
            with self.subTest(url_name=bad):
                self.errors.clear()
                self.rendered.clear()
                self.client.get(f"/configs/global/http/{bad}")
                self.assertTrue(self.errors)
                self.assertEqual(self.rendered, [], "an unknown name opened a config")

    def test_stored_dotted_name_still_opens(self):
        self.db.rows[(None, "http", "from.file")] = {
            "type": "http",
            "name": "from.file",
            "service_id": None,
            "data": b"x",
            "method": "scheduler",
            "template": None,
        }
        self.edit_get("from.file")
        self.assertEqual(self.errors, [])
        self.assertEqual(self.rendered[-1]["name"], "from.file")


if __name__ == "__main__":
    unittest.main()

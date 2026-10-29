"""Tests for the plugin blueprint replacement done by main.py (DynamicFlask.register_blueprint and register_plugin_blueprints).

main.py builds the whole Web UI at import time, so the two units under test are lifted from its source.
"""

import ast
import tempfile
import unittest
from logging import getLogger
from operator import itemgetter
from os.path import abspath
from pathlib import Path

from flask import Blueprint, Flask
from jinja2 import ChoiceLoader, FileSystemLoader

MAIN = Path(__file__).resolve().parents[2] / "src/ui/main.py"
WANTED = {"should_replace_blueprint", "DynamicFlask", "register_plugin_blueprints"}

namespace = {
    "Flask": Flask,
    "ChoiceLoader": ChoiceLoader,
    "FileSystemLoader": FileSystemLoader,
    "itemgetter": itemgetter,
    "abspath": abspath,
    "LOGGER": getLogger("test_ui_blueprint_reload"),
}
tree = ast.parse(MAIN.read_text(encoding="utf-8"))
exec(compile(ast.Module([n for n in tree.body if getattr(n, "name", None) in WANTED], []), str(MAIN), "exec"), namespace)
DynamicFlask = namespace["DynamicFlask"]
register_plugin_blueprints = namespace["register_plugin_blueprints"]


class BlueprintReloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = DynamicFlask("test_ui_blueprint_reload")
        self.app.config["EXTRA_PAGES"] = []
        self.client = self.app.test_client()

    def plugin_blueprint(self, name, body, priority, route="/", extra_routes=(), loaded=True):
        """Build a blueprint the way refresh_app_context does: a fresh object per load, templates in its own folder."""
        folder = Path(self.tmp.name, f"{name}-{priority}-{body}")
        folder.mkdir(parents=True)
        folder.joinpath("page.html").write_text(f"template:{body}", encoding="utf-8")
        bp = Blueprint(name, f"bw_ui_blueprint_{name}", template_folder=str(folder))

        def view():
            return f"view:{body}"

        def tpl():
            return self.app.jinja_env.get_template("page.html").render()

        bp.add_url_rule(route, endpoint=f"{name}_page", view_func=view)
        bp.add_url_rule(f"{route.rstrip('/')}/tpl", endpoint="tpl", view_func=tpl)
        for extra in extra_routes:
            bp.add_url_rule(extra, endpoint=extra.strip("/").replace("/", "_"), view_func=view)
        bp.plugin_priority = priority
        if loaded:
            bp.import_path = str(folder)
        bp.template_folder = abspath(bp.template_folder)
        return bp

    def reload(self, *blueprints):
        register_plugin_blueprints(self.app, {bp.name: bp for bp in blueprints})

    def get(self, path):
        response = self.client.get(path)
        return response.status_code, response.get_data(as_text=True)

    def rules(self, name):
        return sorted(str(rule) for rule in self.app.url_map.iter_rules() if rule.endpoint.startswith(f"{name}."))

    def test_same_plugin_same_priority_replaces_view_and_template(self):
        self.reload(self.plugin_blueprint("demo", "v1", 2, "/demo"))
        self.assertEqual(self.get("/demo"), (200, "view:v1"))
        self.assertEqual(self.get("/demo/tpl"), (200, "template:v1"))

        updated = self.plugin_blueprint("demo", "v2", 2, "/demo")
        self.reload(updated)

        self.assertIs(self.app.blueprints["demo"], updated)
        self.assertEqual(self.get("/demo"), (200, "view:v2"))
        self.assertEqual(self.get("/demo/tpl"), (200, "template:v2"))

    def test_same_priority_reload_drops_routes_the_update_removed(self):
        self.reload(self.plugin_blueprint("demo", "v1", 2, "/demo", extra_routes=("/demo/old",)))
        self.assertEqual(self.get("/demo/old"), (200, "view:v1"))

        self.reload(self.plugin_blueprint("demo", "v2", 2, "/demo"))

        self.assertEqual(self.get("/demo/old")[0], 404)
        self.assertEqual(self.rules("demo"), ["/demo", "/demo/tpl"])

    def test_no_duplicate_rules_or_handlers_after_several_reloads(self):
        for version in ("v1", "v2", "v3", "v4"):
            bp = self.plugin_blueprint("demo", version, 1, "/demo")
            bp.before_request(lambda: None)
            self.reload(bp)
        self.assertEqual(self.rules("demo"), ["/demo", "/demo/tpl"])
        self.assertEqual(len(self.app.before_request_funcs["demo"]), 1)
        self.assertEqual(self.get("/demo"), (200, "view:v4"))

    def test_higher_priority_still_overrides(self):
        self.reload(self.plugin_blueprint("demo", "ext", 1, "/demo"))
        pro = self.plugin_blueprint("demo", "pro", 2, "/demo")
        self.reload(pro)
        self.assertIs(self.app.blueprints["demo"], pro)
        self.assertEqual(self.get("/demo"), (200, "view:pro"))
        self.assertEqual(self.get("/demo/tpl"), (200, "template:pro"))

    def test_lower_priority_from_another_source_does_not_override(self):
        pro = self.plugin_blueprint("demo", "pro", 2, "/demo")
        self.reload(pro)
        self.reload(self.plugin_blueprint("demo", "ext", 1, "/demo"))
        self.assertIs(self.app.blueprints["demo"], pro)
        self.assertEqual(self.get("/demo"), (200, "view:pro"))
        self.assertEqual(self.get("/demo/tpl"), (200, "template:pro"))

    def test_plugin_does_not_override_a_core_blueprint_of_the_same_priority(self):
        core = self.plugin_blueprint("demo", "core", 0, "/demo", loaded=False)
        self.app.register_blueprint(core)
        self.reload(self.plugin_blueprint("demo", "core-plugin", 0, "/demo"))
        self.assertIs(self.app.blueprints["demo"], core)
        self.assertEqual(self.get("/demo"), (200, "view:core"))

    def test_bare_alias_rule_registered_by_record_once_is_replaced_with_the_blueprint(self):
        """PRO plugins add `/<name>` from a record_once callback, with the bare blueprint name as endpoint."""

        def alias_blueprint(body):
            bp = self.plugin_blueprint("demo", body, 2, "/demo/page")

            def alias_view():
                return f"alias:{body}"

            @bp.record_once
            def register_alias(state):
                if "demo" in state.app.view_functions:
                    return
                state.app.add_url_rule("/demo", endpoint="demo", view_func=alias_view, methods=["GET"])

            return bp

        self.reload(alias_blueprint("v1"))
        self.assertEqual(self.get("/demo"), (200, "alias:v1"))

        self.reload(alias_blueprint("v2"))
        self.assertEqual(self.get("/demo"), (200, "alias:v2"))
        self.assertEqual(self.get("/demo/page"), (200, "view:v2"))
        self.assertEqual(self.rules("demo"), ["/demo/page", "/demo/page/tpl"])
        self.assertEqual(sorted(str(rule) for rule in self.app.url_map.iter_rules() if rule.endpoint == "demo"), ["/demo"])

    def test_bare_alias_rule_is_dropped_when_the_update_no_longer_registers_it(self):
        bp = self.plugin_blueprint("demo", "v1", 2, "/demo/page")
        bp.record_once(lambda state: state.app.add_url_rule("/demo", endpoint="demo", view_func=lambda: "alias"))
        self.reload(bp)
        self.assertEqual(self.get("/demo"), (200, "alias"))

        self.reload(self.plugin_blueprint("demo", "v2", 2, "/demo/page"))
        self.assertEqual(self.get("/demo")[0], 404)
        self.assertNotIn("demo", self.app.view_functions)

    def test_register_blueprint_replaces_a_loaded_plugin_blueprint_of_equal_priority(self):
        self.app.register_blueprint(self.plugin_blueprint("demo", "v1", 1, "/demo"))
        updated = self.plugin_blueprint("demo", "v2", 1, "/demo")
        self.app.register_blueprint(updated)
        self.assertIs(self.app.blueprints["demo"], updated)
        self.assertEqual(self.get("/demo"), (200, "view:v2"))


if __name__ == "__main__":
    unittest.main()

"""main.py ``refresh_app_context``: plugin hooks and blueprints are loaded from the plugin directories on disk.

Each test writes real ``ui/hooks.py`` and ``ui/blueprints/*.py`` files under ``tmp_path`` plugin trees and
runs the real refresh against the real app; the fixture refreshes once more at the end so the shared app
loses every plugin blueprint again.
"""

import json
import sys
from textwrap import dedent

import pytest


@pytest.fixture
def plugins(um):
    um.app.config["EXTRA_PAGES"] = ["crowdsec"]
    yield um
    for root in (um.deps.CORE_PLUGINS_PATH, um.deps.EXTERNAL_PLUGINS_PATH, um.deps.PRO_PLUGINS_PATH):
        for child in list(root.iterdir()):
            import shutil

            shutil.rmtree(child)
    um.main.refresh_app_context()
    um.app.config["EXTRA_PAGES"] = ["crowdsec"]


def write_plugin(root, name, *, hooks=None, blueprints=None, version="1.2.3", hooks_proxy=None):
    plugin = root / name
    (plugin / "ui").mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({"id": name, "version": version}))
    if hooks is not None:
        (plugin / "ui" / "hooks.py").write_text(dedent(hooks))
    if hooks_proxy is not None:
        (plugin / "ui" / "hooks_proxy.py").write_text(dedent(hooks_proxy))
    for bp_name, source in (blueprints or {}).items():
        (plugin / "ui" / "blueprints").mkdir(exist_ok=True)
        (plugin / "ui" / "blueprints" / f"{bp_name}.py").write_text(dedent(source))
    return plugin


def blueprint_source(name, body="ok", route=None):
    return f"""
        from flask import Blueprint
        {name} = Blueprint("{name}", __name__)

        @{name}.route("{route or '/' + name}")
        def view():
            return "{body}"
    """


HOOKS = """
    def before_request():
        return None

    def after_request(response):
        response.headers["X-Plugin"] = "yes"
        return response

    def context_processor():
        return {"from_plugin": True}

    def scripts():
        return {"src": "/p.js"}

    def styles():
        return {"href": "/p.css"}

    def teardown_request(exc):
        pass
"""


class TestHooks:
    def test_hooks_of_every_plugin_tree_are_loaded_in_order(self, plugins):
        write_plugin(plugins.deps.CORE_PLUGINS_PATH, "coreplug", hooks=HOOKS)
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", hooks="def before_request():\n    return None\n")
        write_plugin(plugins.deps.PRO_PLUGINS_PATH, "proplug", hooks="def styles():\n    return {}\n")
        plugins.main.refresh_app_context()
        config = plugins.app.config
        assert [f.__module__ for f in config["BEFORE_REQUEST_HOOKS"]] == ["bw_ui_hooks_coreplug_hooks", "bw_ui_hooks_extplug_hooks"]
        assert [f.__module__ for f in config["STYLES_HOOKS"]] == ["bw_ui_hooks_coreplug_hooks", "bw_ui_hooks_proplug_hooks"]
        for key in ("AFTER_REQUEST_HOOKS", "CONTEXT_PROCESSOR_HOOKS", "SCRIPTS_HOOKS", "TEARDOWN_REQUEST_HOOKS"):
            assert len(config[key]) == 1

    def test_hooks_run_inside_requests(self, plugins):
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", hooks=HOOKS)
        plugins.main.refresh_app_context()
        resp = plugins.client(None).get("/check")
        assert resp.headers["X-Plugin"] == "yes"

    def test_refreshing_twice_does_not_duplicate_hooks(self, plugins):
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", hooks=HOOKS)
        plugins.main.refresh_app_context()
        plugins.main.refresh_app_context()
        assert len(plugins.app.config["AFTER_REQUEST_HOOKS"]) == 1

    def test_proxy_module_wins_over_the_hooks_file(self, plugins):
        write_plugin(
            plugins.deps.EXTERNAL_PLUGINS_PATH,
            "extplug",
            hooks="def before_request():\n    return 'real'\n",
            hooks_proxy="def before_request():\n    return 'proxy'\n",
        )
        plugins.main.refresh_app_context()
        (hook,) = plugins.app.config["BEFORE_REQUEST_HOOKS"]
        assert hook() == "proxy"

    def test_a_plugin_that_fails_to_import_denies_requests_without_affecting_others(self, plugins):
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "broken", hooks="raise RuntimeError('import time failure')\n")
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "fine", hooks="def styles():\n    return {}\n")
        plugins.main.refresh_app_context()
        (guard,) = plugins.app.config["BEFORE_REQUEST_HOOKS"]
        assert guard.__module__ == "bw_ui_hooks_broken_hooks"
        assert len(plugins.app.config["STYLES_HOOKS"]) == 1
        resp = plugins.client(None).get("/check")
        assert resp.status_code == 500

    def test_loading_a_plugin_does_not_leak_path_or_module_state(self, plugins):
        plugin = write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", hooks=HOOKS)
        sys.modules.pop("hooks", None)
        plugins.main.refresh_app_context()
        assert str(plugin / "ui") not in sys.path and "hooks" not in sys.modules

    def test_non_callable_attributes_are_not_hooks(self, plugins):
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", hooks="before_request = 'not callable'\n")
        plugins.main.refresh_app_context()
        assert plugins.app.config["BEFORE_REQUEST_HOOKS"] == []

    def test_stale_context_flag_is_dropped(self, plugins):
        plugins.data["NEEDS_CONTEXT_REFRESH"] = True
        plugins.main.refresh_app_context()
        assert "NEEDS_CONTEXT_REFRESH" not in plugins.data


class TestBlueprints:
    def test_external_blueprint_is_registered_with_priority_and_version(self, plugins):
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", blueprints={"extpage": blueprint_source("extpage", "hello")})
        plugins.main.refresh_app_context()
        bp = plugins.app.blueprints["extpage"]
        assert (bp.plugin_priority, bp.plugin_version) == (1, "1.2.3") and bp.import_path.endswith("extplug/ui/blueprints")
        assert plugins.client(None).get("/extpage").status_code != 404
        assert "extpage" in plugins.app.config["EXTRA_PAGES"]

    def test_pro_beats_external_for_the_same_blueprint_name(self, plugins):
        write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", blueprints={"shared": blueprint_source("shared", "from-ext", "/shared")})
        write_plugin(plugins.deps.PRO_PLUGINS_PATH, "proplug", blueprints={"shared": blueprint_source("shared", "from-pro", "/shared")})
        plugins.main.refresh_app_context()
        assert plugins.app.blueprints["shared"].plugin_priority == 2
        view = plugins.app.view_functions["shared.view"]
        assert view() == "from-pro"

    def test_removing_the_plugin_removes_the_blueprint_and_its_page(self, plugins):
        import shutil

        plugin = write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", blueprints={"gone": blueprint_source("gone")})
        plugins.main.refresh_app_context()
        assert "gone" in plugins.app.blueprints and "gone" in plugins.app.config["EXTRA_PAGES"]
        shutil.rmtree(plugin)
        plugins.main.refresh_app_context()
        assert "gone" not in plugins.app.blueprints and "gone" not in plugins.app.config["EXTRA_PAGES"]
        assert "gone.view" not in plugins.app.view_functions

    def test_removed_plugin_page_answers_404(self, plugins):
        import shutil

        plugin = write_plugin(plugins.deps.EXTERNAL_PLUGINS_PATH, "extplug", blueprints={"gone404": blueprint_source("gone404")})
        plugins.main.refresh_app_context()
        shutil.rmtree(plugin)
        plugins.main.refresh_app_context()
        assert plugins.client(None).get("/gone404").status_code == 404

    def test_invalid_objects_and_broken_files_are_skipped(self, plugins):
        write_plugin(
            plugins.deps.EXTERNAL_PLUGINS_PATH,
            "extplug",
            blueprints={
                "notbp": "notbp = 42\n",
                "wrongname": blueprint_source("other"),
                "syntax": "def (:\n",
                "good": blueprint_source("good"),
            },
        )
        plugins.main.refresh_app_context()
        names = set(plugins.app.blueprints)
        assert "good" in names and not names & {"notbp", "wrongname", "syntax", "other"}

    def test_proxy_files_are_not_loaded_as_blueprints_but_replace_their_target(self, plugins):
        write_plugin(
            plugins.deps.EXTERNAL_PLUGINS_PATH,
            "extplug",
            blueprints={"page": blueprint_source("page", "real", "/page"), "page_proxy": blueprint_source("page", "proxied", "/page")},
        )
        plugins.main.refresh_app_context()
        assert plugins.app.view_functions["page.view"]() == "proxied"
        assert "page_proxy" not in plugins.app.blueprints

    def test_builtin_blueprints_are_restored_when_missing(self, plugins):
        plugins.app.blueprints.pop("about", None)
        plugins.main.refresh_app_context()
        assert "about" in plugins.app.blueprints

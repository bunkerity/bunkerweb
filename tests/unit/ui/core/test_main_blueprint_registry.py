"""main.py: ``DynamicFlask`` blueprint replacement, plugin registration and the plain helpers beside them."""

import pytest
from flask import Blueprint
from jinja2 import TemplateNotFound


@pytest.fixture
def main(um):
    return um.main


def bp(name="plug", *, priority=None, reload=False, route="/x", handler_value="v1", template_folder=None):
    blueprint = Blueprint(name, f"{name}_{handler_value}", template_folder=template_folder)
    blueprint.add_url_rule(route, "view", lambda: handler_value)
    blueprint.before_request(lambda: None)
    if priority is not None:
        blueprint.plugin_priority = priority
    if reload:
        blueprint.import_path = "/some/dir"
    return blueprint


class TestPureHelpers:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("52428800", 52428800), ("50M", 50 * 1024**2), ("50 MiB", 50 * 1024**2), ("1G", 1024**3), ("1.5k", 1536), (" 2 kb ", 2048), ("3TiB", 3 * 1024**4)],
    )
    def test_parse_size_accepts(self, main, text, expected):
        assert main.parse_size_to_bytes(text) == expected

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("abc", "invalid format"),
            ("", "invalid format"),
            ("5 parsecs", "invalid unit"),
            ("0", "non-positive size"),
            ("0.4", "non-positive size"),
            ("-5", "invalid format"),
        ],
    )
    def test_parse_size_rejects(self, main, text, message):
        with pytest.raises(ValueError, match=message):
            main.parse_size_to_bytes(text)

    def test_static_cache_control(self, main):
        assert main._static_cache_control("1.0", "1.0") == "public, max-age=31536000, immutable"
        assert main._static_cache_control("0.9", "1.0") is None
        assert main._static_cache_control(None, "1.0") is None

    @pytest.mark.parametrize(
        ("host", "allowed", "expected"),
        [
            ("ui.example.com", ["ui.example.com"], True),
            ("UI.Example.com:8443", ["ui.example.com"], True),
            ("evil.test", ["ui.example.com"], False),
            ("a.example.com", ["*.example.com"], True),
            ("example.com", ["*.example.com"], True),
            ("badexample.com", ["*.example.com"], False),
            ("anything", ["*"], True),
            ("ui.example.com", [" ", "ui.example.com:7000"], True),
            ("", ["*"], False),
            ("x", [], False),
        ],
    )
    def test_host_allowed(self, main, host, allowed, expected):
        assert main._host_allowed(host, allowed) is expected

    def test_should_replace_blueprint(self, main):
        core, ext, pro = bp(priority=0), bp(priority=1), bp(priority=2)
        assert main.should_replace_blueprint(core, pro) is True
        assert main.should_replace_blueprint(pro, ext) is False
        assert main.should_replace_blueprint(bp(), bp()) is False  # built-in at its own priority is never replaced
        reload_a, reload_b = bp(priority=1, reload=True), bp(priority=1, reload=True)
        assert main.should_replace_blueprint(reload_a, reload_b) is True
        assert main.should_replace_blueprint(bp(priority=1, reload=True), bp(priority=1)) is False


class TestDynamicFlask:
    def app(self, main):
        return main.DynamicFlask("registry_test")

    def test_higher_priority_replaces_and_drops_everything_the_old_one_added(self, main):
        app = self.app(main)
        app.register_blueprint(bp(priority=0, handler_value="old"))
        assert app.test_client().get("/x").data == b"old"
        before_count = len(app.before_request_funcs["plug"])
        app.register_blueprint(bp(priority=2, handler_value="new", route="/y"))
        client = app.test_client()
        assert client.get("/y").data == b"new"
        assert client.get("/x").status_code == 404  # the stale rule no longer matches
        assert len(app.before_request_funcs["plug"]) == before_count  # handlers are not stacked

    def test_lower_or_equal_priority_is_ignored(self, main):
        app = self.app(main)
        app.register_blueprint(bp(priority=2, handler_value="pro"))
        app.register_blueprint(bp(priority=1, handler_value="ext"))
        app.register_blueprint(bp(priority=2, handler_value="again"))
        assert app.test_client().get("/x").data == b"pro"

    def test_plugin_reload_replaces_at_equal_priority(self, main):
        app = self.app(main)
        app.register_blueprint(bp(priority=1, reload=True, handler_value="v1"))
        app.register_blueprint(bp(priority=1, reload=True, handler_value="v2"))
        assert app.test_client().get("/x").data == b"v2"

    def test_rules_added_outside_the_namespace_are_removed_too(self, main):
        app = self.app(main)
        blueprint = bp(priority=0)
        blueprint.record_once(lambda state: state.app.add_url_rule("/plug", "plug", lambda: "alias"))
        app.register_blueprint(blueprint)
        assert app.test_client().get("/plug").data == b"alias"
        app.register_blueprint(bp(priority=2, route="/z"))
        assert app.test_client().get("/plug").status_code == 404

    def test_jinja_loader_orders_blueprints_by_priority(self, main, tmp_path):
        for label, priority in (("low", 0), ("high", 2)):
            folder = tmp_path / label
            folder.mkdir()
            (folder / "page.html").write_text(label)
        app = self.app(main)
        low = bp("low", priority=0, template_folder=str(tmp_path / "low"))
        high = bp("high", priority=2, template_folder=str(tmp_path / "high"))
        app.register_blueprint(low)
        app.register_blueprint(high)
        loader = app.create_global_jinja_loader()
        assert [type(item).__name__ for item in loader.loaders][:2] == ["FileSystemLoader", "FileSystemLoader"]
        assert loader.get_source(app.jinja_env, "page.html")[0] == "high"
        with pytest.raises(TemplateNotFound):
            loader.get_source(app.jinja_env, "missing.html")

    def test_register_plugin_blueprints_adds_root_pages_and_resets_templates(self, main):
        app = self.app(main)
        app.config["EXTRA_PAGES"] = []
        root = Blueprint("rootpage", "rootpage")
        root.add_url_rule("/rootpage", "page", lambda: "root")
        other = bp("other", route="/other/sub")
        app.jinja_env.cache = {"stale": 1}
        main.register_plugin_blueprints(app, {"rootpage": root, "other": other})
        assert app.config["EXTRA_PAGES"] == ["rootpage"]
        assert app.jinja_env.cache == {}
        assert {"rootpage", "other"} <= set(app.blueprints)

    def test_register_plugin_blueprints_skips_a_lower_priority_duplicate(self, main):
        app = self.app(main)
        app.config["EXTRA_PAGES"] = []
        app.register_blueprint(bp(priority=2, handler_value="pro"))
        main.register_plugin_blueprints(app, {"plug": bp(priority=1, handler_value="ext")})
        assert app.test_client().get("/x").data == b"pro"


def test_deny_plugin_requests_installs_a_fail_closed_hook(um):
    um.main.app.config[um.main.HOOKS["before_request"]["key"]] = []
    um.main.deny_plugin_requests("bw_ui_hooks_broken_hooks")
    (hook,) = um.main.app.config["BEFORE_REQUEST_HOOKS"]
    assert hook.__module__ == "bw_ui_hooks_broken_hooks"
    with um.app.test_request_context("/"):
        body, status = hook()
    assert status == 500 and "An unexpected error occurred during authorization." in body

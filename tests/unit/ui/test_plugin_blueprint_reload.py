"""A reloaded plugin replaces its blueprint; a built-in one is never replaced.

``refresh_app_context`` re-imports every plugin blueprint after a plugin update. The new object has
the same name and the same ``plugin_priority`` as the one already registered, and the old rule
("new priority <= existing priority: skip") kept serving the stale pages, routes and templates.

Importing ``main.py`` boots the whole UI, so the three pieces under test are lifted out by AST and
exec'd against a stubbed namespace -- the bodies are the shipped ones, not copies.
"""

from ast import ClassDef, FunctionDef, Module, parse
from operator import itemgetter
from os.path import abspath
from pathlib import Path
from unittest.mock import Mock

import pytest

flask = pytest.importorskip("flask")
from jinja2 import ChoiceLoader, FileSystemLoader  # noqa: E402

MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"
WANTED = {"should_replace_blueprint", "DynamicFlask", "register_plugin_blueprints"}


@pytest.fixture(scope="module")
def main_ns():
    tree = parse(MAIN.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (FunctionDef, ClassDef)) and n.name in WANTED]
    namespace = {
        "Flask": flask.Flask,
        "ChoiceLoader": ChoiceLoader,
        "FileSystemLoader": FileSystemLoader,
        "abspath": abspath,
        "itemgetter": itemgetter,
        "LOGGER": Mock(),
    }
    exec(compile(Module(body=nodes, type_ignores=[]), str(MAIN), "exec"), namespace)  # noqa: S102
    return namespace


def _blueprint(name, answer, priority=None, plugin_folder=False):
    bp = flask.Blueprint(name, f"{__name__}.{name}.{answer}")

    @bp.route(f"/{name}")
    def page():
        return answer

    @bp.route(f"/{name}/old-only" if answer == "old" else f"/{name}/new-only")
    def side():
        return answer

    if priority is not None:
        bp.plugin_priority = priority
    if plugin_folder:
        bp.import_path = "/etc/bunkerweb/plugins/x/ui"
    return bp


def _get(app, path):
    return app.test_client().get(path)


def test_equal_priority_plugin_blueprints_replace_each_other(main_ns):
    app = main_ns["DynamicFlask"](__name__)
    app.register_blueprint(_blueprint("plug", "old", priority=1, plugin_folder=True))
    assert _get(app, "/plug").get_data(as_text=True) == "old"

    app.register_blueprint(_blueprint("plug", "new", priority=1, plugin_folder=True))

    assert _get(app, "/plug").get_data(as_text=True) == "new"
    assert _get(app, "/plug/old-only").status_code == 404, "a route of the old blueprint is still served"
    assert _get(app, "/plug/new-only").status_code == 200


def test_the_old_view_functions_and_rules_are_gone(main_ns):
    app = main_ns["DynamicFlask"](__name__)
    app.register_blueprint(_blueprint("plug", "old", priority=1, plugin_folder=True))
    app.register_blueprint(_blueprint("plug", "new", priority=1, plugin_folder=True))

    assert sorted(ep for ep in app.view_functions if ep.startswith("plug.")) == ["plug.page", "plug.side"]
    assert [str(r) for r in app.url_map.iter_rules() if r.endpoint.startswith("plug.")].count("/plug") == 1


def test_a_builtin_blueprint_is_never_replaced_at_its_own_priority(main_ns):
    app = main_ns["DynamicFlask"](__name__)
    app.register_blueprint(_blueprint("home", "builtin"))
    app.register_blueprint(_blueprint("home", "impostor"))

    assert _get(app, "/home").get_data(as_text=True) == "builtin"


def test_a_plugin_folder_blueprint_does_not_replace_a_builtin_at_equal_priority(main_ns):
    app = main_ns["DynamicFlask"](__name__)
    app.register_blueprint(_blueprint("home", "builtin"))
    app.register_blueprint(_blueprint("home", "plugin", priority=0, plugin_folder=True))

    assert _get(app, "/home").get_data(as_text=True) == "builtin"


def test_a_higher_priority_still_wins_and_a_lower_one_still_loses(main_ns):
    app = main_ns["DynamicFlask"](__name__)
    app.register_blueprint(_blueprint("plug", "ext", priority=1, plugin_folder=True))
    app.register_blueprint(_blueprint("plug", "pro", priority=2, plugin_folder=True))
    assert _get(app, "/plug").get_data(as_text=True) == "pro"

    app.register_blueprint(_blueprint("plug", "core", priority=0, plugin_folder=True))
    assert _get(app, "/plug").get_data(as_text=True) == "pro"


def test_a_replacement_does_not_stack_the_blueprint_handlers(main_ns):
    calls = []
    app = main_ns["DynamicFlask"](__name__)

    def blueprint(answer):
        bp = _blueprint("plug", answer, priority=1, plugin_folder=True)
        bp.before_request(lambda: calls.append(answer))
        return bp

    app.register_blueprint(blueprint("old"))
    app.register_blueprint(blueprint("new"))
    _get(app, "/plug")

    assert calls == ["new"]


def test_refresh_replaces_registered_plugin_blueprints(main_ns):
    app = main_ns["DynamicFlask"](__name__)
    app.config["EXTRA_PAGES"] = []
    app.register_blueprint(_blueprint("plug", "old", priority=1, plugin_folder=True))
    app.register_blueprint(_blueprint("home", "builtin"))

    main_ns["register_plugin_blueprints"](
        app,
        {"plug": _blueprint("plug", "new", priority=1, plugin_folder=True), "home": _blueprint("home", "impostor", priority=0, plugin_folder=True)},
    )

    assert _get(app, "/plug").get_data(as_text=True) == "new"
    assert _get(app, "/home").get_data(as_text=True) == "builtin"
    assert "plug" in app.config["EXTRA_PAGES"]

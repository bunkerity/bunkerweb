"""A POST that lacks a required form field redirects with its message instead of falling through (dev d51b8b584).

`verify_data_in_form()` flashes and *returns* the redirect `Response`. Routes that called it as a bare
statement dropped that response and went on to `request.form["field"]`, which raised a bare 400 page
after the flash was already queued. Every call must hand its result back.

Two layers: an AST guard over every route module (a new bare call fails the build), and the behaviour
of a few routes whose handler, once past the check, would have run a destructive step.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes"


def _bare_calls(path: Path):
    """Line numbers of `verify_data_in_form(...)` calls whose result is thrown away."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", getattr(node.value.func, "attr", None)) == "verify_data_in_form"
    ]


def _route_files():
    return sorted(path for path in ROUTES.glob("*.py") if "verify_data_in_form(" in path.read_text(encoding="utf-8"))


def test_the_guard_finds_the_routes_it_is_meant_to_cover():
    names = {path.name for path in _route_files()}

    assert {"configs.py", "instances.py", "jobs.py", "plugins.py", "pro.py", "profile.py", "services.py", "totp.py"} <= names


@pytest.mark.parametrize("path", _route_files(), ids=lambda path: path.name)
def test_no_route_drops_the_result_of_verify_data_in_form(path):
    assert _bare_calls(path) == [], f"{path.name}: the redirect `Response` of verify_data_in_form is discarded at these lines"


# ---------------------------------------------------------------------------- behaviour


class _Deps(ModuleType):
    """`app.dependencies` stand-in: any name a route imports resolves to a Mock."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = Mock(name=name)
        setattr(self, name, value)
        return value


def _load(name):
    dependencies = _Deps("app.dependencies")
    dependencies.DATA = {"TO_FLASH": []}
    dependencies.API_CLIENT = Mock(readonly=False)
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = f"app.routes._form_missing_{name}"
    spec = importlib.util.spec_from_file_location(module_name, ROUTES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
    return module


def _client(module, view, rule):
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    flashed = []
    module.flash = lambda message, category="message", **_kwargs: flashed.append((category, str(message)))
    # `handle_error` flashes through `app.routes.utils.flash`; the redirect it returns is what matters here.
    app.add_url_rule(rule, endpoint=view.__name__, view_func=view.__wrapped__ if hasattr(view, "__wrapped__") else view, methods=["POST"])
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
    for page in ("jobs", "pro", "configs", "services", "instances", "plugins"):
        app.add_url_rule(f"/{page}", endpoint=f"{page}.{page}_page", view_func=lambda: "page")
    return app.test_client()


CASES = (
    # (module, view name, rule, form that is non-empty but lacks the required field, collaborator that must not run)
    ("jobs", "jobs_run", "/jobs/run", {"unrelated": "x"}, lambda m: m.API_CLIENT.run_jobs),
    (
        "pro",
        "pro_key",
        "/pro/key",
        {"unrelated": "x"},
        lambda m: m.API_CLIENT.update_global_settings if hasattr(m.API_CLIENT, "update_global_settings") else m.API_CLIENT.patch_global_settings,
    ),
    ("instances", "instances_action", "/instances/<action>", {"unrelated": "x"}, lambda m: m.API_CLIENT.delete_instance),
    ("configs", "configs_delete", "/configs/delete", {"unrelated": "x"}, lambda m: m.API_CLIENT.delete_configs),
)


@pytest.mark.parametrize("module_name, view_name, rule, form, forbidden", CASES, ids=[case[1] for case in CASES])
def test_a_missing_field_redirects_and_the_handler_stops(module_name, view_name, rule, form, forbidden):
    module = _load(module_name)
    module.is_readonly_request = lambda *_args, **_kwargs: False
    client = _client(module, getattr(module, view_name), rule)
    url = rule.replace("<action>", "delete")

    with patch("app.utils.current_user", Mock(list_permissions=["read", "write"], admin=True)):
        response = client.post(url, data=form)

    assert response.status_code == 302, f"{view_name} answered {response.status_code}: a bare 400 means the redirect was dropped"
    assert "/loading" in response.headers["Location"]
    assert not forbidden(module).called

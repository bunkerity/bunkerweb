"""Service names and service-operation failures in the Web UI.

Dev ``cea19bc67`` (a service's ``SERVER_NAME`` cannot be emptied) and ``71820652d`` (#3893: a failed
service operation must not read as a success).

The shared helper ``submit_config_task`` already flashes the generic error for a task that raises. What it
leaves behind is ``CONFIG_CHANGED``: ``main.py`` turns it into "The last changes have been applied
successfully." on the next page, so a failed save was announced as applied.
"""

import ast
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

from app.models.config import Config  # type: ignore  (src/ui on path via the ui conftest)
from test_save_scope import _FakeData, _import_services_module, _with_permissions

SERVICES_ROUTE = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "services.py"
MODULE = _import_services_module()


# ----------------------------------------------------------------- an empty service SERVER_NAME
SERVER_NAME_SETTING = {"SERVER_NAME": {"type": "text", "regex": r"^(?:(\S+)(?:\s+\S+)*)?$", "context": "multisite"}}


def _config():
    cfg = Config.__new__(Config)  # skip __init__ (avoids the image-only settings.json read)
    cfg._Config__data = type("Data", (dict,), {"load_from_file": lambda self: None})(TO_FLASH=[])
    cfg._Config__ignore_regex_check = False
    cfg.get_plugins_settings = lambda: SERVER_NAME_SETTING  # type: ignore[method-assign]
    return cfg


@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "blank"])
def test_a_service_cannot_be_given_an_empty_server_name(blank):
    refused = []
    variables = {"SERVER_NAME": blank}

    result = _config().check_variables(
        variables,
        {"SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False}},
        dict(variables),
        global_config=False,
        threaded=True,
        refused=refused,
    )

    assert "SERVER_NAME" not in result
    assert len(refused) == 1 and "can't be empty" in refused[0], refused


def test_a_service_server_name_with_aliases_passes():
    variables = {"SERVER_NAME": "app.example.com alias.example.com"}

    result = _config().check_variables(
        variables, {"SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False}}, dict(variables), global_config=False, threaded=True
    )

    assert result == variables


# ------------------------------------------------------------------ a failed task is not applied
def _submit_calls():
    """Every `submit_config_task(...)` call in the route module, by line."""
    tree = ast.parse(SERVICES_ROUTE.read_text(encoding="utf-8"))
    return sorted(
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "submit_config_task"
    )


def test_every_service_task_goes_through_the_one_submit_helper():
    """Seven call sites; the one that is forgotten keeps announcing its failures as applied."""
    assert hasattr(MODULE, "_submit_service_task"), "no helper owns the CONFIG_CHANGED reset"
    helper = next(node for node in ast.parse(SERVICES_ROUTE.read_text(encoding="utf-8")).body if getattr(node, "name", "") == "_submit_service_task")
    inside = {call for call in range(helper.lineno, helper.end_lineno + 1)}
    outside = [line for line in _submit_calls() if line not in inside]
    assert outside == [], f"submit_config_task called directly at lines {outside}"


def _run_submit(monkeypatch, *, error):
    data = _FakeData(TO_FLASH=[], CONFIG_CHANGED=True, RELOADING=True)
    monkeypatch.setattr(MODULE, "DATA", data)
    from concurrent.futures import Future

    future = Future()
    monkeypatch.setattr(MODULE, "submit_config_task", lambda task, *args, **kwargs: future)

    returned = MODULE._submit_service_task(lambda: None)
    assert returned is future
    if error:
        future.set_exception(error)
    else:
        future.set_result(None)
    return data


def test_a_task_that_raises_does_not_leave_the_change_marked_applied(monkeypatch):
    data = _run_submit(monkeypatch, error=RuntimeError("boom"))

    assert data["CONFIG_CHANGED"] is False


def test_a_task_that_succeeds_keeps_the_change_marked(monkeypatch):
    data = _run_submit(monkeypatch, error=None)

    assert data["CONFIG_CHANGED"] is True


# ------------------------------------------------------- a failed custom config save is not a success
def _save_with_a_config_that_fails(monkeypatch, *, raises):
    api = Mock()
    api.get_service.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}}
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    api.bulk_save_configs.side_effect = raises
    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = {}
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("Configuration saved", None)
    data = _FakeData(TO_FLASH=[], CONFIG_CHANGED=True)
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", data)
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)

    MODULE.update_service(
        "app.example.com",
        {"SERVER_NAME": "app.example.com", "USE_UI": "no", "CUSTOM_CONF_SERVER_HTTP_test": "# hello"},
        False,
        "easy",
        "",
        {},
    )
    assert api.bulk_save_configs.called, "the bulk-save branch was never reached -- this test proves nothing"
    return data


def test_a_failed_custom_config_save_is_not_announced_as_a_success(monkeypatch):
    data = _save_with_a_config_that_fails(monkeypatch, raises=RuntimeError("database is gone"))

    types = [flash["type"] for flash in data["TO_FLASH"]]
    assert "error" in types, data["TO_FLASH"]
    assert "success" not in types, data["TO_FLASH"]
    assert data["CONFIG_CHANGED"] is False
    assert data["RELOADING"] is False


# ------------------------------------------------------- creating a service says "Creating"
@pytest.fixture
def route_app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(MODULE.services)
    app.add_url_rule("/loading", "loading", lambda: "")
    return app


def _post(app, monkeypatch, *, service, form):
    api = Mock()
    api.readonly = False
    api.get_service.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False}}
    api.get_metadata.return_value = {"is_pro": False}
    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = {}
    bw_config.get_config.return_value = {"SERVER_NAME": "app.example.com"}
    bw_config.get_plugins.return_value = {}
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "submit_config_task", Mock())
    monkeypatch.setattr(MODULE, "DATA", _FakeData(TO_FLASH=[]))
    with app.test_request_context(f"/services/{service}", method="POST", data={"csrf_token": "x"} | form), _with_permissions("read", "write"):
        response = MODULE.services_service_page.__wrapped__(service)
    return parse_qs(urlparse(response.location).query)["message"][0]


def test_creating_a_service_says_creating(route_app, monkeypatch):
    message = _post(route_app, monkeypatch, service="new", form={"SERVER_NAME": "new.example.com"})

    assert message.startswith("Creating"), message
    assert "new.example.com" in message


def test_saving_a_service_still_says_saving(route_app, monkeypatch):
    message = _post(route_app, monkeypatch, service="app.example.com", form={"SERVER_NAME": "app.example.com"})

    assert message.startswith("Saving"), message

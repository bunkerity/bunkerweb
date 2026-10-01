"""/services/new: a refused server name is reported as what it is (QA-UI H6), and the resource
band's flashes go through the catalog (QA-UI L7).

H6: `check_variables` DROPS an invalid posted SERVER_NAME and says "Variable SERVER_NAME is not
valid."; the queued `update_service` then found no SERVER_NAME and added "The service was not
created because the server name was not provided." -- two contradictory errors for one typo. The
"not provided" case is now refused by the route itself, before anything is queued (the task runs
without a request and cannot translate), and the task stays silent about a name it saw dropped.

Harness: the loader of `test_service_save_flash_type.py`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages

REPO_ROOT = Path(__file__).resolve().parents[3]


def _import_services_module():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.CORE_PLUGINS_PATH = REPO_ROOT / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._services_test_new_name_feedback"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_services_module()


class _FakeData(dict):
    def load_from_file(self):
        pass


def test_a_dropped_server_name_is_not_also_reported_as_missing(monkeypatch):
    def drop_the_name(variables, *args, refused=None, **kwargs):
        # models/config.py:check_variables on a NEW service: report_error, then the key is gone.
        if refused is not None:
            refused.append("Variable SERVER_NAME is not valid.")
        variables = dict(variables)
        variables.pop("SERVER_NAME", None)
        return variables

    api = Mock()
    api.get_global_settings.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}}
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    bw_config = Mock()
    # No secret settings: routes/services.py masks and restores `type: password` values.
    bw_config.get_plugins_settings.return_value = {}
    bw_config.check_variables.side_effect = drop_the_name
    data = _FakeData(TO_FLASH=[])
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", data)
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)

    MODULE.update_service("new", {"SERVER_NAME": "bad name!!", "OLD_SERVER_NAME": ""}, False, "compose", "", {})

    assert bw_config.check_variables.called, "check_variables never ran -- this test proves nothing"
    assert not any("not provided" in flashed["content"] for flashed in data["TO_FLASH"]), data["TO_FLASH"]
    assert not bw_config.new_service.called and not bw_config.edit_service.called


@pytest.fixture
def route_app(monkeypatch):
    api = Mock()
    api.readonly = False
    bw_config = Mock()
    # No secret settings: routes/services.py masks and restores `type: password` values.
    bw_config.get_plugins_settings.return_value = {}
    bw_config.get_config.return_value = {"SERVER_NAME": "app.example.com"}
    executor = Mock()
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr(MODULE, "CONFIG_TASKS_EXECUTOR", executor)
    monkeypatch.setattr(MODULE, "is_readonly_request", lambda api_readonly: api_readonly)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(MODULE.services)
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "", methods=["GET"])
    return app, executor


@pytest.mark.parametrize("posted", [{}, {"SERVER_NAME": ""}, {"SERVER_NAME": "   "}])
def test_a_creation_without_a_name_is_refused_before_anything_is_queued(route_app, monkeypatch, posted):
    app, executor = route_app
    monkeypatch.setattr(MODULE, "translated", lambda key, **variables: f"[{key}]")

    with app.test_request_context("/services/new?mode=compose", method="POST", data={"csrf_token": "x", "OLD_SERVER_NAME": ""} | posted):
        response = MODULE.services_service_page.__wrapped__("new")
        messages = get_flashed_messages(with_categories=True)

    assert not executor.submit.called, "a creation with no name was queued anyway"
    assert response.status_code == 302 and "/loading" not in response.location
    assert ("error", "[services.flash.server_name_missing]") in messages


def test_a_named_creation_is_still_queued(route_app):
    app, executor = route_app

    with app.test_request_context(
        "/services/new?mode=compose", method="POST", data={"csrf_token": "x", "SERVER_NAME": "new.example.com", "OLD_SERVER_NAME": ""}
    ):
        MODULE.services_service_page.__wrapped__("new")

    assert executor.submit.called


@pytest.mark.parametrize(
    ("side_effect", "key", "variables"),
    [
        (None, "services.flash.resource_detached", {"service": "app.example.com"}),
        (PermissionError("read-only"), "services.flash.resource_detach_refused", {"error": "read-only"}),
        (ValueError("bad family"), "services.flash.resource_unknown_family", {}),
    ],
)
def test_the_detach_flashes_go_through_the_catalog(route_app, monkeypatch, side_effect, key, variables):
    app, _ = route_app
    calls = []

    def recording_translated(requested, **kwargs):
        calls.append((requested, kwargs))
        return f"[{requested}]"

    monkeypatch.setattr(MODULE, "translated", recording_translated)
    monkeypatch.setattr(MODULE, "detach_service_resource", Mock(side_effect=side_effect))

    with app.test_request_context("/services/app.example.com/resources/detach", method="POST", data={"family": "upstream", "resource_id": "pool"}):
        MODULE.services_resource_detach.__wrapped__("app.example.com")
        messages = get_flashed_messages(with_categories=True)

    assert calls == [(key, variables)]
    assert [message for _, message in messages] == [f"[{key}]"]

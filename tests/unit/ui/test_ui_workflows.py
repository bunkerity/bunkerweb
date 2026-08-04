"""Workflow UI client and Flask route contracts."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.api_client import ApiClient, ApiClientError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


@pytest.fixture(scope="module")
def workflows_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    # app.routes.utils pulls in qrcode (TOTP QR codes), which the unit venv does not carry;
    # only the CORS decorator is needed here and it is a pass-through in tests.
    routes_utils = ModuleType("app.routes.utils")
    routes_utils.cors_required = lambda function: function
    module_name = "app.routes._workflows_test"
    route_path = ROOT / "src" / "ui" / "app" / "routes" / "workflows.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "app.utils": app_utils, "app.routes.utils": routes_utils, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, app_utils.flash


@pytest.fixture
def route_app(workflows_route):
    module, client, flash = workflows_route
    client.reset_mock(return_value=True, side_effect=True)
    flash.reset_mock()
    client.readonly = False
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.workflows)
    return module, client, flash, app


def test_api_client_paths_and_payloads(api_client, monkeypatch):
    get = Mock(side_effect=[{"workflows": []}, {"workflow": {"id": "wf-1"}}, {"definition": {"rules": []}}])
    post = Mock(return_value={"status": "success"})
    put = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_get", get)
    monkeypatch.setattr(api_client, "_post", post)
    monkeypatch.setattr(api_client, "_put", put)

    api_client.get_workflows(search="login", service_id="app.example.com")
    api_client.get_workflow("wf-1")
    api_client.get_workflow_definition("wf-1")
    api_client.save_workflow_definition("wf-1", {"schema_version": 1, "rules": []})
    api_client.validate_workflow({"schema_version": 1, "rules": []}, workflow_id="wf-1", service_ids=["app.example.com"])
    api_client.attach_workflow("wf-1", "app.example.com")

    assert get.call_args_list[0].args[0] == "/workflows"
    assert get.call_args_list[0].kwargs["params"]["search"] == "login"
    assert get.call_args_list[2].args[0] == "/workflows/wf-1/definition"
    assert put.call_args.args[0] == "/workflows/wf-1/definition"
    assert put.call_args.kwargs["json"] == {"definition": {"schema_version": 1, "rules": []}}
    assert post.call_args_list[0].args[0] == "/workflows/validate"
    assert post.call_args_list[0].kwargs["json"]["service_ids"] == ["app.example.com"]
    assert post.call_args_list[1].args[0] == "/workflows/wf-1/attachments"


def test_get_workflow_unwraps_the_envelope(api_client, monkeypatch):
    monkeypatch.setattr(api_client, "_get", Mock(return_value={"status": "success", "workflow": {"id": "wf-1"}}))
    assert api_client.get_workflow("wf-1") == {"id": "wf-1"}


def test_create_posts_the_selected_services(route_app):
    module, client, flash, app = route_app
    client.create_workflow.return_value = {"status": "success"}

    with app.test_request_context(
        "/workflows/create",
        method="POST",
        data={"name": "login-protection", "description": "d", "service_ids": ["a.example.com", "b.example.com"]},
    ):
        module.workflows_create.__wrapped__()

    assert client.create_workflow.call_args.kwargs["service_ids"] == ["a.example.com", "b.example.com"]
    assert client.create_workflow.call_args.kwargs["name"] == "login-protection"


def test_a_missing_name_is_refused_before_the_api_is_called(route_app):
    module, client, flash, app = route_app
    with app.test_request_context("/workflows/create", method="POST", data={"description": "d"}):
        module.workflows_create.__wrapped__()
    assert not client.create_workflow.called
    assert "name is required" in flash.call_args.args[0]


def test_readonly_blocks_every_mutation(route_app):
    module, client, flash, app = route_app
    client.readonly = True
    with app.test_request_context("/workflows/delete", method="POST", data={"workflow_id": "wf-1"}):
        module.workflows_delete.__wrapped__()
    assert not client.delete_workflow.called


def test_validate_proxies_the_api_and_writes_nothing(route_app):
    module, client, flash, app = route_app
    client.validate_workflow.return_value = {"status": "success", "valid": True, "summaries": []}

    with app.test_request_context(
        "/workflows/wf-1/validate",
        method="POST",
        json={"definition": {"schema_version": 1, "rules": []}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ):
        response = module.workflows_validate.__wrapped__("wf-1")

    assert json.loads(response.get_data())["valid"] is True
    assert client.validate_workflow.call_args.kwargs["workflow_id"] == "wf-1"
    assert not client.save_workflow_definition.called


def test_validate_refuses_a_payload_without_a_definition(route_app):
    module, client, flash, app = route_app
    with app.test_request_context("/workflows/wf-1/validate", method="POST", json={}, headers={"X-Requested-With": "XMLHttpRequest"}):
        response, status = module.workflows_validate.__wrapped__("wf-1")
    assert status == 400
    assert not client.validate_workflow.called


def test_test_proxies_the_api_and_writes_nothing(route_app):
    module, client, flash, app = route_app
    client.test_workflow.return_value = {"status": "success", "valid": True, "outcome": {"type": "no_match"}}

    with app.test_request_context(
        "/workflows/wf-1/test",
        method="POST",
        json={"request": {"uri": "/login", "country": "FR"}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ):
        response = module.workflows_test.__wrapped__("wf-1")

    assert json.loads(response.get_data())["outcome"]["type"] == "no_match"
    assert not client.save_workflow_definition.called


def test_test_refuses_a_payload_without_a_request(route_app):
    module, client, flash, app = route_app
    with app.test_request_context("/workflows/wf-1/test", method="POST", json={}, headers={"X-Requested-With": "XMLHttpRequest"}):
        response, status = module.workflows_test.__wrapped__("wf-1")
    assert status == 400
    assert not client.test_workflow.called


def test_test_is_allowed_in_readonly(route_app):
    """Testing stores nothing, so a read-only database is no reason to refuse it."""
    module, client, flash, app = route_app
    client.readonly = True
    client.test_workflow.return_value = {"status": "success", "valid": True, "outcome": {"type": "no_match"}}

    with app.test_request_context(
        "/workflows/wf-1/test",
        method="POST",
        json={"request": {"uri": "/", "country": "FR"}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ):
        module.workflows_test.__wrapped__("wf-1")

    assert client.test_workflow.called


def test_save_reports_the_api_error_instead_of_pretending_it_worked(route_app):
    module, client, flash, app = route_app
    client.save_workflow_definition.side_effect = ApiClientError("Invalid regular expression", 400)

    with app.test_request_context(
        "/workflows/wf-1/save",
        method="POST",
        json={"definition": {"schema_version": 1, "rules": []}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ):
        response, status = module.workflows_save.__wrapped__("wf-1")

    assert status == 400
    assert json.loads(response.get_data())["message"] == "Invalid regular expression"


def test_save_is_refused_in_readonly(route_app):
    module, client, flash, app = route_app
    client.readonly = True
    with app.test_request_context(
        "/workflows/wf-1/save",
        method="POST",
        json={"definition": {"schema_version": 1, "rules": []}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ):
        response, status = module.workflows_save.__wrapped__("wf-1")
    assert status == 409
    assert not client.save_workflow_definition.called


def test_the_editor_page_is_reachable_from_the_menu_and_the_locale():
    """A page nobody can navigate to is a page nobody uses."""
    menu = (ROOT / "src" / "ui" / "app" / "templates" / "menu.html").read_text(encoding="utf-8")
    assert "workflows.workflows_page" in menu

    locale = json.loads((ROOT / "src" / "ui" / "app" / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
    assert locale["navigation"]["workflows"] == "Workflows"
    # The editor's inline errors are rendered from the API's messages, but the static labels
    # around them are translated like every other page. "conditions" was one of them until the
    # rule-ladder rework deleted the <template> that carried it, so "add_rule" stands in: a
    # label the page still emits, which is the only kind worth asserting on.
    for key in ("add_rule", "action", "threshold", "order_help", "no_rules"):
        assert key in locale["workflows"]

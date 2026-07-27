"""Redirect UI client and Flask route contracts."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call, patch

import pytest
from flask import Flask

from app.api_client import ApiClient, ApiClientError


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


@pytest.fixture(scope="module")
def redirects_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    module_name = "app.routes._redirects_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "redirects.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "app.utils": app_utils, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client, app_utils.flash


@pytest.fixture
def route_app(redirects_route):
    module, client, flash = redirects_route
    client.reset_mock(return_value=True, side_effect=True)
    flash.reset_mock()
    client.readonly = False
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.redirects)
    return module, client, flash, app


def test_api_client_paths_and_payloads(api_client, monkeypatch):
    get = Mock(side_effect=[{"redirects": []}, {"redirect": {"id": "red-1"}}])
    post = Mock(return_value={"status": "success"})
    patch_request = Mock(return_value={"status": "success"})
    delete = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_get", get)
    monkeypatch.setattr(api_client, "_post", post)
    monkeypatch.setattr(api_client, "_patch", patch_request)
    monkeypatch.setattr(api_client, "_delete", delete)

    api_client.get_redirects(search="docs", service_id="svc", offset=10, limit=20)
    assert api_client.get_redirect("red-1") == {"id": "red-1"}
    api_client.create_redirect(name="docs", from_path="/docs", to_url="https://docs.example.com")
    api_client.update_redirect("red-1", to_url="https://new.example.com")
    api_client.attach_redirect("red-1", "svc")
    api_client.detach_redirect("red-1", "svc")
    api_client.delete_redirect("red-1")

    assert get.call_args_list == [
        call("/redirects", params={"offset": 10, "limit": 20, "search": "docs", "service_id": "svc"}),
        call("/redirects/red-1"),
    ]
    assert post.call_args_list == [
        call("/redirects", json={"name": "docs", "from_path": "/docs", "to_url": "https://docs.example.com"}),
        call("/redirects/red-1/attachments", json={"service_id": "svc"}),
    ]
    patch_request.assert_called_once_with("/redirects/red-1", json={"to_url": "https://new.example.com"})
    assert delete.call_args_list == [call("/redirects/red-1/attachments/svc"), call("/redirects/red-1")]


def test_page_loads_rules_and_services(route_app, monkeypatch):
    module, client, _, app = route_app
    rule = {"id": "red-1", "name": "docs", "from_path": "/docs", "to_url": "https://docs.example.com", "services": ["svc"]}
    client.get_redirects.return_value = {"redirects": [rule], "total": 2}
    client.get_services.return_value = [{"id": "svc"}]
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/redirects"):
        assert module.redirects_page.__wrapped__() == "rendered"

    client.get_redirects.assert_called_once_with(limit=500)
    client.get_services.assert_called_once_with(with_drafts=True)
    context = render.call_args.kwargs
    assert context["redirects"] == [rule]
    assert context["truncated"] is True
    assert context["status_codes"] == ("301", "302", "303", "307", "308")


def test_page_survives_an_api_failure(route_app, monkeypatch):
    module, client, flash, app = route_app
    client.get_redirects.side_effect = ApiClientError("boom", status_code=502)
    client.get_services.return_value = []
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/redirects"):
        assert module.redirects_page.__wrapped__() == "rendered"

    assert render.call_args.kwargs["redirects"] == []
    assert flash.call_args_list[0].args[1] == "error"


def test_create_forwards_the_rule_and_the_selected_services(route_app):
    module, client, _, app = route_app
    form = {
        "name": "docs",
        "from_path": "/docs",
        "to_url": "https://docs.example.com",
        "status_code": "308",
        "append_request_uri": "yes",
        "description": "Docs moved",
        "service_ids": ["svc", "svc2"],
    }

    with app.test_request_context("/redirects/create", method="POST", data=form):
        module.redirects_create.__wrapped__()

    client.create_redirect.assert_called_once_with(
        name="docs",
        to_url="https://docs.example.com",
        from_path="/docs",
        status_code="308",
        description="Docs moved",
        append_request_uri=True,
        service_ids=["svc", "svc2"],
    )


def test_create_applies_defaults_and_rejects_a_bad_status_code(route_app):
    module, client, flash, app = route_app

    with app.test_request_context("/redirects/create", method="POST", data={"name": "docs", "to_url": "https://docs.example.com"}):
        module.redirects_create.__wrapped__()
    payload = client.create_redirect.call_args.kwargs
    assert payload["from_path"] == "/" and payload["status_code"] == "301"
    # An unchecked switch submits nothing, which must read as an explicit "no".
    assert payload["append_request_uri"] is False

    client.reset_mock()
    with app.test_request_context("/redirects/create", method="POST", data={"name": "docs", "to_url": "https://x.example.com", "status_code": "404"}):
        module.redirects_create.__wrapped__()
    client.create_redirect.assert_not_called()
    assert flash.call_args.args[1] == "error"


def test_update_sends_only_the_submitted_fields(route_app):
    module, client, _, app = route_app

    with app.test_request_context("/redirects/update", method="POST", data={"redirect_id": "red-1", "to_url": "https://new.example.com"}):
        module.redirects_update.__wrapped__()

    # from_path/status_code/description are absent, so the PATCH must leave them alone.
    assert client.update_redirect.call_args == call("red-1", to_url="https://new.example.com", append_request_uri=False)

    # An emptied description is submitted as a present-but-blank field and must clear it.
    client.reset_mock()
    with app.test_request_context("/redirects/update", method="POST", data={"redirect_id": "red-1", "name": "docs", "description": ""}):
        module.redirects_update.__wrapped__()
    assert client.update_redirect.call_args.kwargs["description"] == ""


def test_attach_loops_over_services_and_detach_takes_one(route_app):
    module, client, _, app = route_app

    with app.test_request_context("/redirects/attach", method="POST", data={"redirect_id": "red-1", "service_ids": ["a", "b"]}):
        module.redirects_attach.__wrapped__()
    assert client.attach_redirect.call_args_list == [call("red-1", "a"), call("red-1", "b")]

    with app.test_request_context("/redirects/detach", method="POST", data={"redirect_id": "red-1", "service_id": "a"}):
        module.redirects_detach.__wrapped__()
    client.detach_redirect.assert_called_once_with("red-1", "a")


def test_delete_surfaces_the_still_attached_refusal(route_app):
    module, client, flash, app = route_app
    client.delete_redirect.side_effect = ApiClientError("Redirect is attached to a service", status_code=409)

    with app.test_request_context("/redirects/delete", method="POST", data={"redirect_id": "red-1"}):
        module.redirects_delete.__wrapped__()

    assert "attached to a service" in flash.call_args.args[0]
    assert flash.call_args.args[1] == "error"


def test_mutations_are_blocked_in_read_only_mode(route_app):
    module, client, _, app = route_app
    client.readonly = True

    for endpoint, data in (
        (module.redirects_create, {"name": "docs", "to_url": "https://x.example.com"}),
        (module.redirects_update, {"redirect_id": "red-1", "to_url": "https://x.example.com"}),
        (module.redirects_delete, {"redirect_id": "red-1"}),
        (module.redirects_attach, {"redirect_id": "red-1", "service_ids": ["a"]}),
        (module.redirects_detach, {"redirect_id": "red-1", "service_id": "a"}),
    ):
        with app.test_request_context("/redirects", method="POST", data=data):
            endpoint.__wrapped__()

    client.create_redirect.assert_not_called()
    client.update_redirect.assert_not_called()
    client.delete_redirect.assert_not_called()
    client.attach_redirect.assert_not_called()
    client.detach_redirect.assert_not_called()

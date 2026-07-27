"""Upstream UI client and Flask route contracts."""

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
def upstreams_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    module_name = "app.routes._upstreams_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "upstreams.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "app.utils": app_utils, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client, app_utils.flash


@pytest.fixture
def route_app(upstreams_route):
    module, client, flash = upstreams_route
    client.reset_mock(return_value=True, side_effect=True)
    flash.reset_mock()
    client.readonly = False
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.upstreams)
    return module, client, flash, app


def _server_form(hosts, **overrides):
    """Build the parallel form lists the editor submits, one entry per server."""
    form = {
        "server_host": hosts,
        "server_weight": ["1"] * len(hosts),
        "server_max_fails": ["1"] * len(hosts),
        "server_fail_timeout": ["10s"] * len(hosts),
        "server_role": ["primary"] * len(hosts),
    }
    form.update(overrides)
    return form


def test_api_client_paths_and_payloads(api_client, monkeypatch):
    get = Mock(side_effect=[{"upstreams": []}, {"upstream": {"id": "up-1"}}])
    post = Mock(return_value={"status": "success"})
    patch_request = Mock(return_value={"status": "success"})
    delete = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_get", get)
    monkeypatch.setattr(api_client, "_post", post)
    monkeypatch.setattr(api_client, "_patch", patch_request)
    monkeypatch.setattr(api_client, "_delete", delete)

    api_client.get_upstreams(search="pool", service_id="svc", offset=10, limit=20)
    assert api_client.get_upstream("up-1") == {"id": "up-1"}
    api_client.create_upstream(name="web_pool", servers=[{"host": "10.0.0.1"}])
    api_client.update_upstream("up-1", method="least_conn")
    api_client.attach_upstream("up-1", "svc", match_path="/api")
    api_client.detach_upstream("up-1", "svc", match_path="/api")
    api_client.detach_upstream("up-1", "svc")
    api_client.delete_upstream("up-1")

    assert get.call_args_list == [
        call("/upstreams", params={"offset": 10, "limit": 20, "search": "pool", "service_id": "svc"}),
        call("/upstreams/up-1"),
    ]
    assert post.call_args_list == [
        call("/upstreams", json={"name": "web_pool", "servers": [{"host": "10.0.0.1"}]}),
        call("/upstreams/up-1/attachments", json={"service_id": "svc", "match_path": "/api"}),
    ]
    patch_request.assert_called_once_with("/upstreams/up-1", json={"method": "least_conn"})
    # Without a path every attachment of that pool on the service is detached.
    assert delete.call_args_list == [
        call("/upstreams/up-1/attachments/svc", params={"match_path": "/api"}),
        call("/upstreams/up-1/attachments/svc", params=None),
        call("/upstreams/up-1"),
    ]


def test_page_loads_pools_and_services(route_app, monkeypatch):
    module, client, _, app = route_app
    pool = {"id": "up-1", "name": "web_pool", "servers": [{"host": "10.0.0.1"}], "services": []}
    client.get_upstreams.return_value = {"upstreams": [pool], "total": 2}
    client.get_services.return_value = [{"id": "svc"}]
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/upstreams"):
        assert module.upstreams_page.__wrapped__() == "rendered"

    client.get_upstreams.assert_called_once_with(limit=500)
    client.get_services.assert_called_once_with(with_drafts=True)
    context = render.call_args.kwargs
    assert context["upstreams"] == [pool]
    assert context["truncated"] is True
    assert context["methods"] == ("round_robin", "least_conn", "ip_hash")
    assert context["protocols"] == ("http", "grpc", "stream")


def test_page_survives_an_api_failure(route_app, monkeypatch):
    module, client, flash, app = route_app
    client.get_upstreams.side_effect = ApiClientError("boom", status_code=502)
    client.get_services.return_value = []
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/upstreams"):
        assert module.upstreams_page.__wrapped__() == "rendered"

    assert render.call_args.kwargs["upstreams"] == []
    assert flash.call_args_list[0].args[1] == "error"


def test_create_forwards_the_pool_and_the_selected_services(route_app):
    module, client, _, app = route_app
    form = _server_form(
        ["10.0.0.1:8080", "10.0.0.2:8080"],
        server_weight=["2", "1"],
        server_role=["primary", "backup"],
    )
    form |= {
        "name": "web_pool",
        "method": "least_conn",
        "keepalive": "32",
        "description": "Shared backends",
        "service_ids": ["svc", "svc2"],
        "match_path": "/api",
    }

    with app.test_request_context("/upstreams/create", method="POST", data=form):
        module.upstreams_create.__wrapped__()

    payload = client.create_upstream.call_args.kwargs
    assert payload["name"] == "web_pool" and payload["method"] == "least_conn" and payload["keepalive"] == 32
    assert payload["protocol"] == "http" and payload["backend_ssl"] is False
    assert payload["servers"] == [
        {"host": "10.0.0.1:8080", "weight": 2, "max_fails": 1, "fail_timeout": "10s", "backup": False, "down": False},
        {"host": "10.0.0.2:8080", "weight": 1, "max_fails": 1, "fail_timeout": "10s", "backup": True, "down": False},
    ]
    assert payload["services"] == [{"service_id": "svc", "match_path": "/api"}, {"service_id": "svc2", "match_path": "/api"}]


def test_create_applies_defaults_and_refuses_bad_input(route_app):
    module, client, flash, app = route_app

    with app.test_request_context("/upstreams/create", method="POST", data=_server_form(["10.0.0.1"]) | {"name": "web_pool"}):
        module.upstreams_create.__wrapped__()
    payload = client.create_upstream.call_args.kwargs
    assert payload["method"] == "round_robin"
    # An emptied keepalive field is an explicit "no keepalive", not an omission.
    assert payload["keepalive"] is None
    assert payload["services"] == []

    for data, reason in (
        (_server_form([]) | {"name": "web_pool"}, "at least one server"),
        (_server_form(["10.0.0.1"]) | {"name": "web_pool", "method": "magic"}, "method must be one of"),
        (_server_form(["10.0.0.1"]) | {"name": "web_pool", "protocol": "carrier_pigeon"}, "protocol must be one of"),
        (_server_form(["10.0.0.1"]) | {"name": "web_pool", "keepalive": "0"}, "keepalive count"),
        (_server_form(["10.0.0.1"]) | {"name": "web_pool", "match_path": "api", "service_ids": ["svc"]}, "must start with /"),
        (_server_form(["10.0.0.1"], server_weight=["many"]) | {"name": "web_pool"}, "whole numbers"),
    ):
        client.reset_mock()
        with app.test_request_context("/upstreams/create", method="POST", data=data):
            module.upstreams_create.__wrapped__()
        client.create_upstream.assert_not_called()
        assert reason.lower() in flash.call_args.args[0].lower()
        assert flash.call_args.args[1] == "error"


def test_blank_server_rows_are_ignored(route_app):
    module, client, _, app = route_app
    # The editor keeps empty slots around; they are unused rows, not an error.
    form = _server_form(["10.0.0.1", "", "10.0.0.2"]) | {"name": "web_pool"}

    with app.test_request_context("/upstreams/create", method="POST", data=form):
        module.upstreams_create.__wrapped__()

    assert [server["host"] for server in client.create_upstream.call_args.kwargs["servers"]] == ["10.0.0.1", "10.0.0.2"]


def test_update_sends_only_the_submitted_fields(route_app):
    module, client, _, app = route_app

    with app.test_request_context("/upstreams/update", method="POST", data={"upstream_id": "up-1", "method": "ip_hash"}):
        module.upstreams_update.__wrapped__()

    # Name, description, keepalive and servers are absent, so the PATCH must leave them alone.
    # backend_ssl is always sent: an unchecked switch submits nothing and that is a real "no".
    assert client.update_upstream.call_args == call("up-1", method="ip_hash", backend_ssl=False)

    # An emptied keepalive is submitted as a present-but-blank field and must clear it.
    client.reset_mock()
    with app.test_request_context("/upstreams/update", method="POST", data={"upstream_id": "up-1", "name": "web_pool", "keepalive": ""}):
        module.upstreams_update.__wrapped__()
    assert client.update_upstream.call_args.kwargs["keepalive"] is None


def test_attach_loops_over_services_and_detach_takes_one(route_app):
    module, client, _, app = route_app

    with app.test_request_context("/upstreams/attach", method="POST", data={"upstream_id": "up-1", "service_ids": ["a", "b"], "match_path": "/api"}):
        module.upstreams_attach.__wrapped__()
    assert client.attach_upstream.call_args_list == [call("up-1", "a", match_path="/api"), call("up-1", "b", match_path="/api")]

    with app.test_request_context("/upstreams/detach", method="POST", data={"upstream_id": "up-1", "service_id": "a", "match_path": "/api"}):
        module.upstreams_detach.__wrapped__()
    client.detach_upstream.assert_called_once_with("up-1", "a", match_path="/api")


def test_delete_surfaces_the_still_attached_refusal(route_app):
    module, client, flash, app = route_app
    client.delete_upstream.side_effect = ApiClientError("Upstream is attached to a service", status_code=409)

    with app.test_request_context("/upstreams/delete", method="POST", data={"upstream_id": "up-1"}):
        module.upstreams_delete.__wrapped__()

    assert "attached to a service" in flash.call_args.args[0]
    assert flash.call_args.args[1] == "error"


def test_mutations_are_blocked_in_read_only_mode(route_app):
    module, client, _, app = route_app
    client.readonly = True

    for endpoint, data in (
        (module.upstreams_create, _server_form(["10.0.0.1"]) | {"name": "web_pool"}),
        (module.upstreams_update, {"upstream_id": "up-1", "method": "ip_hash"}),
        (module.upstreams_delete, {"upstream_id": "up-1"}),
        (module.upstreams_attach, {"upstream_id": "up-1", "service_ids": ["a"]}),
        (module.upstreams_detach, {"upstream_id": "up-1", "service_id": "a"}),
    ):
        with app.test_request_context("/upstreams", method="POST", data=data):
            endpoint.__wrapped__()

    client.create_upstream.assert_not_called()
    client.update_upstream.assert_not_called()
    client.delete_upstream.assert_not_called()
    client.attach_upstream.assert_not_called()
    client.detach_upstream.assert_not_called()

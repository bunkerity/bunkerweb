"""Every instance/config/service route enforces its signed resource/action grant over HTTP."""

import importlib
from base64 import b64encode
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bcrypt import gensalt, hashpw
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from _api_http_helpers import ADMIN_TOKEN
from test_configs_move_authz import _token

import app.auth.biscuit as biscuit
import app.auth.guard as auth
import app.deps as deps
import app.routers.configs as configs
import app.routers.instances as instances
import app.routers.services as services
import app.utils as utils
from app.config import api_config
from model import API_PERMISSION_ENUM, API_RESOURCE_ENUM

_BASIC_HASH = hashpw(b"correct", gensalt(rounds=4))


@pytest.fixture
def api_routes(monkeypatch):
    database = Mock()
    instant = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    instance = {"hostname": "node", "method": "api", "creation_date": instant, "last_seen": None}
    snippet = {"service_id": "example", "type": "http", "name": "snippet", "data": b"old", "method": "api", "is_draft": True}
    snapshot = {"SERVER_NAME": "example other", "example_SERVER_NAME": "example alias", "example_USE_GZIP": "yes", "other_USE_GZIP": "no"}
    database.get_instance.side_effect = lambda *_: deepcopy(instance)
    database.get_instances.side_effect = lambda: [deepcopy(instance)]
    database.get_services.side_effect = lambda **_: [{"id": "example", "method": "api", "creation_date": instant, "last_update": None}]
    database.get_custom_config.side_effect = lambda *_, **__: deepcopy(snippet)
    database.get_custom_configs.side_effect = lambda **_: [deepcopy(snippet)]
    database.get_config.side_effect = lambda **_: {"SERVER_NAME": "example other", "API_HTTPS_PORT": "5443"}
    database.get_non_default_settings.side_effect = lambda **_: deepcopy(snapshot)
    database.add_instance.return_value = ""
    database.update_instance_fields.return_value = ""
    database.delete_instance.return_value = ""
    database.delete_instances.return_value = ""
    database.upsert_custom_config.return_value = ""
    database.delete_custom_configs.return_value = ("", {("example", "http", "snippet")}, set())
    database.save_config.return_value = {"gzip", "general"}
    database.is_valid_setting.return_value = (True, "")

    for module in (instances, configs, services, deps):
        monkeypatch.setattr(module, "get_db", lambda **_: database)
    for key, value in {"API_RATE_LIMIT_ENABLED": "no", "API_WHITELIST_ENABLED": "no", "API_ALLOWED_HOSTS": "", "API_ROOT_PATH": None}.items():
        monkeypatch.setattr(api_config, key, value)
    monkeypatch.setattr(auth, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    auth_database = Mock()
    auth_database.get_api_user.return_value = {"admin": True, "password": _BASIC_HASH}
    monkeypatch.setattr(auth, "get_api_db", lambda **_: auth_database)
    monkeypatch.setattr(auth.guard, "_admin_cache", {})
    monkeypatch.setattr(
        biscuit,
        "api_config",
        SimpleNamespace(API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None, biscuit_ttl_seconds=60, check_private_ip=True),
    )
    monkeypatch.setattr(instances, "api_config", SimpleNamespace(internal_api_host_header="bwapi", internal_api_port="5000"))
    # core checks API users at import; leave every imported route's real guards intact.
    with monkeypatch.context() as bootstrap:
        bootstrap.setattr(utils, "get_api_db", lambda **_: database)
        main = importlib.import_module("app.main")
    application = main.create_app()
    broadcast = Mock()
    broadcast.send_to_apis.return_value = (True, {"node": {"status": "ok"}})
    api = Mock()
    api.request.return_value = (True, "", 200, {"status": "ok"})
    application.dependency_overrides[deps.get_instances_api_caller] = lambda: broadcast
    application.dependency_overrides[deps.get_api_for_hostname] = lambda: api
    single = Mock()
    single.send_to_apis.return_value = (True, {})
    factory = Mock(return_value=single)
    monkeypatch.setattr(instances, "ApiCaller", factory)
    database.reset_mock()
    with TestClient(application, client=("127.0.0.1", 50000), raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client,
            database=database,
            auth_database=auth_database,
            api=api,
            broadcast=broadcast,
            single=single,
            factory=factory,
            snapshot=snapshot,
            instant=instant,
        )


# method, path, persisted permission, path resource id (None means wildcard required), body, expected status, observable action
ROUTES = [
    ("GET", "/instances/ping", "instances_read", None, {}, 200, "broadcast"),
    ("POST", "/instances/reload", "instances_execute", None, {}, 200, "broadcast"),
    ("POST", "/instances/stop", "instances_execute", None, {}, 200, "broadcast"),
    ("GET", "/instances/node/ping", "instances_read", "node", {}, 200, "instance"),
    ("POST", "/instances/node/reload", "instances_execute", "node", {}, 200, "single"),
    ("POST", "/instances/node/stop", "instances_execute", "node", {}, 200, "instance"),
    ("GET", "/instances", "instances_read", None, {}, 200, "get_instances"),
    ("POST", "/instances", "instances_create", None, {"json": {"hostname": "new-node"}}, 201, "add_instance"),
    ("GET", "/instances/node", "instances_read", "node", {}, 200, "get_instance"),
    ("PATCH", "/instances/node", "instances_update", "node", {"json": {"name": "new name"}}, 200, "update_instance_fields"),
    ("DELETE", "/instances/node", "instances_delete", "node", {}, 200, "delete_instance"),
    ("DELETE", "/instances", "instances_delete", None, {"json": {"instances": ["node"]}}, 200, "delete_instances"),
    ("GET", "/configs", "configs_read", None, {}, 200, "get_custom_configs"),
    (
        "POST",
        "/configs/upload",
        "config_create",
        None,
        {"data": {"type": "http", "service": "example"}, "files": {"files": ("snippet.conf", b"new")}},
        201,
        "upsert_custom_config",
    ),
    ("GET", "/configs/example/http/snippet", "config_read", "example", {}, 200, "get_custom_config"),
    (
        "POST",
        "/configs",
        "config_create",
        None,
        {"json": {"service": "example", "type": "http", "name": "snippet", "data": "new"}},
        201,
        "upsert_custom_config",
    ),
    ("PATCH", "/configs/example/http/snippet", "config_update", "example", {"json": {"data": "new"}}, 200, "upsert_custom_config"),
    ("PATCH", "/configs/example/http/snippet/upload", "config_update", "example", {"files": {"file": ("snippet.conf", b"new")}}, 200, "upsert_custom_config"),
    (
        "DELETE",
        "/configs",
        "config_delete",
        None,
        {"json": {"configs": [{"service": "example", "type": "http", "name": "snippet"}]}},
        200,
        "delete_custom_configs",
    ),
    ("DELETE", "/configs/example/http/snippet", "config_delete", "example", {}, 200, "delete_custom_configs"),
    ("GET", "/services", "service_read", None, {}, 200, "get_services"),
    ("GET", "/services/example", "service_read", "example", {}, 200, "get_config"),
    ("POST", "/services", "service_create", None, {"json": {"server_name": "new.example"}}, 200, "save_config"),
    ("PATCH", "/services/example", "service_update", "example", {"json": {"variables": {"USE_GZIP": "no"}}}, 200, "save_config"),
    ("DELETE", "/services/example", "service_delete", "example", {}, 200, "save_config"),
    ("POST", "/services/example/convert?convert_to=online", "service_convert", "example", {}, 200, "save_config"),
]


def test_route_matrix_covers_every_registered_method():
    registered = {
        (method, route.path)
        for module in (instances, configs, services)
        for route in module.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    # Compare endpoint identities, so newly added routes cannot escape the matrix silently.
    represented = set()
    for method, path, *_ in ROUTES:
        for module in (instances, configs, services):
            for route in module.router.routes:
                match, _ = route.matches({"type": "http", "method": method, "path": path.split("?")[0]})
                if match.name == "FULL":
                    represented.add((method, route.path))
    assert represented == registered


@pytest.mark.parametrize("case", ROUTES, ids=[f"{row[0]}-{row[1]}" for row in ROUTES])
@pytest.mark.parametrize(
    "credential",
    [
        "wildcard",
        "scoped",
        "biscuit-admin",
        "api-token",
        "basic-admin",
        "basic-nonadmin",
        "basic-wrong-password",
        "no-grant",
        "wrong-type",
        "wrong-permission",
        "wrong-id",
        "coarse",
        "malformed",
        "missing",
    ],
)
def test_route_permission_matrix(api_routes, case, credential, request):
    method, path, permission, rid, kwargs, status, action = case
    resource = path.split("/")[1]
    assert resource in API_RESOURCE_ENUM.enums
    assert permission in API_PERMISSION_ENUM.enums
    allowed = credential in {"wildcard", "biscuit-admin", "api-token", "basic-admin"} or credential == "scoped" and rid is not None
    grants = {
        "wildcard": (resource, "*", permission),
        "scoped": (resource, rid or "unrelated", permission),
        "wrong-type": ("services" if resource != "services" else "instances", "*", permission),
        "wrong-permission": (resource, "*", "service_delete" if permission != "service_delete" else "service_read"),
        "wrong-id": (resource, "unrelated", permission),
    }
    if credential == "api-token":
        token = ADMIN_TOKEN
    elif credential == "malformed":
        token = "not-a-signed-token"
    elif credential == "coarse":
        from biscuit_auth import BiscuitBuilder
        from _api_http_helpers import VERSION, _KEYPAIR

        token = (
            BiscuitBuilder(
                'version({version}); time({now}); client_ip("127.0.0.1"); role("api_user", ["read", "write"]);',
                {"version": VERSION, "now": datetime.now(timezone.utc)},
            )
            .build(_KEYPAIR.private_key)
            .to_base64()
        )
    else:
        token = _token(*([grants[credential]] if credential in grants else []), admin=credential == "biscuit-admin")
    headers = {} if credential == "missing" else {"Authorization": f"Bearer {token}"}
    if credential.startswith("basic-"):
        api_routes.auth_database.get_api_user.return_value["admin"] = credential != "basic-nonadmin"
        password = "wrong" if credential == "basic-wrong-password" else "correct"
        headers = {"Authorization": "Basic " + b64encode(f"matrix-admin:{password}".encode()).decode()}
    response = api_routes.client.request(method, path, headers=headers, **kwargs)
    if not allowed:
        code = 401 if credential in {"malformed", "missing", "basic-nonadmin", "basic-wrong-password"} else 403
        assert response.status_code == code, response.text
        assert response.json() == {"status": "error", "message": "Unauthorized" if code == 401 else "Forbidden"}
        assert api_routes.database.mock_calls == []
        assert api_routes.broadcast.mock_calls == []
        assert api_routes.api.mock_calls == []
        assert api_routes.factory.mock_calls == []
        return
    if method == "PATCH" and path == "/instances/node":
        api_routes.database.update_instance_fields.assert_called_once_with(
            "node", name="new name", port=None, server_name=None, method=None, listen_https=None, https_port=None
        )
    assert response.status_code == status, response.text
    if action == "broadcast" and method == "GET":
        assert response.json() == {"node": {"status": "ok"}}
    else:
        assert response.json()["status"] == ("ok" if action == "instance" and method == "GET" else "success")
    if action == "broadcast":
        api_routes.broadcast.send_to_apis.assert_called_once()
    elif action == "instance":
        api_routes.api.request.assert_called_once()
    elif action == "single":
        api_routes.factory.assert_called_once_with([api_routes.api])
        api_routes.single.send_to_apis.assert_called_once()
    else:
        getattr(api_routes.database, action).assert_called_once()


@pytest.mark.parametrize("state", ["seen", "unseen", "missing"])
def test_instance_patch_serializes_dates(api_routes, state):
    instance = (
        None
        if state == "missing"
        else {
            "hostname": "node",
            "creation_date": api_routes.instant,
            "last_seen": api_routes.instant if state == "seen" else None,
        }
    )
    api_routes.database.get_instance.side_effect = lambda *_: deepcopy(instance)
    response = api_routes.client.patch("/instances/node", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}, json={"name": "new name"})
    assert response.status_code == 200, response.text
    if instance:
        instance["creation_date"] = api_routes.instant.astimezone().isoformat()
        instance["last_seen"] = api_routes.instant.astimezone().isoformat() if state == "seen" else None
    assert response.json() == {"status": "success", "instance": instance}
    api_routes.database.update_instance_fields.assert_called_once_with(
        "node", name="new name", port=None, server_name=None, method=None, listen_https=None, https_port=None
    )

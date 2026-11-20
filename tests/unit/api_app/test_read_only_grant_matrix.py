"""Every API route is classified independently of the permission resolver under test."""

import importlib
import re
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient
import pytest

from _api_http_helpers import ADMIN_TOKEN
from test_configs_move_authz import _token

import app.auth.biscuit as biscuit
import app.auth.guard as auth
import app.deps as deps
import app.utils as utils
from app.config import api_config
from model import API_PERMISSION_ENUM, API_RESOURCE_ENUM

READ_PAIRS = {
    ("GET", path)
    for path in (
        "/instances/ping",
        "/instances/{hostname}/ping",
        "/instances",
        "/instances/{hostname}",
        "/bans",
        "/global_settings",
        "/global_config",
        "/services",
        "/services/{service}",
        "/configs",
        "/configs/{service}/{config_type}/{name}",
        "/plugins",
        "/cache",
        "/cache/{service}/{plugin_id}/{job_name}/{file_name}",
        "/jobs",
        "/crowdsec",
        "/crowdsec/{connection_id}/decisions",
        "/crowdsec/{connection_id}/alerts/{alert_id}",
        "/crowdsec/{connection_id}/allowlists",
        "/crowdsec/{connection_id}/allowlists/check",
        "/crowdsec/{connection_id}/ips/{ip}",
    )
}

WRITE_PAIRS = {
    ("POST", "/instances/reload"),
    ("POST", "/instances/stop"),
    ("POST", "/instances/{hostname}/reload"),
    ("POST", "/instances/{hostname}/stop"),
    ("POST", "/instances"),
    ("PATCH", "/instances/{hostname}"),
    ("DELETE", "/instances/{hostname}"),
    ("DELETE", "/instances"),
    ("POST", "/bans"),
    ("POST", "/bans/ban"),
    ("DELETE", "/bans"),
    ("POST", "/bans/unban"),
    ("PATCH", "/global_settings"),
    ("PATCH", "/global_config"),
    ("POST", "/services"),
    ("PATCH", "/services/{service}"),
    ("DELETE", "/services/{service}"),
    ("POST", "/services/{service}/convert"),
    ("POST", "/configs/upload"),
    ("POST", "/configs"),
    ("PATCH", "/configs/{service}/{config_type}/{name}"),
    ("PATCH", "/configs/{service}/{config_type}/{name}/upload"),
    ("DELETE", "/configs"),
    ("DELETE", "/configs/{service}/{config_type}/{name}"),
    ("DELETE", "/plugins/{plugin_id}"),
    ("POST", "/plugins/upload"),
    ("DELETE", "/cache"),
    ("DELETE", "/cache/{service}/{plugin_id}/{job_name}/{file_name}"),
    ("POST", "/jobs/run"),
    ("DELETE", "/crowdsec/{connection_id}/decisions/{decision_id}"),
}

PUBLIC_PAIRS = {
    ("GET", "/ping"),
    ("GET", "/health"),
    ("POST", "/auth"),
    ("GET", "/openapi.yaml"),
    *((method, path) for path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc") for method in ("GET", "HEAD")),
}

# Persisted resource types differ from permission prefixes (including CrowdSec and config lists).
READ_GRANTS = {
    ("instances", "*", "instances_read"),
    ("global_config", "*", "global_config_read"),
    ("services", "*", "service_read"),
    ("configs", "*", "configs_read"),
    ("configs", "*", "config_read"),
    ("plugins", "*", "plugin_read"),
    ("cache", "*", "cache_read"),
    ("bans", "*", "ban_read"),
    ("bans", "*", "crowdsec_read"),
    ("jobs", "*", "job_read"),
}


with pytest.MonkeyPatch.context() as bootstrap:
    # core decides whether to register /auth at import, before create_app is called.
    bootstrap.setattr(utils, "get_api_db", lambda **_: SimpleNamespace(has_api_user=lambda: True))
    bootstrap.setattr(api_config, "API_RATE_LIMIT_ENABLED", "no")
    main = importlib.import_module("app.main")


@pytest.fixture
def read_only_api(monkeypatch):
    for key, value in {
        "API_RATE_LIMIT_ENABLED": "no",
        "API_WHITELIST_ENABLED": "no",
        "API_ALLOWED_HOSTS": "",
        "API_ROOT_PATH": None,
        "API_TOKEN": None,
        "API_DOCS_URL": "/docs",
        "API_REDOC_URL": "/redoc",
        "API_OPENAPI_URL": "/openapi.json",
    }.items():
        monkeypatch.setattr(api_config, key, value)
    monkeypatch.setattr(auth, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    monkeypatch.setattr(
        biscuit,
        "api_config",
        SimpleNamespace(API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None, biscuit_ttl_seconds=60, check_private_ip=True),
    )
    application = main.create_app()
    backends = Mock()
    # A controlled backend response proves reads passed the real guard, without live DB/network I/O.
    for name in ("get_db", "get_api_db", "get_instances_api_caller", "get_api_for_hostname", "ApiCaller", "CrowdSecClient"):
        getattr(backends, name).side_effect = HTTPException(status_code=503, detail="matrix backend reached")
    modules = {utils, deps, auth}
    modules.update(importlib.import_module(route.endpoint.__module__) for route in iter_route_contexts(application.routes))
    for module in modules:
        for name in ("get_db", "get_api_db", "ApiCaller", "CrowdSecClient"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, getattr(backends, name))
    application.dependency_overrides[deps.get_instances_api_caller] = lambda: backends.get_instances_api_caller()
    application.dependency_overrides[deps.get_api_for_hostname] = lambda: backends.get_api_for_hostname()
    with TestClient(application, client=("127.0.0.1", 50000), raise_server_exceptions=False) as client:
        yield SimpleNamespace(client=client, backends=backends)


def _url(path):
    values = {name: "example" for name in re.findall(r"\{([^}:]+)(?::[^}]+)?\}", path)}
    values.update(ip="192.0.2.1", alert_id="1", decision_id="1", config_type="http", service="global")
    url = path.format(**values)
    return url + "?ip=192.0.2.1" if path.endswith("/allowlists/check") else url


def test_api_route_classes_cover_app(read_only_api):
    classified = READ_PAIRS | WRITE_PAIRS | PUBLIC_PAIRS
    assert len(classified) == len(READ_PAIRS) + len(WRITE_PAIRS) + len(PUBLIC_PAIRS), "overlapping API route classes"
    registered = [(method, route.path) for route in iter_route_contexts(read_only_api.client.app.routes) for method in sorted(route.methods or ())]
    assert len(registered) == len(set(registered)), "duplicate registered API method/path"
    assert set(registered) == classified, f"unclassified: {set(registered) - classified}; stale: {classified - set(registered)}"
    assert {permission for _, _, permission in READ_GRANTS} == {permission for permission in API_PERMISSION_ENUM.enums if permission.endswith("_read")}
    assert all(resource in API_RESOURCE_ENUM.enums and rid == "*" for resource, rid, _ in READ_GRANTS)
    for route in iter_route_contexts(read_only_api.client.app.routes):
        for method in route.methods or ():
            if (method, route.path) in PUBLIC_PAIRS:
                continue
            dependencies = route.dependant.dependencies  # codespell:ignore dependant
            assert any(dependency.call is auth.guard for dependency in dependencies), f"{method} {route.path} lost its guard"
            resource, permission = biscuit._resolve_resource_and_perm(_url(route.path).split("?")[0], method)
            assert resource in API_RESOURCE_ENUM.enums
            assert permission in API_PERMISSION_ENUM.enums


@pytest.mark.parametrize("method,path", sorted(WRITE_PAIRS), ids=[f"{method} {path}" for method, path in sorted(WRITE_PAIRS)])
def test_read_only_token_denied_on_every_write_pair(read_only_api, method, path):
    response = read_only_api.client.request(method, _url(path), json={}, headers={"Authorization": f"Bearer {_token(*sorted(READ_GRANTS))}"})
    assert read_only_api.backends.mock_calls == []
    assert response.status_code == 403, response.text
    assert response.json() == {"status": "error", "message": "Forbidden"}


@pytest.mark.parametrize("method,path", sorted(READ_PAIRS), ids=[f"{method} {path}" for method, path in sorted(READ_PAIRS)])
def test_read_only_token_not_refused_on_read_pairs(read_only_api, method, path):
    response = read_only_api.client.request(method, _url(path), headers={"Authorization": f"Bearer {_token(*sorted(READ_GRANTS))}"})
    assert response.status_code not in (401, 403), response.text
    assert response.status_code == 503, response.text
    assert response.json() == {"status": "error", "message": "matrix backend reached"}
    assert read_only_api.backends.mock_calls

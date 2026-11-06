"""UB4-1: every registered management route rejects missing or insufficient credentials."""

import importlib
import re
from datetime import datetime, timezone
from types import SimpleNamespace

from biscuit_auth import BiscuitBuilder
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient
import pytest

from _api_http_helpers import VERSION, _KEYPAIR
from test_configs_move_authz import _token

import app.auth.biscuit as biscuit
import app.auth.guard as auth
import app.deps as deps
import app.utils as utils
from app.config import api_config

# Exact method/path pairs: a new route never inherits a public prefix exemption.
PUBLIC = {
    ("GET", "/ping"): "core.py:ping is the public liveness probe",
    ("GET", "/health"): "core.py:health probes the API without calling instances",
    ("POST", "/auth"): "auth.py:login verifies credentials itself to issue a Biscuit",
    ("GET", "/openapi.yaml"): "main.py:read_openapi_yaml publishes the API schema without a guard",
    **{
        (method, path): "main.py:create_app enables public FastAPI documentation/schema endpoints"
        for path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")
        for method in ("GET", "HEAD")
    },
}


def _application_module():
    # core checks API users at import; disable rate limiting before main creates its global app.
    with pytest.MonkeyPatch.context() as bootstrap:
        bootstrap.setattr(utils, "get_api_db", lambda **_: SimpleNamespace(has_api_user=lambda: True))
        bootstrap.setattr(api_config, "API_RATE_LIMIT_ENABLED", "no")
        return importlib.import_module("app.main")


main = _application_module()
with pytest.MonkeyPatch.context() as bootstrap:
    bootstrap.setattr(api_config, "API_RATE_LIMIT_ENABLED", "no")
    # iter_route_contexts expands FastAPI's lazy included routers, including inherited dependencies.
    PROTECTED = [
        (method, route.path)
        for route in iter_route_contexts(main.create_app().routes)
        for method in sorted(route.methods or ())
        if (method, route.path) not in PUBLIC
    ]


@pytest.fixture
def protected_client(monkeypatch):
    for key, value in {
        "API_RATE_LIMIT_ENABLED": "no",
        "API_WHITELIST_ENABLED": "no",
        "API_ALLOWED_HOSTS": "",
        "API_ROOT_PATH": None,
        "API_TOKEN": None,
    }.items():
        monkeypatch.setattr(api_config, key, value)

    def forbidden_backend(**_):
        raise AssertionError("an unauthorized request reached a backend")

    application = main.create_app()
    for route in iter_route_contexts(application.routes):
        module = importlib.import_module(route.endpoint.__module__)
        if hasattr(module, "get_db"):
            monkeypatch.setattr(module, "get_db", forbidden_backend)
    application.dependency_overrides[deps.get_instances_api_caller] = forbidden_backend
    application.dependency_overrides[deps.get_api_for_hostname] = forbidden_backend
    return TestClient(application, client=("127.0.0.1", 50000), raise_server_exceptions=False)


@pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{method} {path}" for method, path in PROTECTED])
@pytest.mark.parametrize("credential", ["missing", "insufficient"])
def test_every_protected_route_refuses_unauthorized_requests(protected_client, method, path, credential):
    values = {name: "example" for name in re.findall(r"\{([^}:]+)(?::[^}]+)?\}", path)}
    values.update(ip="192.0.2.1", alert_id="1", decision_id="1", config_type="http", service="global")
    url = path.format(**values)
    headers = {}
    if credential == "insufficient":
        _, permission = biscuit._resolve_resource_and_perm(url, method)
        # Coarse read/write cannot stand in for a required resource/action grant.
        token = (
            BiscuitBuilder(
                'version({version}); time({now}); client_ip("127.0.0.1"); role("api_user", ["read", "write"]);',
                {"version": VERSION, "now": datetime.now(timezone.utc)},
            )
            .build(_KEYPAIR.private_key)
            .to_base64()
            if permission
            else _token()
        )
        headers["Authorization"] = f"Bearer {token}"
    response = protected_client.request(method, url, json={}, headers=headers)
    expected = 401 if credential == "missing" else 403
    assert response.status_code == expected, response.text
    assert response.json() == {"status": "error", "message": "Unauthorized" if expected == 401 else "Forbidden"}
    route = next(route for route in iter_route_contexts(protected_client.app.routes) if route.path == path and method in route.methods)
    assert any(dependency.call is auth.guard for dependency in route.dependant.dependencies), f"{method} {path} lost its guard"  # codespell:ignore dependant

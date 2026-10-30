"""Application setup preserves host/IP restrictions and normalized HTTP errors."""

import importlib
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from yaml import CSafeLoader, load

from _api_http_helpers import VERSION  # noqa: F401 - import bootstrap

from app.config import api_config
import app.utils as utils


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setattr(api_config, "API_RATE_LIMIT_ENABLED", "no")
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", "no")
    monkeypatch.setattr(api_config, "API_ALLOWED_HOSTS", "")
    monkeypatch.setattr(api_config, "API_ROOT_PATH", None)
    db = Mock()
    db.get_config.return_value = {"API_SERVER_NAME": "bwapi"}
    # core.py checks for API users at import; don't capture a fake get_db in other routers.
    with monkeypatch.context() as bootstrap:
        bootstrap.setattr(utils, "get_api_db", lambda **_: db)
        main = importlib.import_module("app.main")
    monkeypatch.setattr(utils, "get_db", lambda **_: db)
    monkeypatch.setattr(utils, "_DB_INSTANCE", None)
    monkeypatch.setattr(utils, "_API_DB_INSTANCE", None)
    return main


def test_real_app_openapi_json_and_yaml_share_routes(application):
    app = application.create_app()
    with TestClient(app, client=("127.0.0.1", 5000)) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "/plugins/upload" in schema["paths"] and "/configs" in schema["paths"]
        yaml_response = client.get("/openapi.yaml")
        assert yaml_response.status_code == 200
        assert load(yaml_response.text, Loader=CSafeLoader) == schema
        assert "text/yaml" in yaml_response.headers["content-type"]


@pytest.mark.parametrize("code,detail,message", [(401, "denied", "denied"), (500, "failure", "failure"), (403, {"hidden": "detail"}, "error")])
def test_http_exceptions_preserve_status_auth_headers_and_normalize_body(application, code, detail, message):
    app = application.create_app()

    @app.get("/failure")
    def fail():
        raise HTTPException(code, detail, headers={"WWW-Authenticate": "Bearer"})

    response = TestClient(app).get("/failure")
    assert response.status_code == code
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {"status": "error", "message": message}


def test_unexpected_errors_hide_internal_details(application):
    app = application.create_app()

    @app.get("/failure")
    def fail():
        raise ValueError("sensitive details")

    response = TestClient(app, raise_server_exceptions=False).get("/failure")
    assert response.status_code == 500
    assert response.json() == {"status": "error", "message": "internal error"}


def test_host_allowlist_keeps_internal_host_and_rejects_foreign_host(application, monkeypatch):
    monkeypatch.setattr(api_config, "API_ALLOWED_HOSTS", "api.example.com *.example.net")
    client = TestClient(application.create_app(), client=("127.0.0.1", 5000))
    for host in ("api.example.com", "sub.example.net", "bwapi"):
        assert client.get("/ping", headers={"host": host}).status_code == 200
    assert client.get("/ping", headers={"host": "foreign.test"}).status_code == 400


def test_ip_allowlist_filters_requests_and_root_path_is_set(application, monkeypatch):
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", "yes")
    monkeypatch.setattr(api_config, "API_WHITELIST_IPS", "192.0.2.0/24, 2001:db8::1 invalid")
    monkeypatch.setattr(api_config, "API_ROOT_PATH", "/api")
    app = application.create_app()
    assert app.root_path == "/api"
    assert TestClient(app, client=("192.0.2.5", 5000)).get("/ping").status_code == 200
    assert TestClient(app, client=("2001:db8::1", 5000)).get("/ping").status_code == 200
    response = TestClient(app, client=("198.51.100.1", 5000)).get("/ping")
    assert response.status_code == 403
    assert response.json() == {"status": "error", "message": "forbidden"}


def test_lifespan_closes_each_database_even_if_one_close_fails(application, monkeypatch):
    db, api_db = Mock(), Mock()
    db.close.side_effect = RuntimeError("already closed")
    monkeypatch.setattr(utils, "_DB_INSTANCE", db)
    monkeypatch.setattr(utils, "_API_DB_INSTANCE", api_db)
    with TestClient(application.create_app()):
        db.close.assert_not_called()
    db.close.assert_called_once_with()
    api_db.close.assert_called_once_with()

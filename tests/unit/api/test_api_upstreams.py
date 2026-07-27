"""Upstream router response and rollback contracts."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import schemas  # type: ignore

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    patch = get
    delete = get


class _Response:
    def __init__(self, content=b"", *, status_code=200, media_type=None, headers=None):
        self.status_code = status_code
        self.body = content if isinstance(content, bytes) else str(content).encode()
        self.media_type = media_type
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}


class _JSONResponse(_Response):
    def __init__(self, *, status_code, content):
        super().__init__(json.dumps(content).encode(), status_code=status_code, media_type="application/json")


def _load_router():
    modules = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_upstreams": ModuleType("bw_upstreams"),
        "bw_upstreams.routers": ModuleType("bw_upstreams.routers"),
        "bw_upstreams.auth": ModuleType("bw_upstreams.auth"),
        "bw_upstreams.auth.guard": ModuleType("bw_upstreams.auth.guard"),
        "bw_upstreams.schemas": schemas,
        "bw_upstreams.utils": ModuleType("bw_upstreams.utils"),
    }
    modules["bw_upstreams"].__path__ = []
    modules["bw_upstreams.routers"].__path__ = []
    modules["bw_upstreams.auth"].__path__ = []
    modules["bw_upstreams.auth.guard"].guard = lambda: None
    modules["fastapi"].APIRouter = _Router
    modules["fastapi"].Depends = lambda dependency: dependency
    modules["fastapi"].Query = lambda default=..., **_kwargs: default
    modules["fastapi.responses"].JSONResponse = _JSONResponse
    modules["fastapi.responses"].Response = _Response
    modules["bw_upstreams.utils"].get_db = Mock()
    with patch.dict(sys.modules, modules):
        path = ROOT / "src" / "api" / "app" / "routers" / "upstreams.py"
        spec = importlib.util.spec_from_file_location("bw_upstreams.routers.upstreams", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _json(response):
    return json.loads(response.body)


def _upstream(services=None):
    return {
        "id": "up-1",
        "name": "web_pool",
        "description": "",
        "protocol": "http",
        "backend_ssl": False,
        "method": "round_robin",
        "keepalive": None,
        "servers": [{"host": "10.0.0.1:8080", "weight": 1, "max_fails": 1, "fail_timeout": "10s", "backup": False, "down": False}],
        "services": services or [],
    }


def _create_payload(**kwargs):
    return schemas.UpstreamCreateRequest(**{"name": "web_pool", "servers": [{"host": "10.0.0.1:8080"}], **kwargs})


def test_list_contract(monkeypatch):
    db = Mock()
    db.get_upstreams.return_value = {"items": [_upstream()], "total": 1, "offset": 0, "limit": 100}
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.list_upstreams(search="", service_id="", offset=0, limit=100)

    assert response.status_code == 200
    body = _json(response)
    assert body["total"] == 1 and body["upstreams"][0]["id"] == "up-1"


def test_create_attaches_every_requested_service(monkeypatch):
    db = Mock()
    db.create_upstream.return_value = ("up-1", "")
    db.attach_upstream.return_value = ""
    db.get_upstream_details.return_value = _upstream([{"service_id": "a.example.com", "match_path": "/"}])
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    payload = _create_payload(services=[{"service_id": "a.example.com"}, {"service_id": "b.example.com", "match_path": "/api"}])
    response = ROUTER.create_upstream(payload)

    assert response.status_code == 201
    assert db.attach_upstream.call_count == 2
    assert db.attach_upstream.call_args_list[1].kwargs == {"match_path": "/api"}
    assert "services" not in db.create_upstream.call_args.kwargs


def test_create_rolls_back_when_an_attachment_is_refused(monkeypatch):
    db = Mock()
    db.create_upstream.return_value = ("up-1", "")
    # The second service already proxies that path, so the whole creation must be undone
    # rather than leaving a pool attached to only half of what was asked for.
    db.attach_upstream.side_effect = ["", "Service b.example.com already has an inline reverse proxy on path /"]
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    payload = _create_payload(services=[{"service_id": "a.example.com"}, {"service_id": "b.example.com"}])
    response = ROUTER.create_upstream(payload)

    assert response.status_code == 409
    assert db.detach_upstream.call_count == 2
    db.delete_upstream.assert_called_once_with("up-1")


def test_create_reports_a_database_error_without_attaching(monkeypatch):
    db = Mock()
    db.create_upstream.return_value = ("", "Upstream name web_pool already exists")
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.create_upstream(_create_payload())

    assert response.status_code == 409
    db.attach_upstream.assert_not_called()


def test_update_sends_only_the_submitted_fields(monkeypatch):
    db = Mock()
    db.update_upstream.return_value = ""
    db.get_upstream_details.return_value = _upstream()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    ROUTER.update_upstream("up-1", schemas.UpstreamUpdateRequest(method="least_conn"))

    assert db.update_upstream.call_args.kwargs == {"method": "least_conn"}


def test_an_explicit_null_keepalive_clears_it(monkeypatch):
    db = Mock()
    db.update_upstream.return_value = ""
    db.get_upstream_details.return_value = _upstream()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    # Omitting the field keeps the stored value; sending null is the only way to turn the
    # directive off, and a plain None cannot carry that difference to the database layer.
    ROUTER.update_upstream("up-1", schemas.UpstreamUpdateRequest(keepalive=None))
    assert db.update_upstream.call_args.kwargs == {"clear_keepalive": True}

    ROUTER.update_upstream("up-1", schemas.UpstreamUpdateRequest())
    assert db.update_upstream.call_args.kwargs == {}


def test_error_status_codes(monkeypatch):
    db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    db.get_upstream_details.return_value = None
    assert ROUTER.get_upstream("missing").status_code == 404

    db.delete_upstream.return_value = "Upstream is attached to a service"
    assert ROUTER.delete_upstream("up-1").status_code == 409

    db.delete_upstream.return_value = "Upstream not found"
    assert ROUTER.delete_upstream("up-1").status_code == 404

    db.attach_upstream.return_value = "The database is read-only, the changes will not be saved"
    assert ROUTER.attach_upstream("up-1", schemas.UpstreamAttachmentRequest(service_id="a.example.com")).status_code == 409

    db.detach_upstream.return_value = "Upstream attachment not found"
    assert ROUTER.detach_upstream("up-1", "a.example.com").status_code == 404


def test_schema_rejects_bad_payloads():
    with pytest.raises(ValueError):
        _create_payload(name="  ")
    with pytest.raises(ValueError):
        schemas.UpstreamCreateRequest(name="web_pool", servers=[])
    with pytest.raises(ValueError):
        _create_payload(method="magic")
    with pytest.raises(ValueError):
        _create_payload(protocol="carrier_pigeon")
    with pytest.raises(ValueError):
        _create_payload(keepalive=0)
    with pytest.raises(ValueError):
        schemas.UpstreamAttachmentRequest(service_id="a.example.com", match_path="api")
    with pytest.raises(ValueError):
        schemas.UpstreamServerRequest(host="10.0.0.1", weight=0)

    # An unset field must stay unset so PATCH never overwrites what was not submitted.
    assert schemas.UpstreamUpdateRequest(method="ip_hash").model_dump(exclude_unset=True) == {"method": "ip_hash"}

"""Redirect router response and rollback contracts."""

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
        "bw_redirects": ModuleType("bw_redirects"),
        "bw_redirects.routers": ModuleType("bw_redirects.routers"),
        "bw_redirects.auth": ModuleType("bw_redirects.auth"),
        "bw_redirects.auth.guard": ModuleType("bw_redirects.auth.guard"),
        "bw_redirects.schemas": schemas,
        "bw_redirects.utils": ModuleType("bw_redirects.utils"),
    }
    modules["bw_redirects"].__path__ = []
    modules["bw_redirects.routers"].__path__ = []
    modules["bw_redirects.auth"].__path__ = []
    modules["bw_redirects.auth.guard"].guard = lambda: None
    modules["fastapi"].APIRouter = _Router
    modules["fastapi"].Depends = lambda dependency: dependency
    modules["fastapi"].Query = lambda default=..., **_kwargs: default
    modules["fastapi.responses"].JSONResponse = _JSONResponse
    modules["fastapi.responses"].Response = _Response
    modules["bw_redirects.utils"].get_db = Mock()
    with patch.dict(sys.modules, modules):
        path = ROOT / "src" / "api" / "app" / "routers" / "redirects.py"
        spec = importlib.util.spec_from_file_location("bw_redirects.routers.redirects", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _json(response):
    return json.loads(response.body)


def _redirect(services=None):
    return {
        "id": "red-1",
        "name": "docs",
        "description": "",
        "from_path": "/docs",
        "to_url": "https://docs.example.com",
        "status_code": "301",
        "append_request_uri": False,
        "services": services or [],
    }


def test_list_contract(monkeypatch):
    db = Mock()
    db.get_redirects.return_value = {"items": [_redirect()], "total": 1, "offset": 0, "limit": 100}
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.list_redirects(search="", service_id="", offset=0, limit=100)

    assert response.status_code == 200
    body = _json(response)
    assert body["total"] == 1 and body["redirects"][0]["id"] == "red-1"


def test_create_attaches_every_requested_service(monkeypatch):
    db = Mock()
    db.create_redirect.return_value = ("red-1", "")
    db.attach_redirect.return_value = ""
    db.get_redirect_details.return_value = _redirect(["a.example.com", "b.example.com"])
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    payload = schemas.RedirectCreateRequest(name="docs", from_path="/docs", to_url="https://docs.example.com", service_ids=["a.example.com", "b.example.com"])
    response = ROUTER.create_redirect(payload)

    assert response.status_code == 201
    assert db.attach_redirect.call_count == 2
    assert "service_ids" not in db.create_redirect.call_args.kwargs


def test_create_rolls_back_when_an_attachment_is_refused(monkeypatch):
    db = Mock()
    db.create_redirect.return_value = ("red-1", "")
    # The second service already serves that path, so the whole creation must be undone
    # rather than leaving a rule attached to only half of what was asked for.
    db.attach_redirect.side_effect = ["", "Service b.example.com already has an inline redirect on path /docs"]
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    payload = schemas.RedirectCreateRequest(name="docs", from_path="/docs", to_url="https://docs.example.com", service_ids=["a.example.com", "b.example.com"])
    response = ROUTER.create_redirect(payload)

    assert response.status_code == 409
    assert db.detach_redirect.call_count == 2
    db.delete_redirect.assert_called_once_with("red-1")


def test_create_reports_a_database_error_without_attaching(monkeypatch):
    db = Mock()
    db.create_redirect.return_value = ("", "Redirect name docs already exists")
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.create_redirect(schemas.RedirectCreateRequest(name="docs", to_url="https://docs.example.com"))

    assert response.status_code == 409
    db.attach_redirect.assert_not_called()


def test_update_sends_only_the_submitted_fields(monkeypatch):
    db = Mock()
    db.update_redirect.return_value = ""
    db.get_redirect_details.return_value = _redirect()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    ROUTER.update_redirect("red-1", schemas.RedirectUpdateRequest(to_url="https://new.example.com"))

    assert db.update_redirect.call_args.kwargs == {"to_url": "https://new.example.com"}


def test_error_status_codes(monkeypatch):
    db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    db.get_redirect_details.return_value = None
    assert ROUTER.get_redirect("missing").status_code == 404

    db.delete_redirect.return_value = "Redirect is attached to a service"
    assert ROUTER.delete_redirect("red-1").status_code == 409

    db.delete_redirect.return_value = "Redirect not found"
    assert ROUTER.delete_redirect("red-1").status_code == 404

    db.attach_redirect.return_value = "The database is read-only, the changes will not be saved"
    assert ROUTER.attach_redirect("red-1", schemas.RedirectAttachmentRequest(service_id="a.example.com")).status_code == 409

    db.detach_redirect.return_value = "Redirect attachment not found"
    assert ROUTER.detach_redirect("red-1", "a.example.com").status_code == 404


def test_schema_rejects_bad_payloads():
    with pytest.raises(ValueError):
        schemas.RedirectCreateRequest(name="  ", to_url="https://docs.example.com")
    with pytest.raises(ValueError):
        schemas.RedirectCreateRequest(name="docs", to_url="https://docs.example.com", status_code="404")
    with pytest.raises(ValueError):
        schemas.RedirectCreateRequest(name="docs", to_url="https://docs.example.com", service_ids=["a.example.com", "a.example.com"])
    with pytest.raises(ValueError):
        schemas.RedirectAttachmentRequest(service_id="   ")

    # An unset field must stay unset so PATCH never overwrites what was not submitted.
    assert schemas.RedirectUpdateRequest(to_url="https://x.example.com").model_dump(exclude_unset=True) == {"to_url": "https://x.example.com"}

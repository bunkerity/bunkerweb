"""FastAPI resource-group mutation contracts."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call, patch

import pytest

# Preload Pydantic's lazy model modules before patching ``sys.modules`` in the
# router loader. Otherwise patch.dict removes modules imported inside its scope,
# leaving Pydantic with mixed BaseModel classes for later test modules.
from pydantic import BaseModel, Field, RootModel, ValidationError  # noqa: F401

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
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_resource_groups": ModuleType("bw_resource_groups"),
        "bw_resource_groups.routers": ModuleType("bw_resource_groups.routers"),
        "bw_resource_groups.auth": ModuleType("bw_resource_groups.auth"),
        "bw_resource_groups.auth.guard": ModuleType("bw_resource_groups.auth.guard"),
        "bw_resource_groups.utils": ModuleType("bw_resource_groups.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_resource_groups"].__path__ = []
    names["bw_resource_groups.routers"].__path__ = []
    names["bw_resource_groups.auth"].__path__ = []
    names["bw_resource_groups.auth.guard"].guard = object()
    names["bw_resource_groups.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "resource_groups.py"
        spec = importlib.util.spec_from_file_location("bw_resource_groups.routers.resource_groups", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def test_create_marks_all_plugin_configs_dirty(monkeypatch):
    db = Mock()
    db.create_resource_group.return_value = ""
    db.checked_changes.return_value = ""
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.create_resource_group(ROUTER.ResourceGroupCreateRequest(id="office", name="office"))

    assert response.status_code == 201
    db.create_resource_group.assert_called_once_with("office", name="office", description="", entries=[], method="api")
    db.checked_changes.assert_called_once_with(["config"], plugins_changes="all", value=True)


def test_failed_mutation_does_not_schedule_reload(monkeypatch):
    db = Mock()
    db.create_resource_group.return_value = "Resource group office already exists"
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.create_resource_group(ROUTER.ResourceGroupCreateRequest(id="office", name="office"))

    assert response.status_code == 400
    db.checked_changes.assert_not_called()


def test_reload_failure_reports_persisted_write(monkeypatch):
    db = Mock()
    db.update_resource_group.return_value = ""
    db.checked_changes.return_value = "metadata unavailable"
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.update_resource_group("office", ROUTER.ResourceGroupUpdateRequest(description="HQ"))

    assert response.status_code == 500
    assert response.content["persisted"] is True
    assert "reload could not be scheduled" in response.content["message"]


def test_delete_and_clone_mark_all_plugin_configs_dirty(monkeypatch):
    db = Mock()
    db.delete_resource_group.return_value = ""
    db.clone_resource_group.return_value = ""
    db.checked_changes.return_value = ""
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    deleted = ROUTER.delete_resource_group("office")
    cloned = ROUTER.clone_resource_group("office", ROUTER.ResourceGroupCloneRequest(id="branch", name="branch"))

    assert (deleted.status_code, cloned.status_code) == (200, 201)
    assert db.checked_changes.call_args_list == [
        call(["config"], plugins_changes="all", value=True),
        call(["config"], plugins_changes="all", value=True),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "office", "name": "office", "description": "x" * 4001},
        {"id": "office", "name": "office", "entries": [{}] * 5001},
        {"id": "office", "name": "office", "entries": [{"kind": "uri", "value": "x" * 8193}]},
        {"id": "office", "name": "office", "entries": [{"kind": "uri", "value": "x", "comment": "x" * 1001}]},
    ],
)
def test_request_size_limits(payload):
    with pytest.raises(ValidationError):
        ROUTER.ResourceGroupCreateRequest(**payload)

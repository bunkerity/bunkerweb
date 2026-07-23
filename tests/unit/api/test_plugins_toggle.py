"""FastAPI plugins router — PATCH /plugins/{id} enable/disable toggle + only_enabled listing.

Follows the module-loader + stubbed-``sys.modules`` pattern established by
``test_metrics_dashboard.py``/``test_api_web_cache.py``: there is no live FastAPI
``TestClient`` in ``tests/unit/api``, so router functions are called directly against a
``Mock`` db. The router also imports ``common_utils`` (bytes_hash/create_plugin_tar_gz) and
the ``..schemas``/``..auth.guard``/``..utils`` package modules — all stubbed here.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def _passthrough(self, *_args, **_kwargs):
        return lambda function: function

    get = _passthrough
    put = _passthrough
    post = _passthrough
    patch = _passthrough
    delete = _passthrough


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


class _PluginEnabledRequest:
    """Stand-in for the pydantic schema — the router only reads ``.enabled``."""

    def __init__(self, enabled: bool):
        self.enabled = enabled


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_plugins": ModuleType("bw_plugins"),
        "bw_plugins.routers": ModuleType("bw_plugins.routers"),
        "bw_plugins.auth": ModuleType("bw_plugins.auth"),
        "bw_plugins.auth.guard": ModuleType("bw_plugins.auth.guard"),
        "bw_plugins.schemas": ModuleType("bw_plugins.schemas"),
        "bw_plugins.utils": ModuleType("bw_plugins.utils"),
        "common_utils": ModuleType("common_utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].File = lambda *a, **k: None
    names["fastapi"].Form = lambda *a, **k: None
    names["fastapi"].UploadFile = object
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_plugins"].__path__ = []
    names["bw_plugins.routers"].__path__ = []
    names["bw_plugins.auth"].__path__ = []
    names["bw_plugins.auth.guard"].guard = object()
    names["bw_plugins.schemas"].PluginEnabledRequest = _PluginEnabledRequest
    names["bw_plugins.schemas"].UpdateExternalPluginsRequest = object
    names["bw_plugins.utils"].get_db = Mock()
    names["common_utils"].bytes_hash = Mock()
    names["common_utils"].create_plugin_tar_gz = Mock()
    names["common_utils"].plugin_icon_content_type = Mock()
    names["common_utils"].read_plugin_icon = Mock()
    names["common_utils"].read_local_plugin_icon = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "plugins.py"
        spec = importlib.util.spec_from_file_location("bw_plugins.routers.plugins", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def _req(enabled):
    return _PluginEnabledRequest(enabled)


def test_toggle_success(db):
    db.set_plugin_enabled.return_value = ""
    resp = ROUTER.set_plugin_enabled("myplugin", _req(False))
    assert resp.status_code == 200
    assert resp.content == {"status": "success"}
    db.set_plugin_enabled.assert_called_once_with("myplugin", False)


def test_toggle_enable_true(db):
    db.set_plugin_enabled.return_value = ""
    resp = ROUTER.set_plugin_enabled("myplugin", _req(True))
    assert resp.status_code == 200
    db.set_plugin_enabled.assert_called_once_with("myplugin", True)


def test_core_refusal_maps_to_422(db):
    db.set_plugin_enabled.return_value = "Plugin general is a core plugin and cannot be disabled"
    resp = ROUTER.set_plugin_enabled("general", _req(False))
    assert resp.status_code == 422
    assert resp.content["status"] == "error"


def test_missing_maps_to_404(db):
    db.set_plugin_enabled.return_value = "Plugin with id nope not found"
    resp = ROUTER.set_plugin_enabled("nope", _req(False))
    assert resp.status_code == 404
    assert resp.content["status"] == "error"


def test_other_error_maps_to_500(db):
    db.set_plugin_enabled.return_value = "database is locked"
    resp = ROUTER.set_plugin_enabled("myplugin", _req(False))
    assert resp.status_code == 500


def test_invalid_id_rejected_before_db(db):
    resp = ROUTER.set_plugin_enabled("a", _req(False))  # too short for _PLUGIN_ID_RX
    assert resp.status_code == 422
    db.set_plugin_enabled.assert_not_called()


def test_list_threads_only_enabled(db):
    db.get_plugins.return_value = [{"id": "p1", "enabled": True}]
    resp = ROUTER.list_plugins(type="external", with_data=False, only_enabled=True)
    assert resp.status_code == 200
    db.get_plugins.assert_called_once_with(_type="external", with_data=False, only_enabled=True)


def test_list_default_only_enabled_false(db):
    db.get_plugins.return_value = []
    ROUTER.list_plugins(type="all")
    db.get_plugins.assert_called_once_with(_type="all", with_data=False, only_enabled=False)

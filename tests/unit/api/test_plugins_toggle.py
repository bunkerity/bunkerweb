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
from types import ModuleType, SimpleNamespace
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
    db.get_plugins.assert_called_once_with(_type="external", with_data=False, only_enabled=True, with_settings=True)


def test_list_default_only_enabled_false(db):
    db.get_plugins.return_value = []
    ROUTER.list_plugins(type="all")
    db.get_plugins.assert_called_once_with(_type="all", with_data=False, only_enabled=False, with_settings=True)


def test_list_threads_with_settings_off(db):
    """The settings schema is 95% of this response; a caller that only lists plugins says so."""
    db.get_plugins.return_value = [{"id": "p1", "settings": {}}]
    resp = ROUTER.list_plugins(type="all", with_settings=False)
    assert resp.status_code == 200
    db.get_plugins.assert_called_once_with(_type="all", with_data=False, only_enabled=False, with_settings=False)


def test_list_keeps_the_schema_unless_asked_otherwise(db):
    """Default-on: every existing caller — the scheduler, the CLI, the UI's settings pages —
    reads the schema off this endpoint and must keep getting it."""
    db.get_plugins.return_value = []
    ROUTER.list_plugins()
    assert db.get_plugins.call_args.kwargs["with_settings"] is True


# --- POST /plugins/upload: `created` must mean installed --------------------------------------
# `update_external_plugins` returns "" both when it wrote the plugin and when `_uep_sync_plugin_row`
# SKIPPED it (method mismatch, or the id already belongs to a core/non-external plugin). The router
# appended the id to `created` either way, so the API answered 201 success — and the UI flashed
# "uploaded successfully" — for a plugin that was never installed.


def _tar_gz(plugin_id, filename=None):
    """A minimal .tar.gz carrying one plugin.json, the shape the tar branch parses."""
    from io import BytesIO as _BytesIO
    from json import dumps
    from tarfile import TarInfo, open as tar_open

    payload = dumps({"id": plugin_id, "name": plugin_id, "description": "d", "version": "1.0", "stream": "no", "settings": {}}).encode()
    buffer = _BytesIO()
    with tar_open(fileobj=buffer, mode="w:gz") as archive:
        member = TarInfo(f"{plugin_id}/plugin.json")
        member.size = len(payload)
        archive.addfile(member, _BytesIO(payload))
    return SimpleNamespace(filename=filename or f"{plugin_id}.tar.gz", file=_BytesIO(buffer.getvalue()))


@pytest.fixture
def upload_db(db, monkeypatch, tmp_path):
    monkeypatch.setattr(ROUTER, "TMP_UI_ROOT", tmp_path / "ui")
    monkeypatch.setattr(ROUTER, "create_plugin_tar_gz", lambda *a, **k: __import__("io").BytesIO(b"blob"))
    monkeypatch.setattr(ROUTER, "bytes_hash", lambda *a, **k: "sha")
    db.update_external_plugins.return_value = ""
    return db


def test_a_core_id_collision_is_refused_before_the_write(upload_db):
    """A core plugin owns the id. The pre-check listed only `_type="ui"`, so this archive reached
    the DB layer, was skipped there, and came back as a success."""
    upload_db.get_plugins.return_value = [{"id": "antibot", "type": "core"}]

    resp = ROUTER.upload_plugins(files=[_tar_gz("antibot")], method="ui")

    assert resp.status_code == 400
    assert resp.content["status"] == "error"
    assert "created" not in resp.content
    assert resp.content["errors"] == [{"file": "antibot.tar.gz", "error": "Plugin antibot already exists"}]
    upload_db.update_external_plugins.assert_not_called()


def test_the_collision_check_covers_every_plugin_type(upload_db):
    upload_db.get_plugins.return_value = []
    ROUTER.upload_plugins(files=[_tar_gz("brandnew")], method="ui")
    assert upload_db.get_plugins.call_args_list[0].kwargs["_type"] == "all"


def test_a_silent_db_skip_is_reported_instead_of_claimed_as_created(upload_db):
    """The race the pre-check cannot cover: the id is free when listed, taken by the time the DB
    writes. `update_external_plugins` still returns "", so the row itself is the only evidence."""
    upload_db.get_plugins.side_effect = [[], []]  # free before; still absent after -> skipped

    resp = ROUTER.upload_plugins(files=[_tar_gz("ghost")], method="ui")

    assert resp.status_code == 400
    assert resp.content["status"] == "error"
    assert "created" not in resp.content
    assert resp.content["errors"] == [{"file": "ghost", "error": "Plugin ghost was not installed: the id is already taken by another plugin"}]


def test_a_real_install_still_reports_created(upload_db):
    upload_db.get_plugins.side_effect = [[], [{"id": "brandnew", "type": "ui"}]]

    resp = ROUTER.upload_plugins(files=[_tar_gz("brandnew")], method="ui")

    assert resp.status_code == 201
    assert resp.content == {"status": "success", "created": ["brandnew"]}


def test_a_mixed_upload_separates_the_installed_from_the_skipped(upload_db):
    """The catalogue route asserts `created == [plugin_id]`; a partial must not hide a skip."""
    upload_db.get_plugins.side_effect = [[], [{"id": "goodone", "type": "ui"}]]

    resp = ROUTER.upload_plugins(files=[_tar_gz("goodone"), _tar_gz("badone")], method="ui")

    assert resp.status_code == 207
    assert resp.content["status"] == "partial"
    assert resp.content["created"] == ["goodone"]
    assert resp.content["errors"] == [{"file": "badone", "error": "Plugin badone was not installed: the id is already taken by another plugin"}]


def test_an_unreadable_plugin_list_never_erases_created(upload_db):
    """`get_plugins` failing must not turn a successful install into a reported skip."""
    upload_db.get_plugins.side_effect = [[], Exception("db down")]

    resp = ROUTER.upload_plugins(files=[_tar_gz("brandnew")], method="ui")

    assert resp.status_code == 201
    assert resp.content == {"status": "success", "created": ["brandnew"]}

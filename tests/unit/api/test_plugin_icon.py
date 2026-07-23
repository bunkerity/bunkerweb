"""FastAPI plugins router — GET /plugins/{id}/icon.

Same module-loader + stubbed-``sys.modules`` pattern as ``test_plugins_toggle.py``, but the
REAL ``common_utils`` is left in place so ``read_plugin_icon`` / ``plugin_icon_content_type``
actually extract from a real tar.gz blob. ``fastapi.responses.Response`` is stubbed so the binary
response is inspectable. The router is called directly against a ``Mock`` db.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]

from common_utils import create_plugin_tar_gz  # noqa: E402  (real helper, for building test archives)


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


class _JSONResponse:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


class _BinResponse:
    def __init__(self, *, content=None, media_type=None, headers=None, status_code=200):
        self.content = content
        self.media_type = media_type
        self.headers = headers or {}
        self.status_code = status_code


# fastapi stubs kept module-level: the /icon endpoint does a lazy ``from fastapi.responses
# import Response`` at call time, so the stub must stay in sys.modules while the endpoint runs
# (see the _patch_fastapi autouse fixture), not only during module load.
_FASTAPI = ModuleType("fastapi")
_FASTAPI.APIRouter = _Router
_FASTAPI.Depends = lambda dependency: dependency
_FASTAPI.File = lambda *a, **k: None
_FASTAPI.Form = lambda *a, **k: None
_FASTAPI.UploadFile = object
_FASTAPI_RESPONSES = ModuleType("fastapi.responses")
_FASTAPI_RESPONSES.JSONResponse = _JSONResponse
_FASTAPI_RESPONSES.Response = _BinResponse


def _load_router():
    names = {
        "fastapi": _FASTAPI,
        "fastapi.responses": _FASTAPI_RESPONSES,
        "bw_plugins": ModuleType("bw_plugins"),
        "bw_plugins.routers": ModuleType("bw_plugins.routers"),
        "bw_plugins.auth": ModuleType("bw_plugins.auth"),
        "bw_plugins.auth.guard": ModuleType("bw_plugins.auth.guard"),
        "bw_plugins.schemas": ModuleType("bw_plugins.schemas"),
        "bw_plugins.utils": ModuleType("bw_plugins.utils"),
    }
    names["bw_plugins"].__path__ = []
    names["bw_plugins.routers"].__path__ = []
    names["bw_plugins.auth"].__path__ = []
    names["bw_plugins.auth.guard"].guard = object()
    names["bw_plugins.schemas"].PluginEnabledRequest = object
    names["bw_plugins.schemas"].UpdateExternalPluginsRequest = object
    names["bw_plugins.utils"].get_db = Mock()
    # NOTE: common_utils is intentionally NOT stubbed -> the real icon helpers run.
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "plugins.py"
        spec = importlib.util.spec_from_file_location("bw_plugins.routers.plugins", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture(autouse=True)
def _patch_fastapi():
    """Keep the fastapi stubs live during each test so the endpoint's lazy
    ``from fastapi.responses import Response`` resolves to _BinResponse."""
    with patch.dict(sys.modules, {"fastapi": _FASTAPI, "fastapi.responses": _FASTAPI_RESPONSES}):
        yield


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def _archive(plugin_id, files):
    d = Path(tempfile.mkdtemp()) / plugin_id
    d.mkdir(parents=True)
    (d / "plugin.json").write_text(f'{{"id":"{plugin_id}"}}')
    for name, content in files.items():
        (d / name).write_bytes(content)
    return create_plugin_tar_gz(d, arc_root=d.name).getvalue()


EXPECTED_ICON_HEADERS_SVG = {
    "Content-Disposition": 'inline; filename="icon.svg"',
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


def _assert_headers(resp, name):
    # Every icon response must carry the three neutralizing headers exactly, with a quoted filename.
    assert resp.headers["Content-Disposition"] == f'inline; filename="{name}"'
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"


# ── Blob branch (external/ui/pro): icon extracted from the stored data blob ─────────────


def test_blob_serves_svg_with_headers(db):
    blob = _archive("myplugin", {"icon.svg": b"<svg>ok</svg>"})
    db.get_plugin_icon.return_value = ("external", "@file/icon.svg", blob)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 200
    assert resp.content == b"<svg>ok</svg>"
    assert resp.media_type == "image/svg+xml"
    _assert_headers(resp, "icon.svg")


def test_blob_serves_png_content_type(db):
    blob = _archive("myplugin", {"logo.png": b"\x89PNG\r\n"})
    db.get_plugin_icon.return_value = ("pro", "@file/logo.png", blob)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 200
    assert resp.media_type == "image/png"
    assert resp.content == b"\x89PNG\r\n"
    _assert_headers(resp, "logo.png")


def test_blob_marker_but_file_absent_in_archive_is_404(db):
    blob = _archive("myplugin", {"readme.md": b"x"})  # no icon.svg despite the marker
    db.get_plugin_icon.return_value = ("external", "@file/icon.svg", blob)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_blob_marker_but_no_data_is_404(db):
    # Non-core plugin with an @file marker but a missing/None blob has nothing to serve.
    db.get_plugin_icon.return_value = ("external", "@file/icon.svg", None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_blob_oversized_icon_is_413(db):
    blob = _archive("myplugin", {"icon.png": b"P" * (600 * 1024)})
    db.get_plugin_icon.return_value = ("ui", "@file/icon.png", blob)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 413


# ── Core FS branch: icon read from CORE_PLUGINS_ROOT/<id>/<name> off disk ────────────────


@pytest.fixture
def core_root(tmp_path, monkeypatch):
    monkeypatch.setattr(ROUTER, "CORE_PLUGINS_ROOT", tmp_path)
    return tmp_path


def _core_dir(root, plugin_id, files):
    d = root / plugin_id
    d.mkdir(parents=True)
    for name, content in files.items():
        (d / name).write_bytes(content)
    return d


def test_core_serves_svg_from_disk_with_headers(db, core_root):
    _core_dir(core_root, "myplugin", {"icon.svg": b"<svg>core</svg>"})
    db.get_plugin_icon.return_value = ("core", "@file/icon.svg", None)  # core carries no blob
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 200
    assert resp.content == b"<svg>core</svg>"
    assert resp.media_type == "image/svg+xml"
    _assert_headers(resp, "icon.svg")


def test_core_serves_png_from_disk(db, core_root):
    _core_dir(core_root, "myplugin", {"logo.png": b"\x89PNG\r\n"})
    db.get_plugin_icon.return_value = ("core", "@file/logo.png", None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 200
    assert resp.media_type == "image/png"
    assert resp.content == b"\x89PNG\r\n"
    _assert_headers(resp, "logo.png")


def test_core_file_absent_on_disk_is_404(db, core_root):
    _core_dir(core_root, "myplugin", {"readme.md": b"x"})  # no icon.svg despite the marker
    db.get_plugin_icon.return_value = ("core", "@file/icon.svg", None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_core_oversized_icon_is_413(db, core_root):
    _core_dir(core_root, "myplugin", {"icon.png": b"P" * (600 * 1024)})
    db.get_plugin_icon.return_value = ("core", "@file/icon.png", None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 413


# ── Non-servable icons / errors ─────────────────────────────────────────────────────────


def test_non_file_marker_is_404(db):
    # A static-asset icon (core .svg convention) is not an @file marker -> not servable here.
    db.get_plugin_icon.return_value = ("core", "plugin-myplugin.svg", None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_boxicon_class_is_404(db):
    # A boxicon class string is not servable.
    db.get_plugin_icon.return_value = ("external", "bx-shield", None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_no_icon_is_404(db):
    db.get_plugin_icon.return_value = ("core", None, None)
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_plugin_not_found_is_404(db):
    db.get_plugin_icon.return_value = None
    resp = ROUTER.get_plugin_icon("myplugin")
    assert resp.status_code == 404


def test_invalid_id_rejected_before_db(db):
    resp = ROUTER.get_plugin_icon("a")  # too short for _PLUGIN_ID_RX
    assert resp.status_code == 422
    db.get_plugin_icon.assert_not_called()

"""``PATCH /services/{service}`` with a new ``server_name`` must keep the service's custom configs.

The handler (``src/api/app/routers/services.py:409-460``) renames SERVER_NAME and the prefixed
setting keys, then hands the whole snapshot to ``save_config``. Everything that makes the rename
non-destructive lives in the DB layer (``db_methods/config_save.py``,
``_sc_apply_service_rename``) -- so this file drives the REAL handler against a REAL ``Database``
instead of a Mock: a Mock ``save_config`` cannot tell a rename from a delete plus a create, which
is exactly the bug that shipped.

Same module-loader + stubbed-``sys.modules`` pattern as ``test_services_reserved.py`` (there is no
live ``TestClient`` in ``tests/unit/api``); only ``get_db`` differs.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from fixtures.api_utils import load_api_utils
from fixtures.seed import seed_multisite, session
import schemas  # type: ignore
from model import Settings  # type: ignore

from default_server import DEFAULT_SERVER_ID  # type: ignore

ROOT = Path(__file__).resolve().parents[3]

OLD = "api.example.com"
NEW = "renamed.example.com"


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    put = get
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
        "bw_services": ModuleType("bw_services"),
        "bw_services.routers": ModuleType("bw_services.routers"),
        "bw_services.auth": ModuleType("bw_services.auth"),
        "bw_services.auth.guard": ModuleType("bw_services.auth.guard"),
        "bw_services.schemas": schemas,
        "bw_services.utils": ModuleType("bw_services.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_services"].__path__ = []
    names["bw_services.routers"].__path__ = []
    names["bw_services.auth"].__path__ = []
    names["bw_services.auth.guard"].guard = object()
    names["bw_services.utils"].get_db = Mock()
    names["bw_services.utils"].LOGGER = Mock()
    names["bw_services.utils"].reportable_config = load_api_utils().reportable_config
    http01_spec = importlib.util.spec_from_file_location("bw_services.http01", ROOT / "src" / "api" / "app" / "http01.py")
    http01 = importlib.util.module_from_spec(http01_spec)
    http01_spec.loader.exec_module(http01)
    names["bw_services.http01"] = http01
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "services.py"
        spec = importlib.util.spec_from_file_location("bw_services.routers.services", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()

pytestmark = pytest.mark.slow


@pytest.fixture
def live_db(db, monkeypatch):
    """A real Database holding one api-owned service that carries one api custom config."""
    seed_multisite(db)
    # `get_non_default_settings` materialises `{service}_IS_DRAFT` for every service
    # (config_read.py:185) and the handler ships the snapshot untouched, so save_config validates
    # the key. seed_multisite does not declare it; settings.json:394 does.
    with session(db) as s:
        s.add(Settings(id="IS_DRAFT", name="IS_DRAFT", plugin_id="general", context="multisite", help="h", regex="^(yes|no)$", type="check", default="no"))
    conf = {k: v for k, v in db.get_non_default_settings(methods=False, with_drafts=True).items() if not k.endswith("IS_DRAFT")}
    conf["SERVER_NAME"] = f"{conf['SERVER_NAME']} {OLD}"
    conf[f"{OLD}_USE_REVERSE_PROXY"] = "yes"
    assert not isinstance(db.save_config(conf, "api", changed=True), str)
    assert (
        db.save_custom_configs(
            [{"service_id": OLD, "type": "server_http", "name": "mysnippet", "data": "# keep me", "method": "api"}],
            "api",
        )
        == ""
    )
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    return db


def _configs(db):
    return {(c["service_id"], c["name"]) for c in db.get_custom_configs(with_drafts=True, with_data=False)}


def _service_ids(db):
    return {service["id"] for service in db.get_services(with_drafts=True)}


def test_patching_server_name_keeps_the_custom_configs(live_db):
    assert (OLD, "mysnippet") in _configs(live_db)

    response = ROUTER.update_service(OLD, schemas.ServiceUpdateRequest(server_name=NEW))

    assert response.status_code == 200, response.content
    assert NEW in _service_ids(live_db) and OLD not in _service_ids(live_db)
    assert (NEW, "mysnippet") in _configs(live_db)


def test_patching_server_name_keeps_the_settings(live_db):
    response = ROUTER.update_service(OLD, schemas.ServiceUpdateRequest(server_name=NEW))

    assert response.status_code == 200, response.content
    stored = live_db.get_non_default_settings(methods=False, with_drafts=True)
    assert stored.get(f"{NEW}_USE_REVERSE_PROXY") == "yes"
    assert f"{OLD}_USE_REVERSE_PROXY" not in stored


def test_a_patch_that_changes_only_a_variable_is_not_a_rename(live_db):
    response = ROUTER.update_service(OLD, schemas.ServiceUpdateRequest(variables={"USE_REVERSE_PROXY": "no"}))

    assert response.status_code == 200, response.content
    assert OLD in _service_ids(live_db)
    assert (OLD, "mysnippet") in _configs(live_db)


class TestTheReservedRulesStillHold:
    """``services.py:438-446`` -- both directions, against the live database this time."""

    def test_renaming_a_service_onto_the_reserved_id_is_still_refused(self, live_db):
        response = ROUTER.update_service(OLD, schemas.ServiceUpdateRequest(server_name=DEFAULT_SERVER_ID))

        assert response.status_code == 403
        assert DEFAULT_SERVER_ID in response.content["message"]
        assert OLD in _service_ids(live_db)
        assert (OLD, "mysnippet") in _configs(live_db)

    def test_renaming_the_reserved_service_away_is_still_refused(self, live_db):
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(server_name="stolen.example.com"))

        assert response.status_code == 403
        assert DEFAULT_SERVER_ID in _service_ids(live_db)
        assert "stolen.example.com" not in _service_ids(live_db)

    def test_renaming_onto_an_existing_service_is_still_refused(self, live_db):
        response = ROUTER.update_service(OLD, schemas.ServiceUpdateRequest(server_name="app1.example.com"))

        assert response.status_code == 400
        assert OLD in _service_ids(live_db)
        assert (OLD, "mysnippet") in _configs(live_db)

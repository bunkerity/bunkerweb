"""The global settings write path must validate before saving.

Follows the module-loader + stubbed-``sys.modules`` pattern established by
``test_api_upstreams.py``/``test_api_web_cache.py``: there is no live FastAPI
``TestClient`` in ``tests/unit/api``, so the router function is called directly against a
``Mock`` db.
"""

import importlib.util
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
    put = get
    patch = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_global_settings": ModuleType("bw_global_settings"),
        "bw_global_settings.routers": ModuleType("bw_global_settings.routers"),
        "bw_global_settings.auth": ModuleType("bw_global_settings.auth"),
        "bw_global_settings.auth.guard": ModuleType("bw_global_settings.auth.guard"),
        "bw_global_settings.schemas": schemas,
        "bw_global_settings.utils": ModuleType("bw_global_settings.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_global_settings"].__path__ = []
    names["bw_global_settings.routers"].__path__ = []
    names["bw_global_settings.auth"].__path__ = []
    names["bw_global_settings.auth.guard"].guard = object()
    names["bw_global_settings.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "global_settings.py"
        spec = importlib.util.spec_from_file_location("bw_global_settings.routers.global_settings", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    # Empty by default: no pre-existing API-managed overrides to merge into the save.
    fake_db.get_non_default_settings.return_value = {}
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def test_patch_rejects_a_value_the_setting_regex_forbids(db):
    db.is_valid_setting.return_value = (False, "not matching regex: '^(no|cookie|captcha)$'")

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "yes"}))

    assert response.status_code == 400
    assert "USE_ANTIBOT" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_accepts_a_legal_value(db):
    db.is_valid_setting.return_value = (True, "")
    db.save_config.return_value = set()

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_a_legacy_invalid_value_on_an_untouched_key_does_not_block_the_save(db):
    """Validation applies to keys in THIS payload, not to pre-existing rows."""

    # A previously-stored, now-illegal value on a key absent from this payload.
    db.get_non_default_settings.return_value = {
        "OLD_BAD_SETTING": {"value": "not-legal-anymore", "method": "api"},
    }

    def validate(setting, **_kwargs):
        return (False, "legacy") if setting == "OLD_BAD_SETTING" else (True, "")

    db.is_valid_setting.side_effect = validate
    db.save_config.return_value = set()

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()
    # is_valid_setting must never have been asked about the untouched legacy key.
    validated_keys = {call.args[0] for call in db.is_valid_setting.call_args_list}
    assert "OLD_BAD_SETTING" not in validated_keys

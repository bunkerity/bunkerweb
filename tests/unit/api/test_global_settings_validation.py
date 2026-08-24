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
from Database import Database  # type: ignore

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
    # The ownership gate must be exercised against the real compatibility rule, not a Mock
    # (a Mock return value is truthy, i.e. "always compatible", which would hide the gate).
    fake_db._methods_are_compatible = Database._methods_are_compatible
    # Same reason as above: a bare Mock is truthy, which the USE_TEMPLATE gate would read as
    # "every layer is unknown" and reject every save.
    fake_db.unknown_template_layers.return_value = []
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


# --- ownership gate ---------------------------------------------------------------
# save_config silently skips a row whose method 'api' may not take over, so without this
# gate the endpoint answered 200 "success" having written nothing at all.


@pytest.fixture
def writable_db(db):
    """A db that accepts every value and every save — leaves ownership as the only variable."""
    db.is_valid_setting.return_value = (True, "")
    db.save_config.return_value = set()
    return db


@pytest.mark.parametrize("owner", ("scheduler", "autoconf"))
def test_patch_refuses_a_key_owned_by_a_method_api_cannot_overwrite(writable_db, owner):
    writable_db.get_non_default_settings.return_value = {"USE_ANTIBOT": {"value": "no", "method": owner}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 409
    assert "USE_ANTIBOT" in response.content["message"]
    assert owner in response.content["message"]
    writable_db.save_config.assert_not_called()


@pytest.mark.parametrize("owner", ("ui", "api"))
def test_patch_overwrites_a_key_owned_by_an_interchangeable_method(writable_db, owner):
    """ui and api are interchangeable per Database._methods_are_compatible."""

    writable_db.get_non_default_settings.return_value = {"USE_ANTIBOT": {"value": "no", "method": owner}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


def test_patch_accepts_a_key_that_has_no_row_yet(writable_db):
    """No entry means no Global_values row, so save_config INSERTs it whatever the method."""

    writable_db.get_non_default_settings.return_value = {"SOMETHING_ELSE": {"value": "x", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


def test_patch_refuses_the_whole_payload_when_one_key_is_owned_elsewhere(writable_db):
    """All-or-nothing: a partial silent apply is the defect this gate fixes."""

    writable_db.get_non_default_settings.return_value = {
        "USE_ANTIBOT": {"value": "no", "method": "scheduler"},
        "USE_REVERSE_PROXY": {"value": "no", "method": "api"},
    }

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_REVERSE_PROXY": "yes", "USE_ANTIBOT": "captcha"}))

    assert response.status_code == 409
    assert "USE_ANTIBOT (scheduler)" in response.content["message"]
    assert "USE_REVERSE_PROXY" not in response.content["message"]
    writable_db.save_config.assert_not_called()


def test_patch_of_a_foreign_owned_key_already_at_the_requested_value_is_not_a_conflict(writable_db):
    """Ownership alone is not a refused write — save_config gates its refusal on `value_changed`.

    If the row already holds what the caller is asking for, nothing was going to be written and
    nothing was silently dropped, so the 200 is truthful. Conflicting on ownership alone broke the
    canonical merge-PATCH flow (GET the config, edit one key, PATCH the whole dict back), which in
    Docker/compose carries a scheduler-owned value for nearly every non-default global.
    """

    writable_db.get_non_default_settings.return_value = {"LOG_LEVEL": {"value": "info", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"LOG_LEVEL": "info"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


def test_patch_refuses_a_suffix_zero_key_whose_row_is_keyed_plainly(writable_db):
    """`FOO_0` must resolve to the plainly-keyed row, or it slips the gate and gets a false 200.

    get_non_default_settings appends the suffix only when the setting is `multiple` AND the suffix
    is > 0, so a suffix-0 row comes back as `WHITELIST_URL`. save_config's SUFFIX_RX resolves the
    payload key `WHITELIST_URL_0` to that same row and then drops the write.
    """

    writable_db.get_non_default_settings.return_value = {"WHITELIST_URL": {"value": "http://a", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"WHITELIST_URL_0": "http://b"}))

    assert response.status_code == 409
    assert "WHITELIST_URL_0 (scheduler)" in response.content["message"]
    writable_db.save_config.assert_not_called()


def test_patch_does_not_mistake_a_double_digit_suffix_for_suffix_zero(writable_db):
    """`FOO_10` ends in a '0' but is keyed with its suffix, so it must not be truncated to `FOO_1`."""

    writable_db.get_non_default_settings.return_value = {"WHITELIST_URL_10": {"value": "http://a", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"WHITELIST_URL_10": "http://b"}))

    assert response.status_code == 409
    assert "WHITELIST_URL_10 (scheduler)" in response.content["message"]


def test_patch_does_not_let_the_synthetic_server_name_method_trigger_a_conflict(writable_db):
    """get_non_default_settings always reports SERVER_NAME as method='scheduler' (it overwrites
    the entry with the service list), so the gate must skip it or every payload carrying
    SERVER_NAME would 409 on a method that is not the row's real owner."""

    writable_db.get_non_default_settings.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "scheduler"}}

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"SERVER_NAME": "app.example.com other.example.com"}))

    assert response.status_code == 200
    writable_db.save_config.assert_called_once()


# --- the USE_TEMPLATE referential gate --------------------------------------------


def test_patch_rejects_an_unknown_global_template_layer(db):
    """A global USE_TEMPLATE is the fallback for every service without its own, so a typo here
    drops a layer fleet-wide. Its regex is `^.*$`, so only a referential check can catch it."""
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = [(2, "typo")]

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_TEMPLATE": "low typo"}))

    assert response.status_code == 400
    assert "USE_TEMPLATE" in response.content["message"]
    assert "position 2" in response.content["message"]
    db.save_config.assert_not_called()


def test_patch_accepts_a_fully_known_global_template_list(db):
    db.is_valid_setting.return_value = (True, "")
    db.unknown_template_layers.return_value = []
    db.save_config.return_value = set()

    response = ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_TEMPLATE": "low high"}))

    assert response.status_code == 200
    db.save_config.assert_called_once()


def test_the_layer_check_runs_only_for_use_template(db):
    db.is_valid_setting.return_value = (True, "")
    db.save_config.return_value = set()

    ROUTER.update_global_settings(schemas.GlobalSettingsUpdate({"USE_ANTIBOT": "captcha"}))

    db.unknown_template_layers.assert_not_called()

"""An untouched global Save must not be refused (smoke Q8, item 2 side finding).

The RAW page renders the EFFECTIVE config (defaults included), the save reads the STORED one. So a
secret still at its default posts its placeholder with nothing stored to restore, and a duration or
size left empty posts `""`, which the unit canonicalizer refused although the setting's own regex
accepts it. Four values were refused on every RAW save of a fresh install.
"""

from copy import deepcopy
from unittest.mock import patch

import pytest

from app.models.config import Config  # type: ignore
from app.models.secret_settings import SECRET_PLACEHOLDER  # type: ignore

from test_raw_setting_drafts import GLOBAL, _FakeData  # type: ignore

SETTINGS = {
    "SERVER_NAME": {"type": "text", "regex": "^.*$", "context": "multisite"},
    "AUTH_BASIC_PASSWORD": {"type": "password", "regex": "^.+$", "context": "multisite"},
    "SESSIONS_SECRET": {"type": "password", "regex": "^.+$", "context": "global"},
    "GRPC_NEXT_UPSTREAM_TIMEOUT": {"type": "duration", "regex": r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d*$", "context": "multisite"},
    "MODSECURITY_SEC_REQUEST_BODY_LIMIT": {"type": "size", "regex": r"^(\d+[kKmMgG]?)?$", "context": "multisite"},
}
# The exact POST of an untouched Save on a fresh install.
UNTOUCHED = {
    "AUTH_BASIC_PASSWORD": SECRET_PLACEHOLDER,
    "SESSIONS_SECRET": SECRET_PLACEHOLDER,
    "GRPC_NEXT_UPSTREAM_TIMEOUT": "",
    "MODSECURITY_SEC_REQUEST_BODY_LIMIT": "",
}
STORED = {"SERVER_NAME": {"value": "svc1", "global": True, "method": "scheduler", "default": "", "template": None}}


def _save(posted, draft_settings):
    data = _FakeData(TO_FLASH=[])
    captured = {}
    config = Config.__new__(Config)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: deepcopy(STORED)
    config.edit_global_conf = lambda variables, **kwargs: (captured.update(payload=variables, **kwargs), ("Saved.", 0))[1]
    with patch.object(GLOBAL, "BW_CONFIG", config), patch.object(GLOBAL, "DATA", data), patch.object(GLOBAL, "wait_applying", lambda: None):
        GLOBAL.update_global_config({"SERVER_NAME": "svc1"} | posted, False, {}, scope=None, draft_settings=draft_settings)
    return captured, [flash["content"] for flash in data["TO_FLASH"]]


@pytest.mark.parametrize("draft_settings", [{}, None], ids=["raw", "form"])
def test_an_untouched_save_refuses_nothing(draft_settings):
    captured, flashes = _save(UNTOUCHED, draft_settings)

    assert [flash for flash in flashes if "not valid" in flash or "refused" in flash] == []
    # The placeholder never reaches the store as a value, nor as an emptied secret.
    payload = captured.get("payload", {})
    assert "AUTH_BASIC_PASSWORD" not in payload and "SESSIONS_SECRET" not in payload


def test_a_new_secret_still_replaces_the_default():
    captured, flashes = _save(UNTOUCHED | {"AUTH_BASIC_PASSWORD": "s3cret"}, {})

    assert captured["payload"]["AUTH_BASIC_PASSWORD"] == "s3cret"
    assert [flash for flash in flashes if "not valid" in flash] == []


@pytest.mark.parametrize("key,value", [("GRPC_NEXT_UPSTREAM_TIMEOUT", "1h30m"), ("MODSECURITY_SEC_REQUEST_BODY_LIMIT", "10m")])
def test_a_real_unit_value_still_canonicalizes(key, value):
    captured, _ = _save(UNTOUCHED | {key: value}, {})

    assert captured["payload"][key] == value


@pytest.mark.parametrize("key", ["GRPC_NEXT_UPSTREAM_TIMEOUT", "MODSECURITY_SEC_REQUEST_BODY_LIMIT"])
def test_an_empty_unit_value_the_regex_refuses_is_still_refused(key):
    tight = {**SETTINGS, key: {**SETTINGS[key], "regex": r"^\d+.*$"}}
    with patch.dict(SETTINGS, tight):
        _, flashes = _save(UNTOUCHED, {})

    assert any(key in flash for flash in flashes), flashes

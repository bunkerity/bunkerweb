"""The same flash-type defect as lane P2's (`tests/unit/ui/test_service_save_flash_type.py`),
here on the global-settings save path.

`update_global_config` decided the final flash's *type* by string-matching `operation` against
("Can't", "The database is read-only") instead of the `error` flag it already holds from
`BW_CONFIG.edit_global_conf(...)` (`routes/global_settings.py`). Two real consequences: a backend
refusal whose message matches neither prefix was flashed green; and a save where the UI's own
regex gate refused at least one field -- reverting it to its stored value, or dropping it outright
-- still ended on an unconditional green "successfully saved", next to the red flash(es) the
operator has to notice on their own.

`update_global_config` now passes `check_variables` a `refused` list it owns, exactly like
`services.py`'s `update_service` (lane P2). A fresh, caller-owned list is used rather than diffing
`DATA["TO_FLASH"]` around the call, for the same reload-hazard reason documented in
`models/config.py:check_variables`'s own docstring.

Same harness as `test_global_settings_propagation.py`: a real `Config` instance (skipping
`__init__`) drives the real `check_variables`, so a regex-rejected value produces a genuine
refusal instead of a stubbed one; `edit_global_conf` is swapped per test to control the
error/success outcome this lane's fix reacts to.
"""

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from app.models.config import Config  # type: ignore  (src/ui on path via the ui conftest)

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTE_PATH = REPO_ROOT / "src" / "ui" / "app" / "routes" / "global_settings.py"


def _import_route_module() -> ModuleType:
    """Own module name so this load never shares a Blueprint object with
    `test_global_settings_propagation.py`'s own load of the same file."""
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.CORE_PLUGINS_PATH = REPO_ROOT / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._global_settings_test_save_flash_type"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_route_module()

# A multiselect whose regex rejects the empty string an emptied multiselect posts -- the value
# that drives the real `check_variables` down its `reject_value` (revert, not drop) path.
SETTINGS = {
    "SSL_PROTOCOLS": {
        "type": "multiselect",
        "regex": r"^(?! )( ?(?:SSLv[23]|TLSv1(?:\.[1-3])?))+$",
        "context": "multisite",
        "separator": " ",
        "multiselect": [{"id": v, "label": v, "value": v} for v in ("SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3")],
    },
    "SERVER_NAME": {"type": "text", "regex": "^.*$", "context": "multisite"},
}


class _FakeData(dict):
    def load_from_file(self):  # check_variables and the route both call this
        return None


def _stored_config() -> dict:
    return {
        "SERVER_NAME": {"value": "", "global": True, "method": "scheduler", "default": "", "template": None},
        "SSL_PROTOCOLS": {"value": "TLSv1.2 TLSv1.3", "global": True, "method": "ui", "default": "TLSv1.2 TLSv1.3", "template": None},
    }


def _save(posted: dict, *, edit_global_conf_return):
    """Run the real `update_global_config`; return what was flashed as (type, content) pairs."""
    stored = _stored_config()
    data = _FakeData(TO_FLASH=[])

    config = Config.__new__(Config)  # skip __init__ (hardcoded settings.json read)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: deepcopy(stored)
    config.edit_global_conf = lambda variables, **kwargs: edit_global_conf_return

    with patch.object(MODULE, "BW_CONFIG", config), patch.object(MODULE, "DATA", data), patch.object(MODULE, "wait_applying", lambda: None):
        MODULE.update_global_config(dict(posted), False, {}, scope=None)

    return [(entry["type"], entry["content"]) for entry in data["TO_FLASH"]]


def test_a_backend_refusal_matching_neither_prefix_is_flashed_error():
    """`edit_global_conf` returning an `ApiUnavailableError` string (500 from
    `PUT /global_settings/config`) starts with neither "Can't" nor "The database is read-only" --
    the exact miss the prefix match had."""
    flashed = _save({"SSL_PROTOCOLS": "TLSv1.2"}, edit_global_conf_return=("ApiUnavailableError: API returned 500", 1))

    assert ("error", "ApiUnavailableError: API returned 500") in flashed, flashed
    assert not any(t == "success" for t, _ in flashed), flashed


def test_a_value_the_regex_gate_reverted_ends_on_a_warning_not_a_success():
    """An emptied multiselect: no client gate, rejected by the real regex, restored to the stored
    value by `check_variables` -- and now reported through the caller-owned `refused` list."""
    flashed = _save({"SSL_PROTOCOLS": ""}, edit_global_conf_return=("Global settings successfully saved.", 0))

    assert ("warning", "Global settings saved, but 1 value(s) were refused.") in flashed, flashed
    assert not any(t == "success" and content.startswith("Global settings successfully saved.") for t, content in flashed), flashed


def test_a_clean_save_is_still_flashed_success():
    flashed = _save({"SSL_PROTOCOLS": "TLSv1.2"}, edit_global_conf_return=("Global settings successfully saved.", 0))

    assert ("success", "Global settings successfully saved.") in flashed, flashed
    assert not any(t == "warning" for t, _ in flashed), flashed


def test_the_read_only_refusal_is_still_flashed_error():
    flashed = _save(
        {"SSL_PROTOCOLS": "TLSv1.2"},
        edit_global_conf_return=("The database is read-only, the changes will not be saved", 1),
    )

    assert any(t == "error" and "read-only" in content for t, content in flashed), flashed
    assert not any(t == "success" for t, _ in flashed), flashed

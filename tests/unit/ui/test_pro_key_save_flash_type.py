"""The same flash-type defect as lane P2's (`tests/unit/ui/test_service_save_flash_type.py`),
here on the PRO-license-key save path.

`update_license_key` (the closure `pro_key()` submits to `CONFIG_TASKS_EXECUTOR`) decided the
final flash's *type* by string-matching `operation` against ("Can't", "The database is
read-only") instead of the `error` flag it already holds from `BW_CONFIG.edit_global_conf(...)`
(`routes/pro.py`). Same two consequences as the global-settings and services pages: a backend
refusal whose message matches neither prefix was flashed green, and a save the UI's own regex
gate partially refused still ended on an unconditional green success.

`pro_key()` now passes `check_variables` a `refused` list it owns and threads the resulting count
into `update_license_key`, exactly like `services.py`'s `update_service` (lane P2) and
`global_settings.py`'s `update_global_config` (this lane).

Route loading follows `test_pro_refresh.py`'s module-loader pattern. `CONFIG_TASKS_EXECUTOR` is a
synchronous fake -- `.submit(fn, *a)` calls `fn(*a)` immediately -- so the closure actually runs
inside the test instead of being handed to a real thread pool that a `Mock()` would swallow.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask


class _SyncExecutor:
    """`ThreadPoolExecutor.submit`, but synchronous -- runs the job in-line so its side effects
    (the flashes under test) land before the view function returns."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)
        return Mock()


class _FakeData(dict):
    def load_from_file(self):
        return None


@pytest.fixture(scope="module")
def pro_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = _SyncExecutor()
    dependencies.DATA = _FakeData(TO_FLASH=[])
    route_utils = ModuleType("app.routes.utils")
    route_utils.get_remain = Mock()
    route_utils.handle_error = Mock()
    route_utils.verify_data_in_form = Mock()
    route_utils.wait_applying = Mock()
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    app_utils.billable_service_count = Mock(return_value=0)
    module_name = "app.routes._pro_key_test_save_flash_type"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "pro.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "app.routes.utils": route_utils,
        "app.utils": app_utils,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


def _save(pro_route, *, edit_global_conf_return, check_variables_return=None):
    pro_route.API_CLIENT.reset_mock()
    pro_route.API_CLIENT.readonly = False
    pro_route.BW_CONFIG.reset_mock()
    pro_route.DATA.clear()
    pro_route.DATA["TO_FLASH"] = []

    pro_route.BW_CONFIG.get_config.return_value = {"PRO_LICENSE_KEY": "OLDKEY"}
    pro_route.BW_CONFIG.check_variables.return_value = check_variables_return or {"PRO_LICENSE_KEY": "NEWKEY123"}
    pro_route.BW_CONFIG.edit_global_conf.return_value = edit_global_conf_return

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pro_route.pro)
    app.add_url_rule("/loading", "loading", lambda: "")

    with app.test_request_context("/pro/key", method="POST", data={"PRO_LICENSE_KEY": "NEWKEY123"}):
        pro_route.pro_key.__wrapped__()

    return [(entry["type"], entry["content"]) for entry in pro_route.DATA["TO_FLASH"]]


def test_a_backend_refusal_matching_neither_prefix_is_flashed_error(pro_route):
    """`edit_global_conf` returning an `ApiUnavailableError` string (500 from
    `PUT /global_settings/config`) starts with neither "Can't" nor "The database is read-only" --
    the exact miss the prefix match had."""
    flashed = _save(pro_route, edit_global_conf_return=("ApiUnavailableError: API returned 500", 1))

    assert ("error", "ApiUnavailableError: API returned 500") in flashed, flashed
    assert not any(t == "success" for t, _ in flashed), flashed


def test_a_refused_value_ends_on_a_warning_not_a_success(pro_route):
    """`check_variables` refusing the posted key -- the caller-owned `refused` list this lane
    threads through -- must not still read as an unconditional success. Unlike services.py /
    global_settings.py, this route checks exactly one variable (PRO_LICENSE_KEY), so a refusal
    here is the WHOLE save, not a partial one: the flash must say the key was not updated, not
    borrow the multi-variable "updated, but N refused" phrasing (that would assert an update
    that never happened -- Criticos round 1 on this lane). The scheduler/"download PRO plugins"
    line must not fire alongside it either -- the payload reject_value reverted is
    byte-identical to what was already stored, so nothing will actually apply (Criticos round 2).

    The refusal reason mirrors the realistic path (`config.py:291-298`): a PRO_LICENSE_KEY set
    via the compose environment has `method != ui/default`, so `check_variables` pops it as
    not-editable rather than rejecting its value (its regex is `^.*$` -- `core/pro/plugin.json`
    -- so a value-shape refusal can never fire here)."""

    def fake_check_variables(*args, refused=None, **kwargs):
        if refused is not None:
            refused.append("Variable PRO_LICENSE_KEY is not editable as it is managed by the environment, ignoring it.")
        return {"PRO_LICENSE_KEY": "NEWKEY123"}

    pro_route.API_CLIENT.reset_mock()
    pro_route.API_CLIENT.readonly = False
    pro_route.BW_CONFIG.reset_mock()
    pro_route.DATA.clear()
    pro_route.DATA["TO_FLASH"] = []
    pro_route.BW_CONFIG.get_config.return_value = {"PRO_LICENSE_KEY": "OLDKEY"}
    pro_route.BW_CONFIG.check_variables.side_effect = fake_check_variables
    pro_route.BW_CONFIG.edit_global_conf.return_value = ("The PRO license key was updated successfully.", 0)

    try:
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(pro_route.pro)
        app.add_url_rule("/loading", "loading", lambda: "")
        with app.test_request_context("/pro/key", method="POST", data={"PRO_LICENSE_KEY": "NEWKEY123"}):
            pro_route.pro_key.__wrapped__()

        flashed = [(entry["type"], entry["content"]) for entry in pro_route.DATA["TO_FLASH"]]
        assert ("warning", "The PRO license key was not updated: the value was refused.") in flashed, flashed
        assert not any(t == "success" for t, _ in flashed), flashed
    finally:
        pro_route.BW_CONFIG.check_variables.side_effect = None


def test_a_clean_save_is_still_flashed_success(pro_route):
    flashed = _save(pro_route, edit_global_conf_return=("The PRO license key was updated successfully.", 0))

    assert ("success", "The PRO license key was updated successfully.") in flashed, flashed
    assert not any(t == "warning" for t, _ in flashed), flashed


def test_the_read_only_refusal_is_still_flashed_error(pro_route):
    flashed = _save(pro_route, edit_global_conf_return=("The database is read-only, the changes will not be saved", 1))

    assert any(t == "error" and "read-only" in content for t, content in flashed), flashed
    assert not any(t == "success" for t, _ in flashed), flashed

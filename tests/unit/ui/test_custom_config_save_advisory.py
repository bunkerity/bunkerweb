"""A custom-config save that LANDED with a warning must say so, not "an error occurred".

``PUT /configs/bulk`` used to answer 500 for the purely advisory
``Service <x> not found, please check your config`` the database returns *after* committing the
rows. `base_api_client` turned that into `ApiUnavailableError("API returned 500")`, and
``update_service``'s `except Exception` flashed "An error occurred while saving the custom
configs" over a write that had succeeded -- while the actual warning, the one saying the config
references a service that does not exist, never reached anyone.

The route now answers 200 with the message (`tests/unit/api/test_configs_bulk_save_classification.py`).
This is the other end: the UI has to render it. Port of dev `abb60b1ea`, refused-write half.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

ADVISORY = "Service app1.example.com not found, please check your config"


def _import_services_module():
    """Same loader as ``test_template_settings_page.py``, under its own module name so the two
    loads never share a Blueprint object."""
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
    module_name = "app.routes._services_test_config_advisory"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_services_module()


class _FakeData(dict):
    def load_from_file(self):
        pass


def _save_with_one_new_config(monkeypatch, *, returns=None, raises=None):
    """Drive the real `update_service` down the bulk-save branch and return what was flashed."""
    api = Mock()
    api.get_service.return_value = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}}
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    api.bulk_save_configs.side_effect = raises
    if raises is None:
        api.bulk_save_configs.return_value = returns

    bw_config = Mock()
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("Configuration saved", None)

    data = _FakeData(TO_FLASH=[])
    monkeypatch.setattr(MODULE, "API_CLIENT", api)
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(MODULE, "DATA", data)
    monkeypatch.setattr(MODULE, "wait_applying", lambda: None)

    posted = {
        "SERVER_NAME": "app.example.com",
        "USE_UI": "no",
        # The stepper posts a custom config as one CUSTOM_CONF_<TYPE>_<NAME> field (utils.py:34).
        "CUSTOM_CONF_SERVER_HTTP_test": "# hello",
    }
    MODULE.update_service("app.example.com", posted, False, "easy", "", {})

    assert api.bulk_save_configs.called, "the bulk-save branch was never reached -- this test proves nothing"
    return [flash for flash in data["TO_FLASH"]]


def test_the_warning_the_api_reports_is_flashed(monkeypatch):
    flashed = _save_with_one_new_config(monkeypatch, returns={"status": "success", "message": ADVISORY})

    assert any(flash["content"] == ADVISORY and flash["type"] == "warning" for flash in flashed), flashed


def test_a_clean_save_flashes_no_warning_of_its_own(monkeypatch):
    flashed = _save_with_one_new_config(monkeypatch, returns={"status": "success"})

    assert not any(flash["type"] == "warning" for flash in flashed), flashed


def test_a_refusal_is_still_an_error(monkeypatch):
    """The other branch has to keep working: a refused write is not a warning.

    The exception is the real one the client raises for the 400 the route now answers a refusal
    with -- `ApiClientError`, not a bare `RuntimeError`. `update_service` catches `Exception`, so
    either would prove the branch, but only this one proves the branch for the shape that occurs.
    """
    from app.api_client import ApiClientError

    flashed = _save_with_one_new_config(monkeypatch, raises=ApiClientError("The database is read-only, the changes will not be saved", status_code=400))

    assert any(flash["type"] == "error" and "read-only" in flash["content"] for flash in flashed), flashed


@pytest.mark.parametrize("returned", [None, {}, {"status": "success", "message": ""}])
def test_nothing_is_flashed_for_a_response_that_reports_nothing(monkeypatch, returned):
    flashed = _save_with_one_new_config(monkeypatch, returns=returned)

    assert not any(flash["type"] == "warning" for flash in flashed), flashed

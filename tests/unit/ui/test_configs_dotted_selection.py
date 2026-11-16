"""The configs bulk selection accepts the names the API stores, dots included (dev 821ecbb81).

A file-managed config (`/etc/bunkerweb/configs/...`) can carry a name `NAME_RX` refuses at creation,
such as `my.conf`. The bulk delete and convert re-validated the selection against `NAME_RX`, so one
such row failed the whole batch with "Invalid configs parameter". The selection only names existing
rows, which the API matches exactly, so the check is now a length and printability bound.

Same loader idiom as `test_configs_write_permission.py`: the route module is executed against stubs.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "configs.py"


@pytest.fixture(scope="module")
def configs_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = {}
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._configs_dotted_selection_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
        yield module


def _selection(name, config_type="server-http", service="app.example.com"):
    return [{"name": name, "type": config_type, "service": service}]


@pytest.mark.parametrize("name", ["my.conf", "site.v2.rules", "a", "x" * 255, "with-dash_and.dot"])
def test_names_the_api_stores_are_accepted(configs_route, name):
    assert configs_route._valid_config_selection(_selection(name))


def test_the_regex_still_rejects_the_dotted_name_at_creation(configs_route):
    # The relaxed check is for selections of existing rows only: creation keeps the strict pattern.
    assert not configs_route.match(configs_route.CONFIG_NAME_RX, "my.conf")


@pytest.mark.parametrize("name", ["", "x" * 256, "line\nbreak", "tab\there", "nul\x00byte", None, 12])
def test_empty_overlong_unprintable_or_non_string_names_are_refused(configs_route, name):
    assert not configs_route._valid_config_selection(_selection(name))


@pytest.mark.parametrize(
    "selection",
    [
        None,
        [],
        "not a list",
        [{"name": "ok", "type": "unknown", "service": None}],
        [{"name": "ok", "type": 3}],
        [{"name": "ok", "type": "http", "service": 4}],
        ["ok"],
    ],
)
def test_the_rest_of_the_shape_is_still_validated(configs_route, selection):
    assert not configs_route._valid_config_selection(selection)


def test_one_bad_row_fails_the_batch(configs_route):
    assert not configs_route._valid_config_selection(_selection("my.conf") + _selection("bad\nname"))


# ---------------------------------------------------------------------------- the delete route end to end


class _Data(dict):
    load_from_file = Mock()


@pytest.fixture
def delete_app(configs_route, monkeypatch):
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    monkeypatch.setattr(configs_route, "handle_error", lambda message, *_args, **_kwargs: (message, 400))
    monkeypatch.setattr(configs_route, "verify_data_in_form", lambda **_kwargs: True)
    monkeypatch.setattr(configs_route, "wait_applying", Mock())
    monkeypatch.setattr(configs_route, "DATA", _Data(TO_FLASH=[]))
    monkeypatch.setattr(configs_route, "submit_config_task", lambda function, *args: function(*args))
    configs_route.API_CLIENT.reset_mock()
    configs_route.API_CLIENT.readonly = False
    app.add_url_rule("/configs/delete", endpoint="configs_delete", view_func=configs_route.configs_delete.__wrapped__, methods=["POST"])
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
    app.add_url_rule("/configs", endpoint="configs.configs_page", view_func=lambda: "configs")
    return app


def _delete(app, selection):
    from json import dumps
    from types import SimpleNamespace

    with patch("app.utils.current_user", SimpleNamespace(list_permissions=["read", "write"])), app.test_client() as client:
        return client.post("/configs/delete", data={"configs": dumps(selection)})


def test_a_dotted_file_config_is_reported_skipped_and_the_rest_is_still_deleted(configs_route, delete_app):
    configs_route.API_CLIENT.delete_configs.return_value = {"deleted": ["app.example.com/server_http/mine"], "skipped": []}
    selection = _selection("mine") + _selection("my.conf")

    response = _delete(delete_app, selection)

    assert response.status_code == 302, response.data
    # The API validates every name of a batch: sending `my.conf` would fail the lot with a 422.
    configs_route.API_CLIENT.delete_configs.assert_called_once_with(_selection("mine"))
    flashed = [item["content"] for item in configs_route.DATA["TO_FLASH"]]
    assert any("app.example.com/server_http/my.conf" in message for message in flashed), flashed
    assert any(item["type"] == "success" for item in configs_route.DATA["TO_FLASH"])


def test_a_selection_of_only_dotted_names_never_reaches_the_api(configs_route, delete_app):
    response = _delete(delete_app, _selection("my.conf"))

    assert response.status_code == 302, response.data
    configs_route.API_CLIENT.delete_configs.assert_not_called()
    flashed = [item["content"] for item in configs_route.DATA["TO_FLASH"]]
    assert any("my.conf" in message for message in flashed), flashed
    assert all(item["type"] == "error" for item in configs_route.DATA["TO_FLASH"])

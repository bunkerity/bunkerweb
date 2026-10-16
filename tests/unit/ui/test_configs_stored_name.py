"""A custom config opens and renames by the name it is stored under (dev dd5a1cd8c).

``configs_edit`` ran the URL name and the posted name through ``werkzeug.secure_filename``, which strips
leading/trailing ``_`` and every non-ASCII letter: a config stored as ``_snippet_`` or ``café`` was looked up as
``snippet`` / ``caf`` and answered "does not exist". The create path keeps ``CONFIG_NAME_RX``.

Same loader idiom as ``test_configs_write_permission.py``.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "configs.py"

SERVICE = "app.example.com"
NAMES = ("_snippet_", "snippet_", "_snippet", "café", "ünï_cøde")


@pytest.fixture
def configs_route(monkeypatch):
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = {}

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()

    module_name = "app.routes._configs_stored_name_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
        yield module


def _config(name):
    return {"service": None, "type": "http", "name": name, "method": "ui", "template": "", "data": "x", "is_draft": False}


@pytest.fixture
def stored(configs_route, monkeypatch):
    """API_CLIENT holds exactly one config; it only answers for the exact name it is stored under."""
    holder = {"name": None}

    def get_config_item(_service, _type, name, **_kwargs):
        return _config(name) if name == holder["name"] else None

    api = configs_route.API_CLIENT
    api.readonly = False
    api.get_config_item.side_effect = get_config_item
    configs_route.BW_CONFIG.get_config.return_value = {"SERVER_NAME": SERVICE}
    monkeypatch.setattr(configs_route, "handle_error", lambda message, *_a, **_k: ("ERROR: " + message, 404))
    monkeypatch.setattr(configs_route, "render_template", lambda *_a, **kwargs: "OK:" + kwargs["name"])
    monkeypatch.setattr(configs_route, "flash", Mock())
    monkeypatch.setattr(configs_route, "verify_data_in_form", lambda **_k: True)
    monkeypatch.setattr(configs_route, "is_readonly_request", lambda *_a, **_k: False)
    monkeypatch.setattr(configs_route, "DATA", Mock())
    return holder


@pytest.fixture
def app(configs_route):
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    app.add_url_rule(
        "/configs/<string:service>/<string:config_type>/<string:name>",
        endpoint="configs.configs_edit",
        view_func=configs_route.configs_edit.__wrapped__,
        methods=["GET", "POST"],
    )
    app.add_url_rule("/configs", endpoint="configs", view_func=lambda: "configs")
    return app


@pytest.mark.parametrize("name", NAMES)
def test_edit_page_opens_by_stored_name(app, stored, name):
    stored["name"] = name
    with app.test_client() as client:
        response = client.get(f"/configs/global/http/{name}")
    assert response.data.decode() == f"OK:{name}"


@pytest.mark.parametrize("name", NAMES)
def test_rename_keeps_the_stored_name_and_the_new_one_verbatim(configs_route, app, stored, name):
    stored["name"] = name
    new_name = f"{name}_2" if name.isascii() else "ünï_cøde_2"
    with app.test_client() as client:
        client.post(
            f"/configs/global/http/{name}",
            data={"service": "global", "type": "HTTP", "name": new_name, "value": "changed"},
        )
    configs_route.API_CLIENT.update_config.assert_called_once()
    args, kwargs = configs_route.API_CLIENT.update_config.call_args
    assert args[2] == name, "the config is addressed by its stored name"
    assert kwargs["body"]["name"] == new_name, "the posted name is stored as typed"


def test_rename_still_refuses_a_name_outside_the_pattern(configs_route, app, stored):
    stored["name"] = "snippet"
    with app.test_client() as client:
        response = client.post("/configs/global/http/snippet", data={"service": "global", "type": "HTTP", "name": "bad name!", "value": "x"})
    assert not configs_route.API_CLIENT.update_config.called
    assert b"Invalid name" in response.data or b"invalid" in response.data.lower()

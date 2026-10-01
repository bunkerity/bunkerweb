"""N-H2: ``/configs/new?clone=nope`` raised ``ValueError: not enough values to unpack``
(``routes/configs.py``'s ``configs_new`` did ``config_service, config_type, config_name =
clone.split("/")`` on a clone reference with no ``/`` in it), and a well-formed but unknown
``service/type/name`` clone crashed the same way once ``get_config_item`` stopped raising on 404
(it now returns ``None``, and the old code called ``.get(...)`` on that ``None`` unconditionally).
Both are now a flash + the create form rendered with an empty clone, instead of a bare 500.

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


@pytest.fixture
def configs_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = {}

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()

    module_name = "app.routes._configs_new_clone_unknown_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def route_app(configs_route):
    module = configs_route
    module.API_CLIENT.reset_mock(return_value=True, side_effect=True)
    module.BW_CONFIG.get_config.return_value = {"SERVER_NAME": "example.com"}
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    return module, app


def _render_kwargs(module, monkeypatch, query_string):
    render = Mock(return_value="rendered")
    flash = Mock()
    monkeypatch.setattr(module, "render_template", render)
    monkeypatch.setattr(module, "flash", flash)
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    with app.test_request_context(f"/configs/new?{query_string}"):
        result = module.configs_new.__wrapped__()
    assert result == "rendered"
    return render.call_args.kwargs, flash


def test_clone_with_no_slash_does_not_raise(route_app, monkeypatch):
    module, _app = route_app

    kwargs, flash = _render_kwargs(module, monkeypatch, "clone=nope")

    assert kwargs["config_value"] == ""
    assert kwargs["config_service"] == ""
    flash.assert_called_once()
    assert "nope" in flash.call_args.args[0]


def test_clone_of_unknown_config_does_not_raise(route_app, monkeypatch):
    module, _app = route_app
    module.API_CLIENT.get_config_item.return_value = None  # ApiClient's post-fix 404 behaviour

    kwargs, flash = _render_kwargs(module, monkeypatch, "clone=global/http/nope")

    assert kwargs["config_value"] == ""
    assert kwargs["config_service"] == ""
    assert kwargs["name"] == ""
    flash.assert_called_once()


def test_clone_of_existing_config_still_prefills(route_app, monkeypatch):
    module, _app = route_app
    module.API_CLIENT.get_config_item.return_value = {"data": "# hello", "is_draft": False}

    kwargs, flash = _render_kwargs(module, monkeypatch, "clone=global/http/mysnippet")

    assert kwargs["config_value"] == "# hello"
    assert kwargs["config_service"] == "global"
    assert kwargs["name"] == "mysnippet"
    flash.assert_not_called()

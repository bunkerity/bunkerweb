"""The setup wizard refuses a blank hostname (dev cea19bc67).

An empty per-service ``SERVER_NAME`` renders ``server_name ;`` and makes nginx refuse the whole
configuration. The API and the service editor refuse it; the wizard posted
``request.form["server_name"]`` straight through, so a blank or whitespace-only hostname created the
first service with no name.

Route loading follows ``test_setup_reserved_default_server.py``.
"""

import importlib.util
import sys
from html import unescape
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user


class _AdminUser(UserMixin):
    list_permissions = ("read", "write")

    def get_id(self):
        return "admin"


@pytest.fixture(scope="module")
def setup_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.DATA = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    module_name = "app.routes._setup_empty_hostname_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "setup.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def route_app(setup_route):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(setup_route.setup)
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: _AdminUser())
    return setup_route, app


# An admin already exists, so the admin-creation block is skipped and the POST reaches the service branch.
_BASE_FORM = {
    "theme": "light",
    "ui_host": "http://app.example.com",
    "ui_url": "/",
    "lets_encrypt_staging": "no",
    "lets_encrypt_wildcard": "no",
    "email_lets_encrypt": "",
    "lets_encrypt_challenge": "http",
    "lets_encrypt_profile": "classic",
    "lets_encrypt_custom_profile": "",
    "lets_encrypt_dns_provider": "",
    "lets_encrypt_dns_propagation": "default",
}


def _post(module, app, server_name):
    module.API_CLIENT.readonly = False
    module.API_CLIENT.get_admin_user.return_value = {"id": "admin", "username": "admin"}
    module.BW_CONFIG.get_config.return_value = {"SERVER_NAME": ""}
    module.BW_CONFIG.new_service.reset_mock()
    module.BW_CONFIG.new_service.return_value = ("", "")
    module.BW_CONFIG.edit_service.reset_mock()
    module.BW_CONFIG.edit_service.return_value = ("", "")
    module.BW_CONFIG.edit_global_conf.reset_mock()

    with app.test_request_context("/setup", method="POST", data={**_BASE_FORM, "server_name": server_name}):
        login_user(_AdminUser())
        module.setup_page()
        # flash() HTML-escapes the message
        return [(category, unescape(message)) for category, message in get_flashed_messages(with_categories=True)]


@pytest.mark.parametrize("server_name", ["", " ", "   ", "\t \n"])
def test_a_blank_hostname_is_refused_and_nothing_is_saved(route_app, server_name):
    module, app = route_app

    messages = _post(module, app, server_name)

    assert messages == [("error", "The hostname can't be empty.")]
    module.BW_CONFIG.new_service.assert_not_called()
    module.BW_CONFIG.edit_service.assert_not_called()
    module.BW_CONFIG.edit_global_conf.assert_not_called()


def test_an_ordinary_hostname_is_not_refused_as_empty(route_app):
    module, app = route_app

    messages = _post(module, app, "app1.example.com")

    assert ("error", "The hostname can't be empty.") not in messages
    module.BW_CONFIG.new_service.assert_called_once()

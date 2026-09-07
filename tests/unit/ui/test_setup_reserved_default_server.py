"""``routes/setup.py`` was the third create surface with no reserved-id refusal (DS-B4
handoff item 1, `.cache/results-2026-09-02-wave12/handoff-DS-B4.md` "Recorded, NOT built" #1):
`routes/services.py` and the API's `POST /services` both refuse a service named
``default-server``, but the setup wizard's own service-creation branch posted
``request.form["server_name"]`` straight through, catching the collision only incidentally
(and only once the reserved row is actually in the roster, which single-site never has).

Route loading follows ``test_bans_stats.py``'s module-loader pattern.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages
from flask_login import LoginManager, UserMixin


class _AdminUser(UserMixin):
    def get_id(self):
        return "admin"


@pytest.fixture(scope="module")
def setup_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.DATA = Mock()
    # routes/utils.py (imported for REVERSE_PROXY_PATH/handle_error) pulls in qrcode.main.QRCode,
    # unavailable in the pared-down unit-test venv -- same stub shape as test_bans_stats.py.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    module_name = "app.routes._setup_reserved_default_server_test"
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


# The form fields needed to reach the create-service branch with an admin already present, so
# the admin-creation block (which needs its own separate fields) is skipped entirely.
_BASE_FORM = {"theme": "light", "ui_host": "app.example.com", "ui_url": "/"}


def _post_new_service(module, app, server_name):
    module.API_CLIENT.readonly = False
    module.API_CLIENT.get_admin_user.return_value = {"id": "admin", "username": "admin"}
    module.BW_CONFIG.get_config.return_value = {"SERVER_NAME": ""}

    with app.test_request_context("/setup", method="POST", data={**_BASE_FORM, "server_name": server_name}):
        from flask_login import login_user

        login_user(_AdminUser())
        response = module.setup_page()
        messages = get_flashed_messages(with_categories=True)
    return response, messages


def test_creating_a_service_named_default_server_is_refused(route_app):
    module, app = route_app

    response, messages = _post_new_service(module, app, "default-server")

    assert messages == [("error", module.DEFAULT_SERVER_RESERVED_MESSAGE)]
    module.API_CLIENT.create_user.assert_not_called()


def test_creating_an_ordinary_service_is_not_touched_by_the_new_guard(route_app):
    module, app = route_app

    response, messages = _post_new_service(module, app, "app1.example.com")

    assert not any(category == "error" and message == module.DEFAULT_SERVER_RESERVED_MESSAGE for category, message in messages)

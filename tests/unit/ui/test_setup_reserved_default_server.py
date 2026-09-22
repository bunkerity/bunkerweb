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
from werkzeug.exceptions import BadRequestKeyError


class _AdminUser(UserMixin):
    # The wizard's POST is reachable while LOGGED IN -- `setup.py` only bounces an ANONYMOUS
    # session back to the login page when an admin already exists but no UI service does. So the
    # route now also checks the session's `write` permission, and `is_readonly_request`
    # (app/utils.py) reads exactly this attribute.
    list_permissions = ("read", "write")

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


def _post_new_service(module, app, server_name, permissions=("read", "write")):
    module.API_CLIENT.readonly = False
    module.API_CLIENT.get_admin_user.return_value = {"id": "admin", "username": "admin"}
    module.BW_CONFIG.get_config.return_value = {"SERVER_NAME": ""}
    module.BW_CONFIG.new_service.reset_mock()

    user = _AdminUser()
    user.list_permissions = permissions
    with app.test_request_context("/setup", method="POST", data={**_BASE_FORM, "server_name": server_name}):
        from flask_login import login_user

        login_user(user)
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


def test_a_logged_in_session_without_write_cannot_finish_the_wizard(route_app):
    """`setup.py` has no `@login_required`, which is why the whole module was first exempted from
    the write-permission rule -- but the exemption only holds for the ANONYMOUS first install. When
    an admin already exists and no UI service does (an env-var-created admin, a wizard that never
    finished), the route bounces an anonymous caller to the login page and lets an AUTHENTICATED
    one straight through to the POST, where it edits the global config and creates a service. A
    role without `write` must not reach that."""
    module, app = route_app

    response, messages = _post_new_service(module, app, "app1.example.com", permissions=("read",))

    # The permission refusal is the FIRST thing in the POST branch, so it must run before the field
    # validation this deliberately-minimal form would otherwise trip ("The hostname is not
    # valid."). Before the gate existed that is exactly what came back instead.
    assert messages == [("error", "You do not have the write permission")], messages
    assert not module.BW_CONFIG.new_service.called
    assert not module.BW_CONFIG.edit_global_conf.called


def test_the_anonymous_first_install_is_not_asked_for_the_write_permission(route_app):
    # First boot: no admin exists and nobody is logged in. `is_readonly_request` reads
    # `current_user.list_permissions`, which is `[]` for the anonymous user, so without the
    # `is_authenticated` guard in front of it the wizard would refuse the very first install.
    module, app = route_app
    module.API_CLIENT.readonly = False
    module.API_CLIENT.get_admin_user.return_value = None
    module.BW_CONFIG.get_config.return_value = {"SERVER_NAME": ""}

    with app.test_request_context("/setup", method="POST", data={**_BASE_FORM, "server_name": "app.example.com"}):
        # Past the gate, the first install reads the admin-creation fields this form does not carry:
        # the 400 proves the request got THROUGH the permission check instead of being refused.
        with pytest.raises(BadRequestKeyError):
            module.setup_page()
        messages = get_flashed_messages(with_categories=True)

    assert ("error", "You do not have the write permission") not in messages

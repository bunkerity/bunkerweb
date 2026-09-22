"""`/instances/<action>` shares one route between `ping` and the three mutating actions.

The wave-21 write gate (`is_readonly_request`) refused the whole route to a session holding
`read` only, which also took `ping` away -- a health probe that changes nothing. `ping` must keep
answering such a session; `reload`, `stop` and `delete` must still be refused before any instance
is touched. Same loader idiom as `test_configs_write_permission.py`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "instances.py"


class _Data(dict):
    load_from_file = Mock()


@pytest.fixture
def route_app(monkeypatch):
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = _Data()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()

    module_name = "app.routes._instances_write_permission_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)

        monkeypatch.setattr(module, "handle_error", lambda message, *_args, **_kwargs: (message, 403))
        monkeypatch.setattr(module, "verify_data_in_form", lambda **_kwargs: True)
        ping = Mock(return_value="pong")
        monkeypatch.setattr(module.Instance, "from_hostname", classmethod(lambda cls, hostname, api: SimpleNamespace(ping=ping)))
        module.API_CLIENT.get_instances.return_value = [{"hostname": "bw-1", "method": "ui"}]

        app = Flask(__name__)
        app.secret_key = "test"  # nosec B105 - unit test
        app.add_url_rule("/instances/<string:action>", view_func=module.instances_action.__wrapped__, methods=["POST"])
        app.add_url_rule("/instances", endpoint="instances.instances_page", view_func=lambda: "instances")
        app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
        app.module = module
        app.ping = ping
        yield app


def _read_only_user():
    return patch("app.utils.current_user", SimpleNamespace(list_permissions=["read"]))


def test_a_session_without_write_can_still_ping(route_app):
    with _read_only_user(), route_app.test_client() as client:
        response = client.post("/instances/ping", data={"instances": "bw-1"})

    assert response.status_code == 200, response.data
    assert response.get_json() == {"succeed": ["bw-1"], "failed": []}
    route_app.ping.assert_called_once()


@pytest.mark.parametrize("action", ("reload", "stop", "delete"))
def test_a_session_without_write_cannot_mutate_instances(route_app, action):
    with _read_only_user(), route_app.test_client() as client:
        response = client.post(f"/instances/{action}", data={"instances": "bw-1"})

    assert response.status_code == 403
    assert b"write permission" in response.data
    assert not route_app.module.API_CLIENT.delete_instances.called
    assert not route_app.module.CONFIG_TASKS_EXECUTOR.submit.called

"""QA-UI-5 N-M5/item 1 tail: ``/services/<unknown>`` redirected to ``/services`` with no
message, silently. Fixed with a flash naming the missing service.

Harness: the loader of ``test_service_new_name_feedback.py``.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages

REPO_ROOT = Path(__file__).resolve().parents[3]


def _import_services_module():
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
    module_name = "app.routes._services_test_unknown_id_flash"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MODULE = _import_services_module()


@pytest.fixture
def route_app(monkeypatch):
    bw_config = Mock()
    bw_config.get_config.return_value = {"SERVER_NAME": "app.example.com other.example.com"}
    monkeypatch.setattr(MODULE, "BW_CONFIG", bw_config)
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    app.register_blueprint(MODULE.services)
    return app


def test_unknown_service_id_redirects_with_a_flash(route_app):
    with route_app.test_request_context("/services/qa5-unknown.example.com"):
        response = MODULE.services_service_page.__wrapped__("qa5-unknown.example.com")
        messages = get_flashed_messages(with_categories=True)

    assert response.status_code == 302
    assert ("error", "Service qa5-unknown.example.com does not exist.") in messages

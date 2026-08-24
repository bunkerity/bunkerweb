import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask


class _Data(dict):
    def load_from_file(self):
        self["loaded"] = True


@pytest.fixture(scope="module")
def pro_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = _Data(IS_RELOADING_PLUGINS=True)
    route_utils = ModuleType("app.routes.utils")
    route_utils.get_remain = Mock()
    route_utils.handle_error = Mock()
    route_utils.verify_data_in_form = Mock()
    route_utils.wait_applying = Mock()
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    app_utils.billable_service_count = Mock(return_value=0)
    module_name = "app.routes._pro_refresh_test"
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


def test_refresh_ui_rearms_extraction_and_schedules_a_plugin_reload(pro_route):
    pro_route.API_CLIENT.reset_mock()
    pro_route.DATA.clear()
    pro_route.DATA["IS_RELOADING_PLUGINS"] = True
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(pro_route.pro)

    with app.test_request_context("/pro/refresh-ui", method="POST"):
        response = pro_route.refresh_ui.__wrapped__()

    assert response.status_code == 302
    assert response.location == "/pro"
    assert pro_route.DATA == {"IS_RELOADING_PLUGINS": False, "loaded": True}
    pro_route.API_CLIENT.checked_changes.assert_called_once_with(["ui_plugins"], value=True)

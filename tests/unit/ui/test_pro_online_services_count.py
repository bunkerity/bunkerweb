"""``pro_page()``'s ``online_services`` count included the reserved default-server row in
multisite (DS-B4 handoff item 4 / RES-1 item 6e): the row is never a draft, so it fell through
the ``is_draft`` check straight into the "online" bucket, inflating the PRO page's non-billable
count by one on every multisite deployment.

Route loading follows ``test_pro_refresh.py``'s module-loader pattern. ``render_template`` is
monkeypatched to a recorder -- this test is about the count, not the template.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask


@pytest.fixture(scope="module")
def pro_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    route_utils = ModuleType("app.routes.utils")
    route_utils.get_remain = Mock(return_value=("Unknown", "Unknown"))
    route_utils.handle_error = Mock()
    route_utils.verify_data_in_form = Mock()
    route_utils.wait_applying = Mock()
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    app_utils.billable_service_count = Mock(return_value=0)

    module_name = "app.routes._pro_online_services_count_test"
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


def _render_pro_page(module, monkeypatch, services):
    module.API_CLIENT.get_services.return_value = services
    module.API_CLIENT.get_metadata.return_value = {"pro_expire": None}
    module.BW_CONFIG.get_config.return_value = {"PRO_LICENSE_KEY": ""}

    captured = {}

    def fake_render_template(_name, **kwargs):
        captured.update(kwargs)
        return ""

    monkeypatch.setattr(module, "render_template", fake_render_template)

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.pro)
    with app.test_request_context("/pro"):
        module.pro_page.__wrapped__()
    return captured


def test_the_reserved_default_server_is_not_counted_as_an_online_service(pro_route, monkeypatch):
    services = [
        {"id": "app1.example.com", "method": "ui", "is_draft": False},
        {"id": "default-server", "method": "wizard", "is_draft": False},
    ]

    captured = _render_pro_page(pro_route, monkeypatch, services)

    assert captured["online_services"] == 1
    assert captured["draft_services"] == 0


def test_an_operator_owned_row_named_default_server_still_counts(pro_route, monkeypatch):
    """Id alone is not enough -- a pre-1.7 row an operator created under that name is an
    ordinary, billable service and must keep being counted."""
    services = [{"id": "default-server", "method": "ui", "is_draft": False}]

    captured = _render_pro_page(pro_route, monkeypatch, services)

    assert captured["online_services"] == 1

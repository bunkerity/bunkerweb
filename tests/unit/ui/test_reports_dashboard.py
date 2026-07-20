"""UI-layer contracts for the reports dashboard glue (Task 6): the 3 new ``ApiClient``
metrics methods and the new ``/reports/dashboard`` Flask route.

Follows the module-loader pattern established by ``test_web_cache.py`` (the immediately
preceding feature in this repo, same shape: new ``ApiClient`` methods + a new Flask
route) — ``app.dependencies`` is stubbed before loading ``reports.py`` since it boots
container-only state (real API/DB connections) at import time; everything else
(``app.utils``, ``app.routes.utils``) imports for real.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call, patch

import pytest
from flask import Flask

from app.api_client import ApiClient


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


@pytest.fixture(scope="module")
def reports_route():
    """Load route without booting container-only app.dependencies state.

    ``reports.py`` also unconditionally imports ``openpyxl`` (Excel export) and
    (transitively, via ``app.routes.utils``) ``qrcode`` — neither is installed in the
    pared-down unit-test venv (see ``tests/unit/requirements.txt``), and neither is
    exercised by these tests (they only cover ``reports_dashboard``, not the export
    routes), so both are stubbed out rather than adding new pinned deps to the shared
    test venv for unrelated code paths.
    """
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = None
    dependencies.BW_INSTANCES_UTILS = None
    openpyxl = ModuleType("openpyxl")
    openpyxl.Workbook = Mock()
    openpyxl_styles = ModuleType("openpyxl.styles")
    openpyxl_styles.Font = Mock()
    openpyxl_styles.PatternFill = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._reports_dashboard_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "reports.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "openpyxl": openpyxl,
        "openpyxl.styles": openpyxl_styles,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def route_app(reports_route):
    module, client = reports_route
    client.reset_mock(return_value=True, side_effect=True)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.reports)
    return module, client, app


def test_api_client_metrics_dashboard_paths(api_client, monkeypatch):
    get = Mock(return_value={})
    monkeypatch.setattr(api_client, "_get", get)

    api_client.get_metrics_timeseries(start=0, end=3600, bucket="hour", search_panes="ip:1.2.3.4")
    api_client.get_metrics_top_offenders(start=0, end=3600, limit=5, search_panes="")
    api_client.get_metrics_top_rules(start=0, end=3600, limit=5)

    assert get.call_args_list == [
        call("/metrics/requests/timeseries", params={"start": 0, "end": 3600, "bucket": "hour", "search_panes": "ip:1.2.3.4"}),
        call("/metrics/requests/top-offenders", params={"start": 0, "end": 3600, "limit": 5, "search_panes": ""}),
        call("/metrics/requests/top-rules", params={"start": 0, "end": 3600, "limit": 5}),
    ]


def test_dashboard_default_start_end_and_bucket(route_app, monkeypatch):
    module, client, app = route_app
    frozen_now = Mock()
    frozen_now.timestamp.return_value = 1704067200.0
    frozen_datetime = Mock()
    frozen_datetime.now.return_value = frozen_now
    monkeypatch.setattr(module, "datetime", frozen_datetime)
    client.get_metrics_timeseries.return_value = {"buckets": [], "counts": [], "total": 0}
    client.get_metrics_top_offenders.return_value = {"offenders": []}
    client.get_metrics_top_rules.return_value = {"rules": []}

    with app.test_request_context("/reports/dashboard", method="POST", data={}):
        response = module.reports_dashboard.__wrapped__.__wrapped__()

    assert response.status_code == 200
    client.get_metrics_timeseries.assert_called_once_with(start=1704067200 - 86400, end=1704067200, bucket="hour")
    client.get_metrics_top_offenders.assert_called_once_with(start=1704067200 - 86400, end=1704067200, limit=10)
    client.get_metrics_top_rules.assert_called_once_with(start=1704067200 - 86400, end=1704067200, limit=10)


def test_dashboard_invalid_start_returns_400(route_app):
    module, client, app = route_app

    with app.test_request_context("/reports/dashboard", method="POST", data={"start": "not-a-number", "end": "3600"}):
        response, status = module.reports_dashboard.__wrapped__.__wrapped__()

    assert status == 400
    assert response.get_json() == {"status": "error", "message": "Invalid start/end"}
    client.get_metrics_timeseries.assert_not_called()


def test_dashboard_api_error_returns_503(route_app):
    module, client, app = route_app
    client.get_metrics_timeseries.side_effect = module.ApiClientError("down")

    with app.test_request_context("/reports/dashboard", method="POST", data={"start": "0", "end": "3600"}):
        response, status = module.reports_dashboard.__wrapped__.__wrapped__()

    assert status == 503
    assert response.get_json() == {"status": "error", "message": "Metrics service unavailable"}


def test_dashboard_success_payload_shape(route_app):
    module, client, app = route_app
    client.get_metrics_timeseries.return_value = {"buckets": [0], "counts": [1], "total": 1}
    client.get_metrics_top_offenders.return_value = {"offenders": [{"ip": "1.2.3.4"}]}
    client.get_metrics_top_rules.return_value = {"rules": [{"rule_id": "942100", "count": 1}]}

    with app.test_request_context("/reports/dashboard", method="POST", data={"start": "0", "end": "3600", "bucket": "hour"}):
        response = module.reports_dashboard.__wrapped__.__wrapped__()

    assert response.get_json() == {
        "status": "success",
        "timeseries": {"buckets": [0], "counts": [1], "total": 1},
        "offenders": [{"ip": "1.2.3.4"}],
        "rules": [{"rule_id": "942100", "count": 1}],
    }
    client.get_metrics_timeseries.assert_called_once_with(start=0, end=3600, bucket="hour")
    client.get_metrics_top_offenders.assert_called_once_with(start=0, end=3600, limit=10)
    client.get_metrics_top_rules.assert_called_once_with(start=0, end=3600, limit=10)

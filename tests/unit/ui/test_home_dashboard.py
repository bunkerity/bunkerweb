"""UI-layer contracts for the home dashboard glue (Phase 2): the extended
``home_page()`` context (metadata / MFA / jobs / bans / top-reasons, each defaulting
independently to an empty state on API failure) and the new ``POST /home/dashboard``
route.

Follows the module-loader pattern established by ``test_reports_dashboard.py`` (the
reference implementation for this exact shape: new ``ApiClient`` methods + a new Flask
route) -- ``app.dependencies`` is stubbed before loading ``home.py`` since it boots
container-only state (real API/DB connections) at import time. ``psutil`` is also
stubbed since it isn't installed in the pared-down unit-test venv (see
``tests/unit/requirements.txt``) and ``virtual_memory()`` is a real system call
unrelated to the logic under test here.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

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


def _fake_virtual_memory():
    return SimpleNamespace(total=16 * 1024**3, used=8 * 1024**3, available=8 * 1024**3)


@pytest.fixture(scope="module")
def home_route():
    client = Mock()
    instances_utils = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_INSTANCES_UTILS = instances_utils
    dependencies.BW_CONFIG = None
    psutil_stub = ModuleType("psutil")
    psutil_stub.virtual_memory = _fake_virtual_memory
    # home.py -> app.routes.utils (for cors_required) -> qrcode.main.QRCode, not
    # installed in the pared-down unit-test venv and unexercised by these tests --
    # same stub test_reports_dashboard.py uses for the same transitive import.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._home_dashboard_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "home.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "psutil": psutil_stub,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, instances_utils


@pytest.fixture
def route_app(home_route):
    module, client, instances_utils = home_route
    client.reset_mock(return_value=True, side_effect=True)
    instances_utils.reset_mock(return_value=True, side_effect=True)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.home)
    return module, client, instances_utils, app


def _stub_home_aggregates(instances_utils):
    instances_utils.get_home_aggregates.return_value = {
        "request_countries": {},
        "top_blocked_ips": {},
        "blocked_unique_ips": 0,
        "time_buckets": {},
    }
    instances_utils.get_metrics.return_value = {}
    instances_utils.get_instances.return_value = []


def _render_and_capture(module, monkeypatch):
    """Patch render_template to capture the kwargs home_page() passes it, returning the
    dict so callers can assert on individual context keys."""
    captured = {}

    def fake_render_template(template_name, **context):
        captured["template"] = template_name
        captured.update(context)
        return "rendered"

    monkeypatch.setattr(module, "render_template", fake_render_template)
    return captured


# ── ApiClient methods (get_metadata / get_jobs) -- the 2 new-to-Home client calls;
#    get_metrics_requests/get_metrics_timeseries/get_metrics_top_offenders already have
#    their own contract tests in test_reports_dashboard.py. ─────────────────────────


def test_api_client_get_metadata(api_client, monkeypatch):
    get = Mock(return_value={"metadata": {"is_initialized": True, "first_config_saved": False}})
    monkeypatch.setattr(api_client, "_get", get)

    assert api_client.get_metadata() == {"is_initialized": True, "first_config_saved": False}
    get.assert_called_once_with("/metadata")


def test_api_client_get_jobs(api_client, monkeypatch):
    get = Mock(return_value={"jobs": {"job1": {}, "job2": {}}})
    monkeypatch.setattr(api_client, "_get", get)

    assert api_client.get_jobs() == {"job1": {}, "job2": {}}
    get.assert_called_once_with("/jobs")


# ── home_page() context ─────────────────────────────────────────────────────────────


def test_home_page_context_happy_path(route_app, monkeypatch):
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    instances_utils.get_bans.return_value = [{"ip": "1.2.3.4"}, {"ip": "5.6.7.8"}]
    client.get_services.return_value = []
    client.get_metadata.return_value = {"is_initialized": True, "first_config_saved": True}
    client.get_jobs.return_value = {"job1": {}, "job2": {}}
    client.get_metrics_requests.return_value = {
        "pane_counts": {
            "reason": {
                "modsecurity": {"total": 30, "count": 30},
                "antibot": {"total": 10, "count": 10},
            }
        }
    }
    monkeypatch.setattr(module, "current_user", SimpleNamespace(totp_secret="a-secret"))
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        result = module.home_page.__wrapped__()

    assert result == "rendered"
    assert captured["template"] == "home.html"
    assert captured["is_initialized"] is True
    assert captured["first_config_saved"] is True
    assert captured["mfa_enabled"] is True
    assert captured["jobs_count"] == 2
    assert captured["bans_active"] == 2
    assert captured["top_reasons"] == [
        {"reason": "modsecurity", "count": 30, "pct": 75.0},
        {"reason": "antibot", "count": 10, "pct": 25.0},
    ]


def test_home_page_context_defaults_to_empty_state_on_api_failure(route_app, monkeypatch):
    """Every new context piece is fetched independently under its own try/except, so one
    failing dependency (metadata, jobs, bans, reason facets) must degrade only its own
    field to a safe empty value -- never blow up the whole page."""
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    instances_utils.get_bans.side_effect = Exception("redis unreachable")
    client.get_services.return_value = []
    client.get_metadata.side_effect = module.ApiUnavailableError("metadata down")
    client.get_jobs.side_effect = module.ApiClientError("jobs down")
    client.get_metrics_requests.side_effect = module.ApiClientError("metrics down")
    monkeypatch.setattr(module, "current_user", SimpleNamespace(totp_secret=None))
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    assert captured["is_initialized"] is False
    assert captured["first_config_saved"] is False
    assert captured["mfa_enabled"] is False
    assert captured["jobs_count"] == 0
    assert captured["bans_active"] == 0
    assert captured["top_reasons"] == []


def test_home_page_top_reasons_pct_uses_reason_total_not_grand_total_of_all_facets(route_app, monkeypatch):
    """reason_facets holds ONLY the "reason" pane's counts (already extracted from
    pane_counts before top_reasons is built) -- percentages must be computed against the
    sum of those reason totals, not accidentally against some other facet's total."""
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    instances_utils.get_bans.return_value = []
    client.get_services.return_value = []
    client.get_metadata.return_value = {}
    client.get_jobs.return_value = {}
    client.get_metrics_requests.return_value = {
        "pane_counts": {
            "reason": {"modsecurity": {"total": 3, "count": 3}},
            "country": {"US": {"total": 100, "count": 100}},
        }
    }
    monkeypatch.setattr(module, "current_user", SimpleNamespace(totp_secret=None))
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    assert captured["top_reasons"] == [{"reason": "modsecurity", "count": 3, "pct": 100.0}]


def test_home_page_top_reasons_limited_to_five_by_count_desc(route_app, monkeypatch):
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    instances_utils.get_bans.return_value = []
    client.get_services.return_value = []
    client.get_metadata.return_value = {}
    client.get_jobs.return_value = {}
    client.get_metrics_requests.return_value = {"pane_counts": {"reason": {f"reason{i}": {"total": i, "count": i} for i in range(1, 8)}}}
    monkeypatch.setattr(module, "current_user", SimpleNamespace(totp_secret=None))
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    assert [row["reason"] for row in captured["top_reasons"]] == ["reason7", "reason6", "reason5", "reason4", "reason3"]


# ── POST /home/dashboard -- mirrors reports_dashboard's start/end/bucket parsing and
#    400/503 error mapping (reports.py:172-199), trimmed to {timeseries, offenders}. ──


def test_home_dashboard_default_start_end_and_bucket(route_app, monkeypatch):
    module, client, instances_utils, app = route_app
    frozen_now = Mock()
    frozen_now.timestamp.return_value = 1704067200.0
    frozen_datetime = Mock()
    frozen_datetime.now.return_value = frozen_now
    monkeypatch.setattr(module, "datetime", frozen_datetime)
    client.get_metrics_timeseries.return_value = {"buckets": [], "counts": [], "total": 0}
    client.get_metrics_top_offenders.return_value = {"offenders": []}

    with app.test_request_context("/home/dashboard", method="POST", data={}):
        response = module.home_dashboard.__wrapped__.__wrapped__()

    assert response.status_code == 200
    client.get_metrics_timeseries.assert_called_once_with(start=1704067200 - 86400, end=1704067200, bucket="hour")
    client.get_metrics_top_offenders.assert_called_once_with(start=1704067200 - 86400, end=1704067200, limit=10)


def test_home_dashboard_invalid_start_returns_400(route_app):
    module, client, instances_utils, app = route_app

    with app.test_request_context("/home/dashboard", method="POST", data={"start": "not-a-number", "end": "3600"}):
        response, status = module.home_dashboard.__wrapped__.__wrapped__()

    assert status == 400
    assert response.get_json() == {"status": "error", "message": "Invalid start/end"}
    client.get_metrics_timeseries.assert_not_called()


def test_home_dashboard_api_error_returns_503(route_app):
    module, client, instances_utils, app = route_app
    client.get_metrics_timeseries.side_effect = module.ApiClientError("down")

    with app.test_request_context("/home/dashboard", method="POST", data={"start": "0", "end": "3600"}):
        response, status = module.home_dashboard.__wrapped__.__wrapped__()

    assert status == 503
    assert response.get_json() == {"status": "error", "message": "Metrics service unavailable"}


def test_home_dashboard_api_400_surfaces_as_400_not_503(route_app):
    module, client, instances_utils, app = route_app
    client.get_metrics_timeseries.side_effect = module.ApiClientError("requested range too large: 50000 buckets exceeds 10000", status_code=400)

    with app.test_request_context("/home/dashboard", method="POST", data={"start": "0", "end": "180000000"}):
        response, status = module.home_dashboard.__wrapped__.__wrapped__()

    assert status == 400
    assert response.get_json() == {"status": "error", "message": "requested range too large: 50000 buckets exceeds 10000"}


def test_home_dashboard_api_unavailable_error_still_returns_503(route_app):
    module, client, instances_utils, app = route_app
    client.get_metrics_timeseries.side_effect = module.ApiUnavailableError("API returned 502")

    with app.test_request_context("/home/dashboard", method="POST", data={"start": "0", "end": "3600"}):
        response, status = module.home_dashboard.__wrapped__.__wrapped__()

    assert status == 503
    assert response.get_json() == {"status": "error", "message": "Metrics service unavailable"}


def test_home_dashboard_success_payload_shape_has_no_rules_key(route_app):
    """Unlike reports_dashboard, home_dashboard has no attack-patterns tab to feed --
    the payload must be exactly {status, timeseries, offenders}, no "rules" key."""
    module, client, instances_utils, app = route_app
    client.get_metrics_timeseries.return_value = {"buckets": [0], "counts": [1], "total": 1}
    client.get_metrics_top_offenders.return_value = {"offenders": [{"ip": "1.2.3.4"}]}

    with app.test_request_context("/home/dashboard", method="POST", data={"start": "0", "end": "3600", "bucket": "hour"}):
        response = module.home_dashboard.__wrapped__.__wrapped__()

    assert response.get_json() == {
        "status": "success",
        "timeseries": {"buckets": [0], "counts": [1], "total": 1},
        "offenders": [{"ip": "1.2.3.4"}],
    }
    client.get_metrics_top_rules.assert_not_called()

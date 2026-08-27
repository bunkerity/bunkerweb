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


def test_api_client_get_last_job_run(api_client, monkeypatch):
    last_run = {"success": False}
    get = Mock(return_value={"last_run": last_run})
    monkeypatch.setattr(api_client, "_get", get)

    assert api_client.get_last_job_run("push-configs") == last_run
    get.assert_called_once_with("/jobs/push-configs/last-run")


# ── home_page() context ─────────────────────────────────────────────────────────────


def test_home_page_context_happy_path(route_app, monkeypatch):
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    client.get_bans.return_value = [{"ip": "1.2.3.4"}, {"ip": "5.6.7.8"}]
    client.get_services.return_value = []
    client.get_metadata.return_value = {"is_initialized": True, "first_config_saved": True}
    client.get_jobs.return_value = {
        "job1": {"history": [{"success": True}]},
        "job2": {"history": [{"success": False}]},
    }
    client.get_upstreams.return_value = {"total": 3, "upstreams": [{"id": "pool-a"}]}
    client.get_metrics_requests.return_value = {
        "pane_counts": {
            "reason": {
                "modsecurity": {"total": 30, "count": 30},
                "antibot": {"total": 10, "count": 10},
            }
        }
    }
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        result = module.home_page.__wrapped__()

    assert result == "rendered"
    assert captured["template"] == "home.html"
    assert captured["is_initialized"] is True
    assert captured["first_config_saved"] is True
    assert captured["jobs_count"] == 2
    assert captured["jobs_failed"] is True
    assert captured["bans_active"] == 2
    assert captured["upstreams_total"] == 3
    # The heavy aggregation is NOT part of this context any more: home.py:140-148 ships the
    # chart series empty on purpose so the shell paints before /home/metrics answers. Asserting
    # they are empty is the actual contract -- a non-empty value here would mean the heavy
    # aggregation crept back onto the first paint. `top_reasons` computation moved wholesale and
    # is covered in the /home/metrics section below.
    assert captured["request_countries"] == {}
    assert captured["request_ips"] == {}
    assert captured["time_buckets"] == {}
    assert captured["blocked_unique_ips"] == 0
    assert captured["countries_count"] == 0
    client.get_metrics_requests.assert_not_called()


def test_home_page_context_defaults_to_empty_state_on_api_failure(route_app, monkeypatch):
    """Every context piece is fetched independently under its own try/except, so one failing
    dependency (metadata, jobs, bans) must degrade only its own field to a safe empty value --
    never blow up the whole page.

    The reason-facet call is deliberately absent: it moved to /home/metrics, so asserting
    `top_reasons == []` here would pass against a hardcoded `[]` and prove nothing. Its real
    degradation is covered by test_home_metrics_degrades_to_empty_top_reasons_when_the_facet_api_fails.
    """
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    client.get_bans.side_effect = Exception("bans API down")
    client.get_services.return_value = []
    client.get_metadata.side_effect = module.ApiUnavailableError("metadata down")
    client.get_jobs.side_effect = module.ApiClientError("jobs down")
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    assert captured["is_initialized"] is False
    assert captured["first_config_saved"] is False
    assert captured["jobs_count"] == 0
    assert captured["jobs_failed"] is False
    assert captured["bans_active"] == 0


def test_home_page_ignores_older_failures_when_the_newest_run_succeeded(route_app, monkeypatch):
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    client.get_services.return_value = []
    client.get_metadata.return_value = {}
    client.get_jobs.return_value = {"push-configs": {"history": [{"success": True}, {"success": False}]}}
    captured = _render_and_capture(module, monkeypatch)

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    assert captured["jobs_failed"] is False


def test_upstreams_tile_links_to_the_live_page():
    template = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "home.html").read_text(encoding="utf-8")
    css = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "css" / "pages" / "home.css").read_text(encoding="utf-8")

    assert "url_for('upstreams.upstreams_page')" in template
    assert "value=upstreams_total" in template
    assert "is-planned" not in template
    assert "is-planned" not in css


# ── GET /home/metrics -- the heavy aggregation, moved off the first paint ────────────
#
# top_reasons used to be computed in home_page() and asserted through the render context.
# It now lives here (home.py:151-198), fetched by home.js after first paint, so these three
# assertions follow the logic rather than the route: same rules, new caller. The endpoint had
# NO tests at all before this -- the split moved the code and left its coverage behind.


def _call_home_metrics(module, app):
    """/home/metrics is @login_required + @cors_required, unwrapped the same way the
    /home/dashboard tests below unwrap the identical decorator pair."""
    with app.test_request_context("/home/metrics"):
        return module.home_metrics.__wrapped__.__wrapped__().get_json()


def test_home_metrics_top_reasons_pct_uses_reason_total_not_grand_total_of_all_facets(route_app):
    """reason_facets holds ONLY the "reason" pane's counts (already extracted from
    pane_counts before top_reasons is built) -- percentages must be computed against the
    sum of those reason totals, not accidentally against some other facet's total."""
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    client.get_metrics_requests.return_value = {
        "pane_counts": {
            "reason": {"modsecurity": {"total": 3, "count": 3}},
            "country": {"US": {"total": 100, "count": 100}},
        }
    }

    assert _call_home_metrics(module, app)["top_reasons"] == [{"reason": "modsecurity", "count": 3, "pct": 100.0}]


def test_home_metrics_top_reasons_limited_to_five_by_count_desc(route_app):
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    client.get_metrics_requests.return_value = {"pane_counts": {"reason": {f"reason{i}": {"total": i, "count": i} for i in range(1, 8)}}}

    payload = _call_home_metrics(module, app)

    assert [row["reason"] for row in payload["top_reasons"]] == ["reason7", "reason6", "reason5", "reason4", "reason3"]


def test_home_metrics_degrades_to_empty_top_reasons_when_the_facet_api_fails(route_app):
    """The facet call has its own try/except: a metrics outage empties this one field rather
    than erroring the dashboard. Asserted here because home_page() no longer calls it at all,
    which made the equivalent assertion in the home_page failure test vacuous."""
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    client.get_metrics_requests.side_effect = module.ApiClientError("metrics down")

    assert _call_home_metrics(module, app)["top_reasons"] == []


def test_home_metrics_degrades_to_an_empty_payload_when_the_aggregation_raises(route_app):
    """The 7-day aggregation is wrapped in a bare `except Exception` (home.py:163-167) so a
    Redis failure returns an empty 200 payload, not a 500 -- the chart containers are already
    on the page and would otherwise sit spinning forever."""
    module, client, instances_utils, app = route_app
    _stub_home_aggregates(instances_utils)
    instances_utils.get_home_aggregates.side_effect = Exception("redis unreachable")
    client.get_metrics_requests.return_value = {}

    payload = _call_home_metrics(module, app)

    assert payload["status"] == "success"
    assert payload["request_countries"] == {}
    assert payload["request_ips"] == {}
    assert payload["blocked_unique_ips"] == 0
    assert payload["time_buckets"] == {}
    assert payload["countries_count"] == 0


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

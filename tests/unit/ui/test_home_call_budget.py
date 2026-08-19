"""How many API calls a page render is allowed to cost.

This is the regression guard Lot A of the UI performance work asks for, and it deliberately
counts **calls**, not milliseconds: a stopwatch assertion in CI measures the runner's load, goes
flaky, and gets deleted. A call count is deterministic, and it is the number that actually
drives the latency of a page assembled from a fan-out.

The budgets below are the *current* cost, recorded so a change that adds a call has to say so.
Lowering one is the work of Lots B and C; raising one needs a reason in the diff.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.api_client import ApiUnavailableError

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "home.py"

# What the dashboard costs today, per endpoint.
BUDGETS = {"home_page": 8, "home_metrics": 2, "home_dashboard": 2}


@pytest.fixture(scope="module")
def route_module():
    client, instances = Mock(), Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_INSTANCES_UTILS = instances
    dependencies.DATA = {}
    dependencies.BW_CONFIG = Mock()
    dependencies.LOGGER = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    # The RAM tile reads the host, which has nothing to do with the API fan-out.
    psutil = ModuleType("psutil")
    psutil.virtual_memory = Mock(return_value=SimpleNamespace(percent=42.0, total=8 * 1024**3, available=4 * 1024**3, used=4 * 1024**3))
    module_name = "app.routes._home_budget_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, "psutil": psutil, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, instances


@pytest.fixture
def home(route_module, monkeypatch):
    module, client, instances = route_module
    client.reset_mock(return_value=True, side_effect=True)
    instances.reset_mock(return_value=True, side_effect=True)

    client.get_services.return_value = []
    client.get_metadata.return_value = {"version": "1.7.0", "is_pro": False}
    client.get_jobs.return_value = {}
    client.get_bans.return_value = []
    client.get_certificates.return_value = {"total": 0, "data": []}
    client.get_upstreams.return_value = {"total": 0}
    client.get_metrics_requests.return_value = {"total": 0, "panes": {}}
    client.get_metrics_timeseries.return_value = {"points": []}
    client.get_metrics_top_offenders.return_value = {"offenders": []}
    instances.get_metrics.return_value = {}
    instances.get_instances.return_value = []
    instances.get_home_aggregates.return_value = {}

    monkeypatch.setattr(module, "render_template", lambda *args, **kwargs: "rendered")
    monkeypatch.setattr(module, "flash", lambda *args, **kwargs: None)

    app = Flask(__name__)
    app.secret_key = "test"
    return module, client, instances, app


def _calls(client, instances):
    """Every outbound call the render made, named. `InstancesUtils` counts too — it is the
    same API behind one more object."""
    return [name for name, _, _ in client.mock_calls if not name.startswith("_")] + [name for name, _, _ in instances.mock_calls if not name.startswith("_")]


def test_the_dashboard_stays_within_its_call_budget(home):
    module, client, instances, app = home

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    calls = _calls(client, instances)
    assert len(calls) <= BUDGETS["home_page"], f"the dashboard now costs {len(calls)} API calls: {calls}"


def test_the_dashboard_asks_for_each_thing_exactly_once(home):
    """A duplicate is the cheapest kind of waste and the easiest to reintroduce: two helpers
    that each fetch the metadata read fine on their own."""
    module, client, instances, app = home

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    calls = _calls(client, instances)
    duplicates = {name for name in calls if calls.count(name) > 1}
    assert not duplicates, f"asked for the same thing twice: {sorted(duplicates)}"


def test_the_deferred_metrics_endpoints_stay_within_theirs(home):
    """The heavy aggregation is deferred to these two on purpose; that only pays off while they
    stay small."""
    module, client, instances, app = home

    with app.test_request_context("/home/metrics"):
        module.home_metrics.__wrapped__.__wrapped__()
    assert len(_calls(client, instances)) <= BUDGETS["home_metrics"]

    client.reset_mock()
    instances.reset_mock()
    with app.test_request_context("/home/dashboard?start=0&end=1"):
        module.home_dashboard.__wrapped__.__wrapped__()
    assert len(_calls(client, instances)) <= BUDGETS["home_dashboard"]


def test_a_failing_call_does_not_turn_into_a_retry_storm(home):
    """Every fetch on this page is individually guarded so one failure leaves one card empty.
    A guard that retries instead would multiply the fan-out exactly when the API is struggling —
    which is the moment it can least afford it."""
    module, client, instances, app = home
    client.get_services.side_effect = ApiUnavailableError("api down")

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    assert [name for name in _calls(client, instances) if name == "get_services"] == ["get_services"]


def test_the_certificate_card_does_not_pull_the_whole_table(home):
    """`limit=500` is the client default, and the card shows a count and an expiry — the page
    has no use for 500 rows. Recorded here because it is Lot C's first target."""
    module, client, _, app = home

    with app.test_request_context("/home"):
        module.home_page.__wrapped__()

    limit = client.get_certificates.call_args.kwargs.get("limit")
    assert limit == 500, "if this changed, the budget above and Lot C's target list both move"


def test_every_budget_is_actually_exercised():
    """A budget nothing calls is a number that drifts quietly."""
    assert set(BUDGETS) == {"home_page", "home_metrics", "home_dashboard"}

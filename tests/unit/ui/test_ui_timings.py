"""Plugin-timings page: the aggregation the route does, and the four states it can be in.

The numbers arrive as an opaque {plugin: {phase: aggregate}} fan-out, so everything an
operator reads on this page — the ordering, the share, the denominator, and which empty state
is shown — is decided here rather than by the API.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from conftest import english  # what a converted template renders for a key
import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.api_client import ApiClient, ApiUnavailableError

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"

PAYLOAD = {
    "metrics": {"request": {"count": 1000, "sum": 12.0, "max": 0.9, "mean": 0.012}},
    "antibot": {"access": {"count": 1000, "sum": 0.6, "max": 0.004, "mean": 0.0006}},
    "blacklist": {"access": {"count": 1000, "sum": 0.09, "max": 0.0009, "mean": 0.00009}},
    "jobs": {"init_worker": {"count": 4, "sum": 2.5, "max": 0.8, "mean": 0.625}},
}


@pytest.fixture(scope="module")
def timings_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    module_name = "app.routes._timings_test"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "src" / "ui" / "app" / "routes" / "timings.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "app.utils": app_utils, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, app_utils.flash


@pytest.fixture
def route(timings_route):
    module, client, flash = timings_route
    client.reset_mock(return_value=True, side_effect=True)
    flash.reset_mock()
    client.get_instances.return_value = [{"hostname": "bw-1"}]
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.timings)
    return module, client, flash, app


@pytest.fixture(scope="module")
def page():
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block page_head %}{% endblock %}{% block content %}{% endblock %}"}),
                FileSystemLoader(str(TEMPLATES)),
            ]
        ),
        autoescape=True,
    )
    env.globals.update(url_for=lambda endpoint, **kwargs: "/x", csrf_token=lambda: "t")
    return env.get_template("timings.html")


def _render(page, module, **overrides):
    context = {
        "rows": [],
        "request_total": None,
        "duration": module.duration,
        "reporting_count": 1,
        "total_instances": 1,
        "partial": False,
        "unreachable": False,
        "collecting": True,
    }
    context.update(overrides)
    return page.render(**context)


def test_the_api_client_asks_for_the_fanned_out_endpoint():
    client = ApiClient("http://api.test", "token")
    try:
        client._get = Mock(return_value={"status": "success", "timings": {}})
        client.get_metrics_timings()
        assert client._get.call_args.args[0] == "/metrics/timings"
    finally:
        client.session.close()


def test_whole_request_duration_is_the_denominator_not_a_row(timings_route):
    """metrics/request is every other row's yardstick, so listing it as a plugin phase would
    both double-count it and put a 100% row at the top of the table."""
    module, _, _ = timings_route
    rows, request_total = module._rows(PAYLOAD)

    assert request_total["count"] == 1000 and request_total["mean"] == 0.012
    assert all(row["plugin"] != "metrics" for row in rows)


def test_rows_are_ordered_by_what_they_actually_cost(timings_route):
    module, _, _ = timings_route
    rows, _ = module._rows(PAYLOAD)

    assert [row["plugin"] for row in rows] == ["jobs", "antibot", "blacklist"]


def test_a_phase_that_is_not_per_request_gets_no_share(timings_route):
    """init_worker runs once per worker. Charging its 2.5s against request time would read as
    latency every visitor paid — here, a 20% share for a plugin that costs a request nothing."""
    module, _, _ = timings_route
    rows, _ = module._rows(PAYLOAD)
    by_plugin = {row["plugin"]: row for row in rows}

    assert by_plugin["jobs"]["share"] is None
    assert by_plugin["antibot"]["share"] == pytest.approx(5.0)


def test_shares_stay_none_when_nothing_measured_the_request(timings_route):
    """No metrics/request aggregate means no denominator — not a division by zero."""
    module, _, _ = timings_route
    rows, request_total = module._rows({"antibot": {"access": {"count": 5, "sum": 0.1, "max": 0.05, "mean": 0.02}}})

    assert request_total is None
    assert rows[0]["share"] is None


def test_a_malformed_instance_entry_does_not_take_down_the_page(timings_route):
    module, _, _ = timings_route
    rows, _ = module._rows({"antibot": "not-a-dict", "blacklist": {"access": None}, "jobs": {"timer": {}}})

    assert [(row["plugin"], row["count"], row["total"]) for row in rows] == [("jobs", 0, 0.0)]


def test_durations_are_rendered_at_a_scale_that_can_be_read(timings_route):
    """Plugin calls land in microseconds and requests in milliseconds; one fixed unit makes
    one of the two a wall of zeroes."""
    module, _, _ = timings_route

    assert module.duration(0.00006) == "60 µs"
    assert module.duration(0.012) == "12.00 ms"
    assert module.duration(2.5) == "2.50 s"
    assert module.duration(None) == "—"


def test_the_populated_page_shows_the_numbers_and_the_dash(timings_route, page):
    module, _, _ = timings_route
    rows, request_total = module._rows(PAYLOAD)

    html = _render(page, module, rows=rows, request_total=request_total)

    assert "5.0%" in html and "600 µs" in html and "12.00 ms" in html
    assert english("timings.share_help") in html
    # The lifecycle row is present but carries no percentage.
    assert "<code>jobs</code>" in html


def test_an_empty_table_says_the_feature_is_off_rather_than_no_data(timings_route, page):
    """ "No data" would read as an idle fleet when the truth is the setting is no."""
    module, _, _ = timings_route

    html = _render(page, module, collecting=False)

    assert "timings-disabled" in html and "METRICS_COLLECT_TIMINGS" in html
    assert "timings-unreachable" not in html


def test_nothing_reporting_is_distinguished_from_nothing_collected(timings_route, page):
    module, _, _ = timings_route

    html = _render(page, module, unreachable=True)

    assert "timings-unreachable" in html and "timings-disabled" not in html


def test_a_partial_fan_out_is_announced(timings_route, page):
    """207 means some instances answered. Showing the figures without saying so understates
    the fleet by however many were missing."""
    module, _, _ = timings_route
    rows, request_total = module._rows(PAYLOAD)

    html = _render(page, module, rows=rows, request_total=request_total, partial=True)

    assert english("timings.partial") in html


def test_the_page_asks_whether_collection_is_on_only_when_there_is_nothing_to_show(route):
    module, client, _, app = route
    client.get_metrics_timings.return_value = {"status": "success", "timings": PAYLOAD, "instances": {"bw-1": {}}}

    with app.test_request_context("/timings"):
        with patch.object(module, "render_template", Mock(return_value="")):
            module.timings_page.__wrapped__()

    assert not client.get_global_settings.called


def test_an_unreachable_fan_out_is_not_flashed_as_an_error(route):
    """The API collapses "no instance reported" and "the API is down" into one 5xx error, so
    the page states it as an empty state instead of a red banner about a healthy API."""
    module, client, flash, app = route
    client.get_metrics_timings.side_effect = ApiUnavailableError("API returned 503")
    client.get_global_settings.return_value = {"METRICS_COLLECT_TIMINGS": "yes"}

    with app.test_request_context("/timings"):
        with patch.object(module, "render_template", Mock(return_value="")) as render:
            module.timings_page.__wrapped__()

    assert render.call_args.kwargs["unreachable"] is True
    assert not flash.called


def test_the_disabled_setting_reaches_the_template(route):
    module, client, _, app = route
    client.get_metrics_timings.return_value = {"status": "success", "timings": {}, "instances": {}}
    client.get_global_settings.return_value = {"METRICS_COLLECT_TIMINGS": "no"}

    with app.test_request_context("/timings"):
        with patch.object(module, "render_template", Mock(return_value="")) as render:
            module.timings_page.__wrapped__()

    assert render.call_args.kwargs["collecting"] is False
    assert client.get_global_settings.call_args.kwargs["filtered_settings"] == ["METRICS_COLLECT_TIMINGS"]


def test_the_page_is_reachable_from_the_menu_and_the_locale():
    """A page nobody can navigate to is a page nobody uses."""
    menu = (TEMPLATES / "menu.html").read_text(encoding="utf-8")
    assert "timings.timings_page" in menu

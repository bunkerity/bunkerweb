"""The "active bans per interval" panel on /bans (#3820): UI route, API client method, and the
template wiring that makes the chart actually appear.

Route tests reuse ``test_bans_stats.py``'s module-loader fixture shape (stub ``app.dependencies``
and the container-only imports, then exec ``routes/bans.py``); render tests reuse the standalone
Jinja env of ``test_bans_stats.py`` / ``test_reports_components.py``.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from conftest import english
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

UI = Path(__file__).resolve().parents[3] / "src" / "ui"
TEMPLATES = UI / "app" / "templates"
STATIC = UI / "app" / "static"
LOCALES = STATIC / "locales"

NEW_KEYS = (
    "bans.chart.timeseries.title",
    "bans.chart.timeseries.subtitle",
    "bans.chart.timeseries.series",
    "bans.chart.timeseries.note",
)


@pytest.fixture(scope="module")
def bans_route():
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
    module_name = "app.routes._bans_timeseries_test"
    spec = importlib.util.spec_from_file_location(module_name, UI / "app" / "routes" / "bans.py")
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
def route_app(bans_route):
    module, client = bans_route
    client.reset_mock()
    client.get_bans_timeseries.side_effect = None
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.bans)
    return module, client, app


def _call(module, app, form):
    with app.test_request_context("/bans/timeseries", method="POST", data=form):
        return module.bans_timeseries.__wrapped__.__wrapped__()


SERIES = {"buckets": [1000], "counts": [2], "total": 2, "prev_total": 1, "trend_pct": 100.0}


class TestRoute:
    def test_it_forwards_the_window_and_returns_the_series(self, route_app):
        module, client, app = route_app
        client.get_bans_timeseries.return_value = SERIES

        response = _call(module, app, {"start": "1000", "end": "4600", "bucket": "hour"})

        assert response.get_json() == {"status": "success", "timeseries": SERIES}
        client.get_bans_timeseries.assert_called_once_with(start=1000, end=4600, bucket="hour")

    def test_a_missing_window_defaults_to_the_last_24_hours(self, route_app):
        module, client, app = route_app
        client.get_bans_timeseries.return_value = SERIES

        _call(module, app, {})

        kwargs = client.get_bans_timeseries.call_args.kwargs
        assert kwargs["end"] - kwargs["start"] == 86400
        assert kwargs["bucket"] == "hour"

    def test_a_non_numeric_window_is_a_400_not_a_500(self, route_app):
        module, client, app = route_app

        response, status = _call(module, app, {"start": "yesterday", "end": "now"})

        assert status == 400
        assert response.get_json()["status"] == "error"
        client.get_bans_timeseries.assert_not_called()

    def test_an_api_400_is_relayed_as_a_400(self, route_app):
        module, client, app = route_app
        error = module.ApiClientError("requested range too large")
        error.status_code = 400
        client.get_bans_timeseries.side_effect = error

        _response, status = _call(module, app, {"start": "0", "end": "999999999"})

        assert status == 400

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_an_api_failure_is_a_503_so_the_page_shows_an_empty_chart(self, route_app, status_code):
        module, client, app = route_app
        error = module.ApiClientError("boom")
        error.status_code = status_code
        client.get_bans_timeseries.side_effect = error

        response, status = _call(module, app, {"start": "0", "end": "3600"})

        assert status == 503
        assert response.get_json()["status"] == "error"

    def test_an_unreachable_api_is_a_503_too(self, route_app):
        module, client, app = route_app
        client.get_bans_timeseries.side_effect = module.ApiUnavailableError("down")

        _response, status = _call(module, app, {"start": "0", "end": "3600"})

        assert status == 503

    def test_the_route_is_login_and_cors_protected(self, bans_route):
        module, _client = bans_route
        # Both decorators wrap the view; `__wrapped__.__wrapped__` (used above) only unwraps
        # if they are actually there, but that alone would not say *which* two they are.
        source = (UI / "app" / "routes" / "bans.py").read_text(encoding="utf-8")
        start = source.index('@bans.route("/bans/timeseries"')
        end = source.index("def bans_timeseries(")
        block = source[start:end]
        assert "@login_required" in block and "@cors_required" in block


class TestApiClient:
    def test_the_client_calls_the_new_endpoint_with_the_window(self):
        source = (UI / "app" / "api_client.py").read_text(encoding="utf-8")
        assert 'def get_bans_timeseries(self, *, start: int, end: int, bucket: str = "hour")' in source
        assert 'self._get("/bans/timeseries", params={"start": start, "end": end, "bucket": bucket})' in source


class TestTemplate:
    @pytest.fixture(scope="class")
    def rendered(self):
        env = Environment(
            loader=ChoiceLoader(
                [
                    DictLoader({"dashboard.html": "{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
                    FileSystemLoader(TEMPLATES),
                ]
            ),
            autoescape=True,
        )
        env.globals["url_for"] = lambda endpoint, **kwargs: f"/{kwargs.get('filename', endpoint)}"
        env.globals["_"] = english
        env.globals["csrf_token"] = lambda: "token"
        return env.get_template("bans.html").render(
            services=[],
            is_readonly=False,
            user_readonly=False,
            theme="light",
            script_nonce="nonce",
            style_nonce="nonce",
            columns_preferences_defaults={"bans": {}},
            columns_preferences={},
        )

    def test_the_chart_mount_point_and_its_picker_are_present(self, rendered):
        assert 'id="bans-timeseries-chart"' in rendered
        assert 'id="bans-range"' in rendered

    def test_the_panel_carries_the_honesty_note(self, rendered):
        assert 'id="bans-timeseries-note"' in rendered
        assert english("bans.chart.timeseries.note") in rendered

    def test_the_panel_is_titled_active_bans_per_interval(self, rendered):
        assert english("bans.chart.timeseries.title") in rendered

    def test_the_chart_libraries_the_panel_needs_are_loaded(self, rendered):
        """A chart with no ApexCharts and no range-picker JS renders an empty div and no error --
        exactly the kind of failure a server-side render test would otherwise pass over."""
        for asset in ("libs/apexcharts/apexcharts.min.js", "js/components/range-picker.js", "js/pages/bans-timeseries.js"):
            assert asset in rendered, asset

    def test_the_page_script_exists_on_disk(self):
        assert (STATIC / "js" / "pages" / "bans-timeseries.js").is_file()

    def test_the_script_posts_to_the_route_the_blueprint_registers(self):
        script = (STATIC / "js" / "pages" / "bans-timeseries.js").read_text(encoding="utf-8")
        assert "${window.location.pathname}/timeseries" in script
        assert "csrf_token" in script


class TestI18n:
    def test_every_new_key_exists_in_every_catalog(self):
        catalogs = sorted(LOCALES.glob("*.json"))
        assert len(catalogs) >= 18, catalogs  # RULE 13
        for path in catalogs:
            data = json.loads(path.read_text(encoding="utf-8"))
            for dotted in NEW_KEYS:
                node = data
                for part in dotted.split("."):
                    assert isinstance(node, dict) and part in node, f"{path.name} is missing {dotted}"
                    node = node[part]
                assert isinstance(node, str) and node, f"{path.name}: {dotted} is empty"

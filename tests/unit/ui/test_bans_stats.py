"""Bans dashboard header (Phase 1B): the new ``POST /bans/stats`` route and the
``bans.html`` tiles/reason-card/alert it feeds.

Route tests follow the module-loader pattern established by ``test_reports_dashboard.py``:
``app.dependencies`` (plus ``openpyxl``/``qrcode``, unavailable in the pared-down unit-test
venv) is stubbed before loading ``bans.py`` so real container-only state never boots.
``_collect_all_bans`` is monkeypatched directly -- it's already exercised by ``bans_fetch``
elsewhere, this route only needs to prove it aggregates that data correctly.

Render tests follow ``test_reports_components.py``'s standalone-Jinja-env pattern.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
STATIC = TEMPLATES.parent / "static"


@pytest.fixture(scope="module")
def bans_route():
    """Load bans.py's route module without booting container-only app.dependencies state."""
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
    module_name = "app.routes._bans_stats_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "bans.py"
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
        yield module


@pytest.fixture
def route_app(bans_route):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(bans_route.bans)
    return bans_route, app


def _call_stats(module, app, monkeypatch, bans_list):
    monkeypatch.setattr(module, "_collect_all_bans", lambda: bans_list)
    with app.test_request_context("/bans/stats", method="POST"):
        return module.bans_stats.__wrapped__.__wrapped__()


def test_stats_counts_active_expiring_countries_permanent(route_app, monkeypatch):
    module, app = route_app
    bans_list = [
        {"reason": "manual", "exp": 1800, "permanent": False, "country": "US"},  # expiring <= 1h
        {"reason": "manual", "exp": 3600, "permanent": False, "country": "US"},  # exactly 1h, still counts
        {"reason": "manual", "exp": 7200, "permanent": False, "country": "DE"},  # not expiring soon
        {"reason": "manual", "exp": 0, "permanent": True, "country": "CN"},  # permanent
        {"reason": "manual", "exp": 0, "permanent": True, "country": None},  # permanent, no country
    ]

    response = _call_stats(module, app, monkeypatch, bans_list)
    data = response.get_json()

    assert data["active"] == 5
    assert data["expiring_1h"] == 2
    assert data["countries"] == 3  # US, DE, CN -- None is dropped
    assert data["permanent"] == 2


def test_stats_reason_breakdown_top_n_and_pct(route_app, monkeypatch):
    module, app = route_app
    # 4 CRS, 3 manual, 2 dnsbl, 1 antibot -- 10 total, 4 distinct reasons (under top-5 cap).
    bans_list = (
        [{"reason": "CRS", "exp": 0, "permanent": True, "country": "US"}] * 4
        + [{"reason": "manual", "exp": 0, "permanent": True, "country": "US"}] * 3
        + [{"reason": "dnsbl", "exp": 0, "permanent": True, "country": "US"}] * 2
        + [{"reason": "antibot", "exp": 0, "permanent": True, "country": "US"}] * 1
    )

    response = _call_stats(module, app, monkeypatch, bans_list)
    data = response.get_json()

    assert data["reason_breakdown"] == [
        {"reason": "CRS", "count": 4, "pct": 40},
        {"reason": "manual", "count": 3, "pct": 30},
        {"reason": "dnsbl", "count": 2, "pct": 20},
        {"reason": "antibot", "count": 1, "pct": 10},
    ]


def test_stats_reason_breakdown_capped_at_top_5(route_app, monkeypatch):
    module, app = route_app
    bans_list = [{"reason": f"reason-{i}", "exp": 0, "permanent": True, "country": "US"} for i in range(7)]

    response = _call_stats(module, app, monkeypatch, bans_list)
    data = response.get_json()

    assert len(data["reason_breakdown"]) == 5


def test_stats_empty_when_no_bans(route_app, monkeypatch):
    module, app = route_app

    response = _call_stats(module, app, monkeypatch, [])
    data = response.get_json()

    assert data == {
        "active": 0,
        "expiring_1h": 0,
        "countries": 0,
        "permanent": 0,
        "reason_breakdown": [],
    }


def test_stats_collect_all_bans_exception_returns_empty_not_500(route_app, monkeypatch):
    module, app = route_app

    def _boom():
        raise RuntimeError("redis unreachable")

    monkeypatch.setattr(module, "_collect_all_bans", _boom)
    with app.test_request_context("/bans/stats", method="POST"):
        response = module.bans_stats.__wrapped__.__wrapped__()

    assert response.status_code == 200
    assert response.get_json()["active"] == 0


# --------------------------------------------------------------------------------------
# Render tests
# --------------------------------------------------------------------------------------


def _render_dashboard_page(template, **context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )
    env.globals.update(
        csrf_token=lambda: "test-token",
        url_for=lambda endpoint, **_kwargs: f"/{endpoint}",
        isinstance=isinstance,
        is_ui_api_method=lambda _method: True,
    )
    return env.get_template(template).render(**context)


def _resolves_in_locale(locale, dotted_key):
    node = locale
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _render_bans(**overrides):
    context = {
        "services": ["app1.example.com"],
        "columns_preferences_defaults": {"bans": {}},
        "columns_preferences": {},
        "is_readonly": True,
        "theme": "light",
        "script_nonce": "nonce",
        "style_nonce": "nonce",
        "config": {"USE_REDIS": {"value": "no", "method": "default"}},
    }
    context.update(overrides)
    return _render_dashboard_page("bans.html", **context)


def test_bans_page_renders_four_stat_tiles():
    html = _render_bans()

    for tile_id in ("bans-tile-active", "bans-tile-expiring", "bans-tile-countries", "bans-tile-permanent"):
        assert f'id="{tile_id}"' in html, tile_id
    assert html.count("bw-kpi-value") == 4


def test_bans_page_keeps_existing_table_and_toolbar_intact():
    html = _render_bans()

    # The DataTable/toolbar block (bans_fetch/_BAN_COLUMNS consumer) must still be present,
    # untouched, inside the col-lg-8 column.
    assert 'id="base_flags_url"' in html
    assert 'id="bans"' in html  # table_toolbar(id="bans", ...)


def test_bans_page_renders_reason_breakdown_card_mount():
    html = _render_bans()

    assert 'id="bans-reason-breakdown"' in html
    assert 'data-i18n="bans.stats.card.by_reason"' in html


def test_bans_page_alert_shown_when_redis_disabled():
    html = _render_bans(config={"USE_REDIS": {"value": "no"}})

    assert 'data-i18n="bans.stats.alert.title"' in html
    assert "<code>USE_REDIS</code>" in html


def test_bans_page_alert_hidden_when_redis_enabled():
    html = _render_bans(config={"USE_REDIS": {"value": "yes"}})

    assert 'data-i18n="bans.stats.alert.title"' not in html
    assert "<code>USE_REDIS</code>" not in html


def test_bans_stats_i18n_keys_resolve_in_en_json():
    html = _render_bans(config={"USE_REDIS": {"value": "no"}})
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))

    expected_keys = [
        "bans.stats.tile.active",
        "bans.stats.tile.active_caption",
        "bans.stats.tile.expiring",
        "bans.stats.tile.expiring_caption",
        "bans.stats.tile.countries",
        "bans.stats.tile.permanent",
        "bans.stats.card.by_reason",
        "bans.stats.alert.title",
        "bans.stats.alert.body_before",
        "bans.stats.alert.body_after",
    ]
    for key in expected_keys:
        assert f'data-i18n="{key}"' in html, key
        assert _resolves_in_locale(locale, key), key

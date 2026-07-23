"""Render-level tests for the home dashboard upgrade (Phase 2): the welcome header +
range-picker, the picker-driven trend tile + area chart mount points, the server-rendered
"Top reasons for blocks" card, and the "Getting started" checklist that hides once every
item is done. Mirrors ``test_reports_components.py``'s render-through-a-bare-Jinja-env
style (no Flask app/request needed for template-only assertions) and its
``_resolves_in_locale`` i18n-resolution helper.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.utils import human_readable_number

TEMPLATES = Path(__file__).parents[3] / "src" / "ui" / "app" / "templates"
STATIC = TEMPLATES.parent / "static"
LOCALE = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))


def _resolves_in_locale(locale, dotted_key):
    node = locale
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _base_context(**overrides):
    context = dict(
        columns_preferences_defaults={"reports": {}},
        columns_preferences={},
        is_readonly=True,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
        current_user=SimpleNamespace(get_id=lambda: "admin"),
        is_pro_version=False,
        pro_diamond_url="/diamond.png",
        memory_info={"total_gb": 8.0, "used_gb": 4.0, "used_percent": 50.0, "available_gb": 4.0, "memory_state": "medium"},
        instances=[],
        services=[],
        plugins={},
        request_errors={},
        request_countries={},
        request_ips={},
        blocked_unique_ips=0,
        time_buckets={},
        home_stats_days=7,
        is_initialized=False,
        first_config_saved=False,
        mfa_enabled=False,
        jobs_count=0,
        bans_active=0,
        top_reasons=[],
    )
    context.update(overrides)
    return context


def _render_home(**overrides):
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
        human_readable_number=human_readable_number,
    )
    env.filters["to_iso"] = lambda value: value
    return env.get_template("home.html").render(**_base_context(**overrides))


# ── Welcome header + range picker ───────────────────────────────────────────────────


def test_home_page_renders_welcome_header_and_range_picker():
    html = _render_home()

    # The welcome name now lives in a Don Jose accent span that is a *sibling* of the
    # data-i18n greeting span (i18n.js applyTranslations() uses .text(), which would
    # otherwise flatten a child accent span away), so the header carries the greeting key.
    assert 'data-i18n="dashboard.welcome.greeting"' in html
    assert "admin" in html
    assert 'id="home-range"' in html
    for preset_key in ("range_picker.1h", "range_picker.24h", "range_picker.7d", "range_picker.30d"):
        assert _resolves_in_locale(LOCALE, preset_key), preset_key

    # active="7d" (the honest range-picker split -- only the new chart/trend tile are
    # picker-driven, the legacy widgets below stay a fixed 7-day aggregate).
    range_picker_block = html.split('id="home-range"', 1)[1].split("</div>", 1)[0]
    seven_day_button = range_picker_block.split('data-range="7d"', 1)[1].split("</button>", 1)[0]
    assert 'aria-pressed="true"' in seven_day_button


def test_home_page_loads_flatpickr_before_range_picker_js():
    source = (TEMPLATES / "home.html").read_text(encoding="utf-8")

    assert "libs/flatpickr/flatpickr.min.css" in source
    assert "libs/flatpickr/flatpickr.min.js" in source
    assert "js/components/range-picker.js" in source
    assert "js/pages/home-dashboard.js" in source
    assert source.index("libs/flatpickr/flatpickr.min.js") < source.index("js/components/range-picker.js")
    assert source.index("js/components/range-picker.js") < source.index("js/pages/home-dashboard.js")
    # ApexCharts must also precede the script that builds the picker-driven chart.
    assert source.index("libs/apexcharts/apexcharts.min.js") < source.index("js/pages/home-dashboard.js")
    # home.js (the untouched legacy chart script) must be left alone.
    assert "js/pages/home.js" in source


# ── Mini-tile row + picker-driven trend tile / chart mount points ──────────────────


def test_home_page_renders_trend_tile_and_timeseries_chart_mounts():
    html = _render_home()

    assert 'id="home-tile-trend"' in html
    # The trend tile is the KPI tile immediately inside the #home-tile-trend wrapper; its
    # value span (written by home-dashboard.js) must carry bw-kpi-value.
    trend_tile = html.split('id="home-tile-trend"', 1)[1].split("</div>", 1)[0]
    assert "bw-kpi-value" in trend_tile
    assert 'id="home-timeseries-chart"' in html
    assert 'id="home-timeseries-chart-data"' in html

    for i18n_key in ("dashboard.tile.trend", "dashboard.tile.bans_active", "dashboard.tile.jobs", "dashboard.chart.timeseries.title"):
        assert f'data-i18n="{i18n_key}"' in html, i18n_key
        assert _resolves_in_locale(LOCALE, i18n_key), i18n_key


def test_home_page_mini_tiles_render_honest_values():
    html = _render_home(bans_active=42, jobs_count=5, blocked_unique_ips=7)

    assert human_readable_number(42) in html
    assert ">5<" in html or "5</span>" in html


# ── "Top reasons for blocks" card ───────────────────────────────────────────────────


def test_home_page_top_reasons_card_renders_rows_when_present():
    html = _render_home(
        top_reasons=[
            {"reason": "modsecurity", "count": 30, "pct": 75.0},
            {"reason": "antibot", "count": 10, "pct": 25.0},
        ]
    )

    assert 'data-i18n="dashboard.card.top_reasons.title"' in html
    assert _resolves_in_locale(LOCALE, "dashboard.card.top_reasons.title")
    assert "modsecurity" in html
    assert "antibot" in html
    assert "75.0%" in html
    assert "25.0%" in html


def test_home_page_top_reasons_card_shows_empty_state_when_absent():
    html = _render_home(top_reasons=[])

    reasons_card = html.split('data-i18n="dashboard.card.top_reasons.title"', 1)[1]
    assert 'data-i18n="status.no_data"' in reasons_card.split('data-i18n="onboarding.title"', 1)[0]


# ── "Getting started" checklist -- flips per item, hides once all done ─────────────


def test_home_page_checklist_shows_pending_items_when_nothing_done():
    html = _render_home(is_initialized=False, first_config_saved=False, services=[], mfa_enabled=False, is_pro_version=False)

    assert 'data-i18n="onboarding.title"' in html
    checklist_block = html.split('data-i18n="onboarding.title"', 1)[1]
    for i18n_key in ("onboarding.item.install", "onboarding.item.service", "onboarding.item.mfa", "onboarding.item.pro"):
        assert f'data-i18n="{i18n_key}"' in checklist_block, i18n_key
        assert _resolves_in_locale(LOCALE, i18n_key), i18n_key
    # None of the 4 items are done -- no bx-check-circle should appear for this list.
    assert "bx-check-circle" not in checklist_block.split("</ul>", 1)[0]


def test_home_page_checklist_flips_items_independently():
    html = _render_home(
        is_initialized=True,
        first_config_saved=True,
        services=[{"id": "svc1", "is_draft": False}],
        mfa_enabled=True,
        is_pro_version=False,
    )

    assert 'data-i18n="onboarding.title"' in html
    checklist_block = html.split('data-i18n="onboarding.title"', 1)[1].split("</ul>", 1)[0]
    # Install/service/MFA are done (green check), PRO is still pending (neutral circle).
    assert checklist_block.count("bx-check-circle") == 3
    assert "bx-circle" in checklist_block


def test_home_page_checklist_hidden_once_everything_is_done():
    html = _render_home(
        is_initialized=True,
        first_config_saved=True,
        services=[{"id": "svc1", "is_draft": False}],
        mfa_enabled=True,
        is_pro_version=True,
    )

    assert 'data-i18n="onboarding.title"' not in html


# ── Existing widgets stay untouched, just relabeled ─────────────────────────────────


def test_home_page_existing_widgets_still_render_and_are_relabeled_last_days():
    html = _render_home(home_stats_days=7)

    # The legacy period-floating badge is gone (replaced by the welcome header + picker).
    assert "home-period-floating" not in html
    # A plain "last N days" caption now precedes the untouched legacy block.
    assert 'data-i18n="dashboard.window.last_days"' in html
    assert "Last 7 days" in html
    # The untouched widgets (donuts, geo-map, blocking-status chart, news) are all
    # still present and unmodified.
    assert 'id="requests-stats"' in html
    assert 'id="requests-map"' in html
    assert 'id="requests-blocking"' in html
    assert 'data-i18n="dashboard.card.news.title"' in html


def test_home_page_source_never_touches_reports_files():
    """File-ownership guard: this phase must not have edited the reports dashboard
    (owned by a different track)."""
    source = (TEMPLATES / "home.html").read_text(encoding="utf-8")
    assert "reports-overview.js" not in source
    assert "reports.html" not in source

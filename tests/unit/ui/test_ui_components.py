import json
import re
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).parents[3] / "src" / "ui" / "app" / "templates"
STATIC = TEMPLATES.parent / "static"


class _InputAttributes(HTMLParser):
    def __init__(self, target_id):
        super().__init__()
        self.target_id = target_id
        self.attrs = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("id") == self.target_id:
            self.attrs = attributes


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
    env.filters["to_iso"] = lambda value: value
    return env.get_template(template).render(**context)


def test_modal_size_belongs_to_dialog():
    html = (
        Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
        .from_string(
            '{% from "components/modal.html" import modal %}'
            '{% call modal(id="example", title_key="modal.example", title="Example", size="xl") %}'
            '<div class="modal-body">Body</div>'
            "{% endcall %}"
        )
        .render()
    )

    assert 'class="modal fade"' in html
    assert 'class="modal-dialog modal-xl modal-dialog-centered"' in html
    assert 'aria-labelledby="example-title"' in html


def test_search_component_renders_trusted_accessibility_attributes():
    html = (
        Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
        .from_string('{% from "components/search.html" import search %}' '{{ search(id="query", attrs=\'aria-controls="results" aria-expanded="false"\') }}')
        .render()
    )

    assert 'aria-controls="results"' in html
    assert 'aria-expanded="false"' in html
    assert "&#34;" not in html


def test_dropzone_has_one_interactive_tab_stop():
    html = (
        Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
        .from_string(
            '{% from "components/file-upload.html" import file_upload %}'
            '{{ file_upload(id="upload", input_id="upload-input", name="file", '
            'hint="Drop a file", show_browse_button=true, browse_label="Browse") }}'
        )
        .render()
    )

    assert 'role="button"' in html
    assert 'class="btn btn-sm btn-outline-primary"' in html
    assert ">Browse</span>" in html
    assert "<button" not in html
    assert 'id="upload-input"' in html
    assert 'tabindex="-1"' in html
    assert 'aria-hidden="true"' in html


def test_inline_file_upload_escapes_pattern_as_one_attribute():
    pattern = '^" onfocus="alert(1)<$'
    html = (
        Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
        .from_string('{% from "components/file-upload.html" import file_upload %}' '{{ file_upload(id="certificate", variant="inline", pattern=pattern) }}')
        .render(pattern=pattern)
    )
    parser = _InputAttributes("certificate")
    parser.feed(html)

    assert parser.attrs["pattern"] == pattern
    assert "onfocus" not in parser.attrs


def test_button_anchor_preserves_link_semantics():
    html = (
        Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
        .from_string('{% from "components/button.html" import button %}' '{{ button(label="Download", tag="a", href="/download") }}')
        .render()
    )

    assert "<a" in html
    assert 'class="btn btn-primary don-jose"' in html
    assert 'href="/download"' in html
    assert 'role="button"' not in html


def _render_range_picker(**overrides):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    params = {"id": "test-range", "active": "24h"}
    params.update(overrides)
    call = ", ".join(f"{key}={value!r}" for key, value in params.items())
    return env.from_string('{% from "components/range-picker.html" import range_picker %}' f"{{{{ range_picker({call}) }}}}").render()


def test_range_picker_renders_one_button_per_preset_with_group_role():
    presets = ["1h", "24h", "7d", "30d"]
    html = _render_range_picker(presets=presets, with_custom=False)

    assert 'role="group"' in html
    assert html.count('class="btn btn-sm btn-outline-primary range-btn') == len(presets)
    for preset in presets:
        assert f'data-range="{preset}"' in html


def test_range_picker_active_preset_is_pressed_others_are_not():
    html = _render_range_picker(presets=["1h", "24h", "7d", "30d"], active="7d", with_custom=False)

    assert re.search(r'data-range="7d"\s+aria-pressed="true"', html)
    for preset in ("1h", "24h", "30d"):
        assert re.search(rf'data-range="{preset}"\s+aria-pressed="false"', html), preset


def test_range_picker_data_i18n_keys_resolve_in_en_json():
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))
    presets = ["1h", "24h", "7d", "30d"]
    html = _render_range_picker(presets=presets, active="24h", with_custom=True)

    # every data-i18n attribute the macro actually renders for this call
    emitted = [f"range_picker.{preset}" for preset in presets] + ["range_picker.custom", "range_picker.aria_label"]
    for key in emitted:
        assert f'data-i18n="{key}"' in html
        assert _resolves_in_locale(locale, key), key


def test_menu_active_match_does_not_overlap_web_cache_and_cache():
    source = (TEMPLATES / "menu.html").read_text(encoding="utf-8")

    assert "endpoint == request.path.split('/')[1]" in source
    assert "endpoint in request.path.split('/')[1]" not in source
    assert 'extra_pages | reject("equalto", "letsencrypt") | list' in source


def _render_table_toolbar(**overrides):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals["csrf_token"] = lambda: "test-token"
    table_id = overrides.get("id", "bans")
    params = {
        "id": table_id,
        "columns_preferences_defaults": {table_id: {"0": True}},
        "columns_preferences": {},
        "loading_key": "status.loading_bans",
        "loading_default": "Loading bans...",
    }
    params.update(overrides)
    call = ", ".join(f"{key}={value!r}" for key, value in params.items())
    return env.from_string(
        '{% from "components/table-toolbar.html" import table_toolbar %}' f"{{% call table_toolbar({call}) %}}<thead><tr><th></th></tr></thead>{{% endcall %}}"
    ).render()


def test_table_toolbar_default_ids_and_classes():
    html = _render_table_toolbar()

    assert 'id="bans"' in html
    assert 'id="bans-waiting"' in html
    assert 'id="columns_preferences_defaults"' in html
    assert 'id="columns_preferences"' in html
    assert 'id="csrf_token"' in html
    assert 'class="table responsive nowrap position-relative w-100 d-none"' in html
    assert "<thead>" in html
    assert 'id="bans_number"' not in html


def test_table_toolbar_number_input_uses_id_suffix_by_default():
    html = _render_table_toolbar(id="instances", number=3)

    assert 'id="instances_number" value="3"' in html


def test_table_toolbar_number_id_override_for_jobs():
    html = _render_table_toolbar(id="jobs", number=7, number_id="job_number")

    assert 'id="job_number" value="7"' in html
    assert 'id="jobs_number"' not in html


def test_bans_instances_plugins_do_not_nest_toolbar_or_card_twice():
    for page in ("bans.html", "instances.html", "plugins.html"):
        source = (TEMPLATES / page).read_text(encoding="utf-8")

        assert source.count("{% call table_toolbar(") == 1, page
        assert source.count('{% call card(classes="table-responsive') == 1, page
        assert "<table " not in source, page


def test_instances_timezone_renders_outside_table():
    html = _render_dashboard_page(
        "instances.html",
        columns_preferences_defaults={"instances": {}},
        columns_preferences={},
        instances=[],
        is_readonly=True,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
    )
    table = html.split('<table id="instances"', 1)[1].split("</table>", 1)[0]

    assert "TZ:" not in table
    assert html.index("</table>") < html.index("TZ:")


def test_plugins_stream_tooltip_has_valid_cell_nesting():
    html = _render_dashboard_page(
        "plugins.html",
        columns_preferences_defaults={"plugins": {}},
        columns_preferences={},
        plugins={
            "demo": {
                "type": "core",
                "name": "Demo",
                "description": "Demo plugin",
                "version": "1.0",
                "stream": "yes",
                "method": "manual",
                "page": False,
            }
        },
        plugin_types={"core": {"text-class": "", "icon": '<i class="bx bx-cube"></i>'}},
        pro_diamond_url="/diamond.svg",
        is_pro_version=False,
        is_readonly=True,
        user_readonly=False,
        theme="light",
    )

    assert re.search(r'tooltip\.stream_support\.yes"[^>]*>\s*<i[^>]*></i>\s*</div>\s*</td>', html)


def test_reports_page_renders_four_tabs_with_event_log_table_intact():
    html = _render_dashboard_page(
        "reports.html",
        columns_preferences_defaults={"reports": {}},
        columns_preferences={},
        is_readonly=True,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )

    # tabs + their panes exist under the reports-tabs namespace
    assert 'id="reports-tabs"' in html
    for pane_id in ("overview", "patterns", "offenders", "eventlog"):
        assert f'id="reports-tabs-pane-{pane_id}"' in html

    # the 3 new tabs are empty roots for Tasks 9-11
    assert 'id="reports-overview-root"' in html
    assert 'id="reports-patterns-root"' in html
    assert 'id="reports-offenders-root"' in html

    # every tab's i18n key is both emitted and resolvable in en.json
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))
    for tab_key in ("overview", "patterns", "offenders", "eventlog"):
        i18n_key = f"reports.tab.{tab_key}"
        assert f'data-i18n="{i18n_key}"' in html
        assert _resolves_in_locale(locale, i18n_key), i18n_key

    # Event log pane still carries the pre-existing table/toolbar/modals unchanged.
    # Bound the slice to the first modal marker after the tab content (not
    # end-of-string): eventlog is the *last* pane, so an unbounded second split
    # finds nothing and silently swallows the rest of the document (modals
    # included), which would let content accidentally left outside the pane
    # still pass this assertion.
    eventlog_pane = html.split('id="reports-tabs-pane-eventlog"', 1)[1].split('id="fullUrlModal"', 1)[0]
    assert 'id="reports"' in eventlog_pane
    assert 'id="base_flags_url"' in eventlog_pane
    assert "IP Geolocation by DB-IP" in eventlog_pane
    assert 'id="fullUrlModal"' in html
    assert 'id="dataModal"' in html

    # The table must sit under the eventlog pane specifically, not an earlier
    # (or, if one is ever added later, a later) pane: the eventlog pane-id
    # marker must be the last "reports-tabs-pane-" occurrence before the
    # table's own id marker.
    table_marker_pos = html.index('id="reports"')
    last_pane_marker_pos = html.rindex('id="reports-tabs-pane-', 0, table_marker_pos)
    assert html[last_pane_marker_pos:].startswith('id="reports-tabs-pane-eventlog"')


def test_reports_overview_tab_renders_kpi_chart_and_incident_mount_points():
    html = _render_dashboard_page(
        "reports.html",
        columns_preferences_defaults={"reports": {}},
        columns_preferences={},
        is_readonly=True,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )

    # Scope to the Overview pane only, so a stray id elsewhere on the page can't
    # make this test pass by accident.
    overview_pane = html.split('id="reports-tabs-pane-overview"', 1)[1].split('id="reports-tabs-pane-patterns"', 1)[0]

    # KPI tiles: reports-overview.js writes into "#<tile-id> .bw-kpi-value" via jQuery,
    # so both the tile id and the value span's class are load-bearing.
    for tile_id in ("reports-tile-blocked", "reports-tile-rate", "reports-tile-unique", "reports-tile-peak"):
        assert f'id="{tile_id}"' in overview_pane, tile_id
    assert overview_pane.count("bw-kpi-value") == 4

    # Chart mount + its chart-area.html companion data div.
    assert 'id="reports-timeseries-chart"' in overview_pane
    assert 'id="reports-timeseries-chart-data"' in overview_pane

    # Recent incidents / top ASN card bodies reports-overview.js targets via .html().
    assert 'id="reports-recent-incidents"' in overview_pane
    assert 'id="reports-top-asns"' in overview_pane

    # Every i18n key emitted in this pane resolves in en.json.
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))
    for i18n_key in (
        "reports.tile.blocked",
        "reports.tile.blocked_rate",
        "reports.tile.unique_ips",
        "reports.tile.peak_hour",
        "reports.chart.timeseries.title",
        "reports.card.recent.title",
        "reports.card.top_asn.title",
    ):
        assert f'data-i18n="{i18n_key}"' in overview_pane, i18n_key
        assert _resolves_in_locale(locale, i18n_key), i18n_key

    # The range picker (Task 7) is rendered into the content block.
    assert 'id="reports-range"' in html

    # head/scripts blocks aren't rendered by the dashboard.html stub above (it only
    # implements {% block content %}), so check the raw template source for the
    # ApexCharts vendor assets and the page's own scripts -- same approach as
    # test_production_pages_use_vendored_datatables_and_apexcharts.
    source = (TEMPLATES / "reports.html").read_text(encoding="utf-8")
    assert "libs/apexcharts/apexcharts.min.css" in source
    assert "libs/apexcharts/apexcharts.min.js" in source
    assert "js/components/range-picker.js" in source
    assert "js/pages/reports-overview.js" in source
    # ApexCharts must load before the script that constructs the chart.
    assert source.index("libs/apexcharts/apexcharts.min.js") < source.index("js/pages/reports-overview.js")

    # "Blocked rate" (id="reports-tile-rate") was repurposed to render the timeseries
    # payload's trend_pct (percent change vs. the previous equal-length window) instead
    # of the old blocked/(blocked+offenders.length) placeholder ratio.
    js_source = (STATIC / "js" / "pages" / "reports-overview.js").read_text(encoding="utf-8")
    assert "ts.trend_pct" in js_source
    assert "detectOnly" not in js_source


def test_reports_html_loads_flatpickr_before_range_picker_js():
    """range-picker.js's "Custom" button guards on window.flatpickr (see the component source),
    but reports.html previously never loaded the flatpickr vendor lib at all -- only bans.html/
    pro.html did -- making Custom a silent no-op. Flatpickr must now be vendored in (CSP blocks a
    CDN) and, since every script tag here is `defer` (execution order == source order), must
    appear before range-picker.js so `window.flatpickr` exists when it runs.
    """
    source = (TEMPLATES / "reports.html").read_text(encoding="utf-8")

    assert "libs/flatpickr/flatpickr.min.css" in source
    assert "libs/flatpickr/flatpickr.min.js" in source
    assert source.index("libs/flatpickr/flatpickr.min.js") < source.index("js/components/range-picker.js")


def test_range_picker_custom_end_epoch_covers_full_end_day():
    """The DB's timeseries window is half-open [start, end); flatpickr's range mode returns both
    endpoints at local midnight, so using dates[1] as-is dropped the entire selected end-day (and
    made a same-day pick collapse to start === end, an empty window). The end epoch must be pushed
    to the end-day's *next* midnight (+86400s); the start epoch must stay untouched.
    """
    source = (STATIC / "js" / "components" / "range-picker.js").read_text(encoding="utf-8")
    on_close = source.split("onClose: (dates) => {", 1)[1].split("},", 1)[0]

    assert "Math.floor(dates[0].getTime() / 1000)," in on_close
    assert "Math.floor(dates[1].getTime() / 1000) + 86400," in on_close


def test_reports_overview_peak_hour_shows_placeholder_on_all_zero_buckets():
    """peakIdx defaults to 0 and buckets[0] is a real (truthy) epoch, so an all-zero-count window
    previously rendered a bogus "HH:00" instead of the tile's "-" empty state. blocked (ts.total)
    is 0 exactly when every bucket is 0, so gating the label on it is the correct, existing signal.
    """
    source = (STATIC / "js" / "pages" / "reports-overview.js").read_text(encoding="utf-8")
    render_fn = source.split("function renderOverview", 1)[1].split("\n  onRangeChange(", 1)[0]

    assert "blocked && buckets[peakIdx]" in render_fn


def test_reports_overview_incident_and_asn_rows_never_use_html_sink():
    """offenders[].ip / .top_reason / .asn_org are request-derived data (ASN org names come
    from a MaxMind/DB-IP lookup keyed on attacker-controlled IPs) round-tripped through the DB --
    untrusted at the render sink. reports-overview.js must build DOM nodes with jQuery .text()
    (escape-at-sink) rather than interpolate those fields into an .html()/template-literal string,
    which would be a stored-XSS hole. Mirrors test_configs_selected_list_contract_is_text_only's
    pattern for the same class of bug.
    """
    source = (STATIC / "js" / "pages" / "reports-overview.js").read_text(encoding="utf-8")
    render_fn = source.split("function renderOverview", 1)[1].split("\n  onRangeChange(", 1)[0]

    assert ".html(" not in render_fn
    assert "innerHTML" not in render_fn
    assert "insertAdjacentHTML" not in render_fn
    # jQuery's $() constructor parses a string as markup too -- a `$(`<tr>${o.ip}</tr>`)` call
    # would smuggle the same class of bug past the three checks above without ever using the
    # literal token ".html(". Every $() call in this function must be a static tag string.
    assert "$(`" not in render_fn
    for field in (
        ".text(o.ip)",
        ".text(o.top_reason)",
        ".text(o.blocks)",
        ".text(relativeTime(o.last_seen))",
        ".text(org)",
        ".text(count)",
    ):
        assert field in render_fn, field


def test_reports_overview_recent_incidents_sorted_by_last_seen_without_mutating_source():
    """The 'Most recent incidents' card must actually be recency-sorted (descending last_seen),
    not the API's volume-sorted offenders order, and must not mutate data.offenders in place --
    the ASN aggregation below in the same renderOverview() reads data.offenders too and depends
    on seeing it untouched. Pins the exact spread-copy + comparator so a regression (e.g. sorting
    data.offenders directly, or flipping the comparator to ascending) fails this test even though
    it wouldn't be caught by the html-sink test above.
    """
    source = (STATIC / "js" / "pages" / "reports-overview.js").read_text(encoding="utf-8")
    render_fn = source.split("function renderOverview", 1)[1].split("\n  onRangeChange(", 1)[0]

    # Copy-before-sort: must not be "data.offenders || []).sort(" (in-place mutation of the
    # shared array the ASN aggregation later reads).
    assert "[...(data.offenders || [])]" in render_fn
    assert "(data.offenders || []).sort(" not in render_fn

    # Descending by last_seen, null-safe on both sides.
    assert "(b.last_seen || 0) - (a.last_seen || 0)" in render_fn

    # The spread-copy must precede the sort call, and the sort must precede the slice --
    # otherwise the assertions above could both be true of unrelated, non-cooperating lines.
    copy_idx = render_fn.index("[...(data.offenders || [])]")
    sort_idx = render_fn.index("(b.last_seen || 0) - (a.last_seen || 0)")
    slice_idx = render_fn.index(".slice(0, 5)")
    assert copy_idx < sort_idx < slice_idx


def test_reports_patterns_tab_renders_kpi_and_card_mount_points():
    html = _render_dashboard_page(
        "reports.html",
        columns_preferences_defaults={"reports": {}},
        columns_preferences={},
        is_readonly=True,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )

    # Scope to the Patterns pane only, so a stray id elsewhere on the page can't
    # make this test pass by accident.
    patterns_pane = html.split('id="reports-tabs-pane-patterns"', 1)[1].split('id="reports-tabs-pane-offenders"', 1)[0]

    # KPI tiles: reports-patterns.js writes into "#<tile-id> .bw-kpi-value" via jQuery,
    # so both the tile id and the value span's class are load-bearing.
    for tile_id in ("reports-tile-sqli", "reports-tile-rce", "reports-tile-bot"):
        assert f'id="{tile_id}"' in patterns_pane, tile_id
    assert patterns_pane.count("bw-kpi-value") == 3

    # Card bodies reports-patterns.js targets via jQuery DOM construction.
    assert 'id="reports-top-rules"' in patterns_pane
    assert 'id="reports-attack-families"' in patterns_pane

    # Every i18n key emitted in this pane resolves in en.json.
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))
    for i18n_key in (
        "reports.tile.sqli",
        "reports.tile.rce",
        "reports.tile.bot",
        "reports.card.top_rules.title",
        "reports.card.attack_families.title",
    ):
        assert f'data-i18n="{i18n_key}"' in patterns_pane, i18n_key
        assert _resolves_in_locale(locale, i18n_key), i18n_key

    # reports-patterns.js must load after reports-overview.js (it consumes the shared
    # window.BWReportsDashboard.onRangeChange hook that script installs).
    source = (TEMPLATES / "reports.html").read_text(encoding="utf-8")
    assert "js/pages/reports-patterns.js" in source
    assert source.index("js/pages/reports-overview.js") < source.index("js/pages/reports-patterns.js")


def test_reports_patterns_consumes_shared_dashboard_fetch_not_a_second_one():
    """The Attack patterns tab must reuse the single /reports/dashboard POST that
    reports-overview.js already issues per range change (via window.BWReportsDashboard),
    not fire its own AJAX request -- see reports-overview.js's onRangeChange/refresh/
    currentRange contract (Task 9)."""
    source = (STATIC / "js" / "pages" / "reports-patterns.js").read_text(encoding="utf-8")

    assert "window.BWReportsDashboard.onRangeChange(render)" in source
    assert "$.ajax(" not in source
    assert ".ajax(" not in source
    assert "fetch(" not in source


def test_reports_patterns_render_never_uses_html_sink():
    """rule_id is DB-round-tripped ModSecurity data (see get_metrics_top_rules) -- untrusted
    at the render sink even though it's typically a well-formed numeric CRS id. reports-
    patterns.js must build DOM nodes with jQuery .text() (escape-at-sink) rather than
    interpolate rule_id/count into an .html()/template-literal string, which would be a
    stored-XSS hole. Mirrors test_reports_overview_incident_and_asn_rows_never_use_html_sink.
    """
    source = (STATIC / "js" / "pages" / "reports-patterns.js").read_text(encoding="utf-8")
    render_fn = source.split("function render(", 1)[1].split("\n  $(document).ready(", 1)[0]

    assert ".html(" not in render_fn
    assert "innerHTML" not in render_fn
    assert "insertAdjacentHTML" not in render_fn
    # jQuery's $() constructor parses a string as markup too -- a `$(`<tr>${r.rule_id}</tr>`)`
    # call would smuggle the same class of bug past the three checks above without ever
    # using the literal token ".html(".
    assert "$(`" not in render_fn
    for field in (".text(`CRS ${r.rule_id}`)", ".text(r.count)"):
        assert field in render_fn, field

    # The rule-family prefix lookup is keyed on attacker-influenced data (a slice of
    # rule_id) -- must not be a plain object literal, which would expose the prototype
    # chain (constructor/toString/__proto__/...) to the bracket lookup.
    assert "Object.create(null)" in source
    assert "const RULE_FAMILY = {" not in source


def test_reports_offenders_tab_renders_kpi_and_table_mount_points():
    html = _render_dashboard_page(
        "reports.html",
        columns_preferences_defaults={"reports": {}},
        columns_preferences={},
        is_readonly=True,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )

    # Scope to the Offenders pane only, so a stray id elsewhere on the page can't make
    # this test pass by accident.
    offenders_pane = html.split('id="reports-tabs-pane-offenders"', 1)[1].split('id="reports-tabs-pane-eventlog"', 1)[0]

    # KPI tiles: reports-offenders.js writes into "#<tile-id> .bw-kpi-value" via jQuery,
    # so both the tile id and the value span's class are load-bearing.
    for tile_id in ("reports-tile-uniqueoff", "reports-tile-repeat", "reports-tile-countries", "reports-tile-asns"):
        assert f'id="{tile_id}"' in offenders_pane, tile_id
    assert offenders_pane.count("bw-kpi-value") == 4

    # Table mount point reports-offenders.js targets via jQuery DOM construction.
    assert 'id="reports-offenders-table"' in offenders_pane

    # Every i18n key emitted in this pane resolves in en.json.
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))
    for i18n_key in (
        "reports.tile.unique_offenders",
        "reports.tile.repeat_offenders",
        "reports.tile.countries",
        "reports.tile.asns",
        "reports.card.top_offenders.title",
    ):
        assert f'data-i18n="{i18n_key}"' in offenders_pane, i18n_key
        assert _resolves_in_locale(locale, i18n_key), i18n_key

    # reports-offenders.js must load after reports-patterns.js (it consumes the same
    # shared window.BWReportsDashboard.onRangeChange hook reports-overview.js installs).
    source = (TEMPLATES / "reports.html").read_text(encoding="utf-8")
    assert "js/pages/reports-offenders.js" in source
    assert source.index("js/pages/reports-patterns.js") < source.index("js/pages/reports-offenders.js")


def test_reports_offenders_consumes_shared_dashboard_fetch_not_a_second_one():
    """The Top offenders tab must reuse the single /reports/dashboard POST that
    reports-overview.js already issues per range change (via window.BWReportsDashboard),
    not fire its own AJAX request -- see reports-overview.js's onRangeChange/refresh/
    currentRange contract (Task 9). Also pins that the subscription happens unconditionally
    at document-ready, not inside a lazy/tab-shown handler -- onRangeChange is push-only
    with no replay-on-subscribe, so a lazy subscription would leave the tab empty until the
    next range change (Task 10 review trip-wire)."""
    source = (STATIC / "js" / "pages" / "reports-offenders.js").read_text(encoding="utf-8")

    assert "window.BWReportsDashboard.onRangeChange(render)" in source
    assert "$.ajax(" not in source
    assert ".ajax(" not in source
    assert "fetch(" not in source

    # The subscription must live directly inside $(document).ready(...), not nested inside
    # a shown.bs.tab (or any other lazy) handler.
    ready_body = source.split("$(document).ready(function () {", 1)[1]
    assert "shown.bs.tab" not in source
    assert "window.BWReportsDashboard.onRangeChange(render)" in ready_body


def test_reports_offenders_render_never_uses_html_sink():
    """ip/asn_org/top_reason/country are DB-round-tripped, request-derived offender data (ASN
    org names come from a MaxMind/DB-IP lookup on attacker-controlled IPs; see
    reports-overview.js's identical comment) -- untrusted at the render sink even though
    they're typically well-formed. reports-offenders.js must build DOM nodes with jQuery
    .text() (escape-at-sink) rather than interpolate those fields into an .html()/
    template-literal string, which would be a stored-XSS hole. Mirrors
    test_reports_patterns_render_never_uses_html_sink. Also covers countryCell(), the helper
    render() delegates to for the country column.
    """
    source = (STATIC / "js" / "pages" / "reports-offenders.js").read_text(encoding="utf-8")
    scope = source.split("function countryCell(code) {", 1)[1].split("\n  $(document).on(", 1)[0]

    assert ".html(" not in scope
    assert "innerHTML" not in scope
    assert "insertAdjacentHTML" not in scope
    # jQuery's $() constructor parses a string as markup too -- a `$(`<tr>${o.ip}</tr>`)` call
    # would smuggle the same class of bug past the three checks above without ever using the
    # literal token ".html(". Every $() call in this scope must be a static tag string.
    assert "$(`" not in scope
    for field in (
        ".text(o.ip)",
        ".text(o.blocks)",
        ".text(o.top_reason)",
        'o.asn_org ? `AS${o.asn_number} — ${o.asn_org}` : "N/A"',
    ):
        assert field in scope, field

    # Country column: rendered via countryCell(), not a bare .text(o.country) -- srcFor()
    # goes into an <img> src attribute (never HTML-parsed) and the visible label is still
    # .text()'d, so this composes with the discipline above rather than bypassing it.
    assert ".append(countryCell(o.country))" in scope
    # srcFor()'s return value must be assigned as an <img> attribute (never HTML-parsed),
    # not concatenated into a markup string.
    assert "src: window.BWCountryFlag.srcFor(code)," in scope
    assert "window.BWCountryFlag.isNA(code)" in scope
    assert "window.BWCountryFlag.normalize(code)" in scope
    # The reusable html()-string builder is deliberately NOT used here (see file's own
    # doc comment on countryCell) -- pin that choice so a future edit can't silently swap
    # back to the raw-HTML-string sink.
    assert "window.BWCountryFlag.html(" not in source


def test_configs_selected_list_contract_is_text_only():
    source = (TEMPLATES.parent / "static" / "js" / "pages" / "configs.js").read_text(encoding="utf-8")
    rows_builder = source.split("const buildConfigsRows", 1)[1].split("const renderSelectedConfigs", 1)[0]

    assert "safe: true" not in source
    assert ".text().trim()" in rows_builder
    assert ".html()" not in rows_builder


def test_home_request_status_chart_declares_empty_state():
    source = (STATIC / "js" / "pages" / "home.js").read_text(encoding="utf-8")
    options = source.split("const requestsOptions", 1)[1].split("requestsChart = new ApexCharts", 1)[0]

    assert "noData:" in options
    assert 'text: t("status.no_data")' in options


def test_admin_shell_uses_design_system_fonts_theme_and_boxicons():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    menu = (TEMPLATES / "menu.html").read_text(encoding="utf-8")
    navbar = (TEMPLATES / "navbar.html").read_text(encoding="utf-8")

    for asset in ("Public_sans.css", "DonJose.css", "Courier_Prime.css", "boxicons.min.css"):
        assert asset in base
    assert 'data-bs-theme="{{ theme }}"' in base
    assert 'aria-label="Toggle navigation"' in navbar
    assert 'id="admin-nav-search"' in navbar
    assert 'aria-label="Close navigation"' in menu
    assert "fontawesome" not in (base + menu + navbar).lower()


def test_admin_theme_has_accessible_focus_motion_and_dark_surface_contracts():
    overrides = (STATIC / "css" / "overrides.css").read_text(encoding="utf-8")
    theme = (STATIC / "css" / "theme-default.css").read_text(encoding="utf-8")
    home = (STATIC / "css" / "pages" / "home.css").read_text(encoding="utf-8")

    assert "--bs-body-line-height: 1.47;" in overrides
    assert "--bw-bg-card: #133044;" in overrides
    assert ".table > thead > tr > th {\n  color: var(--bw-fg-2);" in overrides
    assert "outline: 3px solid rgba(var(--bs-primary-rgb), 0.25);" in overrides
    assert "animation-duration: 0.01ms !important;" in overrides
    assert "animation-iteration-count: 1 !important;" in overrides
    assert 'content: "🔒"' not in overrides
    assert ".layout-menu .menu-link:focus-visible" in theme
    assert ".bw-navbar-search .input-group:focus-within" in theme
    assert "box-shadow: var(--bw-shadow-md);" in theme
    assert theme.count("height: 4rem;") >= 2
    assert ".pro-card {\n  background: #0b354a;" in overrides
    assert "linear-gradient" not in home


def test_motion_sensitive_javascript_honours_reduced_motion():
    main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    home = (STATIC / "js" / "pages" / "home.js").read_text(encoding="utf-8")
    setup = (STATIC / "js" / "pages" / "setup.js").read_text(encoding="utf-8")
    template_edit = (STATIC / "js" / "pages" / "template_edit.js").read_text(encoding="utf-8")
    logs = (STATIC / "js" / "pages" / "logs.js").read_text(encoding="utf-8")

    assert 'matchMedia?.("(prefers-reduced-motion: reduce)")' in main
    assert 'querySelectorAll("lottie-player[autoplay]")' in main
    assert home.count("enabled: !window.bwPrefersReducedMotion()") == 3
    assert 'behavior: window.bwPrefersReducedMotion() ? "auto" : "smooth"' in setup
    assert template_edit.count('behavior: window.bwPrefersReducedMotion() ? "auto" : "smooth"') == 3
    assert "if (window.bwPrefersReducedMotion())" in logs


def test_production_pages_use_vendored_datatables_and_apexcharts():
    datatable_pages = (
        "bans.html",
        "cache.html",
        "configs.html",
        "instances.html",
        "jobs.html",
        "plugin_page.html",
        "plugins.html",
        "reports.html",
        "services.html",
        "templates.html",
    )
    for name in datatable_pages:
        source = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "libs/datatables/datatables.min.css" in source, name
        assert "libs/datatables/datatables.min.js" in source, name

    home = (TEMPLATES / "home.html").read_text(encoding="utf-8")
    assert "libs/apexcharts/apexcharts.min.css" in home
    assert "libs/apexcharts/apexcharts.min.js" in home


def test_product_copy_does_not_use_emoji_as_icons():
    emoji = re.compile("[\\u2600-\\u27bf\\U0001f300-\\U0001faff]")
    paths = list(TEMPLATES.glob("*.html"))
    paths.extend((STATIC / "locales").glob("*.json"))
    paths.extend(path for path in (STATIC / "js" / "pages").glob("*.js") if path.name not in {"logs.js", "ace-mode-bunkerweb_log.js"})

    failures = [str(path.relative_to(TEMPLATES.parents[1])) for path in paths if emoji.search(path.read_text(encoding="utf-8"))]
    assert not failures


def test_plugin_dropzone_is_keyboard_operable():
    template = (TEMPLATES / "plugins.html").read_text(encoding="utf-8")
    script = (STATIC / "js" / "pages" / "plugins.js").read_text(encoding="utf-8")

    dropzone = template.split('id="drag-area"', 1)[1].split(">", 1)[0]
    assert 'tabindex="0"' in dropzone
    assert 'aria-controls="file-input"' in dropzone
    assert 'aria-label="Select plugin archives or drop them here"' in dropzone
    assert 'dragArea.on("keydown"' in script


def _resolves_in_locale(locale, dotted_key):
    node = locale
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _locale_leaf_types(locale, prefix=""):
    leaves = {}
    for key, value in locale.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            leaves.update(_locale_leaf_types(value, path))
        else:
            leaves[path] = type(value)
    return leaves


def test_all_locales_match_en_json_structure():
    expected = _locale_leaf_types(json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8")))

    for path in sorted((STATIC / "locales").glob("*.json")):
        locale = json.loads(path.read_text(encoding="utf-8"))
        assert _locale_leaf_types(locale) == expected, path.name


def test_every_data_i18n_key_resolves_in_en_json():
    """Every literal data-i18n="<key>" found in templates/JS must exist in en.json.

    Dynamic keys built from Jinja/JS expressions (containing "{") are skipped --
    they can't be resolved statically. Occurrences inside {# ... #} Jinja
    comments (macro docs that show data-i18n usage as an example) are stripped
    before scanning so documentation doesn't get flagged as a real usage.
    """
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))

    jinja_comment_re = re.compile(r"\{#.*?#\}", re.DOTALL)
    html_attr_re = re.compile(r'data-i18n="([^"]*)"')
    js_attr_re = re.compile(r'data-i18n[=,]\s*["\']([^"\']*)["\']')

    occurrences = []  # (relative_path, key)

    for path in sorted(TEMPLATES.rglob("*.html")):
        text = jinja_comment_re.sub("", path.read_text(encoding="utf-8"))
        for match in html_attr_re.finditer(text):
            key = match.group(1)
            if key and "{" not in key and "}" not in key:
                occurrences.append((str(path.relative_to(TEMPLATES.parents[1])), key))

    for path in sorted((STATIC / "js").rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in js_attr_re.finditer(text):
            key = match.group(1)
            if key and "{" not in key and "}" not in key:
                occurrences.append((str(path.relative_to(TEMPLATES.parents[1])), key))

    assert occurrences, "expected to find data-i18n usages to validate"

    missing = sorted({(source, key) for source, key in occurrences if not _resolves_in_locale(locale, key)})

    assert not missing, "data-i18n keys missing from en.json (file: key):\n" + "\n".join(f"{source}: {key}" for source, key in missing)


def test_every_t_call_key_in_reports_js_resolves_in_en_json():
    """test_every_data_i18n_key_resolves_in_en_json only catches keys rendered as a
    data-i18n/title_i18n/i18n_key attribute in template/JS source. The reports dashboard's JS
    (all 4 tabs: the pre-existing reports.js event-log script plus the Tasks 9-11
    reports-overview/patterns/offenders.js tab scripts) also calls i18next directly via
    t("key", "fallback") for strings that never render as a data-i18n attribute -- toolbar
    button labels, SearchPanes column headers, chart series names, ARIA/title labels,
    alert() text, relative-time strings, empty-state and modal-detail text set via
    .text()/template-literal interpolation rather than left for i18next's DOM scanner. A
    typo'd key there silently falls back to the English default (i18next's t() contract) and
    nothing else in the suite would catch it. Regex-extract every literal t("...") call's key
    from the 4 reports JS files and assert it resolves in en.json.
    """
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))

    # \b immediately before "t(" requires a word boundary there, so it matches the standalone
    # `t(` identifier call (the local `const t = i18next.t : (key, fallback) => ...` alias each
    # reports*.js file declares) but not `.text(`, `.submit(`, `format(`, etc., whose "t(" is
    # preceded by another word character. \s* between "t(" and the opening quote also matches
    # across newlines (re.match's \s includes "\n"), so multi-line calls like
    # `t(\n  "key",\n  "fallback",\n)` (used repeatedly in reports.js) are still caught.
    t_call_re = re.compile(r'\bt\(\s*["\']([^"\']+)["\']')

    files = (
        STATIC / "js" / "pages" / "reports.js",
        STATIC / "js" / "pages" / "reports-overview.js",
        STATIC / "js" / "pages" / "reports-patterns.js",
        STATIC / "js" / "pages" / "reports-offenders.js",
    )

    occurrences = []  # (relative_path, key)
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in t_call_re.finditer(text):
            occurrences.append((str(path.relative_to(TEMPLATES.parents[1])), match.group(1)))

    # Prove the extractor actually found the known literal calls, not just "non-empty" -- a
    # regex that matches nothing would make the "no missing keys" assertion below vacuously
    # true. This list was hand-verified against the 4 files' source (49 literal t(...) calls /
    # 42 unique keys total as of this writing). Two dynamic calls are correctly excluded since
    # their first argument isn't a string literal:
    #  - t(labelKey, fam) in reports-patterns.js: labelKey resolves to reports.tile.sqli/rce,
    #    which reports.html passes into the tile() macro as title_i18n="..." (a Jinja kwarg,
    #    not a literal data-i18n="..." string in the template source) -- so
    #    test_every_data_i18n_key_resolves_in_en_json's raw-source scan can't and doesn't see
    #    it. Coverage instead comes from test_reports_patterns_tab_renders_kpi_and_card_mount_points
    #    above, which renders the template (the macro emits data-i18n="{{ title_i18n }}" into
    #    the actual HTML output) and asserts both keys resolve.
    #  - t(i18nKey, title) in reports.js's column-visibility toolbar builder: i18nKey is read
    #    from that column header's own data-i18n attribute at runtime, not a fixed literal --
    #    and the attribute values themselves are covered by
    #    test_every_data_i18n_key_resolves_in_en_json above.
    found_keys = {key for _, key in occurrences}
    for expected in (
        # reports.js (event log tab): toolbar buttons, SearchPanes headers, ban/readonly
        # tooltips, load-error flash, and the Security-Report-Details modal's field labels.
        "button.columns",
        "button.export",
        "button.ban_selected",
        "searchpane.ip_address",
        "searchpane.status_code",
        "tooltip.button.ban_ip",
        "tooltip.readonly_mode",
        "error.reports_load_error",
        "reports.bad_behavior_no_details",
        "reports.bad_behavior_activity_detected",
        "reports.bad_behavior_request_id",
        "status.default_server",
        "status.not_applicable",
        # reports-overview.js / reports-patterns.js / reports-offenders.js (Tasks 9-11 tabs).
        "flash.time.just_now",
        "reports.chart.timeseries.series",
        "status.no_data",
        "reports.table.rule",
        "reports.table.fires",
        "reports.table.ip",
        "reports.table.country",
        "reports.table.asn",
        "reports.table.blocks",
        "reports.table.top_rule",
        "alert.readonly_mode",
    ):
        assert expected in found_keys, f"extractor failed to find known key {expected}"

    missing = sorted({(source, key) for source, key in occurrences if not _resolves_in_locale(locale, key)})

    assert not missing, "t(...) keys missing from en.json (file: key):\n" + "\n".join(f"{source}: {key}" for source, key in missing)

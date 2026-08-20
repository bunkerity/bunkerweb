"""Phase 1 / 1C-1D (Services/status/configs shared pass): the `.icon-btn`/`.row-actions`
CSS port into ``overrides.css`` and the colored-btn-outline -> neutral-icon-btn action
swap on services.html, instances.html, configs.html, cache.html and jobs.html, plus the
`components/status.html` swap on instances' health pill and jobs' last-run pill.

Render tests follow the standalone-Jinja-env pattern established by
test_ui_components.py's `_render_dashboard_page` (and mirrored by test_templates_gallery.py
/ test_bans_stats.py for other Phase-1 sub-projects in this same wave).

Every test asserts that the *behavioral* hooks (classes JS binds `$(document).on("click",
...)` to, and `data-*` attributes read by that JS) survive the purely-visual class swap
byte for byte -- that's the binding "never delete working functionality" constraint for
this pass.
"""

import re
from pathlib import Path

from conftest import english  # what a converted template renders for a key
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.utils import can_delete_service, is_editable_method, is_ui_api_method  # type: ignore

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
CSS = TEMPLATES.parent / "static" / "css" / "overrides.css"


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
        can_delete_service=can_delete_service,
        is_editable_method=is_editable_method,
        is_ui_api_method=is_ui_api_method,
    )
    env.filters["to_iso"] = lambda value: value
    return env.get_template(template).render(**context)


# --------------------------------------------------------------------------------------
# overrides.css -- the ported .icon-btn/.row-actions rules exist and are theme-aware
# --------------------------------------------------------------------------------------
def test_overrides_css_defines_icon_btn_and_row_actions():
    css = CSS.read_text(encoding="utf-8")

    assert ".icon-btn {" in css
    assert ".icon-btn:hover {" in css
    for variant in ("primary", "danger", "success", "info", "ban"):
        assert f".icon-btn.{variant} {{" in css, variant
    assert ".table .row-actions {" in css
    assert ".table th.actions-col," in css
    assert ".table td.actions-col {" in css
    # theme-aware: dark overrides use this app's actual toggle attribute, not the kit's
    assert '[data-bs-theme="dark"] .icon-btn' in css
    assert ':root[data-theme="dark"] .icon-btn' not in css
    # the disabled state (draft/readonly-gated actions) must keep working once the
    # `.btn` class -- and with it Bootstrap's `.btn.disabled` pointer-events rule -- is gone
    assert ".icon-btn.disabled," in css


# --------------------------------------------------------------------------------------
# services.html
# --------------------------------------------------------------------------------------
def _services_context(is_draft=False, is_readonly=False, user_readonly=False, method="ui"):
    service = {
        "id": "www.example.com",
        "is_draft": is_draft,
        "method": method,
        "security_mode": "block",
        "template": None,
        "creation_date": "2026-01-01",
        "last_update": "2026-01-01",
    }
    return dict(
        services=[service],
        services_with_configs=[],
        templates=[],
        columns_preferences_defaults={"services": {}},
        columns_preferences={},
        is_readonly=is_readonly,
        user_readonly=user_readonly,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )


# services.html no longer renders the six row actions: they were ~4.8 KB of near-identical
# markup per row, 73% of the page and 2.4 MB of it at 500 services, so the column renderer in
# `static/js/pages/services.js` builds them for the rows on screen instead (Lot C). The cell
# carries the four per-row facts as a `|`-packed payload. The behavioural hooks these tests
# exist to protect therefore live in the JS now, and that is where they are asserted.
SERVICES_JS = TEMPLATES.parent / "static" / "js" / "pages" / "services.js"


def _renderer_source(js):
    """Just the renderer, so an assertion cannot be satisfied by an unrelated part of the file."""
    start = js.index("function renderRowActions")
    end = js.index("const selectedServices")
    return js[start:end]


def test_services_row_actions_keep_their_behavioral_hooks():
    js = SERVICES_JS.read_text(encoding="utf-8")
    actions = _renderer_source(js)

    assert 'class="row-actions"' in actions
    # The classes `$(document).on("click", ...)` is delegated to, and the attribute those
    # handlers read. Delegation is why moving the markup needs no rebinding.
    for hook in ("convert-service", "export-service", "delete-service"):
        assert hook in actions, hook
        assert f'$(document).on("click", ".{hook}"' in js, f"{hook} handler must stay delegated"
    assert 'data-service-id="${safeId}"' in actions
    # danger/info colour variants land on the right actions
    assert "icon-btn danger delete-service" in actions
    assert "icon-btn info export-service" in actions
    # no colored btn-outline-* action classes crept back in
    assert "btn-outline-primary btn-sm" not in actions
    assert "btn-outline-danger btn-sm" not in actions


def test_services_draft_disables_access_action():
    js = SERVICES_JS.read_text(encoding="utf-8")
    actions = _renderer_source(js)

    # The renderer is handed the row object the `/services/fetch` endpoint returns, not the packed
    # `id|draft|method|deletable` string the template used to put in the cell. Same fact, one less
    # encoding to keep in step between Python and JavaScript.
    assert 'const isDraft = row.type === "draft";' in actions
    assert 'class="icon-btn${isDraft ? " disabled" : ""}" href="https://${safeId}"' in actions


def test_the_page_ships_no_rows_at_all():
    """The table is `serverSide` now, so the row facts arrive from `/services/fetch` as JSON —
    they are asserted in `test_services_fetch.py`, against the endpoint that produces them.

    What belongs here is the other half of that move: the document itself carries no row. At 500
    services the old markup was 868 KB of a 1089 KB page and 10 711 DOM nodes, of which DataTables
    kept ten. One row creeping back into the template puts all of it back."""
    html = _render_dashboard_page("services.html", **_services_context(method="ui"))

    assert "<tbody></tbody>" in html
    assert "www.example.com" not in html
    # (`modal-delete-services`, the bulk confirmation dialog, is a page-level element and stays —
    # hence the class, not a substring.)
    assert 'class="row-actions"' not in html
    assert 'class="icon-btn danger delete-service"' not in html


def test_the_row_object_never_reaches_search_or_sort():
    """`display` only. Indexed, a search for "yes" would match every deletable service and a
    search for "ui" every ui-managed one — against a column that shows no text at all."""
    js = SERVICES_JS.read_text(encoding="utf-8")

    # Whitespace-normalised: prettier reflows this arrow depending on how long the line gets.
    assert 'render: (data, type, row) => type === "display" ? renderRowActions(row) : ""' in " ".join(js.split())


def test_the_draft_and_online_badge_stays_a_plain_badge():
    """Rendered in `services.js` now that the rows arrive as JSON. `data-value` is not decoration:
    the bulk-conversion filter reads it off `#type-<name>` to skip services already in the target
    state, and the confirm list clones the badge out of the row."""
    js = SERVICES_JS.read_text(encoding="utf-8")
    render_type = js[js.index("function renderType") : js.index("function renderSecurityMode")]  # noqa: E203

    assert 'id="type-${escapeAttr(idFor(name))}" data-value="${draft ? "draft" : "online"}"' in render_type
    assert "status-dot" not in render_type


def test_services_actions_header_is_right_aligned():
    html = _render_dashboard_page("services.html", **_services_context())

    assert re.search(r'<th class="actions-col"[^>]*' + re.escape(english("tooltip.table.services.actions")), html)


# --------------------------------------------------------------------------------------
# instances.html
# --------------------------------------------------------------------------------------
def _instances_context(status="up", is_readonly=False, user_readonly=False, method="ui"):
    instance = {
        "hostname": "bw-1",
        "name": "bw-1",
        "method": method,
        "status": status,
        "type": "container",
        "creation_date": "2026-01-01",
        "last_seen": "2026-01-01",
    }
    return dict(
        instances=[instance],
        columns_preferences_defaults={"instances": {}},
        columns_preferences={},
        is_readonly=is_readonly,
        user_readonly=user_readonly,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )


def _button_with_class(html, class_value):
    """The opening `<button>` tag carrying exactly `class_value`, or None.

    Deliberately NOT an adjacency regex. These assertions used to require
    `class="..."` to be immediately followed by `data-instance=...`; the a11y pass in
    `feed8103a` inserted `aria-label` + `data-i18n-aria-label` between the two on the
    reload/stop buttons, and the delete button puts `data-instance` *before* `class`
    altogether -- so the old pattern only ever matched `ping` by accident. Attribute order is
    not a contract and pinning it turns an accessibility improvement into a test failure;
    what matters is that the hook and the class sit on the same element.
    """
    match = re.search(r"<button\b[^>]*" + re.escape(f'class="{class_value}"') + r"[^>]*>", html)
    return match.group(0) if match else None


def test_instances_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("instances.html", **_instances_context())

    assert 'class="row-actions"' in html
    for action in ("ping-instance", "reload-instance", "stop-instance"):
        button = _button_with_class(html, f"icon-btn {action}")
        assert button, action
        # The JS delegates off the class and reads the target from data-instance, so both must
        # be on the same button for the action to fire against the right host.
        assert 'data-instance="bw-1"' in button, action
        # The a11y pass's label must survive: an icon-only button has no accessible name
        # without it. The lookbehind is load-bearing -- a plain `"aria-label=" in button`
        # is also satisfied by `data-i18n-aria-label=`, which every one of these buttons
        # carries, so it passes even with the real attribute deleted.
        assert re.search(r'(?<![-\w])aria-label="', button), action
    delete_button = _button_with_class(html, "icon-btn danger delete-instance")
    assert delete_button
    assert 'data-instance="bw-1"' in delete_button
    # scoped past the row-actions marker: the page-head band's own "Create instance"
    # CTA (a legitimately colored button living earlier on the page) must not trip
    # this row-actions-only check.
    after_actions = html.split('class="row-actions"', 1)[1]
    assert "btn btn-primary btn-sm" not in after_actions
    assert "btn-outline-secondary btn-sm" not in after_actions
    assert "btn-outline-danger btn-sm" not in after_actions


def test_instances_health_pill_uses_status_macro_and_keeps_id_contract():
    html = _render_dashboard_page("instances.html", **_instances_context(status="up"))

    assert 'id="status-bw-1"' in html
    assert 'class="status-dot status-dot-pulse"' in html
    assert 'data-value="up"' in html
    assert 'role="status"' in html
    assert "bg-label-bw-green" in html


def test_instances_down_health_pill_is_static_dot_with_danger_variant():
    html = _render_dashboard_page("instances.html", **_instances_context(status="down"))

    assert 'id="status-bw-1"' in html
    assert "bg-label-danger" in html
    # 'down' is a static state, no pulsing dot
    pill = html.split('id="status-bw-1"', 1)[1].split("</span>", 1)[0]
    assert "status-dot-pulse" not in pill


def test_instances_reload_stop_disabled_when_not_up():
    html = _render_dashboard_page("instances.html", **_instances_context(status="down"))

    assert re.search(r'class="icon-btn reload-instance disabled"', html)
    assert re.search(r'class="icon-btn stop-instance disabled"', html)


# --------------------------------------------------------------------------------------
# configs.html
# --------------------------------------------------------------------------------------
def _configs_context(is_readonly=False, user_readonly=False, method="ui", is_draft=False):
    # The API's shape, not the pre-migration one: `routers/configs.py:86` pops `service_id` and
    # emits `service`, and a non-global value at that -- `None` was the one value for which the dead
    # key and the live key render identically, which is why these tests stayed green through the
    # `/configs`-renders-everything-as-Global defect. See test_template_api_key_contract.py.
    config = {
        "type": "http",
        "service": "app1.example.com",
        "name": "my-config",
        "method": method,
        "template": None,
        "checksum": "abc123",
        "is_draft": is_draft,
    }
    return dict(
        configs=[config],
        services="",
        db_templates="",
        config_service="",
        config_type="",
        columns_preferences_defaults={"configs": {}},
        columns_preferences={},
        is_readonly=is_readonly,
        user_readonly=user_readonly,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )


def test_configs_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("configs.html", **_configs_context())

    assert 'class="row-actions"' in html
    assert re.search(r'data-config-name="my-config"[^>]*class="icon-btn convert-config"', html)
    assert re.search(r'class="icon-btn danger delete-config"', html)
    assert re.search(r'class="icon-btn info export-config"', html)
    assert 'data-config-name="my-config"' in html
    assert 'data-config-type="http"' in html
    assert "btn btn-primary btn-sm" not in html
    assert "btn-outline-secondary btn-sm" not in html
    assert "btn-outline-danger btn-sm" not in html
    assert 'class="actions-col"' in html


def test_configs_page_still_has_its_title_header():
    # The page header is now the shared page-head band (breadcrumb + bare H1), with the
    # "Create custom config" CTA relocated from the DataTable toolbar into the band.
    html = _render_dashboard_page("configs.html", **_configs_context())

    assert re.search(r"<h1[^>]*>\s*Configs\s*</h1>", html)
    assert "bw-page-head-title" in html
    assert english("navigation.configs") in html
    assert english("button.create_config") in html


# --------------------------------------------------------------------------------------
# cache.html
# --------------------------------------------------------------------------------------
def _cache_context(is_readonly=False):
    # The API's shape: `routers/cache.py:54-61` builds rows with `service` and `plugin`, and a
    # non-global service. Same reason as `_configs_context` above.
    cache = {
        "service": "app1.example.com",
        "plugin": "blacklist",
        "job_name": "download-blacklists",
        "file_name": "ip.list",
        "last_update": "2026-01-01",
        "checksum": "def456",
    }
    return dict(
        caches=[cache],
        services="",
        cache_service="",
        cache_plugin="",
        cache_job_name="",
        columns_preferences_defaults={"cache": {}},
        columns_preferences={},
        is_readonly=is_readonly,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )


# The KPI band is the sharp edge of the `"global"` sentinel: the API never sends `None`, so the
# counts cannot be derived from truthiness and each filter names the literal. `rejectattr('service',
# 'eq', 'global')` reads like a faithful translation of the old `rejectattr('service_id')` and counts
# the exact opposite set -- a mistake made and caught once here, hence this test.
def test_cache_kpi_band_counts_global_and_per_service_rows():
    ctx = _cache_context()
    ctx["caches"] = [
        {**ctx["caches"][0], "service": "app1.example.com", "plugin": "blacklist"},
        {**ctx["caches"][0], "service": "app2.example.com", "plugin": "blacklist", "file_name": "b.list"},
        {**ctx["caches"][0], "service": "global", "plugin": "whitelist", "file_name": "c.list"},
    ]
    html = _render_dashboard_page("cache.html", **ctx)
    tiles = re.findall(r"bw-kpi-label.*?<span>(.*?)</span>.*?bw-kpi-value\">(.*?)</span>", html, re.S)
    counts = {label.strip(): value.strip() for label, value in tiles}

    assert counts[english("cache.kpi_files")] == "3"
    assert counts[english("scope.global")] == "1", "the Global tile counts global rows, not everything else"
    assert counts[english("cache.kpi_per_service")] == "2"
    assert "Across 2 plugins" in html
    assert "2 services" in html


# `data-service` asserts the fixture's own service, not `"global"`. It read `"global"` until
# 2026-08-20 -- the template was reading a key the API had stopped emitting, so every row collapsed
# to the global scope and this assertion passed for the wrong reason. The value below is the one the
# correct render produces; see test_template_api_key_contract.py for the guard that pins the keys.
def test_cache_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("cache.html", **_cache_context())

    assert 'class="row-actions"' in html
    assert re.search(r'class="icon-btn danger cache-delete-btn"[^>]*data-service="app1\.example\.com"', html)
    assert 'data-plugin="blacklist"' in html
    assert 'data-job="download-blacklists"' in html
    assert 'data-file="ip.list"' in html
    assert re.search(r'class="icon-btn info"[^>]*download=true', html)
    assert "btn btn-primary btn-sm" not in html
    assert "btn-outline-secondary btn-sm" not in html
    assert "btn-outline-danger btn-sm" not in html


# --------------------------------------------------------------------------------------
# jobs.html
# --------------------------------------------------------------------------------------
def _jobs_context(success=True, has_history=True, is_readonly=False):
    history = [{"start_date": "2026-01-01", "end_date": "2026-01-01", "success": success}] if has_history else []
    job_data = {
        "plugin_id": "blacklist",
        "every": "day",
        "reload": True,
        "async": False,
        "history": history,
        "cache": [],
    }
    return dict(
        jobs={"download-blacklists": job_data},
        columns_preferences_defaults={"jobs": {}},
        columns_preferences={},
        is_readonly=is_readonly,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )


def test_jobs_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("jobs.html", **_jobs_context())

    assert 'class="row-actions"' in html
    assert re.search(r'data-job="download-blacklists"\s+data-plugin="blacklist"[^>]*class="icon-btn run-job"', html)
    assert re.search(r'class="icon-btn show-history"', html)
    assert 'data-job="download-blacklists"' in html
    assert 'data-plugin="blacklist"' in html
    assert "btn btn-primary btn-sm" not in html
    assert "btn-outline-primary btn-sm" not in html
    assert 'class="actions-col"' in html


def test_jobs_last_run_pill_uses_status_macro_and_keeps_searchpane_icon_hooks():
    html_success = _render_dashboard_page("jobs.html", **_jobs_context(success=True))
    html_failed = _render_dashboard_page("jobs.html", **_jobs_context(success=False))

    # status() macro's dot + i18n-backed pill
    assert english("status.success") in html_success
    assert "status-dot" in html_success
    assert english("status.failed") in html_failed

    # static/js/pages/jobs.js's searchPanes filter for this column matches raw cell HTML
    # containing "bx-check"/"bx-x" (jobs.js:365-372) -- not touched by this pass, so the
    # substring must still be present even though the visible pill no longer has its own icon.
    assert "bx-check" in html_success
    assert "bx-x" in html_failed


def test_jobs_no_history_still_shows_plain_text():
    html = _render_dashboard_page("jobs.html", **_jobs_context(has_history=False))

    assert english("status.no_history") in html
    assert re.search(r'class="icon-btn show-history disabled"', html)

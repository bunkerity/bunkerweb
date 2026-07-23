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


def test_services_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("services.html", **_services_context())

    assert 'class="row-actions"' in html
    assert re.search(r'class="icon-btn[^"]*\bconvert-service\b[^"]*"\s+data-service-id="www\.example\.com"', html)
    assert re.search(r'class="icon-btn[^"]*\bexport-service\b[^"]*"\s+data-service-id="www\.example\.com"', html)
    assert re.search(r'class="icon-btn[^"]*\bdelete-service\b[^"]*"', html)
    assert 'data-service-id="www.example.com"' in html
    # danger/info color variants land on the right actions
    assert re.search(r'class="icon-btn danger delete-service', html)
    assert re.search(r'class="icon-btn info export-service', html)
    # no leftover colored btn-outline-* action classes on the row itself (scoped past
    # the row-actions marker so the page-head band's own "Create service"/"Import
    # services" CTAs -- legitimately colored buttons living earlier on the page --
    # don't produce a false positive here).
    after_actions = html.split('class="row-actions"', 1)[1]
    assert "btn-outline-primary btn-sm" not in after_actions
    assert "btn-outline-danger btn-sm" not in after_actions
    assert "btn btn-primary btn-sm" not in after_actions
    # actions column carries the shared right-align chrome
    assert 'class="actions-col"' in html
    # Draft/Online stays a plain badge (not the live-state status() pill): no status-dot
    assert 'data-value="online"' in html
    assert "status-dot" not in html


def test_services_draft_disables_access_action_visually():
    html = _render_dashboard_page("services.html", **_services_context(is_draft=True))

    assert re.search(r'class="icon-btn disabled"\s+href="https://www\.example\.com"', html)


def test_services_actions_header_is_right_aligned():
    html = _render_dashboard_page("services.html", **_services_context())

    assert re.search(r'<th class="actions-col"[^>]*data-i18n="tooltip\.table\.services\.actions"', html)


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


def test_instances_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("instances.html", **_instances_context())

    assert 'class="row-actions"' in html
    assert re.search(r'class="icon-btn ping-instance"\s+data-instance="bw-1"', html)
    assert re.search(r'class="icon-btn reload-instance"\s+data-instance="bw-1"', html)
    assert re.search(r'class="icon-btn stop-instance"\s+data-instance="bw-1"', html)
    assert re.search(r'class="icon-btn danger delete-instance"', html)
    assert 'data-instance="bw-1"' in html
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
    config = {
        "type": "http",
        "service_id": None,
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
    assert 'data-i18n="navigation.configs"' in html
    assert 'data-i18n="button.create_config"' in html


# --------------------------------------------------------------------------------------
# cache.html
# --------------------------------------------------------------------------------------
def _cache_context(is_readonly=False):
    cache = {
        "service_id": None,
        "plugin_id": "blacklist",
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


def test_cache_row_actions_use_icon_btn_and_keep_behavioral_hooks():
    html = _render_dashboard_page("cache.html", **_cache_context())

    assert 'class="row-actions"' in html
    assert re.search(r'class="icon-btn danger cache-delete-btn"[^>]*data-service="global"', html)
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
    assert 'data-i18n="status.success"' in html_success
    assert "status-dot" in html_success
    assert 'data-i18n="status.failed"' in html_failed

    # static/js/pages/jobs.js's searchPanes filter for this column matches raw cell HTML
    # containing "bx-check"/"bx-x" (jobs.js:365-372) -- not touched by this pass, so the
    # substring must still be present even though the visible pill no longer has its own icon.
    assert "bx-check" in html_success
    assert "bx-x" in html_failed


def test_jobs_no_history_still_shows_plain_text():
    html = _render_dashboard_page("jobs.html", **_jobs_context(has_history=False))

    assert 'data-i18n="status.no_history"' in html
    assert re.search(r'class="icon-btn show-history disabled"', html)

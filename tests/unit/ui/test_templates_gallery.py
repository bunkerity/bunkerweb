"""Templates card gallery (Phase 1A): the DataTable -> card grid swap in ``templates.html``,
the ``template_usage``/``_template_tag_badges`` backend helpers in ``routes/templates.py``,
and the trimmed ``static/js/pages/templates.js`` bulk-select/delete wiring.

Route tests follow the module-loader pattern established by ``test_web_cache.py``/
``test_bans_stats.py``: ``app.dependencies`` is stubbed before loading ``templates.py`` so
real container-only state never boots.

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


# --------------------------------------------------------------------------------------
# Render harness (mirrors test_reports_components.py's _render_dashboard_page)
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
    )
    return env.get_template(template).render(**context)


def _resolves_in_locale(locale, dotted_key):
    node = locale
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _base_context(**overrides):
    context = dict(
        templates={},
        template_usage={},
        template_badges={},
        is_readonly=False,
        user_readonly=False,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )
    context.update(overrides)
    return context


_TEMPLATE_A = {
    "id": "tpl-a",
    "name": "WordPress site",
    "plugin_id": None,
    "method": "ui",
    "steps": [{"title": "Step 1"}],
    "settings": {"USE_ANTIBOT": "captcha"},
    "configs": {"modsec_crs/before.conf": ""},
}
_TEMPLATE_B = {
    "id": "tpl-b",
    "name": "Static site",
    "plugin_id": None,
    "method": "manual",
    "steps": [],
    "settings": {},
    "configs": {},
}
_BADGES_A = [
    {"text": "Antibot", "type": "plugin", "variant": "primary", "icon": "bx-plug"},
    {"text": "CRS", "type": "config", "variant": "secondary", "icon": "bx-file-blank"},
    {"text": "Gzip", "type": "feature", "variant": "success", "icon": "bx-package"},
]


def _two_template_context(**overrides):
    return _base_context(
        templates={"tpl-a": _TEMPLATE_A, "tpl-b": _TEMPLATE_B},
        template_usage={"tpl-a": 3, "tpl-b": 0},
        # Route now hands the template a {"visible": [...], "overflow": [...]} split per id.
        template_badges={
            "tpl-a": {"visible": _BADGES_A, "overflow": []},
            "tpl-b": {"visible": [], "overflow": []},
        },
        **overrides,
    )


def _card_slice(html, template_id, next_marker='id="feedback-toast"'):
    """Slice the HTML to just one template's card. Bounded by default on the
    feedback-toast block that always follows the grid, so a card slice never
    silently swallows the rest of the document (mirrors
    test_reports_components.py's documented eventlog-pane bounding concern).
    Pass another template's data-template-id marker when slicing a card that
    isn't the last one rendered.
    """
    marker = f'data-template-id="{template_id}"'
    rest = html.split(marker, 1)[1]
    if next_marker:
        rest = rest.split(next_marker, 1)[0]
    return rest


# --------------------------------------------------------------------------------------
# Render tests
# --------------------------------------------------------------------------------------
def test_gallery_renders_one_card_per_template_with_data_template_id():
    html = _render_dashboard_page("templates.html", **_two_template_context())

    assert 'id="templates-grid"' in html
    assert html.count('data-template-id="tpl-a"') >= 1
    assert html.count('data-template-id="tpl-b"') >= 1
    # Empty-state must not render alongside real cards.
    assert 'id="templates-gallery-empty"' not in html


def test_gallery_svc_chip_always_rendered_including_zero():
    html = _render_dashboard_page("templates.html", **_two_template_context())

    tpl_a_card = _card_slice(html, "tpl-a", 'data-template-id="tpl-b"')
    tpl_b_card = _card_slice(html, "tpl-b")

    # Chip shows real usage for every card, including "0 svc" (kit tplCard always has it).
    assert "templates.gallery.svc_suffix" in tpl_a_card
    assert "3&nbsp;" in tpl_a_card
    assert "templates.gallery.svc_suffix" in tpl_b_card
    assert "0&nbsp;" in tpl_b_card


def test_gallery_badge_order_is_plugin_then_config_then_feature():
    html = _render_dashboard_page("templates.html", **_two_template_context())

    tpl_a_card = _card_slice(html, "tpl-a", 'data-template-id="tpl-b"')
    plugin_idx = tpl_a_card.index("Antibot")
    config_idx = tpl_a_card.index("CRS")
    feature_idx = tpl_a_card.index("Gzip")
    assert plugin_idx < config_idx < feature_idx

    # Each badge's typed tooltip key + interpolated name is present.
    assert 'data-i18n="templates.tag.plugin"' in tpl_a_card
    assert 'data-i18n="templates.tag.config"' in tpl_a_card
    assert 'data-i18n="templates.tag.feature"' in tpl_a_card
    assert '{"name": "Antibot"}' in tpl_a_card


def test_gallery_i18n_keys_all_resolve_in_en_json():
    html = _render_dashboard_page("templates.html", **_two_template_context())
    locale = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))

    # Keys that must be present in the rendered markup *and* resolve in en.json.
    for key in (
        "templates.gallery.select",
        "templates.gallery.delete_selected",
        "templates.gallery.svc_suffix",
        "templates.tag.plugin",
        "templates.tag.config",
        "templates.tag.feature",
        "tooltip.link.view_template",
        "tooltip.link.edit_template",
        "tooltip.link.clone_template",
        "tooltip.button.delete_template",
        "button.create_template",
    ):
        assert f'data-i18n="{key}"' in html, key
        assert _resolves_in_locale(locale, key), key

    # Core-template name keys are only emitted for the 5 built-in ids, so they need not
    # appear in this render (tpl-a/tpl-b are custom) -- but they must resolve in en.json.
    for key in (
        "templates.name.low",
        "templates.name.medium",
        "templates.name.high",
        "templates.name.api",
        "templates.name.ui",
    ):
        assert _resolves_in_locale(locale, key), key


def test_gallery_card_title_is_short_id_and_description_is_full_name():
    # Core id -> humanized title via i18n key; the long name becomes the description.
    core = _base_context(
        templates={"low": {**_TEMPLATE_A, "id": "low", "name": "Basic security level for web apps"}},
        template_usage={"low": 0},
        template_badges={"low": {"visible": [], "overflow": []}},
    )
    html = _render_dashboard_page("templates.html", **core)
    card = _card_slice(html, "low")
    assert 'data-i18n="templates.name.low"' in card
    assert "Low security" in card  # English fallback for the short title
    assert 'class="bw-tpl-desc' in card
    assert "Basic security level for web apps" in card  # long name = description

    # Custom id -> capitalized id as static title, no name data-i18n (i18next echoes
    # missing keys, so the fallback text must not be overwritten).
    html = _render_dashboard_page("templates.html", **_two_template_context())
    tpl_a_card = _card_slice(html, "tpl-a", 'data-template-id="tpl-b"')
    assert "templates.name.tpl-a" not in tpl_a_card
    assert "Tpl-a" in tpl_a_card
    assert "WordPress site" in tpl_a_card  # long name = description


def test_gallery_drops_steps_settings_configs_stat_line():
    html = _render_dashboard_page("templates.html", **_two_template_context())
    # The per-card Steps/Settings/Configs counts moved to the View page.
    assert 'data-i18n="table.header.steps"' not in html
    assert 'data-i18n="table.header.settings"' not in html
    assert 'data-i18n="table.header.configs"' not in html


def test_gallery_empty_state_when_no_templates():
    html = _render_dashboard_page("templates.html", **_base_context())

    assert 'id="templates-gallery-empty"' in html
    assert 'id="templates-grid"' not in html
    assert 'data-i18n="templates.gallery.empty_title"' in html
    assert 'data-i18n="templates.gallery.empty_message"' in html
    # Bulk-select toolbar only ever makes sense with templates to select.
    assert 'id="templates-select-toggle"' not in html


def test_gallery_readonly_hides_bulk_toolbar_but_keeps_delete_button_method_gated():
    html = _render_dashboard_page("templates.html", **_two_template_context(is_readonly=True))

    # Bulk select/delete toolbar is gated on "not is_readonly".
    assert 'id="templates-select-toggle"' not in html
    assert 'id="templates-delete-selected"' not in html

    # Create-template CTA becomes disabled.
    assert 'href="/templates.template_create_page"' in html or "template_create_page" in html

    # Pre-existing quirk preserved: the per-card delete button is disabled by
    # *method* (not by is_readonly) -- readonly guarding happens client-side in
    # templates.js's click handler instead. tpl-a is method="ui" -> stays enabled.
    tpl_a_card = _card_slice(html, "tpl-a", 'data-template-id="tpl-b"')
    assert 'class="btn btn-sm bw-icon-btn bw-icon-btn-danger delete-template"' in tpl_a_card

    # tpl-b is method="manual" -> disabled regardless of readonly.
    tpl_b_card = _card_slice(html, "tpl-b")
    assert "delete-template disabled" in tpl_b_card


def test_gallery_selection_checkboxes_carry_template_id_hidden_by_default():
    html = _render_dashboard_page("templates.html", **_two_template_context())

    tpl_a_card = _card_slice(html, "tpl-a", 'data-template-id="tpl-b"')
    assert 'class="form-check template-select-check d-none flex-shrink-0 m-0"' in tpl_a_card
    assert 'class="form-check-input template-checkbox"' in tpl_a_card
    assert 'data-template-id="tpl-a"' in tpl_a_card


def test_scripts_block_drops_datatables_keeps_selected_list_and_templates_js():
    source = (TEMPLATES / "templates.html").read_text(encoding="utf-8")

    assert "datatables" not in source
    assert "dataTableInit" not in source
    assert "lottie-player" not in source
    assert "js/components/selected-list.js" in source
    assert "js/pages/templates.js" in source


# --------------------------------------------------------------------------------------
# Backend unit tests: _compute_template_usage / _template_tag_badges (pure functions,
# no Flask context needed -- loaded straight off the routes module).
# --------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def templates_route():
    """Load routes/templates.py without booting container-only app.dependencies state."""
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = Mock()
    # templates.py imports CONFIG_TYPES from routes.configs, which itself needs these two
    # (unused by templates.py's own routes) to import cleanly.
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    # templates.py -> app.routes.configs -> app.routes.utils imports qrcode.main.QRCode,
    # unavailable in the pared-down unit-test venv (same stub as test_bans_stats.py).
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._templates_gallery_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "templates.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, dependencies.BW_CONFIG


@pytest.fixture
def route_app(templates_route):
    module, client, bw_config = templates_route
    client.reset_mock(return_value=True, side_effect=True)
    bw_config.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.templates)
    return module, client, bw_config, app


def test_compute_template_usage_counts_matching_services_only(templates_route):
    module, client, _bw_config = templates_route
    # templates_route is module-scoped (the exec_module() load is the expensive part to
    # share) and pytest runs in randomized order, so a prior test's side_effect/return_value
    # on this same shared Mock can otherwise leak in here depending on run order.
    client.reset_mock(return_value=True, side_effect=True)
    client.get_services.return_value = [
        {"template": "tpl-a"},
        {"template": "tpl-a"},
        {"template": ""},
        {"template": None},
        {"template": "tpl-unknown"},
    ]

    usage = module._compute_template_usage({"tpl-a": {}, "tpl-b": {}})

    assert usage == {"tpl-a": 2, "tpl-b": 0}


def test_compute_template_usage_falls_back_to_zero_on_api_error(templates_route):
    module, client, _bw_config = templates_route
    client.reset_mock(return_value=True, side_effect=True)
    client.get_services.side_effect = RuntimeError("api unavailable")

    usage = module._compute_template_usage({"tpl-a": {}})

    assert usage == {"tpl-a": 0}


def test_template_tag_badges_orders_plugin_config_feature_and_skips_general(templates_route):
    module, _client, _bw_config = templates_route
    catalog = [
        {"key": "USE_ANTIBOT", "plugin": {"id": "antibot", "name": "Antibot"}},
        {"key": "X_FRAME_OPTIONS", "plugin": {"id": "headers", "name": "Headers"}},  # headers -> config
        {"key": "USE_GZIP", "plugin": {"id": "gzip", "name": "Gzip"}},  # gzip -> feature
        {"key": "SERVER_NAME", "plugin": {"id": "general", "name": "General"}},  # dropped
    ]
    template_data = {
        "settings": {"USE_ANTIBOT": "captcha", "X_FRAME_OPTIONS": "SAMEORIGIN", "USE_GZIP": "yes", "SERVER_NAME": "example.com"},
        "configs": {"modsec_crs/before.conf": "", "http/extra.conf": ""},
    }

    badges = module._template_tag_badges(template_data, catalog)

    # plugin (green) -> config (navy, sorted CRS/HTTP/Headers) -> feature (amber).
    assert badges == [
        {"text": "Antibot", "type": "plugin", "variant": "primary", "icon": "bx-plug"},
        {"text": "CRS", "type": "config", "variant": "secondary", "icon": "bx-file-blank"},
        {"text": "HTTP", "type": "config", "variant": "secondary", "icon": "bx-file-blank"},
        {"text": "Headers", "type": "config", "variant": "secondary", "icon": "bx-file-blank"},
        {"text": "Gzip", "type": "feature", "variant": "success", "icon": "bx-package"},
    ]


def test_split_badges_prefers_a_mix_then_backfills_and_overflows(templates_route):
    module, _client, _bw_config = templates_route
    P = {"text": "P{}", "type": "plugin", "variant": "primary", "icon": "bx-plug"}
    plugins = [{**P, "text": f"P{i}"} for i in range(4)]
    config = {"text": "C", "type": "config", "variant": "secondary", "icon": "bx-file-blank"}
    feature = {"text": "F", "type": "feature", "variant": "success", "icon": "bx-package"}

    # One-per-type first -> visible reads as a mix; the rest overflow.
    split = module._split_badges(plugins + [config, feature])
    assert [b["text"] for b in split["visible"]] == ["P0", "C", "F"]
    assert [b["text"] for b in split["overflow"]] == ["P1", "P2", "P3"]

    # Too few types -> backfill spare slots by rank so visible isn't sparse.
    split = module._split_badges(plugins[:2])
    assert [b["text"] for b in split["visible"]] == ["P0", "P1"]
    assert split["overflow"] == []


def test_template_tag_badges_empty_when_no_matching_catalog_entries(templates_route):
    module, _client, _bw_config = templates_route

    assert module._template_tag_badges({"settings": {"UNKNOWN_KEY": "x"}, "configs": {}}, catalog=[]) == []
    assert module._template_tag_badges({}, catalog=[]) == []


def test_templates_page_route_wires_usage_and_badges(route_app):
    module, client, bw_config, app = route_app
    client.get_templates.return_value = {"tpl-a": _TEMPLATE_A, "tpl-b": _TEMPLATE_B}
    client.get_services.return_value = [{"template": "tpl-a"}, {"template": "tpl-a"}, {"template": "tpl-b"}]
    client.get_plugins.return_value = []
    bw_config.get_settings.return_value = {}
    bw_config.get_plugins.return_value = {}

    render = Mock(return_value="rendered")
    module_render_target = "render_template"
    with patch.object(module, module_render_target, render):
        with app.test_request_context("/templates"):
            assert module.templates_page.__wrapped__() == "rendered"

    context = render.call_args.kwargs
    assert render.call_args.args == ("templates.html",)
    assert context["templates"] == {"tpl-a": _TEMPLATE_A, "tpl-b": _TEMPLATE_B}
    assert context["template_usage"] == {"tpl-a": 2, "tpl-b": 1}
    # Catalog is empty -> no plugin/feature badges resolve, but config badges are catalog-
    # independent (derived straight from the configs dict), so tpl-a's modsec_crs config
    # still yields a "CRS" badge; tpl-b has no configs at all. The route splits each list
    # into the card's visible/overflow shape.
    assert context["template_badges"] == {
        "tpl-a": {"visible": [{"text": "CRS", "type": "config", "variant": "secondary", "icon": "bx-file-blank"}], "overflow": []},
        "tpl-b": {"visible": [], "overflow": []},
    }


def test_templates_page_route_survives_get_services_failure(route_app):
    module, client, bw_config, app = route_app
    client.get_templates.return_value = {"tpl-a": _TEMPLATE_A}
    client.get_services.side_effect = RuntimeError("boom")
    client.get_plugins.return_value = []
    bw_config.get_settings.return_value = {}
    bw_config.get_plugins.return_value = {}

    render = Mock(return_value="rendered")
    with patch.object(module, "render_template", render):
        with app.test_request_context("/templates"):
            assert module.templates_page.__wrapped__() == "rendered"

    context = render.call_args.kwargs
    assert context["template_usage"] == {"tpl-a": 0}

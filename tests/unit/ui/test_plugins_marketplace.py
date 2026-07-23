"""Plugins marketplace grid (Phase 4): the DataTable -> card grid swap in ``plugins.html``,
the ``POST /plugins/enable`` toggle route in ``routes/plugins.py``, and the marketplace i18n
keys.

Route tests follow the module-loader pattern established by ``test_bans_stats.py``/
``test_web_cache.py``: ``app.dependencies`` is stubbed before loading ``plugins.py`` so real
container-only state never boots. Render tests follow ``test_templates_gallery.py``'s
standalone-Jinja-env pattern.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
LOCALES = TEMPLATES.parent / "static" / "locales"


# ======================================================================================
# Render harness
# ======================================================================================
def _fake_is_plugin_active(plugin, name, config):
    # Test stub mirroring app.utils.is_plugin_active's public contract closely enough for the
    # template: a core plugin is "active" when its USE_<ID> master setting is not "no".
    key = f"USE_{plugin.upper()}"
    entry = config.get(key)
    return bool(entry) and entry.get("value") != "no"


def _render(**context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )

    def _url_for(endpoint, **kw):
        # static endpoints keep their filename so the icon <img> src is assertable; the icon proxy
        # route renders its real path so the @file marker's proxy URL is assertable; everything else
        # collapses to /<endpoint> as before (e.g. url_for('plugins') -> /plugins).
        if endpoint == "static" and "filename" in kw:
            return f"/static/{kw['filename']}"
        if endpoint == "plugins.plugin_icon":
            return f"/plugins/{kw['plugin']}/icon"
        return f"/{endpoint}"

    env.globals.update(
        csrf_token=lambda: "test-token",
        url_for=_url_for,
        is_plugin_active=_fake_is_plugin_active,
    )
    base = dict(
        plugins={},
        config={},
        always_used_plugins=("general", "errors", "headers", "misc", "pro", "sessions", "ssl"),
        plugins_specifics={"COUNTRY": {"BLACKLIST_COUNTRY": "", "WHITELIST_COUNTRY": ""}},
        is_readonly=False,
        user_readonly=False,
        user_admin=True,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )
    base.update(context)
    return env.get_template("plugins.html").render(**base)


def _plugin(type="core", name=None, description="d", version="1.0", method="manual", page=False, enabled=True, icon=None):  # noqa: A002
    return {"type": type, "name": name, "description": description, "version": version, "method": method, "page": page, "enabled": enabled, "icon": icon}


def _card_slice(html, plugin_id):
    marker = f'data-plugin="{plugin_id}"'
    assert marker in html, f"card for {plugin_id} not rendered"
    rest = html.split(marker, 1)[1]
    # bound the slice on the next card / the grid-empty marker so we never swallow siblings
    for stop in ('class="col plugin-card-col"', 'id="plugin-grid-empty"'):
        if stop in rest:
            rest = rest.split(stop, 1)[0]
    return rest


ALL_PLUGINS = {
    "general": _plugin(name="General"),  # core, always-on
    "antibot": _plugin(name="Antibot"),  # core, USE_-bound toggle
    "country": _plugin(name="Country"),  # core, PLUGINS_SPECIFICS -> state badge
    "myext": _plugin(type="external", name="My Ext", method="manual", enabled=True),
    "myui": _plugin(type="ui", name="My UI", method="ui", page=True, enabled=False),
    "mypro": _plugin(type="pro", name="My Pro", method="scheduler", enabled=True),
}
CONFIG = {"USE_ANTIBOT": {"value": "yes"}, "USE_COUNTRY": {"value": "no"}}


# ======================================================================================
# Render tests
# ======================================================================================
class TestGridRender:
    def test_one_card_per_plugin(self):
        html = _render(plugins=ALL_PLUGINS, config=CONFIG)
        assert html.count('class="col plugin-card-col"') == len(ALL_PLUGINS)

    def test_empty_seed_dict_skipped(self):
        # config.get_plugins seeds {"general": {}} -- the `if plugin_data` filter drops empties.
        html = _render(plugins={"general": {}, "myext": _plugin(type="external", name="Ext")}, config={})
        assert html.count('class="col plugin-card-col"') == 1
        assert 'data-plugin="myext"' in html

    def test_core_always_on_locked_chip_no_switch(self):
        html = _render(plugins={"general": ALL_PLUGINS["general"]}, config=CONFIG)
        card = _card_slice(html, "general")
        assert "plugins.marketplace.always_on" in card
        assert "plugin-switch" not in card  # no toggle for always-on core

    def test_core_toggleable_has_switch_bound_to_use_setting(self):
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"]}, config=CONFIG)
        card = _card_slice(html, "antibot")
        assert "plugin-switch" in card
        assert 'name="setting" value="USE_ANTIBOT"' in card
        assert "checked" in card  # USE_ANTIBOT=yes -> on

    def test_core_specific_shows_state_badge_no_switch(self):
        html = _render(plugins={"country": ALL_PLUGINS["country"]}, config=CONFIG)
        card = _card_slice(html, "country")
        assert "plugin-switch" not in card  # COUNTRY is multi-key/ambiguous -> no live toggle
        # USE_COUNTRY=no -> inactive state badge
        assert "plugins.marketplace.inactive" in card

    def test_external_has_switch_without_setting(self):
        html = _render(plugins={"myext": ALL_PLUGINS["myext"]}, config={})
        card = _card_slice(html, "myext")
        assert "plugin-switch" in card
        assert 'name="setting"' not in card  # non-core: DB enabled flag, no USE_ setting
        assert 'data-enabled="true"' in html

    def test_disabled_external_switch_unchecked(self):
        html = _render(plugins={"myui": ALL_PLUGINS["myui"]}, config={})
        assert 'data-enabled="false"' in html
        card = _card_slice(html, "myui")
        assert "plugin-switch" in card
        assert "checked" not in card

    def test_pro_tier_chip(self):
        html = _render(plugins={"mypro": ALL_PLUGINS["mypro"]}, config={})
        card = _card_slice(html, "mypro")
        assert "plugin.type.pro" in card
        assert "bx-crown" in card

    def test_uninstall_only_for_ui_method(self):
        html = _render(plugins=ALL_PLUGINS, config=CONFIG)
        # only the method="ui" plugin (myui) gets a delete/uninstall button
        assert _card_slice(html, "myui").count("delete-plugin") == 1
        assert "delete-plugin" not in _card_slice(html, "myext")  # external method=manual: not UI-deletable
        assert "delete-plugin" not in _card_slice(html, "mypro")

    def test_readonly_disables_switch(self):
        html = _render(plugins={"myext": ALL_PLUGINS["myext"]}, config={}, is_readonly=True, user_admin=True)
        card = _card_slice(html, "myext")
        assert "disabled" in card

    def test_filter_tabs_and_counts_present(self):
        html = _render(plugins=ALL_PLUGINS, config=CONFIG)
        for f in ("all", "enabled", "disabled", "core", "community", "pro"):
            assert f'data-filter="{f}"' in html
            assert f'data-filter-count="{f}"' in html


class TestCardIcons:
    # The route passes `custom_icons` = ids that ship a curated brand SVG. Card renders the
    # <img> for those; everything else keeps the boxicon so no card points at a missing file.
    def test_known_id_renders_custom_svg_mark(self):
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"]}, config=CONFIG, custom_icons={"antibot"})
        card = _card_slice(html, "antibot")
        assert "img/plugins/plugin-antibot.svg" in card
        assert "plugin-mark-light" in card
        assert "bx-sm text-primary" not in card  # header boxicon replaced, not rendered alongside

    def test_known_id_ships_dark_variant(self):
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"]}, config=CONFIG, custom_icons={"antibot"})
        card = _card_slice(html, "antibot")
        assert "img/plugins/plugin-antibot-white.svg" in card
        assert "plugin-mark-dark" in card

    def test_unknown_id_falls_back_to_boxicon(self):
        # external plugin not in the curated set -> keeps its boxicon, no custom mark
        html = _render(plugins={"myext": ALL_PLUGINS["myext"]}, config={}, custom_icons={"antibot"})
        card = _card_slice(html, "myext")
        assert "img/plugins/plugin-" not in card
        assert "bx-plug bx-sm text-primary" in card

    def test_missing_context_defaults_to_boxicon(self):
        # route omits custom_icons -> template default([]) keeps every card on its boxicon
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"]}, config=CONFIG)
        card = _card_slice(html, "antibot")
        assert "img/plugins/plugin-" not in card
        assert "bx-shield bx-sm text-primary" in card


class TestFieldFirstIcons:
    # Field-first resolution off plugin_data.icon (curated custom_icons still wins for dark-mode).
    def test_file_marker_uses_proxy_url(self):
        p = _plugin(type="external", name="Ext", method="manual", icon="@file/icon.svg")
        html = _render(plugins={"myext": p}, config={})
        card = _card_slice(html, "myext")
        assert "/plugins/myext/icon" in card  # UI proxy route, not a static asset
        assert "img/plugins/" not in card
        assert "bx-plug bx-sm" not in card  # boxicon replaced by the proxied mark

    def test_bare_svg_present_uses_static_asset(self):
        p = _plugin(type="external", name="Ext", method="manual", icon="custom-foo.svg")
        html = _render(plugins={"myext": p}, config={}, static_icons={"custom-foo.svg"})
        card = _card_slice(html, "myext")
        assert "img/plugins/custom-foo.svg" in card
        assert "/plugins/myext/icon" not in card

    def test_bare_svg_absent_falls_back_to_boxicon(self):
        # a *.svg field naming a static asset that does not ship must not emit a broken <img>
        p = _plugin(type="external", name="Ext", method="manual", icon="ghost.svg")
        html = _render(plugins={"myext": p}, config={}, static_icons=set())
        card = _card_slice(html, "myext")
        assert "img/plugins/ghost.svg" not in card
        assert "bx-plug bx-sm text-primary" in card

    def test_boxicon_class_string_renders_icon_font(self):
        p = _plugin(type="external", name="Ext", method="manual", icon="bx-rocket")
        html = _render(plugins={"myext": p}, config={})
        card = _card_slice(html, "myext")
        assert "bx-rocket bx-sm text-primary" in card
        assert "img/plugins/" not in card

    def test_null_icon_uses_type_boxicon(self):
        p = _plugin(type="external", name="Ext", method="manual", icon=None)
        html = _render(plugins={"myext": p}, config={})
        card = _card_slice(html, "myext")
        assert "bx-plug bx-sm text-primary" in card
        assert "img/plugins/" not in card

    def test_custom_icons_still_wins_over_file_marker(self):
        # a curated-set core plugin keeps its navy+white pair even when its DB icon is an @file marker
        p = _plugin(name="Antibot", icon="@file/icon.svg")
        html = _render(plugins={"antibot": p}, config=CONFIG, custom_icons={"antibot"})
        card = _card_slice(html, "antibot")
        assert "img/plugins/plugin-antibot.svg" in card
        assert "img/plugins/plugin-antibot-white.svg" in card
        assert "/plugins/antibot/icon" not in card


class TestI18n:
    def test_marketplace_keys_exist_in_en(self):
        en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
        market = en["plugins"]["marketplace"]
        for key in ("tab_all", "tab_enabled", "tab_disabled", "tab_community", "always_on", "active", "inactive", "enabled", "disabled", "search", "no_match"):
            assert key in market, f"missing plugins.marketplace.{key}"

    def test_reused_navigation_keys_still_present(self):
        en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
        nav = en["navigation"]
        for key in ("plugin_activated", "plugin_deactivated"):
            assert key in nav


# ======================================================================================
# Route harness — POST /plugins/enable
# ======================================================================================
class _DATA(dict):
    def load_from_file(self):
        pass


@pytest.fixture(scope="module")
def plugins_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.CORE_PLUGINS_PATH = Path("/tmp/core")
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = SimpleNamespace(submit=lambda fn, *a, **k: fn(*a, **k))
    dependencies.DATA = _DATA(TO_FLASH=[])
    dependencies.EXTERNAL_PLUGINS_PATH = Path("/tmp/ext")
    dependencies.PRO_PLUGINS_PATH = Path("/tmp/pro")
    # app.routes.utils (imported transitively) pulls qrcode/openpyxl, absent from the unit venv.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    openpyxl = ModuleType("openpyxl")
    openpyxl.Workbook = Mock()
    openpyxl_styles = ModuleType("openpyxl.styles")
    openpyxl_styles.Font = Mock()
    openpyxl_styles.PatternFill = Mock()
    module_name = "app.routes._plugins_marketplace_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "plugins.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        "openpyxl": openpyxl,
        "openpyxl.styles": openpyxl_styles,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def route_app(plugins_route):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(plugins_route.plugins)
    app.add_url_rule("/loading", "loading", lambda: "")
    return plugins_route, app


def _call_enable(module, app, monkeypatch, form, client):
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True))
    monkeypatch.setattr(module, "wait_applying", lambda: None)
    client.readonly = False
    module.DATA.clear()
    module.DATA["TO_FLASH"] = []
    with app.test_request_context("/plugins/enable", method="POST", data=form):
        return module.enable_plugin.__wrapped__()


def test_enable_external_calls_set_plugin_enabled(route_app, monkeypatch):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "myext", "enabled": "no"}, client)
    client.set_plugin_enabled.assert_called_once_with("myext", False)
    client.checked_changes.assert_called_once()
    client.update_global_settings.assert_not_called()


def test_enable_external_true(route_app, monkeypatch):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "myext", "enabled": "yes"}, client)
    client.set_plugin_enabled.assert_called_once_with("myext", True)


def test_core_setting_toggle_calls_update_global_settings(route_app, monkeypatch):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "antibot", "enabled": "no", "setting": "USE_ANTIBOT"}, client)
    client.update_global_settings.assert_called_once_with({"USE_ANTIBOT": "no"})
    client.set_plugin_enabled.assert_not_called()


def test_invalid_setting_rejected(route_app, monkeypatch):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    monkeypatch.setattr(module, "handle_error", lambda *a, **k: "REJECTED")
    result = _call_enable(module, app, monkeypatch, {"plugin": "antibot", "enabled": "no", "setting": "DROP TABLE"}, client)
    assert result == "REJECTED"
    client.update_global_settings.assert_not_called()
    client.set_plugin_enabled.assert_not_called()


def test_readonly_blocks(route_app, monkeypatch):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True))
    client.readonly = True
    with app.test_request_context("/plugins/enable", method="POST", data={"plugin": "myext", "enabled": "no"}):
        resp = module.enable_plugin.__wrapped__()
    assert resp.status_code == 403


def test_non_admin_blocks(route_app, monkeypatch):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    client.readonly = False
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=False))
    with app.test_request_context("/plugins/enable", method="POST", data={"plugin": "myext", "enabled": "no"}):
        resp = module.enable_plugin.__wrapped__()
    assert resp.status_code == 403


# ======================================================================================
# Route harness — GET /plugins/<plugin>/icon (UI proxy)
# ======================================================================================
def test_icon_proxy_passes_bytes_and_security_headers(route_app):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock(return_value=True, side_effect=True)
    client.get_plugin_icon.return_value = (b"<svg>ok</svg>", "image/svg+xml")
    with app.test_request_context("/plugins/myext/icon"):
        resp = module.plugin_icon.__wrapped__("myext")
    assert resp.status_code == 200
    assert resp.get_data() == b"<svg>ok</svg>"
    assert resp.headers["Content-Type"] == "image/svg+xml"
    assert resp.headers["Content-Disposition"] == 'inline; filename="icon.svg"'
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert resp.headers["Cache-Control"] == "private, max-age=3600"
    client.get_plugin_icon.assert_called_once_with("myext")


def test_icon_proxy_png_content_type(route_app):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock(return_value=True, side_effect=True)
    client.get_plugin_icon.return_value = (b"\x89PNG\r\n", "image/png")
    with app.test_request_context("/plugins/myext/icon"):
        resp = module.plugin_icon.__wrapped__("myext")
    assert resp.headers["Content-Type"] == "image/png"
    assert resp.headers["Content-Disposition"] == 'inline; filename="icon.png"'


def test_icon_proxy_rejects_invalid_id_before_api(route_app):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock(return_value=True, side_effect=True)
    with app.test_request_context("/plugins/a/icon"):
        resp = module.plugin_icon.__wrapped__("a")  # too short for PLUGIN_NAME_RX
    assert resp.status_code == 404
    client.get_plugin_icon.assert_not_called()


def test_icon_proxy_traversal_id_rejected(route_app):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock(return_value=True, side_effect=True)
    with app.test_request_context("/plugins/x/icon"):
        resp = module.plugin_icon.__wrapped__("../../etc/passwd")  # slashes fail the id regex
    assert resp.status_code == 404
    client.get_plugin_icon.assert_not_called()


def test_icon_proxy_api_not_found_maps_to_404(route_app):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock(return_value=True, side_effect=True)
    client.get_plugin_icon.side_effect = module.ApiClientError("not found", status_code=404)
    with app.test_request_context("/plugins/myext/icon"):
        resp = module.plugin_icon.__wrapped__("myext")
    assert resp.status_code == 404


def test_icon_proxy_api_unavailable_maps_to_502(route_app):
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock(return_value=True, side_effect=True)
    client.get_plugin_icon.side_effect = module.ApiUnavailableError("down")
    with app.test_request_context("/plugins/myext/icon"):
        resp = module.plugin_icon.__wrapped__("myext")
    assert resp.status_code == 502

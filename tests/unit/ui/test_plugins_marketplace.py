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

import plugin_extensions  # type: ignore  # noqa: E402 -- on sys.path via the root conftest

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
LOCALES = TEMPLATES.parent / "static" / "locales"
# Real src/common/core manifests -- passed explicitly to iter_plugin_activations below so the
# render fixture's plugin_activations can never hand-drift from what actually ships (S0 review,
# Important #2: the old hand-listed fixture omitted antibot, which let a stale test assert a
# card shape -- a switch -- the real manifest can no longer produce).
CORE_PLUGINS_PATH = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
_REAL_PLUGIN_ACTIVATIONS = plugin_extensions.iter_plugin_activations(paths=[(CORE_PLUGINS_PATH, "core")])
# The real setting definitions BW_CONFIG.get_plugins_settings() serves, flattened the same way
# models/config.py:81-85 flattens them. The activation writer reads `type`/`select`/`multiple`
# from here to decide what a switch may write, so seeding the Mock with the SHIPPED schemas is
# what keeps "antibot is switchable, country is not" a statement about the manifests rather than
# about a hand-written fixture.
_REAL_CORE_PLUGIN_ENV = {}
_REAL_CORE_SETTINGS = {}
for _manifest in sorted(CORE_PLUGINS_PATH.glob("*/plugin.json")):
    _parsed = json.loads(_manifest.read_text(encoding="utf-8"))
    _REAL_CORE_PLUGIN_ENV[_parsed.get("id", _manifest.parent.name)] = {"settings": _parsed.get("settings", {})}
    _REAL_CORE_SETTINGS.update(_parsed.get("settings", {}))
# What `g._env` holds on a real request: main.py:1263 parks BW_CONFIG.get_plugins() there and
# main.py:1297 the global config (methods=True, so `{"value": ...}` entries, every multisite
# setting seeded from its default). The route reads BOTH from `_env`, never from the API, so the
# fixtures below have to supply it or nothing derives.
_REAL_CORE_CONFIG = {key: {"value": data.get("default", "")} for key, data in _REAL_CORE_SETTINGS.items()}


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
        # Manifest-driven activation map (Task 3/4): "always" for the switch-less core plugins,
        # a {setting: inactive_value} map for the ambiguous multi-key ones. "general" is
        # deliberately absent -- it has no plugin.json, so the template special-cases it.
        # Seeded from the REAL src/common/core manifests (same function app.utils.
        # get_activation_map calls) rather than hand-listed, so this fixture cannot silently
        # drift from what actually ships -- see the CORE_PLUGINS_PATH comment above.
        plugin_activations=dict(_REAL_PLUGIN_ACTIVATIONS),
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
    "antibot": _plugin(name="Antibot"),  # core, manifest activation map ({"USE_ANTIBOT": "no"}) -> switch (T2)
    "country": _plugin(name="Country"),  # core, multiselect activation map -> state badge, no switch
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
        # gzip's manifest declares no `extensions.activation` -- undeclared, so it falls to the
        # tier-3 conventional USE_<ID> switch. antibot no longer exercises this path (see
        # test_core_specific_declared_activation_shows_badge_no_switch below): its manifest now
        # declares {"USE_ANTIBOT": "no"}, which makes it core_specific instead of core_toggleable.
        gzip_plugin = _plugin(name="Gzip")
        html = _render(plugins={"gzip": gzip_plugin}, config={"USE_GZIP": {"value": "yes"}})
        card = _card_slice(html, "gzip")
        assert "plugin-switch" in card
        assert 'name="setting" value="USE_GZIP"' in card
        assert "checked" in card  # USE_GZIP=yes -> on

    def test_map_declared_plugin_gets_a_switch_bound_to_its_declared_key(self):
        # S3.4 T2: the read-only badge for map-declared core plugins is gone now that the shared
        # writer can flip them. antibot declares {"USE_ANTIBOT": "no"} -- a 9-value select, so the
        # switch must post the DECLARED key and let the writer pick a legal value, never "yes".
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"]}, config=CONFIG, activation_toggles={"antibot": "USE_ANTIBOT"})
        card = _card_slice(html, "antibot")
        assert "plugin-switch" in card
        assert 'name="setting" value="USE_ANTIBOT"' in card
        assert "plugins.marketplace.active" not in card  # the badge it replaces

    def test_map_declared_plugin_the_writer_refuses_keeps_the_state_badge(self):
        # country's BLACKLIST_COUNTRY/WHITELIST_COUNTRY are multiselect: no derivable active
        # value, and locked with the PO as count + chevron. The route leaves it out of
        # activation_toggles, so the card must fall back to the read-only badge.
        html = _render(plugins={"country": ALL_PLUGINS["country"]}, config=CONFIG, activation_toggles={"antibot": "USE_ANTIBOT"})
        card = _card_slice(html, "country")
        assert "plugin-switch" not in card
        assert 'name="setting"' not in card
        assert "plugins.marketplace.inactive" in card  # USE_COUNTRY=no -> inactive state badge

    def test_absent_activation_toggles_degrades_every_map_plugin_to_the_badge(self):
        # plugins_page swallows a get_plugins_settings() failure and passes nothing; a card must
        # then render the read-only badge rather than a switch it cannot honour.
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"], "country": ALL_PLUGINS["country"]}, config=CONFIG)
        for plugin_id in ("antibot", "country"):
            card = _card_slice(html, plugin_id)
            assert "plugin-switch" not in card, plugin_id
            assert 'name="setting"' not in card, plugin_id

    def test_map_declared_switch_never_borrows_the_use_id_convention(self):
        # limit's tier-3 name would be USE_LIMIT, which is not a setting at all. The switch must
        # post the key activation_toggles names, not the convention-derived one.
        html = _render(plugins={"limit": _plugin(name="Limit")}, config=CONFIG, activation_toggles={"limit": "USE_LIMIT_REQ"})
        card = _card_slice(html, "limit")
        assert 'name="setting" value="USE_LIMIT_REQ"' in card
        assert 'value="USE_LIMIT"' not in card

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


@pytest.fixture(autouse=True)
def _no_stale_settings_mock(route_app):
    """Nothing production-side reads ``BW_CONFIG.get_plugins_settings()`` any more -- schemas come
    from ``g._env``. Reset the module-scoped Mock between tests anyway (pytest-randomly shuffles
    order) so a `side_effect` armed by one test cannot leak into the next, and so the two
    ``assert_not_called`` guards below measure this test's calls, not the module's."""
    module, _ = route_app
    module.BW_CONFIG.get_plugins_settings.reset_mock(return_value=True, side_effect=True)


@pytest.fixture
def plugins_page_context(route_app, monkeypatch, tmp_path):
    """Calls the real `plugins_page()` route (bypassing @login_required, same pattern as
    `_call_enable` below) and captures the kwargs it hands to `render_template` -- i.e. the
    plugins.html template context. `get_activation_map`/`is_plugin_active` are the real
    `app.utils` functions (not stubbed), and `tests/unit/ui/conftest.py`'s autouse fixture
    points `iter_plugin_activations` at this repo's real `src/common/core` manifests, so
    `plugin_activations` reflects the actual shipped plugin.json declarations. TMP_DIR is
    redirected to a pytest tmp_path so the route's rmtree/mkdir housekeeping never touches
    the real /var/tmp/bunkerweb.
    """
    module, app = route_app

    def _build(env=None):
        monkeypatch.setattr(module, "TMP_DIR", tmp_path)
        captured = {}

        def _fake_render_template(template_name, **context):
            captured.update(context)
            return ""

        monkeypatch.setattr(module, "render_template", _fake_render_template)
        with app.test_request_context("/plugins"):
            # `main.py`'s before_request parks this request's plugins + config on g._env; the
            # route reads its setting definitions from there rather than re-querying the API.
            module.g._env = {"plugins": _REAL_CORE_PLUGIN_ENV, "config": _REAL_CORE_CONFIG} if env is None else env
            module.plugins_page.__wrapped__()
        return captured

    return _build


def test_marketplace_toggle_not_offered_for_manifest_declared_plugins(plugins_page_context):
    """A plugin whose activation is a declared map is not a simple on/off switch."""
    context = plugins_page_context()
    assert "plugins_specifics" not in context
    assert "always_used_plugins" not in context
    assert "plugin_activations" in context


def test_activation_map_reaches_the_template(plugins_page_context):
    activations = plugins_page_context()["plugin_activations"]
    assert activations.get("errors") == "always"
    # USE_LIMIT_REQ_GLOBAL is declared too (S3.4 T2): limit.lua:99/:107/:150 runs the request
    # limiter on it alone, so a map without it makes a conformant OFF leave the global rate
    # limiter enforcing, and a service using only it read inactive.
    assert activations.get("limit") == {"USE_LIMIT_REQ": "no", "USE_LIMIT_REQ_GLOBAL": "no", "USE_LIMIT_CONN": "no"}


def test_marketplace_offers_a_switch_exactly_for_the_activations_the_writer_can_flip(plugins_page_context, route_app):
    """The read-only badge for map-declared core plugins is dropped, but only where the shared
    writer can actually derive both directions -- otherwise the card would offer a switch that
    flashes an error. Asserted against the REAL manifests, so a new/changed activation
    declaration shows up here rather than as a dead switch in production."""
    module, _ = route_app
    toggles = plugins_page_context()["activation_toggles"]
    # switchable: single-key check/select activations, and limit's all-`check` multi-key one
    assert toggles["antibot"] == "USE_ANTIBOT"
    assert toggles["customcert"] == "USE_CUSTOM_SSL"
    assert toggles["letsencrypt"] == "AUTO_LETS_ENCRYPT"  # matches no USE_<ID> convention
    assert toggles["selfsigned"] == "GENERATE_SELF_SIGNED_SSL"  # ditto
    assert toggles["limit"] == "USE_LIMIT_REQ"
    # refused: list-shaped (country multiselect, redirect multiple) and free text (inject, php)
    for refused in ("country", "redirect", "inject", "php"):
        assert refused not in toggles, refused
    # "always" declarations are never flippable
    for always in ("errors", "headers", "misc", "pro", "sessions", "ssl"):
        assert always not in toggles, always


def test_an_env_without_plugin_schemas_degrades_to_no_toggles(plugins_page_context, route_app):
    """`main.py:1262-1265` swallows a get_plugins() failure and parks `{}`. With no schemas the
    route can derive nothing, and every map-declared card must fall back to the read-only badge
    rather than offering a switch it cannot honour."""
    module, _ = route_app
    module.BW_CONFIG.get_plugins_settings.side_effect = RuntimeError("must not be called")
    try:
        assert plugins_page_context(env={"plugins": {}, "config": {}})["activation_toggles"] == {}
    finally:
        module.BW_CONFIG.get_plugins_settings.side_effect = None


def test_the_marketplace_page_adds_no_api_round_trip(plugins_page_context, route_app):
    """Definitions come off g._env, which this request already paid for. A fetch here would be a
    second get_plugins() per page load."""
    module, _ = route_app
    module.BW_CONFIG.get_plugins_settings.reset_mock()
    plugins_page_context()
    module.BW_CONFIG.get_plugins_settings.assert_not_called()


def _call_enable(module, app, monkeypatch, form, client, env=None):
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True))
    monkeypatch.setattr(module, "wait_applying", lambda: None)
    client.readonly = False
    module.DATA.clear()
    module.DATA["TO_FLASH"] = []
    with app.test_request_context("/plugins/enable", method="POST", data=form):
        # Same g._env main.py's before_request builds: the route snapshots the definitions and
        # the resolved config from it IN THE REQUEST THREAD, since `g` is gone in the executor.
        module.g._env = {"plugins": _REAL_CORE_PLUGIN_ENV, "config": _REAL_CORE_CONFIG} if env is None else env
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


def test_rejected_toggle_flashes_error_and_clears_reloading(route_app, monkeypatch, caplog):
    """S0 review, Important #1: resolve_activation_write raises ValueError for an "always"
    plugin (crafted-POST scenario: plugin=headers&enabled=yes&setting=USE_HEADERS -- passes
    USE_SETTING_RX, passes CSRF/admin, then rejected downstream). toggle_plugin runs on a bare
    ThreadPoolExecutor whose futures are never retrieved, so before the fix this exception
    vanished with no log and no flash, and DATA["RELOADING"] was never reset to False --
    stranding the user on /loading until the 60s watchdog. Both must now happen."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    with caplog.at_level("ERROR", logger="UI"):
        _call_enable(module, app, monkeypatch, {"plugin": "headers", "enabled": "yes", "setting": "USE_HEADERS"}, client)
    client.update_global_settings.assert_not_called()
    assert module.DATA["RELOADING"] is False
    assert module.DATA["TO_FLASH"], "expected an error flash, got none"
    flashed = module.DATA["TO_FLASH"][-1]
    assert flashed["type"] == "error"
    assert "headers" in flashed["content"]
    assert any("headers" in record.message for record in caplog.records)


# ======================================================================================
# resolve_activation_write / _active_value_for — schema-legal marketplace toggle writes
#
# USE_ANTIBOT is a 9-value select, not a boolean: the old toggle_plugin branch wrote a
# hardcoded "yes" through it, an illegal value later rejected at generation.
# resolve_activation_write derives what to write from the plugin's declared activation
# (get_activation_map, Task 3) instead of assuming a boolean. get_activation_map is the
# REAL app.utils function here (not stubbed by the plugins_route fixture below), and
# tests/unit/ui/conftest.py's autouse fixture points its manifest scan at this repo's
# real src/common/core plugin.json files, so the plugin ids below reflect their actual
# shipped declarations:
#   antibot  -> {"USE_ANTIBOT": "no"}                       (single-key, select)
#   limit    -> {USE_LIMIT_REQ, USE_LIMIT_REQ_GLOBAL, USE_LIMIT_CONN} all "no"  (multi-key)
#   redirect -> {"REDIRECT_TO": ""}                         (single-key, `multiple` -> refused)
#   country  -> {BLACKLIST_COUNTRY, WHITELIST_COUNTRY} ""   (multi-key, multiselect -> refused)
#   gzip     -> not declared -> legacy USE_GZIP convention
# `settings` is a REQUIRED kwarg -- the writer never fetches schemas itself. `_write` supplies the
# real shipped ones so each test states only what it is actually about; the constants below survive
# as ORACLES (what a legal answer looks like), not as inputs.
# ======================================================================================


def _write(module, plugin_id, setting, *, settings=None, **kwargs):
    return module.resolve_activation_write(plugin_id, setting, settings=_REAL_CORE_SETTINGS if settings is None else settings, **kwargs)


def test_settings_is_a_required_kwarg(route_app):
    """MED-6: the writer must never source schemas itself. A default here had zero production
    callers once both surfaces read from `g._env`, and would let a caller silently re-add a
    per-call API round-trip that no test would catch."""
    module, _ = route_app
    with pytest.raises(TypeError):
        module.resolve_activation_write("gzip", "USE_GZIP", enabled=True)


def test_disable_writes_every_declared_key(route_app):
    module, _ = route_app
    assert _write(module, "limit", None, enabled=False) == {"USE_LIMIT_REQ": "no", "USE_LIMIT_REQ_GLOBAL": "no", "USE_LIMIT_CONN": "no"}


def test_enable_a_multi_key_activation_writes_every_declared_key(route_app):
    """The T1 shelf contract: a row owns every key `shelf_plugin_scope` returns, and an in-scope
    key the form does not post is DELETED (db_methods/config_save.py:592). Posting USE_LIMIT_REQ
    alone would delete USE_LIMIT_CONN's row, fall it back to its "yes" default, and silently turn
    the connection limiter ON from an operator enabling the request limiter."""
    module, _ = route_app
    declared = module.get_activation_map()["limit"]
    written = _write(
        module,
        "limit",
        "USE_LIMIT_REQ",
        enabled=True,
        current_values={"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no", "USE_LIMIT_REQ_GLOBAL": "no"},
    )
    assert set(written) == set(declared), "every declared key must be written, not just the toggled one"
    assert written["USE_LIMIT_REQ"] == "yes"


def test_enable_a_multi_key_activation_keeps_siblings_at_their_current_value(route_app):
    """Siblings are re-posted at what they CURRENTLY resolve to, never at their schema default:
    USE_LIMIT_CONN defaults to "yes", so writing the default would switch the connection limiter
    back on behind an operator who had turned it off."""
    module, _ = route_app
    written = _write(
        module,
        "limit",
        "USE_LIMIT_REQ",
        enabled=True,
        current_values={"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no", "USE_LIMIT_REQ_GLOBAL": "yes"},
    )
    assert written["USE_LIMIT_CONN"] == "no", "sibling clobbered with its default instead of its current value"
    assert written["USE_LIMIT_REQ_GLOBAL"] == "yes"


def test_enable_refuses_to_guess_a_sibling_whose_current_value_is_unknown(route_app):
    """The sibling rule is fail-CLOSED. Falling back to the schema default is the exact clobber it
    exists to prevent: USE_LIMIT_CONN defaults to "yes", and Database.py:463 lets the resulting
    `api` write overwrite an operator's `ui` "no"."""
    module, _ = route_app
    with pytest.raises(ValueError):
        _write(module, "limit", "USE_LIMIT_REQ", enabled=True)
    with pytest.raises(ValueError):
        _write(module, "limit", "USE_LIMIT_REQ", enabled=True, current_values={"USE_LIMIT_CONN": "no"})  # REQ_GLOBAL missing


def test_a_multiple_activation_key_is_refused_in_both_directions(route_app):
    """redirect's REDIRECT_TO is `"multiple": "redirect"`: the live values live under
    REDIRECT_TO_<n>, which redirect.conf iterates, so writing the bare base name claims "off"
    while every suffixed redirect keeps serving. Refuse rather than lie -- and refuse ON too,
    since a free-text key has no derivable active value anyway."""
    module, _ = route_app
    assert module.get_activation_map()["redirect"] == {"REDIRECT_TO": ""}, "fixture premise"
    with pytest.raises(ValueError):
        _write(module, "redirect", "REDIRECT_TO", enabled=False)
    with pytest.raises(ValueError):
        _write(module, "redirect", "REDIRECT_TO", enabled=True)


def test_a_multiselect_activation_key_is_refused_in_both_directions(route_app):
    """country's BLACKLIST_COUNTRY/WHITELIST_COUNTRY are `type: multiselect` -- locked with the
    PO as a count + chevron, never a switch, and excluded from the shelf's scope, so a write here
    would post keys the page does not own."""
    module, _ = route_app
    for enabled in (True, False):
        with pytest.raises(ValueError):
            _write(module, "country", "BLACKLIST_COUNTRY", enabled=enabled)


def test_a_declared_activation_key_outside_the_use_convention_is_accepted(route_app):
    """AUTO_LETS_ENCRYPT / GENERATE_SELF_SIGNED_SSL match no USE_<...> pattern; the endpoint's
    pre-thread guard has to consult the manifest or those two plugins can never be toggled."""
    module, _ = route_app
    assert module.is_activation_setting("letsencrypt", "AUTO_LETS_ENCRYPT") is True
    assert module.is_activation_setting("selfsigned", "GENERATE_SELF_SIGNED_SSL") is True
    # ...and the manifest is a TIGHTER gate than the regex, not a looser one
    assert module.is_activation_setting("letsencrypt", "USE_SOMETHING_ELSE") is False
    assert module.is_activation_setting("gzip", "USE_GZIP") is True  # undeclared: regex convention
    assert module.is_activation_setting("gzip", "DROP TABLE") is False


def test_enable_writes_a_schema_legal_value_for_a_select_activation(route_app):
    module, _ = route_app
    assert _write(module, "antibot", "USE_ANTIBOT", enabled=False) == {"USE_ANTIBOT": "no"}
    written = _write(module, "antibot", "USE_ANTIBOT", enabled=True)
    assert written["USE_ANTIBOT"] != "yes"  # "yes" is not a legal USE_ANTIBOT value
    assert written["USE_ANTIBOT"] != "no"  # must actually flip it on
    assert written["USE_ANTIBOT"] in _REAL_CORE_SETTINGS["USE_ANTIBOT"]["select"]


def test_enable_writes_a_schema_legal_value_for_a_check_activation(route_app):
    module, _ = route_app
    assert _write(module, "letsencrypt", "AUTO_LETS_ENCRYPT", enabled=True) == {"AUTO_LETS_ENCRYPT": "yes"}
    assert _write(module, "letsencrypt", "AUTO_LETS_ENCRYPT", enabled=False) == {"AUTO_LETS_ENCRYPT": "no"}


def test_enable_rejects_a_setting_the_plugin_does_not_declare(route_app):
    """The endpoint must not flip an arbitrary USE_* just because it matches a name pattern.

    `current_values` covers every DECLARED key, so the sibling rule cannot fire and the only rule
    left that can raise is the one under test. Without that, this passed with the check deleted --
    the undeclared name became the "toggled" key, antibot's real key became a value-less sibling,
    and the sibling rule raised instead. Caught by mutating the check away."""
    module, _ = route_app
    with pytest.raises(ValueError):
        _write(module, "antibot", "USE_SOMETHING_ELSE", enabled=True, current_values={"USE_ANTIBOT": "no"})


def test_enable_a_multi_key_activation_defaults_to_the_first_declared_key(route_app):
    """A shelf row carries one switch and names no key; dict order is manifest order, so "first
    declared" is well-defined and stable."""
    module, _ = route_app
    written = _write(module, "limit", None, enabled=True, current_values={"USE_LIMIT_CONN": "no", "USE_LIMIT_REQ_GLOBAL": "no"})
    assert written["USE_LIMIT_REQ"] == "yes"
    assert written["USE_LIMIT_CONN"] == "no"


def test_enable_rejects_free_text_activation(route_app):
    """A free-text activation has no derivable active value -- it must never be offered as a
    simple switch. inject/php are the only live cases: REDIRECT_TO is free text too, but it is
    `multiple` and so refused one step earlier, which
    test_a_multiple_activation_key_is_refused_in_both_directions owns."""
    module, _ = route_app
    for plugin_id, key in (("inject", "INJECT_BODY"), ("php", "REMOTE_PHP")):
        # Supply EVERY declared key's current value. With `current_values={}` the sibling rule
        # raises first, so this test passed even with the free-text guard removed -- it was
        # asserting the wrong rule. Caught by mutating `_active_value_for` to stop raising.
        with pytest.raises(ValueError):
            _write(module, plugin_id, key, enabled=True, current_values=dict(module.get_activation_map()[plugin_id]))


def test_always_active_plugin_cannot_be_toggled(route_app):
    """errors/headers/misc/pro/sessions/ssl declare "always" -- no switch, ever, even via a
    crafted setting name that happens to match the USE_<ID> convention."""
    module, _ = route_app
    with pytest.raises(ValueError):
        _write(module, "headers", "USE_HEADERS", enabled=True)
    with pytest.raises(ValueError):
        _write(module, "headers", None, enabled=False)


def test_undeclared_plugin_keeps_conventional_use_boolean(route_app):
    module, _ = route_app
    assert _write(module, "gzip", "USE_GZIP", enabled=True) == {"USE_GZIP": "yes"}
    assert _write(module, "gzip", "USE_GZIP", enabled=False) == {"USE_GZIP": "no"}


def test_undeclared_plugin_still_rejects_non_conventional_setting(route_app):
    module, _ = route_app
    with pytest.raises(ValueError):
        _write(module, "gzip", "DROP TABLE", enabled=True)
    with pytest.raises(ValueError):
        _write(module, "gzip", None, enabled=True)


def test_toggle_plugin_route_writes_schema_legal_value_end_to_end(route_app, monkeypatch):
    """The wired-up /plugins/enable endpoint must go through resolve_activation_write, not
    a hardcoded "yes"/"no", for its core branch."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "antibot", "enabled": "yes", "setting": "USE_ANTIBOT"}, client)
    client.update_global_settings.assert_called_once()
    args, _kwargs = client.update_global_settings.call_args
    written = args[0]
    assert written["USE_ANTIBOT"] != "yes"
    assert written["USE_ANTIBOT"] in _REAL_CORE_SETTINGS["USE_ANTIBOT"]["select"]


def test_enabling_a_multi_key_plugin_end_to_end_uses_the_resolved_sibling_values(route_app, monkeypatch):
    """The route hands the writer this request's RESOLVED config. A sibling explicitly turned off
    must come back written as "no" -- USE_LIMIT_CONN's schema default is "yes", so any path that
    guesses re-arms the connection limiter behind the operator (and Database.py:463 lets an `api`
    write overwrite a `ui` one, so the guess would land)."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    env = {
        "plugins": _REAL_CORE_PLUGIN_ENV,
        "config": {**_REAL_CORE_CONFIG, "USE_LIMIT_CONN": {"value": "no"}, "USE_LIMIT_REQ": {"value": "no"}},
    }
    _call_enable(module, app, monkeypatch, {"plugin": "limit", "enabled": "yes", "setting": "USE_LIMIT_REQ"}, client, env=env)
    written = client.update_global_settings.call_args.args[0]
    assert written == {"USE_LIMIT_REQ": "yes", "USE_LIMIT_REQ_GLOBAL": "no", "USE_LIMIT_CONN": "no"}


@pytest.mark.parametrize("plugin_id,key", [("country", "BLACKLIST_COUNTRY"), ("redirect", "REDIRECT_TO")])
def test_a_list_shaped_plugin_writes_nothing_when_the_schemas_are_missing(route_app, monkeypatch, plugin_id, key):
    """FAIL CLOSED on a MISSING schema, not just a missing value. `_is_list_shaped({})` is False,
    so reading an absent definition as "scalar" made this refusal fail OPEN -- and `main.py:
    1262-1265` parks `{}` whenever the per-request get_plugins() failed, so it was reachable from
    a stale tab or a resubmit. Measured before the fix: `redirect` OFF wrote REDIRECT_TO="" while
    every REDIRECT_TO_<n> kept serving, and `country` OFF wiped both lists."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": plugin_id, "enabled": "no", "setting": key}, client, env={"plugins": {}, "config": {}})
    client.update_global_settings.assert_not_called()
    assert module.DATA["RELOADING"] is False
    assert module.DATA["TO_FLASH"][-1]["type"] == "error"


def test_enabling_with_no_resolved_config_aborts_instead_of_guessing(route_app, monkeypatch, caplog):
    """FAIL CLOSED. `main.py:1296-1299` swallows a get_config() failure and parks `{}`; with no
    current value for a sibling the writer must refuse rather than fall back to its schema default.
    An aborted toggle flashes an error; a guessed one silently re-arms a limiter."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    with caplog.at_level("ERROR", logger="UI"):
        _call_enable(
            module, app, monkeypatch, {"plugin": "limit", "enabled": "yes", "setting": "USE_LIMIT_REQ"}, client, env={"plugins": _REAL_CORE_PLUGIN_ENV}
        )
    client.update_global_settings.assert_not_called()
    assert module.DATA["RELOADING"] is False
    assert module.DATA["TO_FLASH"][-1]["type"] == "error"


def test_disabling_a_multi_key_plugin_end_to_end_needs_no_api_read(route_app, monkeypatch):
    """OFF is a pure function of the manifest plus this request's already-fetched schemas, so the
    route must reach the API only to write -- and must still write every declared key."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    module.BW_CONFIG.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "limit", "enabled": "no", "setting": "USE_LIMIT_CONN"}, client)
    written = client.update_global_settings.call_args.args[0]
    assert written == {"USE_LIMIT_REQ": "no", "USE_LIMIT_REQ_GLOBAL": "no", "USE_LIMIT_CONN": "no"}
    module.BW_CONFIG.get_config.assert_not_called()
    module.BW_CONFIG.get_plugins_settings.assert_not_called()


def test_enabling_antibot_from_a_switch_picks_cookie(route_app, monkeypatch):
    """PINNED ON PURPOSE. USE_ANTIBOT is a 9-value select and `_active_value_for` takes the first
    option that is not the inactive one, i.e. the manifest's array order -- so a bare on/off switch
    silently selects "cookie", the lightest of the nine modes. That is a decision, not an accident:
    reordering core/antibot/plugin.json's `select` changes what a marketplace toggle turns on.
    D2 gives the compose shelf a MODE PICKER for this shape rather than a switch."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "antibot", "enabled": "yes", "setting": "USE_ANTIBOT"}, client)
    assert client.update_global_settings.call_args.args[0] == {"USE_ANTIBOT": "cookie"}


def test_off_then_on_does_not_restore_a_multi_key_plugins_siblings(route_app):
    """DOCUMENTED ASYMMETRY, not a bug to silently fix: OFF drives every declared key to its
    inactive value, so a following ON restores only the toggled key. One switch owning three keys
    cannot remember what they were; the per-plugin page is where the siblings come back."""
    module, _ = route_app
    off = _write(module, "limit", "USE_LIMIT_REQ", enabled=False)
    back_on = _write(module, "limit", "USE_LIMIT_REQ", enabled=True, current_values=off)
    assert back_on == {"USE_LIMIT_REQ": "yes", "USE_LIMIT_REQ_GLOBAL": "no", "USE_LIMIT_CONN": "no"}


def test_a_declared_non_use_setting_survives_the_pre_thread_guard(route_app, monkeypatch):
    """AUTO_LETS_ENCRYPT fails USE_SETTING_RX; before T2 the guard rejected it outright, so
    letsencrypt could not be toggled from the marketplace at all."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    monkeypatch.setattr(module, "handle_error", lambda *a, **k: "REJECTED")
    result = _call_enable(module, app, monkeypatch, {"plugin": "letsencrypt", "enabled": "yes", "setting": "AUTO_LETS_ENCRYPT"}, client)
    assert result != "REJECTED"
    client.update_global_settings.assert_called_once_with({"AUTO_LETS_ENCRYPT": "yes"})


def test_a_setting_the_plugin_does_not_declare_is_still_rejected_before_the_thread(route_app, monkeypatch):
    """The manifest gate is TIGHTER than the regex it replaces: a well-formed USE_* that the
    plugin does not declare must never reach update_global_settings."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    monkeypatch.setattr(module, "handle_error", lambda *a, **k: "REJECTED")
    result = _call_enable(module, app, monkeypatch, {"plugin": "letsencrypt", "enabled": "yes", "setting": "USE_MODSECURITY"}, client)
    assert result == "REJECTED"
    client.update_global_settings.assert_not_called()


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


# ======================================================================================
# Route harness — GET /plugins/<plugin> (custom_plugin_page's plugin_used()/is_used)
#
# The rewritten plugin_used() closure (Task 4) is the one piece of non-trivial rewritten
# logic in this change with no other coverage: it converts db_config's flat methods=False
# strings into is_plugin_active's {"value": ...}-shaped config, both globally and rescoped
# by a per-service prefix. "limit" is a real core plugin whose manifest declares a
# {setting: inactive_value} activation map (USE_LIMIT_REQ/USE_LIMIT_CONN, both "no"), i.e.
# exactly the old PLUGINS_SPECIFICS-driven case, so it's a faithful stand-in.
# ======================================================================================
_LIMIT_PLUGIN_DATA = {"type": "core", "name": "Limit", "description": "d", "version": "1.0", "method": "manual", "page": True, "icon": None}


def _limit_db_config(**service_overrides):
    return {"USE_METRICS": "yes", "SERVER_NAME": "app1.example.com", "USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no", **service_overrides}


def test_custom_plugin_page_is_used_true_via_service_scoped_dict_declaration(route_app, monkeypatch):
    """Globally inactive, but flipped on for one service -- plugin_used(prefix) must catch that
    through its {prefix}-scoped dict comprehension + is_plugin_active delegation, same as the
    old PLUGINS_SPECIFICS-driven code did. Asserted indirectly: is_used=True is what lets the
    route reach the filesystem/API page lookup at all, so with both stubbed to "no page found"
    the observable outcome is the 404 from that branch rather than the is_used=False fallthrough."""
    module, app = route_app
    module.BW_CONFIG.reset_mock(return_value=True, side_effect=True)
    module.API_CLIENT.reset_mock(return_value=True, side_effect=True)
    module.BW_CONFIG.get_plugins.return_value = {"limit": _LIMIT_PLUGIN_DATA}
    module.BW_CONFIG.get_config.return_value = _limit_db_config(**{"app1.example.com_USE_LIMIT_REQ": "yes"})
    monkeypatch.setattr(module, "get_plugin_path", lambda plugin_id: None)
    module.API_CLIENT.get_plugin_page.return_value = None
    with app.test_request_context("/plugins/limit"):
        resp = module.custom_plugin_page.__wrapped__("limit")
    assert resp == ({"status": "ko", "message": "The plugin does not have a page"}, 404)


def test_custom_plugin_page_is_used_false_when_inactive_everywhere(route_app, monkeypatch):
    """Inactive globally and on the only declared service -- is_used must stay False, so the
    route never touches the filesystem/API page lookup and renders plugin_page.html directly."""
    module, app = route_app
    module.BW_CONFIG.reset_mock(return_value=True, side_effect=True)
    module.API_CLIENT.reset_mock(return_value=True, side_effect=True)
    module.BW_CONFIG.get_plugins.return_value = {"limit": _LIMIT_PLUGIN_DATA}
    module.BW_CONFIG.get_config.return_value = _limit_db_config()
    captured = {}
    monkeypatch.setattr(module, "render_template", lambda name, **ctx: captured.update(ctx) or "")
    with app.test_request_context("/plugins/limit"):
        module.custom_plugin_page.__wrapped__("limit")
    assert captured["is_used"] is False
    assert captured["is_metrics"] is True
    module.API_CLIENT.get_plugin_page.assert_not_called()

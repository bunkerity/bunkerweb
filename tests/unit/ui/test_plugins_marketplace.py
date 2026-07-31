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
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

import plugin_extensions  # type: ignore  # noqa: E402 -- on sys.path via the root conftest
from app.utils import get_filtered_settings  # noqa: E402

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
        # The activation link is gated on the SHELF'S own loop filter, so the grid must resolve
        # the real function -- an Undefined here would silently make every link vanish.
        get_filtered_settings=get_filtered_settings,
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


def _plugin(type="core", name=None, description="d", version="1.0", method="manual", page=False, enabled=True, icon=None, settings=None):  # noqa: A002
    # `settings` defaults to one multisite entry because that is what makes a plugin appear in the
    # compose shelf, and therefore what makes its card eligible for an activation link. Pass {} for
    # the settings-less plugins (certificates, jobs, templates) that must NOT get one.
    return {
        "type": type,
        "name": name,
        "description": description,
        "version": version,
        "method": method,
        "page": page,
        "enabled": enabled,
        "icon": icon,
        "settings": {"USE_X": {"context": "multisite", "default": "no"}} if settings is None else settings,
    }


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

    # S5: a core card reports activation and links to the shelf; it never writes it. Before S5
    # `antibot` got a switch here and `country` did not, decided by whether a Python writer could
    # derive both directions -- a second implementation of a rule the shelf already had in Jinja.
    def test_no_core_card_renders_a_switch(self):
        html = _render(plugins={k: ALL_PLUGINS[k] for k in ("general", "antibot", "country")}, config=CONFIG)
        for plugin_id in ("general", "antibot", "country"):
            card = _card_slice(html, plugin_id)
            assert "plugin-switch" not in card, plugin_id
            assert 'name="setting"' not in card, plugin_id
            assert "plugin-toggle-form" not in card, plugin_id

    def test_a_core_card_reports_state_and_links_to_the_shelf(self):
        html = _render(plugins={"antibot": ALL_PLUGINS["antibot"], "country": ALL_PLUGINS["country"]}, config=CONFIG)
        active = _card_slice(html, "antibot")  # USE_ANTIBOT=yes
        inactive = _card_slice(html, "country")  # USE_COUNTRY=no
        assert "plugins.marketplace.active" in active
        assert "plugins.marketplace.inactive" in inactive
        for plugin_id, card in (("antibot", active), ("country", inactive)):
            # `_url_for` collapses an endpoint to /<endpoint>, so the host part is the stub's,
            # not a real path; the fragment is what this test is about.
            assert f'href="/global_settings.global_settings_page#shelf-row-{plugin_id}"' in card, plugin_id
            # Word-bounded: a bare substring check also passes for `plugin-activation-linkX`,
            # which is a renamed (i.e. unstyled, unqueryable) class. Mutation caught exactly that.
            assert re.search(r'class="[^"]*\bplugin-activation-link\b[^"]*"', card), plugin_id

    def test_an_always_on_core_card_offers_no_activation_link(self):
        """There is nothing to manage: the plugin is on unconditionally, and a link into the shelf
        would land on a row that renders a locked chip rather than a control."""
        card = _card_slice(_render(plugins={"general": ALL_PLUGINS["general"]}, config=CONFIG), "general")
        assert "plugins.marketplace.always_on" in card
        assert "plugin-activation-link" not in card

    def test_external_has_switch_without_setting(self):
        """The switch survives S5 for external / pro / ui plugins, where it means the one thing the
        shelf cannot express: the DB `enabled` flag, i.e. installed or not."""
        html = _render(plugins={"myext": ALL_PLUGINS["myext"]}, config={})
        card = _card_slice(html, "myext")
        assert "plugin-switch" in card
        assert 'name="setting"' not in card  # non-core: DB enabled flag, no USE_ setting
        assert "plugin-activation-link" not in card  # its activation IS its installation
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
    the observable outcome is the 404 from that branch rather than the is_used=False fallthrough.

    Admin is now part of "reaches the page lookup": loading a plugin-shipped page executes plugin
    code, so the route refuses a non-admin before it looks the page up at all."""
    module, app = route_app
    module.BW_CONFIG.reset_mock(return_value=True, side_effect=True)
    module.API_CLIENT.reset_mock(return_value=True, side_effect=True)
    module.BW_CONFIG.get_plugins.return_value = {"limit": _LIMIT_PLUGIN_DATA}
    module.BW_CONFIG.get_config.return_value = _limit_db_config(**{"app1.example.com_USE_LIMIT_REQ": "yes"})
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True))
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


# --------------------------------------------------------------------------------------
# S4 gate: loading a plugin-shipped page EXECUTES that plugin's code
# --------------------------------------------------------------------------------------
#
# `custom_plugin_page` serves GET and POST from one view. The POST arm has always refused a
# non-admin ("Plugin management is restricted to administrators"), and so do /plugins/delete,
# /plugins/enable, /plugins/refresh and /plugins/upload. The GET arm reached
# `run_action(plugin, "pre_render")` -- `SourceFileLoader(...).load_module()` called with
# `app=current_app` -- and rendered the plugin's own template.html through a NON-sandboxed
# jinja2.Environment, with no admin check at all. `reader` is a seeded role whose whole
# permission set is ["read"] (db_methods/ui_users.py) and the biscuit middleware maps
# GET -> "read", so a read-only account got code execution by loading a page.


@pytest.fixture
def plugin_page_call(route_app, monkeypatch, tmp_path):
    """Drive the real `custom_plugin_page` GET arm far enough to reach the execution gate."""
    module, app = route_app

    def _call(*, admin, plugin="myext", with_ui_dir=True):
        module.API_CLIENT.reset_mock()
        monkeypatch.setattr(module, "TMP_DIR", tmp_path / "tmp")
        monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=admin))
        module.BW_CONFIG.get_plugins.return_value = {plugin: {"name": "My Ext", "type": "pro", "settings": {}}}
        module.BW_CONFIG.get_config.return_value = {"USE_METRICS": "yes", "SERVER_NAME": "www.example.com"}

        plugin_root = tmp_path / "plugins" / plugin
        if with_ui_dir:
            (plugin_root / "ui").mkdir(parents=True, exist_ok=True)
            (plugin_root / "ui" / "template.html").write_text("<p>owned</p>", encoding="utf-8")
            (plugin_root / "ui" / "actions.py").write_text("def pre_render(**kwargs):\n    return {'status': 'ok'}\n", encoding="utf-8")
        monkeypatch.setattr(module, "get_plugin_path", lambda _: plugin_root if with_ui_dir else None)

        captured = {}
        monkeypatch.setattr(module, "render_template", lambda name, **context: captured.update(context) or "")
        ran = []
        monkeypatch.setattr(module, "run_action", lambda *a, **k: ran.append((a, k)) or {"status": "ok"})

        with app.test_request_context(f"/plugins/{plugin}", method="GET"):
            module.custom_plugin_page.__wrapped__(plugin)
        return captured, ran

    return _call


def test_a_non_admin_never_executes_plugin_code(plugin_page_call):
    context, ran = plugin_page_call(admin=False)
    assert ran == [], "run_action reached on a non-admin GET -- that is arbitrary plugin Python in the UI process"
    assert context.get("restricted") is True
    assert context.get("plugin_page") == "", "the plugin's own template must not be rendered either"


def test_an_admin_still_gets_the_plugin_page(plugin_page_call):
    """The gate must not break the supported case, or it would read as 'plugin pages are gone'."""
    _, ran = plugin_page_call(admin=True)
    assert ran, "an admin GET no longer reaches the plugin's pre_render"


def test_the_gate_precedes_the_tarball_extraction(route_app, plugin_page_call):
    """Ordering, not just presence: below the gate the route pulls the plugin blob from the API and
    untars it. A non-admin request must not get that far -- refusing only after unpacking
    attacker-supplied archive members is a weaker position for no benefit. `get_plugin_page` is
    the fetch that feeds the untar, so its absence is the ordering claim."""
    module, _ = route_app
    context, _ = plugin_page_call(admin=False, with_ui_dir=False)
    assert context.get("restricted") is True
    module.API_CLIENT.get_plugin_page.assert_not_called()


def test_the_restricted_notice_is_distinct_from_the_no_page_one():
    """Reusing `no_page` would tell a reader to "restart the web UI" to fix a permission refusal --
    a support ticket by construction."""
    markup = (TEMPLATES / "plugin_page.html").read_text(encoding="utf-8")
    assert "plugin.page.status.restricted_to_admins" in markup
    assert markup.index("{% elif restricted %}") < markup.index("{% elif no_page %}")
    locales = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    assert "restricted_to_admins" in locales["plugin"]["page"]["status"]


# --------------------------------------------------------------------------------------
# S5: /plugins/enable means INSTALLED-OR-NOT, and nothing else
# --------------------------------------------------------------------------------------
#
# This route used to carry a second meaning. For a core plugin -- which cannot be DB-toggled at
# all -- the grid passed a `setting` name and the route wrote that plugin's activation value
# globally, through `resolve_activation_write`: a second derivation of "what is the active value"
# beside the one models/compose_shelf.html already had in Jinja, reached by a second write path.
# S5 split the two by meaning. The tests below pin the half that matters after the split: the
# route no longer writes settings AT ALL, so a crafted POST cannot make it.


def test_enable_never_writes_a_global_setting(route_app, monkeypatch):
    """The strong form: whatever the form carries, this route touches only the enabled flag."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "antibot", "enabled": "yes", "setting": "USE_ANTIBOT"}, client)
    client.update_global_settings.assert_not_called()
    client.set_plugin_enabled.assert_called_once_with("antibot", True)


def test_a_crafted_setting_parameter_is_inert(route_app, monkeypatch):
    """A POST naming another plugin's key -- the shape the old `is_activation_setting` guard
    existed to reject, and whose own docstring recorded that it trusted the manifest to declare
    only its own keys, something nothing verifies. With no write path left there is nothing for a
    crafted key to reach, which is why the guard could be deleted rather than hardened."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    _call_enable(module, app, monkeypatch, {"plugin": "myext", "enabled": "no", "setting": "SERVER_NAME"}, client)
    client.update_global_settings.assert_not_called()
    client.set_plugin_enabled.assert_called_once_with("myext", False)


def test_a_toggle_failure_still_flashes_and_clears_reloading(route_app, monkeypatch):
    """`toggle_plugin` runs on a bare ThreadPoolExecutor whose futures are never retrieved, so an
    uncaught exception there vanishes with no log and no flash while the user waits on /loading
    for main.py's 60s watchdog. The broad `except` is what prevents that, and it must survive the
    narrowing of this route."""
    module, app = route_app
    client = module.API_CLIENT
    client.reset_mock()
    client.set_plugin_enabled.side_effect = RuntimeError("boom")
    _call_enable(module, app, monkeypatch, {"plugin": "myext", "enabled": "yes"}, client)
    client.set_plugin_enabled.side_effect = None
    assert module.DATA["RELOADING"] is False
    assert any("Couldn't update plugin myext" in flash["content"] for flash in module.DATA["TO_FLASH"])


def test_the_shelf_row_carries_the_anchor_the_card_links_to():
    """The card's link and the shelf's row id are one contract across two files; a rename on
    either side leaves a link that silently lands at the top of the page."""
    shelf = (TEMPLATES / "models" / "compose_shelf.html").read_text(encoding="utf-8")
    grid = (TEMPLATES / "plugins.html").read_text(encoding="utf-8")
    assert 'id="shelf-row-{{ plugin }}"' in shelf
    assert "#shelf-row-{{ plugin }}" in grid


def test_the_shelf_unfolds_the_row_a_link_names():
    """An inactive plugin's row is folded (`display: none`) and that is exactly the row someone
    arrives wanting, so the fragment must unfold before anything can scroll to it."""
    script = (TEMPLATES.parent / "static" / "js" / "components" / "compose-shelf.js").read_text(encoding="utf-8")
    hook = script[script.index("shelf-row-") :]  # noqa: E203
    assert "expanded = true" in hook
    assert "scrollIntoView" in hook


def test_no_card_links_to_a_shelf_row_the_shelf_would_not_render():
    """THE DEFECT THE RUNNING STACK FOUND, in its general form.

    The card's link and the shelf's row live on two different pages, so no rendered-markup
    assertion about either one alone can see a mismatch between them. On the real stack three core
    plugins -- `certificates`, `jobs`, `templates` -- shipped a link to a row that does not exist:
    all three declare ZERO settings, and the shelf's loop is
    `for plugin, plugin_data in plugins.items() if get_filtered_settings(...)`, so they never enter
    it. The link landed on a page where its fragment named nothing.

    Computed over the REAL shipped manifests rather than a fixture, because the failure was a set
    difference between what ships and what the two templates each decide to render.
    """
    # Source-level half: both templates must gate on the SAME function. Asserting the two
    # computed sets are equal would be vacuous -- one expression evaluated twice always agrees.
    grid = (TEMPLATES / "plugins.html").read_text(encoding="utf-8")
    shelf = (TEMPLATES / "models" / "compose_shelf.html").read_text(encoding="utf-8")
    before = grid[: grid.index("plugin-activation-link")].splitlines()
    link_gate = next(line for line in reversed(before) if line.lstrip().startswith("{% if "))
    assert "get_filtered_settings(" in link_gate, f"the link is gated on something else: {link_gate.strip()}"
    assert "if get_filtered_settings(" in shelf, "the shelf stopped filtering its loop on get_filtered_settings"

    # Behavioural half, over what actually ships.
    settings_less = {
        manifest.parent.name for manifest in CORE_PLUGINS_PATH.glob("*/plugin.json") if not json.loads(manifest.read_text(encoding="utf-8")).get("settings", {})
    }
    assert settings_less, "no settings-less core plugin ships any more -- this guard has gone vacuous"
    for plugin_id in sorted(settings_less):
        html = _render(plugins={plugin_id: _plugin(name=plugin_id.title(), settings={})}, config={})
        card = _card_slice(html, plugin_id)
        assert "plugin-activation-link" not in card, f"{plugin_id} has no shelf row but its card links to one"

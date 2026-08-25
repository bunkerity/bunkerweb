"""The per-service plugin page: what it renders and what it is authoritative for.

The page owns exactly one plugin's settings. Three things make that safe rather than
destructive: the scope it derives (`postable_scope`, so a save cannot touch another plugin's
rows -- or a row of its OWN plugin the form cannot actually post), the control keys it posts
(because `restore_unowned_settings` deliberately never restores `restore_skip` keys, so a
surface that omits them destroys them), and the plugin id it resolves (`resolve_plugin`, a
membership check rather than a length-limited regex).
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.utils import get_blacklisted_settings, get_filtered_settings, get_multiples, is_editable_method

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "src" / "ui" / "app" / "templates"


def _import_services_module():
    """``app.routes.services`` transitively imports ``app.dependencies``, which builds real
    singletons at module scope (``Config()`` reads ``/usr/share/bunkerweb/settings.json`` --
    only present inside a built image, never in a bare checkout) and, via
    ``app.routes.configs`` -> ``app.routes.utils``, ``qrcode.main.QRCode`` (absent from the
    pared-down unit-test venv). A bare ``from app.routes.services import postable_scope`` fails
    at collection time regardless of whether ``postable_scope`` exists, so load the file
    directly against stub modules for both -- exactly the pattern
    ``test_ui_service_resources.py``'s ``services_route`` fixture already uses for this same
    module.
    """
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    # The real one is the image-only /usr/share/bunkerweb/core; point it at the repo so
    # `core_plugin_order()` reads the SHIPPED order.json instead of falling back to {}.
    dependencies.CORE_PLUGINS_PATH = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._services_test_plugin_scope"
    route_path = REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py"
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
    return module


_services_module = _import_services_module()
postable_scope = _services_module.postable_scope
resolve_plugin = _services_module.resolve_plugin

ANTIBOT = {
    "id": "antibot",
    "name": "Antibot",
    "settings": {
        "USE_ANTIBOT": {"id": "use-antibot", "context": "multisite", "default": "no", "type": "select", "select": ["no", "captcha"], "label": "Antibot"},
        "ANTIBOT_URI": {"id": "antibot-uri", "context": "multisite", "default": "/challenge", "type": "text", "label": "URI"},
        "ANTIBOT_GLOBAL_ONLY": {"id": "antibot-global-only", "context": "global", "default": "", "type": "text", "label": "Global only"},
    },
}

# A plugin whose manifest declares a `multiple` setting (e.g. reverseproxy's REVERSE_PROXY_HOST) --
# the C3 regression: the multiples section's ADD button and multisite badge are only reachable
# through a plugin shaped like this one, never through ANTIBOT.
PROXY_MULTI = {
    "id": "proxy_multi",
    "name": "Proxy Multi",
    "settings": {
        "PROXY_HOST": {"id": "proxy-host", "context": "multisite", "default": "", "type": "text", "label": "Proxy host", "multiple": "proxy"},
    },
}

# A PRO plugin, for postable_scope's license-gated rule (F1a below).
PRO_PLUGIN = {
    "id": "waf_extra",
    "name": "WAF Extra",
    "type": "pro",
    "settings": {
        "WAF_EXTRA_MODE": {
            "id": "waf-extra-mode",
            "context": "multisite",
            "default": "off",
            "type": "select",
            "select": ["off", "on"],
            "label": "Mode",
        },
    },
}

# The "general" plugin has no plugin.json of its own -- db_methods/initialization.py:323
# synthesizes it straight from settings.json at boot -- so this is the one place a hand-typed
# stand-in can silently diverge from what ships. SERVER_NAME and IS_DRAFT (both real multisite
# settings.json entries) are the F2 collision: the shell always emits hidden inputs for both,
# and a 1-setting stand-in that declares only SERVER_NAME is exactly what let a round of tests
# pass on the IS_DRAFT bug without ever exercising it.
GENERAL_LIKE = {
    "id": "general",
    "name": "General",
    "type": "core",
    "settings": json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text()),
}

# The real "ui" plugin -- USE_UI is a real declared setting of type "check" (not a stand-in),
# so on a service page the body renders an editable checkbox for it in addition to
# plugin_settings_page.html's own unconditional hidden USE_UI control input, both sharing the
# name "USE_UI". This is the fix-round-4 F1 collision: the unchecked-checkbox fallback used to
# be appended at the end of the form, landing after that hidden control input, so
# request.form.to_dict() (which keeps the FIRST value for a repeated name) always kept the
# control input's stale "yes" and silently discarded a "no" fallback -- turning "Use UI" off
# from this page never worked. The normalisation now lives in js/components/settings-widgets.js
# (S3.3 folded the page's own script into it and deleted js/pages/plugin-settings-page.js), and
# it inserts the fallback with insertAdjacentElement("afterend", ...) instead of appending.
UI_PLUGIN_LIKE = {
    "id": "ui",
    "name": "UI",
    "type": "core",
    "settings": json.loads((REPO_ROOT / "src" / "common" / "core" / "ui" / "plugin.json").read_text())["settings"],
}

# base.html sets this at module scope (`{% set plugin_types = {...} %}`); the stubbed
# dashboard.html below doesn't extend base.html, and the multiples section reads it
# unconditionally, so it needs stubbing here too.
PLUGIN_TYPES = {
    "core": {"icon": "", "title-class": " border-dark"},
    "external": {"icon": "", "title-class": " border-secondary", "text-class": " text-secondary fw-bold"},
    "ui": {"icon": "", "title-class": " border-secondary", "text-class": " text-secondary"},
    "pro": {"title-class": " border-primary", "text-class": " text-primary fw-bold shine"},
}


# --------------------------------------------------------------------------------------
# postable_scope -- F1. The keys a plugin's page can actually submit, mirroring the
# `disabled` computation in models/plugin_settings_body.html rule for rule (see its own
# docstring in app/routes/services.py for the numbered contract). Each test below is named
# after, and must fail if the interpreter's behaviour regresses on, exactly one rule.
# --------------------------------------------------------------------------------------


def test_postable_scope_pro_plugin_without_license_is_empty():
    """Rule 1 (F1a): a PRO plugin with an inactive license renders every field disabled --
    nothing posts, so nothing may be claimed as in-scope, or every ui-method row of that
    plugin is deleted on save."""
    assert postable_scope(PRO_PLUGIN, {}, global_page=False, is_pro_version=False, blacklisted=set()) == set()


def test_postable_scope_pro_plugin_with_license_yields_its_settings():
    """Rule 1 only short-circuits while the license is inactive."""
    assert postable_scope(PRO_PLUGIN, {}, global_page=False, is_pro_version=True, blacklisted=set()) == {"WAF_EXTRA_MODE"}


def test_postable_scope_is_readonly_short_circuits_to_empty():
    """Fix round 4, F2: plugin_settings_body.html sets disabled=True for EVERY setting when
    is_readonly, regardless of method or PRO status -- so postable_scope must short-circuit the
    same way, right beside the PRO check. Without this, a form that somehow became submittable
    while is_readonly (e.g. current_user.list_permissions transiently empty from an API error)
    would claim its whole key set as in scope while actually posting none of it, deleting every
    ui-method row of the plugin. ANTIBOT is a plugin that would otherwise yield a non-empty
    scope here (see test_postable_scope_includes_a_key_absent_from_db_config)."""
    assert postable_scope(ANTIBOT, {}, global_page=False, is_pro_version=False, blacklisted=set(), is_readonly=True) == set()


def test_postable_scope_multiple_setting_evaluated_per_suffix_row():
    """Fix round 4, F3: a `multiple` setting's suffixed rows must each be judged on their OWN
    stored method/global, not the base/suffix-0 row's -- mirrors plugin_settings_body.html's
    multiples loop, which reads `config.get(setting)` per suffix (a plugin.json only ever names
    the base, e.g. PROXY_HOST, the same shape as reverseproxy's REVERSE_PROXY_HOST/URL). Before
    this fix, postable_scope only ever looked up db_config[base_name] once, so a stored suffix
    like PROXY_HOST_2 was invisible to it and fell back to the "no row at all" branch -- and
    since _in_scope (app/models/save_scope.py) also matches a suffixed key by its base name, a
    disabled suffix riding in on a differently-configured base was silently put in scope, so
    omitting it from the post (because it rendered disabled) deleted its row."""
    db_config = {
        "PROXY_HOST_1": {"value": "http://a", "method": "ui", "global": False},
        "PROXY_HOST_2": {"value": "http://b", "method": "scheduler", "global": False},
    }
    scope = postable_scope(PROXY_MULTI, db_config, global_page=False, is_pro_version=False, blacklisted=set())
    assert "PROXY_HOST_1" in scope
    assert "PROXY_HOST_2" not in scope


def test_postable_scope_excludes_blacklisted_keys():
    """Rule 2: a blacklisted key is rendered by nobody at all (see IS_DRAFT, F2) -- it can
    never post, whatever its method or context."""
    scope = postable_scope(ANTIBOT, {}, global_page=False, is_pro_version=False, blacklisted={"ANTIBOT_URI"})
    assert scope == {"USE_ANTIBOT"}


def test_postable_scope_global_context_key_only_in_scope_on_the_global_page():
    """Rule 3: a service-page save can never write a global-context key at all
    (models/config.py:61 drops it silently), so claiming authority over one there would mean
    declaring it deletable while being unable to set it."""
    service_scope = postable_scope(ANTIBOT, {}, global_page=False, is_pro_version=False, blacklisted=set())
    global_scope = postable_scope(ANTIBOT, {}, global_page=True, is_pro_version=False, blacklisted=set())
    assert "ANTIBOT_GLOBAL_ONLY" not in service_scope
    assert "ANTIBOT_GLOBAL_ONLY" in global_scope


def test_postable_scope_excludes_a_disabled_scheduler_managed_key_on_a_service_page():
    """Rule 4 (F1b): mirrors the template's own `disabled` expression exactly -- a
    scheduler-managed setting whose stored entry has global=False renders disabled on a
    service page, so the page cannot post it (USE_TEMPLATE is the real-world instance)."""
    db_config = {"USE_ANTIBOT": {"value": "no", "method": "scheduler", "global": False}}
    scope = postable_scope(ANTIBOT, db_config, global_page=False, is_pro_version=False, blacklisted=set())
    assert "USE_ANTIBOT" not in scope


def test_postable_scope_includes_a_ui_method_key():
    db_config = {"USE_ANTIBOT": {"value": "captcha", "method": "ui", "global": False}}
    scope = postable_scope(ANTIBOT, db_config, global_page=False, is_pro_version=False, blacklisted=set())
    assert "USE_ANTIBOT" in scope


def test_postable_scope_includes_a_key_absent_from_db_config():
    """A key with no stored row has no method to be disabled by -- default it to "default"
    (editable) and keep it, per the function's own conservative-when-in-doubt contract."""
    scope = postable_scope(ANTIBOT, {}, global_page=False, is_pro_version=False, blacklisted=set())
    assert "USE_ANTIBOT" in scope


# --------------------------------------------------------------------------------------
# The scope SET is only half of the contract: what it buys is decided by
# `restore_unowned_settings`, and until this section nothing here drove `update_service` at
# all -- so `scope=scope` could become `scope=None` or `scope=set(db_config)` at
# services.py:713 (the call site this page shares with the per-template page) and every test
# above stayed green while the save deleted every row the plugin does not own.
# --------------------------------------------------------------------------------------


class _FakeData(dict):
    def load_from_file(self):
        pass


_STORED = {
    "SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False},
    "USE_TEMPLATE": {"value": "low", "method": "ui", "global": False},
    "USE_UI": {"value": "no", "method": "ui", "global": False},
    "USE_ANTIBOT": {"value": "captcha", "method": "ui", "global": False},
    "ANTIBOT_URI": {"value": "/challenge", "method": "ui", "global": False},
    # Another plugin's row. ui-method on purpose: the method-based restore skips it precisely
    # because "ui" is editable, so the ONLY thing that keeps it alive across a save of the
    # antibot page is the declared scope.
    "X_FRAME_OPTIONS": {"value": "DENY", "method": "ui", "global": False},
    # ...and another plugin's row that the service's TEMPLATE owns. Restored only while
    # `template_unchanged` is true, which it is here (USE_TEMPLATE is posted unchanged): hardcode
    # that argument to False at services.py:715 and this row stops being carried.
    "SECURITY_MODE": {"value": "block", "method": "default", "global": False, "template": "low"},
}

# What the antibot page's form really sends: its own fields plus the shell's control inputs.
_POSTED = {
    "SERVER_NAME": "app.example.com",
    "USE_TEMPLATE": "low",
    "USE_UI": "no",
    "USE_ANTIBOT": "no",
    "ANTIBOT_URI": "/challenge",
}


def _run_plugin_save(monkeypatch, *, db_config, posted, scope):
    """Drive the real `update_service` the way services.py:1112-1128 does -- mode "compose",
    scope from `postable_scope` -- and return the payload handed to `edit_service`."""
    module = _services_module
    api = Mock()
    api.get_service.return_value = db_config
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    bw_config = Mock()
    # The real check_variables validates and returns the payload; identity keeps this test about
    # the restore layer rather than about validation.
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("Configuration saved", None)
    monkeypatch.setattr(module, "API_CLIENT", api)
    monkeypatch.setattr(module, "BW_CONFIG", bw_config)
    monkeypatch.setattr(module, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr(module, "wait_applying", lambda: None)

    module.update_service("app.example.com", dict(posted), False, "compose", "", {}, scope=scope)

    assert bw_config.edit_service.called, "update_service returned early -- nothing reached the save, so this test proves nothing"
    return bw_config.edit_service.call_args[0][1]


def test_a_plugin_page_save_keeps_a_row_no_field_of_this_plugin_can_post(monkeypatch):
    """`save_config` treats its payload as the complete desired state, so a stored key missing
    from it has its row DELETED (db_methods/config_save.py:592). This page renders one plugin,
    so every other plugin's ui-method rows are out of scope AND unposted -- exactly the shape
    `restore_unowned_settings` exists for."""
    scope = postable_scope(ANTIBOT, _STORED, global_page=False, is_pro_version=False, blacklisted=get_blacklisted_settings())
    assert "X_FRAME_OPTIONS" not in scope, "fixture premise: the antibot page declares no authority over it"

    payload = _run_plugin_save(monkeypatch, db_config=_STORED, posted=_POSTED, scope=scope)

    assert payload["X_FRAME_OPTIONS"] == "DENY", "an out-of-scope stored setting was dropped -> its row dies"
    assert payload["SECURITY_MODE"] == "block", "a template-owned row was dropped by a save that never touched USE_TEMPLATE"
    # ...without freezing what the page DOES own: a scope-blind restore would look just as green.
    assert payload["USE_ANTIBOT"] == "no"


# --------------------------------------------------------------------------------------
# Route wiring: where the save sends the user. Nothing in this file POSTed through the real
# route before, so both branches of the post-rename redirect (services.py:1136-1140) were
# unobservable -- deleting the conditional entirely left the suite green.
# --------------------------------------------------------------------------------------


@pytest.fixture
def route_app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(_services_module.services)
    app.add_url_rule("/loading", "loading", lambda: "")
    return _services_module, app


def _post_plugin_page(module, app, monkeypatch, *, db_config=None, form=None, plugin="antibot"):
    """POST the real route and return the Mock executor, with the route's response attached."""
    api = Mock()
    api.readonly = False
    api.get_service.return_value = _STORED if db_config is None else db_config
    api.get_metadata.return_value = {"is_pro": False}
    bw_config = Mock()
    bw_config.get_plugins.return_value = {"antibot": ANTIBOT}
    executor = Mock()
    monkeypatch.setattr(module, "API_CLIENT", api)
    monkeypatch.setattr(module, "BW_CONFIG", bw_config)
    monkeypatch.setattr(module, "CONFIG_TASKS_EXECUTOR", executor)
    monkeypatch.setattr(module, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr("app.utils.current_user", SimpleNamespace(list_permissions=["read", "write"]))

    data = {"csrf_token": "x"} | (form or {})
    with app.test_request_context(f"/services/app.example.com/plugins/{plugin}", method="POST", data=data):
        executor.response = module.services_plugin_page.__wrapped__("app.example.com", plugin)
    return executor


def _redirect_next(response):
    """The `next` the loading page will bounce to once the save finishes."""
    return parse_qs(urlsplit(response.headers["Location"]).query).get("next")


def test_a_rename_sends_the_user_to_the_service_list(route_app, monkeypatch):
    """A rename makes this page's own URL dead -- the path segment still names the pre-rename
    service, so the GET behind the loading page would flash "Service not found" right next to the
    save's success message."""
    module, app = route_app
    executor = _post_plugin_page(module, app, monkeypatch, form={"SERVER_NAME": "renamed.example.com", "USE_ANTIBOT": "no"})

    assert _redirect_next(executor.response) == ["/services"]


def test_a_save_without_a_rename_comes_back_to_this_page(route_app, monkeypatch):
    """The control half, and it is not optional: an UNCONDITIONAL
    `url_for("services.services_page")` satisfies the rename test above while throwing the user
    off the page on every ordinary save."""
    module, app = route_app
    executor = _post_plugin_page(module, app, monkeypatch, form={"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "no"})

    assert _redirect_next(executor.response) == ["/services/app.example.com/plugins/antibot"]


# --------------------------------------------------------------------------------------
# resolve_plugin -- F3. Membership in the real plugin set replaces PLUGIN_NAME_RX on these
# two routes: the regex's 4-64 character range rejected the real single/two/three-character
# core plugin ids "db", "ui", "php", "pro" and "ssl".
# --------------------------------------------------------------------------------------

_REAL_SHAPED_PLUGINS = {"ssl": {"id": "ssl"}, "db": {"id": "db"}, "antibot": {"id": "antibot"}}


def test_resolve_plugin_accepts_short_core_plugin_ids():
    assert resolve_plugin("ssl", _REAL_SHAPED_PLUGINS) == {"id": "ssl"}
    assert resolve_plugin("db", _REAL_SHAPED_PLUGINS) == {"id": "db"}


def test_resolve_plugin_rejects_a_traversal_payload():
    assert resolve_plugin("../../etc/passwd", _REAL_SHAPED_PLUGINS) is None


def test_resolve_plugin_rejects_an_unknown_id():
    assert resolve_plugin("not_a_real_plugin", _REAL_SHAPED_PLUGINS) is None


# --------------------------------------------------------------------------------------
# plugin_settings_page.html -- rendered directly off a standalone Jinja env, following the
# same pattern as test_ui_service_resources.py's `_render_band`. Unlike that partial, this
# page `{% extends "dashboard.html" %}`, so the loader also stubs dashboard.html down to its
# `content` and `scripts` blocks (the same trick test_row_actions.py's `_render_dashboard_page`
# uses) rather than reconstructing the whole sidebar/navbar context this page never touches.
# `scripts` is real base.html's block (dashboard.html inherits it); without a placeholder here
# the page's own `{% block scripts %}` override has nothing to attach to and is silently dropped.
# --------------------------------------------------------------------------------------


@pytest.fixture
def render_plugin_page():
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )

    def _url_for(endpoint, **kwargs):
        # Real url_for embeds `filename` in the static asset's path; reflect that here so a
        # test can assert on which static file the page actually points at.
        if endpoint == "static" and "filename" in kwargs:
            return f"/static/{kwargs['filename']}"
        return f"/{endpoint}"

    env.globals.update(
        csrf_token=lambda: "test-csrf-token",
        url_for=_url_for,
        get_blacklisted_settings=get_blacklisted_settings,
        get_filtered_settings=get_filtered_settings,
        get_multiples=get_multiples,
        is_editable_method=is_editable_method,
        plugin_types=PLUGIN_TYPES,
        # multivalue_setting.html calls this for the resource-group-picker; real settings.json
        # settings include several multivalue entries (PLUGINS_ORDER_*), which the real "general"
        # shape fixture below now exercises. None means "no resource-group kind", same as
        # production for any setting resource_group_resolver.kind_for_key doesn't recognise.
        resource_kind_for_setting=lambda *_: None,
    )

    def _render(service_id="", is_draft="no", is_readonly=False, use_ui="no", plugin_data=None, extra_config=None):
        if plugin_data is None:
            plugin_data = ANTIBOT | {"version": "1.2.3", "description": "Bot detection challenge."}
        # Every plugin has a type in production (BW_CONFIG.get_plugins()); default it here too so
        # plugin_types[plugin_data["type"]] (used by the multiple-settings header) always resolves.
        plugin_data = plugin_data | {"type": plugin_data.get("type", "core")}
        config = {
            "SERVER_NAME": {"value": service_id},
            "IS_DRAFT": {"value": is_draft},
            "USE_TEMPLATE": {"value": ""},
            "USE_UI": {"value": use_ui},
        }
        config.update(extra_config or {})
        return env.get_template("plugin_settings_page.html").render(
            plugin=plugin_data["id"],
            plugin_data=plugin_data,
            config=config,
            service_id=service_id,
            clone=None,
            is_readonly=is_readonly,
            user_readonly=False,
        )

    return _render


CONTROL_KEYS = ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "USE_UI")


@pytest.mark.parametrize("key", CONTROL_KEYS)
def test_page_posts_every_restore_skip_control_key(key, render_plugin_page):
    """`restore_unowned_settings` never restores restore_skip keys, so anything this form
    omits is deleted. Omitting IS_DRAFT publishes a draft service."""
    html = render_plugin_page(service_id="app.example.com", is_draft="yes")
    assert f'name="{key}"' in html


def test_draft_state_round_trips(render_plugin_page):
    html = render_plugin_page(service_id="app.example.com", is_draft="yes")
    assert 'name="IS_DRAFT" value="yes"' in html


def test_form_action_is_relative(render_plugin_page):
    """A hardcoded absolute action posts the __Host- session cookie and a valid CSRF token to
    whatever serves / when the UI is mounted behind REVERSE_PROXY_URL."""
    html = render_plugin_page(service_id="app.example.com")
    assert 'action=""' in html
    assert 'action="/services' not in html


def test_readonly_disables_save(render_plugin_page):
    html = render_plugin_page(service_id="app.example.com", is_readonly=True)
    assert "save-settings" in html
    assert "disabled" in html


def test_global_page_omits_the_service_control_inputs(render_plugin_page):
    """There is no service to name, draft or template, and posting an empty SERVER_NAME
    into a global save would be worse than posting nothing."""
    html = render_plugin_page(service_id="")
    assert 'name="IS_DRAFT"' not in html
    assert 'name="OLD_SERVER_NAME"' not in html


def test_global_page_breadcrumb_points_at_global_settings(render_plugin_page):
    html = render_plugin_page(service_id="")
    assert "global_settings" in html or "Global settings" in html


def test_use_ui_value_round_trips(render_plugin_page):
    """C1: USE_UI is in restore_skip (services.py's update_service builds it from
    get_blacklisted_settings() | {..., "USE_UI"}), so an omitted USE_UI deletes the row --
    including the wizard-created admin-UI service's USE_UI=yes."""
    html = render_plugin_page(service_id="app.example.com", use_ui="yes")
    assert 'name="USE_UI" value="yes"' in html


def test_page_loads_the_shared_widgets_module(render_plugin_page):
    """C2: the per-plugin page submits natively and needs the submit normalisation to turn an
    unchecked switch into "no" -- without the script tag that JS never runs, and an omitted
    in-scope key is deleted rather than set. S3.3 folded js/pages/plugin-settings-page.js into
    js/components/settings-widgets.js and deleted it, which also wired up this page's multiselect
    and multivalue widgets for the first time.

    The negative is D0.1's invariant and it is asserted here on RENDERED html, not on the
    template source: plugin_settings_page.html carries a Jinja comment naming the monolith on
    purpose, and Jinja strips `{# #}` before render, so a source grep false-positives."""
    html = render_plugin_page(service_id="app.example.com")
    assert "js/components/settings-widgets.js" in html
    assert "js/plugins-settings.js" not in html
    assert "js/pages/plugin-settings-page.js" not in html


def test_form_carries_the_native_submit_marker(render_plugin_page):
    """settings-widgets.js binds its submit normalisation to `form[data-plugin-settings-form]`;
    without the attribute the script is a silent no-op and every unchecked switch posts nothing
    at all."""
    html = render_plugin_page(service_id="app.example.com")
    assert "data-plugin-settings-form" in html


def test_plugin_with_multiple_settings_renders(render_plugin_page):
    """C3: plugin_settings_body.html called the `button` macro and `docs_url` without importing
    either (both are only imported by the OLD consumer, models/plugins_settings.html), so any
    plugin whose manifest declares a `multiple` setting raised UndefinedError."""
    html = render_plugin_page(service_id="app.example.com", plugin_data=PROXY_MULTI)
    assert "PROXY_HOST" in html


def test_global_page_disables_a_scheduler_managed_setting(render_plugin_page):
    """C5: current_endpoint is the plugin id on this exact route (main.py takes the last URL
    path segment), never "global-settings", so the disabled branch never fired and a
    scheduler/env/manual-managed global setting rendered as an editable input."""
    html = render_plugin_page(service_id="", extra_config={"USE_ANTIBOT": {"value": "no", "method": "scheduler"}})
    assert "Disabled by scheduler" in html


# --------------------------------------------------------------------------------------
# F2 -- the real "general" plugin shape (SERVER_NAME + IS_DRAFT declared as its own settings,
# IS_DRAFT permanently blacklisted so the body never renders an editable field for it). Both
# tests below render GENERAL_LIKE, built straight from settings.json (see its definition
# above) rather than a 1-setting stand-in, because the stand-in is exactly what hid this bug.
# --------------------------------------------------------------------------------------


def test_general_shape_posts_is_draft_despite_being_permanently_blacklisted(render_plugin_page):
    """F2: IS_DRAFT is permanently blacklisted (app/utils.py:get_blacklisted_settings), so the
    settings body never renders an editable field for it even though the general plugin
    declares it as a real setting -- the hidden control input is the ONLY thing that posts it.
    Losing it makes services.py's `variables.pop("IS_DRAFT", "no")` read False and PUBLISH A
    DRAFT SERVICE."""
    html = render_plugin_page(service_id="app.example.com", is_draft="yes", plugin_data=GENERAL_LIKE)
    assert 'name="IS_DRAFT" value="yes"' in html


def test_general_shape_editable_server_name_precedes_the_hidden_fallback(render_plugin_page):
    """F2: the general plugin declares SERVER_NAME as a real setting, so both the body's
    editable field and the shell's unconditional hidden fallback share the name "SERVER_NAME".
    request.form.to_dict() keeps the FIRST value for a repeated field name -- so as long as the
    editable field renders before the hidden fallback, a rename typed here is kept, and the
    hidden fallback still runs for every service that lands on this page with SERVER_NAME left
    untouched. Both keys render exactly once each, and the editable one must come first.

    `index(x) < rindex(x)` is NOT the assertion for that: it is true of every string containing
    the needle twice, so it restates the count above and proves nothing. Assert instead that the
    LAST occurrence is the hidden fallback and the FIRST is the editable field -- the last-only
    form would also hold if BOTH of them were hidden."""
    html = render_plugin_page(service_id="app.example.com", plugin_data=GENERAL_LIKE)
    assert html.count('name="SERVER_NAME"') == 2
    first, last = html.index('name="SERVER_NAME"'), html.rindex('name="SERVER_NAME"')
    assert html[:last].rstrip().endswith('<input type="hidden"')
    first_tag_end = html.index(">", first)
    assert "plugin-setting" in html[first:first_tag_end]


# --------------------------------------------------------------------------------------
# Fix round 4, F1 -- the real "ui" plugin shape (USE_UI declared as its own check-typed
# setting, same collision pattern as F2 above but for a checkbox rather than a text input).
# js/components/settings-widgets.js is not under a JS test harness in this repo (Prettier only,
# no Jest -- see src/ui/CLAUDE.md), so its behaviour is exercised with `node --check` for syntax
# only (tests/unit/ui/test_template_settings_page.py runs it, along with source assertions on
# the invariants it must keep); the ordering contract it depends on is asserted here, at the
# template level.
# --------------------------------------------------------------------------------------


def test_use_ui_checkbox_precedes_the_shells_hidden_fallback(render_plugin_page):
    """F1: USE_UI is type "check" (src/common/core/ui/plugin.json), so the body renders an
    editable checkbox for it in addition to the shell's unconditional hidden control input --
    both named "USE_UI". request.form.to_dict() keeps the FIRST value for a repeated field
    name, so the body's checkbox must render before the shell's hidden fallback for a typed
    change to survive at all; settings-widgets.js then relies on this same ordering to insert
    its own unchecked-box "no" fallback right after the checkbox (afterend), ahead of the hidden
    control input, instead of appending it at the end of the form.

    Asserted by position at both ends, not by `index < rindex` -- see the note on the SERVER_NAME
    test above for why that form cannot fail."""
    html = render_plugin_page(service_id="app.example.com", use_ui="yes", plugin_data=UI_PLUGIN_LIKE)
    assert html.count('name="USE_UI"') == 2
    first, last = html.index('name="USE_UI"'), html.rindex('name="USE_UI"')
    assert html[:last].rstrip().endswith('<input type="hidden"')
    first_tag_end = html.index(">", first)
    assert "plugin-setting" in html[first:first_tag_end]


# --- the multivalue hidden input's `pattern` on a resource-group setting ---------------------
# The template steps page validates .plugin-setting fields explicitly through
# `$input.attr("pattern")` (static/js/pages/template-settings-page.js), hidden inputs included.
# A resource-list setting's regex describes literal items only, so emitting it there made the
# picker's own `@alias` token permanently un-saveable on that page.


def _render_multivalue(setting, regex, kind):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(resource_kind_for_setting=lambda key: kind, _=lambda text, **kwargs: text)
    return env.get_template("models/multivalue_setting.html").render(
        setting=setting,
        setting_data={"id": setting.lower(), "regex": regex, "separator": " "},
        setting_value="",
        setting_default="",
        setting_config=None,
        setting_method="ui",
        setting_id_prefix="setting-x-",
        resource_groups={"g1": {"name": "office-eu", "entries": [{"kind": kind, "value": "1.2.3.4"}]}} if kind else {},
    )


def test_a_resource_group_setting_emits_no_narrow_pattern():
    html = _render_multivalue("BLACKLIST_IP", r"^( *([0-9.]+) *)*$", "ip")
    assert "pattern=" not in html
    assert 'value="@office-eu"' in html, "the picker that inserts @tokens must still be rendered"


def test_a_plain_multivalue_setting_keeps_its_pattern():
    html = _render_multivalue("DNS_RESOLVERS", r"^( *([0-9.]+) *)*$", None)
    assert 'pattern="^( *([0-9.]+) *)*$"' in html

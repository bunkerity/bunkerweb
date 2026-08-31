"""Plugin-supplied settings bodies: the hook, and antibot -- the first body to use it.

A plugin may replace the LAYOUT of its per-plugin settings form
(`templates/plugin_bodies/<id>.html`, resolved by `app.utils.plugin_settings_body`). It replaces
nothing else: the route, `postable_scope`, `restore_unowned_settings` and the writer are the
generic ones, so there is still exactly one settings save path in the UI. The design and the
options weighed are in `.cache/results-2026-08-24/plugin-pages-mechanism.md`.

Two properties are worth a test, and they are the two that fail silently:

**The hook is inert without a body.** Every plugin that ships no override must render exactly
what it rendered before the hook existed. `settings_body` is Undefined on any surface that does
not pass it, and Undefined must behave like None.

**A body HIDES a field, it never OMITS it.** `postable_scope` claims authority over every key the
form can send, and an in-scope key the POST does not carry has its row DELETED
(`db_methods/config_save.py:579-585`). A mode-driven page that rendered only the chosen
provider's fields would therefore destroy the operator's stored credentials for every other
provider on the first save -- the failure is invisible until they switch back and find the
secrets gone. `hidden` suppresses rendering only; the inputs still serialise. The biconditional
below is the same pin `test_compose_shelf.py::test_row_posts_exactly_the_declared_scope` puts on
the shelf, for the same reason.

The per-mode expectations are derived from `plugin.json` rather than hand-copied into a table:
a hand-written table is only ever as right as the day it was typed, and this file's whole job is
to catch the day the mapping and the manifest disagree.
"""

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from re import compile as compile_regex

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.utils import (
    get_blacklisted_settings,
    get_filtered_settings,
    get_multiples,
    is_editable_method,
    plugin_settings_body,
    plugin_settings_body_script,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import english  # noqa: E402
from test_save_scope import _import_services_module  # noqa: E402

postable_scope = _import_services_module().postable_scope

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "src" / "ui" / "app" / "templates"
CORE_PLUGINS = REPO_ROOT / "src" / "common" / "core"
STATIC = REPO_ROOT / "src" / "ui" / "app" / "static"

PLUGIN_TYPES = {
    "core": {"icon": "<i class='bx bx-cube'></i>", "text-class": " text-primary", "title-class": " border-primary"},
    "external": {"icon": "<i class='bx bx-cube'></i>", "text-class": "", "title-class": ""},
    "pro": {"icon": "", "text-class": "", "title-class": ""},
    "ui": {"icon": "", "text-class": "", "title-class": ""},
}

ANTIBOT = json.loads((CORE_PLUGINS / "antibot" / "plugin.json").read_text(encoding="utf-8")) | {"type": "core"}
ANTIBOT_SETTINGS = ANTIBOT["settings"]
MODES = ANTIBOT_SETTINGS["USE_ANTIBOT"]["select"]
CHALLENGE_MODES = [mode for mode in MODES if mode != "no"]

# The shared blocks, by the same reading of the runtime the page's own header cites:
# antibot.lua:169 (the five IGNORE_* lists), :180-194 (the two country lists), and the
# ANTIBOT_URI / TIME_* / SUCCESS_URI vars every provider's challenge page uses.
SHARED_WHEN_CHALLENGING = {
    "ANTIBOT_URI",
    "ANTIBOT_TIME_RESOLVE",
    "ANTIBOT_TIME_VALID",
    "ANTIBOT_SUCCESS_URI",
    "ANTIBOT_IGNORE_URI",
    "ANTIBOT_IGNORE_IP",
    "ANTIBOT_IGNORE_RDNS",
    "ANTIBOT_RDNS_GLOBAL",
    "ANTIBOT_IGNORE_ASN",
    "ANTIBOT_IGNORE_USER_AGENT",
}
# The two country lists live behind the picker, so they are shared-but-not-necessarily-visible.
COUNTRY_SETTINGS = {"ANTIBOT_IGNORE_COUNTRY", "ANTIBOT_ONLY_COUNTRY"}
# Named controls the PAGE owns rather than the plugin: the CSRF token (popped in the route,
# routes/services.py:1715) and the control keys the page must post itself whatever the plugin
# declares (models/save_scope.py:59). Neither is ever in `postable_scope`.
FORM_ONLY = {"csrf_token", "SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "USE_UI"}
# reCAPTCHA is the one provider whose credential block is split by a second switch
# (antibot.lua:769-819): SITEKEY and SCORE are live in both editions, SECRET only in classic,
# PROJECT_ID / API_KEY / JA3 / JA4 only in Enterprise.
RECAPTCHA_BOTH = {"ANTIBOT_RECAPTCHA_CLASSIC", "ANTIBOT_RECAPTCHA_SITEKEY", "ANTIBOT_RECAPTCHA_SCORE"}
RECAPTCHA_CLASSIC_ONLY = {"ANTIBOT_RECAPTCHA_SECRET"}
RECAPTCHA_ENTERPRISE_ONLY = {"ANTIBOT_RECAPTCHA_PROJECT_ID", "ANTIBOT_RECAPTCHA_API_KEY", "ANTIBOT_RECAPTCHA_JA3", "ANTIBOT_RECAPTCHA_JA4"}


def _provider_settings(mode):
    """Every declared key that belongs to `mode`, derived from the manifest.

    `ANTIBOT_<MODE>_*` is the shipped naming convention for a provider's credentials, and
    `captcha`'s single ANTIBOT_CAPTCHA_ALPHABET follows it too. Deriving instead of listing is
    what makes this a check rather than a second copy of the template's own table.
    """
    prefix = f"ANTIBOT_{mode.upper()}_"
    return {key for key in ANTIBOT_SETTINGS if key.startswith(prefix)}


class _Form(HTMLParser):
    """Which named controls a rendered form would serialise, and which are on screen.

    A control posts unless it is `disabled`; it is on screen unless it or an ancestor carries
    `hidden`. Those are the two distinctions the whole design rests on, so the parser tracks
    exactly them and nothing else.
    """

    VOID = {"input", "br", "img", "hr", "meta", "link", "source", "col"}

    def __init__(self):
        super().__init__()
        self._open = []
        self._hidden_depth = 0
        self.controls = []  # (name, hidden, disabled)
        self.groups = []  # (group id, modes attr, classic attr, hidden)  -- antibot
        self.body_groups = []  # (group id, effectively hidden)  -- modsecurity, headers
        self.hideable = []  # (tag, class list) for every element that can be taken off screen

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        hidden = "hidden" in attributes
        if attributes.get("data-antibot-group") is not None:
            self.groups.append((attributes["data-antibot-group"], attributes.get("data-antibot-modes"), attributes.get("data-antibot-classic"), hidden))
        # The same idea for the bodies that came after antibot, but ancestor-aware: modsecurity
        # and headers nest a note INSIDE the group it belongs to, so a note whose own `when` holds
        # is still off screen when its section is hidden. `_hidden_depth` counts ancestors only at
        # this point (self is pushed below), so `hidden or depth` is exactly "effectively hidden".
        for marker in ("data-modsec-group", "data-headers-group"):
            if attributes.get(marker) is not None:
                self.body_groups.append((attributes[marker], hidden or self._hidden_depth > 0))
        # Every element the page can take off screen: one that is hidden right now, or one a
        # `when` term can hide later. Both are checked for the CSS trap below, because an element
        # that is visible in this render is the one a switch is about to try to hide.
        conditioned = any(name.endswith("-when") and name.startswith("data-") for name in attributes)
        if hidden or conditioned:
            self.hideable.append((tag, (attributes.get("class") or "").split()))
        if tag not in self.VOID:
            self._open.append((tag, hidden))
            if hidden:
                self._hidden_depth += 1
        if tag in ("input", "select", "textarea") and "name" in attributes:
            self.controls.append((attributes["name"], hidden or self._hidden_depth > 0, "disabled" in attributes))

    def handle_endtag(self, tag):
        while self._open:
            open_tag, hidden = self._open.pop()
            if hidden:
                self._hidden_depth -= 1
            if open_tag == tag:
                break

    @property
    def posted(self):
        return {name for name, _hidden, disabled in self.controls if not disabled}

    @property
    def visible(self):
        return {name for name, hidden, disabled in self.controls if not hidden and not disabled}

    @property
    def visible_groups(self):
        return {group for group, _modes, _classic, hidden in self.groups if not hidden}

    @property
    def visible_body_groups(self):
        return {group for group, hidden in self.body_groups if not hidden}

    @property
    def all_body_groups(self):
        return {group for group, _hidden in self.body_groups}


def _parse(html):
    parser = _Form()
    parser.feed(html)
    return parser


@pytest.fixture
def render_page():
    """`plugin_settings_page.html` off a standalone env -- the fixture in
    test_plugin_settings_page.py, extended with the `settings_body` the hook adds. dashboard.html
    is stubbed down to its two blocks for the same reason it is there."""
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
                FileSystemLoader(str(TEMPLATES)),
            ]
        ),
        autoescape=True,
    )

    def _url_for(endpoint, **kwargs):
        if endpoint == "static" and "filename" in kwargs:
            return f"/static/{kwargs['filename']}"
        # Leftover kwargs become a query string, which is what Flask does with any argument the
        # rule does not consume. modsecurity's tuning band deep-links into /configs with the
        # config type pre-chosen (`?service=&type=MODSEC_CRS`, routes/configs.py:245-247), and a
        # stub that dropped them would let all four links render identically and still pass.
        query = "&".join(f"{key}={value}" for key, value in kwargs.items())
        return f"/{endpoint}?{query}" if query else f"/{endpoint}"

    env.globals.update(
        csrf_token=lambda: "test-csrf-token",
        url_for=_url_for,
        get_blacklisted_settings=get_blacklisted_settings,
        get_filtered_settings=get_filtered_settings,
        get_multiples=get_multiples,
        is_editable_method=is_editable_method,
        plugin_types=PLUGIN_TYPES,
        resource_kind_for_setting=lambda *_: None,
    )

    def _render(plugin_data, *, config=None, service_id="app.example.com", is_readonly=False, settings_body=..., settings_body_script=...):
        plugin = plugin_data["id"]
        kwargs = {}
        # `...` means "do not pass it at all", which is how every surface that predates the hook
        # renders this page -- the Undefined case the inertness test needs.
        if settings_body is not ...:
            kwargs["settings_body"] = settings_body
        if settings_body_script is not ...:
            kwargs["settings_body_script"] = settings_body_script
        return env.get_template("plugin_settings_page.html").render(
            plugin=plugin,
            plugin_data=plugin_data,
            config=config or {},
            service_id=service_id,
            clone=None,
            is_readonly=is_readonly,
            user_readonly=False,
            script_nonce="n",
            style_nonce="n",
            **kwargs,
        )

    return _render


def _antibot_config(mode="no", classic="yes", overrides=None, method="ui"):
    """Every declared antibot key stored, so `postable_scope` sees real rows -- the shape
    `API_CLIENT.get_service(full=True, methods=True)` returns."""
    config = {key: {"value": data.get("default", ""), "method": method, "global": False, "template": ""} for key, data in ANTIBOT_SETTINGS.items()}
    config["USE_ANTIBOT"]["value"] = mode
    config["ANTIBOT_RECAPTCHA_CLASSIC"]["value"] = classic
    for key, value in (overrides or {}).items():
        config[key]["value"] = value
    config |= {
        "SERVER_NAME": {"value": "app.example.com", "method": "ui"},
        "IS_DRAFT": {"value": "no", "method": "ui"},
        "USE_TEMPLATE": {"value": "", "method": "ui"},
        "USE_UI": {"value": "no", "method": "ui"},
    }
    return config


def _core_manifests():
    plugins = {}
    for path in sorted(CORE_PLUGINS.glob("*/plugin.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        plugins[manifest.get("id") or path.parent.name] = manifest | {"type": "core", "id": manifest.get("id") or path.parent.name}
    return plugins


CORE_MANIFESTS = _core_manifests()


# --------------------------------------------------------------------------------------
# The hook itself
# --------------------------------------------------------------------------------------


def test_only_the_plugins_that_ship_a_body_resolve_one():
    """The helper is a membership check over what actually ships, not a path built from the URL
    segment -- `plugin` reaches these routes as a raw path segment."""
    assert plugin_settings_body("antibot") == "plugin_bodies/antibot.html"
    assert (TEMPLATES / "plugin_bodies" / "antibot.html").is_file()
    for plugin in CORE_MANIFESTS:
        expected = f"plugin_bodies/{plugin}.html" if (TEMPLATES / "plugin_bodies" / f"{plugin}.html").is_file() else None
        assert plugin_settings_body(plugin) == expected, plugin
    assert plugin_settings_body("../../etc/passwd") is None
    assert plugin_settings_body("nope") is None


def test_a_body_script_is_only_claimed_when_it_ships():
    """A body that needs no JS must not put a 404 <script> on the page."""
    assert plugin_settings_body_script("antibot") == "js/plugin_bodies/antibot.js"
    assert (STATIC / "js" / "plugin_bodies" / "antibot.js").is_file()
    assert plugin_settings_body_script("nope") is None


@pytest.mark.parametrize("plugin", sorted(plugin for plugin in CORE_MANIFESTS if plugin_settings_body(plugin) is None))
def test_the_hook_is_inert_for_a_plugin_with_no_body(plugin, render_page):
    """A plugin without an override still renders the generic grid, and the three falsy forms of
    `settings_body` -- Undefined, None, "" -- are interchangeable.

    Undefined is the one that matters: any surface rendering this page without passing the kwarg
    gets it, and Jinja's Undefined is falsy but not None, so a gate written as `is not none` would
    silently take the override branch and blow up on `{% include Undefined %}`.

    What this does NOT claim is that the page is byte-identical to its pre-hook self. It is not:
    the `{% if settings_body %}` split and the script block add 3 whitespace-only lines, 23 bytes
    per render (measured over all 45 core plugins x both scopes x readonly on/off -- 180/180
    differ, 180/180 whitespace-only, same DOM). The move that IS byte-identical is the field
    partial's, and it is pinned separately.

    Byte equality across the three falsy forms, over every shipped core manifest rather than a
    spot check -- the gate sits directly around the generic include, so a mistake there is a
    mistake on 44 pages at once.
    """
    manifest = CORE_MANIFESTS[plugin]
    config = {key: {"value": data.get("default", ""), "method": "ui", "global": False, "template": ""} for key, data in manifest.get("settings", {}).items()}
    undefined = render_page(manifest, config=config)
    assert undefined == render_page(manifest, config=config, settings_body=None, settings_body_script=None)
    assert undefined == render_page(manifest, config=config, settings_body="", settings_body_script="")
    assert "plugin_bodies/" not in undefined


def test_the_generic_page_still_loads_only_the_shared_widget_bundle(render_page):
    html = render_page(CORE_MANIFESTS["misc"], config={})
    assert "/static/js/components/settings-widgets.js" in html
    assert "js/plugin_bodies/" not in html


def test_a_body_pulls_in_its_own_script_after_the_shared_bundle(render_page):
    html = render_page(
        ANTIBOT | {"id": "antibot"}, config=_antibot_config(), settings_body="plugin_bodies/antibot.html", settings_body_script="js/plugin_bodies/antibot.js"
    )
    assert html.index("/static/js/components/settings-widgets.js") < html.index("/static/js/plugin_bodies/antibot.js")


# --------------------------------------------------------------------------------------
# EVERY shipped body, not just antibot
# --------------------------------------------------------------------------------------

# Parametrized over what is on disk rather than over a list someone has to remember to extend,
# the same shape test_every_plugin_body_script_the_page_can_ask_for_is_on_disk uses. Adding
# templates/plugin_bodies/<id>.html is all a future lane has to do to inherit the checks below.
SHIPPED_BODIES = sorted(path.stem for path in (TEMPLATES / "plugin_bodies").glob("*.html"))


def test_the_body_scan_is_not_vacuous():
    """Every check below is parametrized over SHIPPED_BODIES. An empty glob would turn all of
    them into zero test cases and the file would still report green."""
    assert SHIPPED_BODIES, "no plugin body was found -- every parametrized check below is vacuous"
    assert set(SHIPPED_BODIES) <= set(CORE_MANIFESTS), f"a body has no core manifest: {sorted(set(SHIPPED_BODIES) - set(CORE_MANIFESTS))}"


def _stored_config(settings, method="ui"):
    """Every declared setting stored at its default -- the shape a real page renders from."""
    return {key: {"value": data.get("default", ""), "method": method, "global": False, "template": ""} for key, data in settings.items()}


def _switch_values(settings):
    """One variation per (setting, value) that can make a body change what it renders.

    Every option of every `select`, and both values of every `check`, ONE AT A TIME. A body's
    "mode" is always one of those -- antibot's is USE_ANTIBOT plus the ANTIBOT_RECAPTCHA_CLASSIC
    checkbox -- but which one it is is the body's business, not this test's. Varying one at a
    time keeps this linear (13 variations for antibot) instead of combinatorial, and still
    exercises every branch a body can key off, which is what the biconditional below needs.
    """
    variations = [(None, None)]
    for key, data in settings.items():
        if data.get("multiple"):
            continue
        if data.get("type") == "select":
            variations.extend((key, option) for option in data.get("select", []))
        elif data.get("type") == "check":
            variations.extend((key, value) for value in ("yes", "no"))
    return variations


@pytest.mark.parametrize("plugin", SHIPPED_BODIES)
@pytest.mark.parametrize("global_page", [False, True], ids=["service", "global"])
def test_every_shipped_body_posts_exactly_the_declared_scope(plugin, global_page, render_page):
    """THE contract every plugin body owes, checked for all of them.

    `postable_scope` claims authority over every key the form can send, and an in-scope key the
    POST does not carry has its row DELETED (db_methods/config_save.py:579-585). So a body must
    HIDE a field it does not want on screen, never omit it -- and it must keep doing that in
    every state its own mode switch can reach, which is why this walks every select option and
    every checkbox value rather than rendering the default once.

    Under-claiming is safe (the key is merely preserved), over-claiming destroys data, so the
    assertion is equality modulo the keys the PAGE owns rather than the plugin (`FORM_ONLY`).
    """
    manifest = CORE_MANIFESTS[plugin]
    settings = manifest.get("settings") or {}
    blacklisted = get_blacklisted_settings(global_page)

    for switch, value in _switch_values(settings):
        config = _stored_config(settings)
        if switch is not None:
            config[switch]["value"] = value
        html = render_page(manifest, config=config, service_id="" if global_page else "app.example.com", settings_body=f"plugin_bodies/{plugin}.html")
        scope = postable_scope(manifest, config, global_page=global_page, is_pro_version=False, blacklisted=blacklisted)
        posted = _parse(html).posted

        where = (
            f"{plugin} [{'global' if global_page else 'service'}] with {switch}={value}"
            if switch
            else f"{plugin} [{'global' if global_page else 'service'}] at defaults"
        )
        assert scope - posted == set(), f"{where}: in scope but never posted -> these rows are DELETED on save: {sorted(scope - posted)}"
        assert posted - scope - FORM_ONLY == set(), f"{where}: posted but not owned: {sorted(posted - scope - FORM_ONLY)}"


@pytest.mark.parametrize("plugin", SHIPPED_BODIES)
@pytest.mark.parametrize("global_page", [False, True], ids=["service", "global"])
def test_every_shipped_body_places_every_setting_it_declares(plugin, global_page, render_page):
    """No body may fall back on its own straggler block for a setting the manifest declares.

    A straggler still posts -- that is the point of the backstop -- but it renders outside every
    group, so it is a setting nobody laid out. Failing here is the signal to give it a home.

    BOTH scopes, because they see different sets. `get_filtered_settings` drops every
    `global`-context setting on a service page, so a service-only render cannot see a new global
    setting land unplaced -- which is exactly the shape of `USE_MODSECURITY_GLOBAL_CRS`, the one
    global setting any of these bodies declares today. A service-only check was green on a page
    that would have shown a stray field at /global-settings/plugins/<id>.
    """
    manifest = CORE_MANIFESTS[plugin]
    html = render_page(
        manifest,
        config=_stored_config(manifest.get("settings") or {}),
        service_id="" if global_page else "app.example.com",
        settings_body=f"plugin_bodies/{plugin}.html",
    )
    where = "global" if global_page else "service"
    assert (
        "data-plugin-body-unplaced" not in html
    ), f"{plugin} [{where}]: a declared setting is not placed in any group of templates/plugin_bodies/{plugin}.html"


@pytest.mark.parametrize("plugin", SHIPPED_BODIES)
def test_every_shipped_body_declares_no_multiple_setting_it_cannot_render(plugin):
    """A body renders its own fields, so it renders no `multiple` group unless it arranges to.

    `_in_scope` matches a stored `FOO_2` by its BASE name (models/save_scope.py:99-110), so the
    moment a body's plugin declares a `multiple` setting, every suffixed row is inside the
    declared scope -- and a body that renders none of them posts none of them, which deletes them
    all. Two ways to render them and both count: the body writes its own `get_multiples` loop, or
    it delegates to `models/plugin_settings_body.html`, which is the same loop the generic page
    uses and the same markup components/settings-widgets.js' cloner was written against
    (`plugin_bodies/headers.html` takes the second route, with `filtered_settings` narrowed to its
    `multiple` settings so only that half of the generic body renders).

    This is the cheap static half. The half that actually proves it is the render below.
    """
    settings = CORE_MANIFESTS[plugin].get("settings") or {}
    multiples = sorted(key for key, data in settings.items() if data.get("multiple"))
    body = (TEMPLATES / "plugin_bodies" / f"{plugin}.html").read_text(encoding="utf-8")
    if multiples:
        renders_multiples = "get_multiples" in body or "models/plugin_settings_body.html" in body
        assert renders_multiples, f"{plugin} declares {multiples} but its body renders no multiples loop -- every suffixed row would be deleted on save"


def _with_suffixed_rows(settings, count=2):
    """Every declared setting stored at its default, plus `count` suffixed rows per `multiple`.

    The shape a service that has been used looks like: an operator who added two custom headers
    has CUSTOM_HEADER (suffix 0), CUSTOM_HEADER_1 and CUSTOM_HEADER_2 stored.
    """
    config = _stored_config(settings)
    for key, data in settings.items():
        if not data.get("multiple"):
            continue
        for suffix in range(1, count + 1):
            config[f"{key}_{suffix}"] = {"value": f"stored-{key}-{suffix}", "method": "ui", "global": False, "template": ""}
    return config


@pytest.mark.parametrize("plugin", SHIPPED_BODIES)
@pytest.mark.parametrize("global_page", [False, True], ids=["service", "global"])
def test_every_shipped_body_renders_the_suffixed_rows_it_declares(plugin, global_page, render_page):
    """The `multiple` half of hide-never-omit, proven by rendering rather than by grepping.

    `postable_scope` walks the STORED config, so a stored CUSTOM_HEADER_2 is in scope by its own
    name (routes/services.py:1023-1030) -- and an in-scope key the POST does not carry has its row
    DELETED (db_methods/config_save.py:579-585). A body that renders the base field and no cloner
    therefore deletes every custom header past the first the first time the operator saves
    anything else on the page, and nothing tells them until the header stops being sent.

    Vacuous for a plugin with no `multiple` setting, which is most of them -- guarded by the
    non-vacuity assertion in ::test_at_least_one_shipped_body_has_suffixed_rows_to_lose.
    """
    manifest = CORE_MANIFESTS[plugin]
    settings = manifest.get("settings") or {}
    config = _with_suffixed_rows(settings)
    blacklisted = get_blacklisted_settings(global_page)

    html = render_page(manifest, config=config, service_id="" if global_page else "app.example.com", settings_body=f"plugin_bodies/{plugin}.html")
    scope = postable_scope(manifest, config, global_page=global_page, is_pro_version=False, blacklisted=blacklisted)
    posted = _parse(html).posted

    where = f"{plugin} [{'global' if global_page else 'service'}]"
    assert scope - posted == set(), f"{where}: in scope but never posted -> these rows are DELETED on save: {sorted(scope - posted)}"
    assert posted - scope - FORM_ONLY == set(), f"{where}: posted but not owned: {sorted(posted - scope - FORM_ONLY)}"
    # And the stored VALUES come back out, not just the names -- a cloner that rendered two empty
    # rows would satisfy the biconditional above and still wipe both headers.
    for key in config:
        if key.rsplit("_", 1)[-1].isdigit() and key.rsplit("_", 1)[0] in settings:
            assert config[key]["value"] in html, f"{where}: {key} renders no input carrying its stored value"


# Bootstrap's display utilities, every one of which DEFEATS the `hidden` attribute. `[hidden]`
# is an attribute selector, specificity (0,1,0); each of these is a single class, also (0,1,0);
# all of them are `!important`. Equal specificity, equal importance -- so the LATER declaration in
# the sheet wins, and every one of these is declared after `[hidden]`:
#   css/core.css:532    [hidden]        { display: none !important }
#   css/core.css:7593   .btn            { display: inline-flex !important }
#   css/core.css:10672  .d-block        { display: block !important }
#   css/core.css:10676  .d-grid         { display: grid !important }
#   css/core.css:10692  .d-flex         { display: flex !important }
#   css/core.css:10696  .d-inline-flex  { display: inline-flex !important }
# `.d-none` (:10700) is the one that still wins, which is why it is the permitted escape hatch.
DISPLAY_UTILITIES = frozenset({"btn", "d-block", "d-grid", "d-flex", "d-inline-flex", "d-inline", "d-inline-block", "d-table", "d-table-row", "d-table-cell"})


@pytest.mark.parametrize("plugin", SHIPPED_BODIES)
@pytest.mark.parametrize("global_page", [False, True], ids=["service", "global"])
def test_a_hideable_element_never_carries_a_display_utility(plugin, global_page, render_page):
    """`hidden` is not a hiding mechanism on an element with a Bootstrap display class.

    This is the bug the rest of this file could not see. Every other check here reads the
    ATTRIBUTE (`_Form.handle_starttag`: `hidden = "hidden" in attributes`), so a body that put
    `hidden` on a `d-flex` alert passed every visibility test while rendering the alert at full
    height in a browser. On modsecurity's shipped defaults that meant four mutually contradictory
    banners on screen at once -- "ModSecurity is off", "loaded and inspects nothing",
    "DetectionOnly", "CRS 3 cannot load plugins" -- none of them true. No data was at risk (the
    inputs were never in those alerts) but the page lied about the runtime, which is worse than
    the flat grid these bodies replace.

    The rule this pins is the cheap one: an element that can be taken off screen carries the
    layout classes on an INNER WRAPPER, never on itself. `.alert` and a bare `<span>` set no
    `display`, so `[hidden]` works on them.

    A future body that would rather keep the utility on the conditioned element has to toggle
    `d-none` beside `hidden` in BOTH the template and its script -- `.d-none` is declared last and
    beats them all. That is a deliberate relaxation with two places to keep in step; add the class
    to the allowance below only together with the script change, never to make this test pass.
    """
    manifest = CORE_MANIFESTS[plugin]
    settings = manifest.get("settings") or {}
    html = render_page(
        manifest,
        config=_with_suffixed_rows(settings),
        service_id="" if global_page else "app.example.com",
        settings_body=f"plugin_bodies/{plugin}.html",
    )
    offenders = [
        (tag, sorted(set(classes) & DISPLAY_UTILITIES))
        for tag, classes in _parse(html).hideable
        if (set(classes) & DISPLAY_UTILITIES) and "d-none" not in classes
    ]
    assert not offenders, (
        f"{plugin} [{'global' if global_page else 'service'}]: these elements can be hidden but carry a display "
        f"utility that outranks `[hidden]`, so they stay on screen: {offenders}"
    )


def test_the_display_utility_scan_is_not_vacuous(render_page):
    """The check above is worthless if nothing on these pages is hideable at all, or if the
    utility names stopped matching what the sheet declares."""
    hideable = 0
    for plugin in SHIPPED_BODIES:
        manifest = CORE_MANIFESTS[plugin]
        html = render_page(manifest, config=_stored_config(manifest.get("settings") or {}), settings_body=f"plugin_bodies/{plugin}.html")
        hideable += len(_parse(html).hideable)
    assert hideable, "no shipped body renders a single hideable element -- the scan above proves nothing"

    css = (STATIC / "css" / "core.css").read_text(encoding="utf-8")
    for utility in ("btn", "d-flex", "d-none"):
        assert f".{utility} {{" in css, f".{utility} is no longer declared in core.css"
    assert "[hidden] {" in css
    # And `[hidden]` really is declared before the utilities that beat it -- the whole reason the
    # rule exists. If someone ever moves it last, this fails and the rule can be reconsidered.
    assert css.index("[hidden] {") < css.index(".d-flex {"), "[hidden] now wins on order -- revisit test_a_hideable_element_never_carries_a_display_utility"


def test_at_least_one_shipped_body_has_suffixed_rows_to_lose():
    """The check above is a no-op for a plugin that declares no `multiple` setting. Say out loud
    that at least one shipped body is actually exercising it, so the day the only such body is
    removed the coverage loss is visible instead of silent."""
    with_multiples = [plugin for plugin in SHIPPED_BODIES if any(data.get("multiple") for data in (CORE_MANIFESTS[plugin].get("settings") or {}).values())]
    assert with_multiples, "no shipped body declares a `multiple` setting -- the suffixed-row check above proves nothing"


def test_the_shared_bundle_reveals_a_hidden_invalid_control():
    """A hidden control failing its own `pattern=` makes the browser refuse to submit, fail to
    focus the offender, and log to the console only: Save does nothing and says nothing.

    The reveal lives in the SHARED bundle so every body inherits it -- pinning it here rather
    than in each body's script is the difference between a rule and a mechanism. Capture phase
    is load-bearing: `invalid` does not bubble.
    """
    bundle = (STATIC / "js" / "components" / "settings-widgets.js").read_text(encoding="utf-8")
    assert 'addEventListener(\n      "invalid"' in bundle or '"invalid"' in bundle, "the shared bundle no longer listens for invalid"
    start = bundle.index('"invalid"')
    handler = bundle[start:][:900]
    assert 'removeAttribute("hidden")' in handler, "the invalid handler no longer unhides the offending control"
    assert "true," in handler or "true)" in handler, "the invalid listener must be registered in the CAPTURE phase -- invalid does not bubble"


# --------------------------------------------------------------------------------------
# antibot: hide, never omit
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("classic", ["yes", "no"])
def test_antibot_body_posts_exactly_the_declared_scope(mode, classic, render_page):
    """The biconditional, in both directions, for every mode the picker offers.

    Over-claiming is silent data loss; under-claiming only preserves. Asserting equality catches
    both. The keys that must survive here are the OTHER providers' credentials -- the ones the
    page is deliberately not showing.
    """
    config = _antibot_config(mode=mode, classic=classic)
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, settings_body="plugin_bodies/antibot.html")
    scope = postable_scope(ANTIBOT, config, global_page=False, is_pro_version=False, blacklisted=get_blacklisted_settings())

    posted = _parse(html).posted
    assert scope - posted == set(), f"in scope but never posted -> these rows are DELETED on save: {sorted(scope - posted)}"
    assert posted - scope - FORM_ONLY == set(), f"posted but not owned: {sorted(posted - scope - FORM_ONLY)}"


@pytest.mark.parametrize("mode", MODES)
def test_every_other_providers_credentials_are_still_posted(mode, render_page):
    """The concrete version of the rule, spelled out because it is the whole point of the design:
    configure hCaptcha, switch the mode to Turnstile, save -- the hCaptcha keys must come back."""
    stored = {key: f"stored-{key}" for key in ANTIBOT_SETTINGS if key.endswith(("_SITEKEY", "_SECRET", "_API_KEY", "_PROJECT_ID"))}
    config = _antibot_config(mode=mode, overrides=stored)
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, settings_body="plugin_bodies/antibot.html")

    posted = _parse(html).posted
    assert set(stored) <= posted
    for key, value in stored.items():
        assert value in html, key


def test_no_declared_antibot_setting_is_left_unplaced(render_page):
    """The body lays its fields out group by group. A setting added to the manifest and forgotten
    here still posts (the straggler block below the groups renders it), but that block is a
    backstop, not a home -- if it fires, the new setting needs a real group."""
    html = render_page(ANTIBOT | {"id": "antibot"}, config=_antibot_config(mode="captcha"), settings_body="plugin_bodies/antibot.html")
    assert "data-plugin-body-unplaced" not in html, "an antibot setting is not placed in any group of templates/plugin_bodies/antibot.html"


# --------------------------------------------------------------------------------------
# antibot: what each mode shows
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_a_mode_shows_its_own_provider_fields_and_no_other(mode, render_page):
    """The reason the page exists: the flat form showed 8 reCAPTCHA fields, 6 provider password
    fields and no hint which of them were live.

    The expectation is derived from the manifest's `ANTIBOT_<MODE>_*` naming, so a provider added
    to `USE_ANTIBOT`'s select without a group in the body fails here rather than rendering an
    invisible credential block.
    """
    config = _antibot_config(mode=mode, classic="yes")
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, settings_body="plugin_bodies/antibot.html")
    visible = _parse(html).visible

    mine = _provider_settings(mode)
    if mode == "recaptcha":
        mine = RECAPTCHA_BOTH | RECAPTCHA_CLASSIC_ONLY
    others = set()
    for other in CHALLENGE_MODES:
        if other != mode:
            others |= _provider_settings(other)
    others -= mine

    assert mine <= visible, f"{mode}: its own fields are not on screen: {sorted(mine - visible)}"
    assert not (others & visible), f"{mode}: another provider's fields are on screen: {sorted(others & visible)}"

    shared_expected = SHARED_WHEN_CHALLENGING if mode != "no" else set()
    assert shared_expected <= visible
    if mode == "no":
        assert visible & set(ANTIBOT_SETTINGS) == {"USE_ANTIBOT"}, "nothing but the mode picker belongs on screen while antibot is off"


@pytest.mark.parametrize(
    "classic,expected,forbidden",
    [
        ("yes", RECAPTCHA_CLASSIC_ONLY, RECAPTCHA_ENTERPRISE_ONLY),
        ("no", RECAPTCHA_ENTERPRISE_ONLY, RECAPTCHA_CLASSIC_ONLY),
    ],
)
def test_the_recaptcha_sub_toggle_swaps_its_two_field_sets(classic, expected, forbidden, render_page):
    """`ANTIBOT_RECAPTCHA_CLASSIC` picks the verification endpoint, and the two endpoints take
    disjoint credentials (antibot.lua:769-819). SITEKEY and SCORE are live either way."""
    config = _antibot_config(mode="recaptcha", classic=classic)
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, settings_body="plugin_bodies/antibot.html")
    parsed = _parse(html)

    assert expected <= parsed.visible
    assert not (forbidden & parsed.visible)
    assert RECAPTCHA_BOTH <= parsed.visible
    # And the hidden half still posts -- switching editions must not lose the other one's keys.
    assert forbidden <= parsed.posted


def test_the_mode_picker_offers_every_declared_mode(render_page):
    html = render_page(ANTIBOT | {"id": "antibot"}, config=_antibot_config(), settings_body="plugin_bodies/antibot.html")
    for mode in MODES:
        assert f'value="{mode}"' in html, mode


# --------------------------------------------------------------------------------------
# antibot: the country picker
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides,on_screen,off_screen",
    [
        ({}, set(), COUNTRY_SETTINGS),
        ({"ANTIBOT_IGNORE_COUNTRY": "FR DE"}, {"ANTIBOT_IGNORE_COUNTRY"}, {"ANTIBOT_ONLY_COUNTRY"}),
        ({"ANTIBOT_ONLY_COUNTRY": "US"}, {"ANTIBOT_ONLY_COUNTRY"}, {"ANTIBOT_IGNORE_COUNTRY"}),
        ({"ANTIBOT_IGNORE_COUNTRY": "FR", "ANTIBOT_ONLY_COUNTRY": "US"}, {"ANTIBOT_ONLY_COUNTRY"}, {"ANTIBOT_IGNORE_COUNTRY"}),
    ],
)
def test_the_country_picker_opens_on_whichever_list_is_stored(overrides, on_screen, off_screen, render_page):
    config = _antibot_config(mode="captcha", overrides=overrides)
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, settings_body="plugin_bodies/antibot.html")
    parsed = _parse(html)

    assert on_screen <= parsed.visible
    assert not (off_screen & parsed.visible)
    assert COUNTRY_SETTINGS <= parsed.posted, "a hidden country list must still post -- hiding is not clearing"


def test_both_country_lists_stored_says_so(render_page):
    """antibot.lua:1198-1203 ORs the two lists; the picker can only show one, so the page has to
    say the other is still live rather than imply it is empty."""
    both = render_page(
        ANTIBOT | {"id": "antibot"},
        config=_antibot_config(mode="captcha", overrides={"ANTIBOT_IGNORE_COUNTRY": "FR", "ANTIBOT_ONLY_COUNTRY": "US"}),
        settings_body="plugin_bodies/antibot.html",
    )
    one = render_page(
        ANTIBOT | {"id": "antibot"},
        config=_antibot_config(mode="captcha", overrides={"ANTIBOT_ONLY_COUNTRY": "US"}),
        settings_body="plugin_bodies/antibot.html",
    )
    assert 'role="alert"' in both
    assert 'role="alert"' not in one


def test_the_country_picker_posts_nothing_of_its_own(render_page):
    """It is a client-side control. Giving it a `name` would push a key the plugin never declared
    into `request.form.to_dict()`, and every route would have to learn to pop it."""
    html = render_page(ANTIBOT | {"id": "antibot"}, config=_antibot_config(mode="captcha"), settings_body="plugin_bodies/antibot.html")
    start = html.index('id="antibot-country-mode"')
    picker = html[start:][:400]
    assert "name=" not in picker
    assert set(_parse(html).posted) <= set(ANTIBOT_SETTINGS) | FORM_ONLY


# --------------------------------------------------------------------------------------
# antibot: read-only
# --------------------------------------------------------------------------------------


def test_readonly_disables_every_control_and_empties_the_scope(render_page):
    """`postable_scope` short-circuits to the empty set when the page rendered read-only, so the
    form must post nothing -- at global scope a read-only POST that still claimed the scope would
    wipe the plugin's whole configuration (routes/global_settings.py:257-263)."""
    config = _antibot_config(mode="recaptcha")
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, is_readonly=True, settings_body="plugin_bodies/antibot.html")

    assert postable_scope(ANTIBOT, config, global_page=False, is_pro_version=False, blacklisted=get_blacklisted_settings(), is_readonly=True) == set()
    enabled = {name for name, _hidden, disabled in _parse(html).controls if not disabled} - FORM_ONLY
    assert enabled == set(), f"read-only page still posts: {sorted(enabled)}"


# --------------------------------------------------------------------------------------
# antibot: the body and its script must agree
# --------------------------------------------------------------------------------------

# Every hook static/js/plugin_bodies/antibot.js reaches for, and where it has to exist. A
# selector that stops matching is the quietest failure this page has: the markup renders, the
# fields are all there, and only the liveness is gone -- exactly the class of bug a browser check
# would find and a unit suite normally would not. Naming the pairs is what makes it findable.
JS_HOOKS = [
    # (label, what the SCRIPT must contain, what the MARKUP must contain, where the markup is)
    ("the form", "form[data-plugin-settings-form]", "data-plugin-settings-form", "page"),
    ("the mode picker", "select[name='USE_ANTIBOT']", 'name="USE_ANTIBOT"', "page"),
    ("the classic/Enterprise switch", "input[name='ANTIBOT_RECAPTCHA_CLASSIC']", 'name="ANTIBOT_RECAPTCHA_CLASSIC"', "page"),
    ("the group marker", "[data-antibot-group]", "data-antibot-group=", "page"),
    ("the per-mode visibility attribute", "antibotModes", "data-antibot-modes=", "page"),
    ("the reCAPTCHA edition attribute", "antibotClassic", "data-antibot-classic=", "page"),
    ("the country picker", "[data-antibot-country-mode]", "data-antibot-country-mode", "page"),
    ("the country list wrappers", "[data-antibot-country-list]", "data-antibot-country-list=", "page"),
    # Owned by models/multiselect_setting.html, not by this body: the script clears a country
    # list by unchecking its option boxes and firing one `change`, which is the shared widget's
    # own bookkeeping path (settings-widgets.js:1584-1593 -> updateMultiselectDisplay).
    ("the multiselect option boxes", ".multiselect-options input[type='checkbox']", "multiselect-options", "widget"),
]


@pytest.mark.parametrize("label,in_script,in_markup,where", JS_HOOKS, ids=[hook[0] for hook in JS_HOOKS])
def test_every_hook_the_body_script_reaches_for_exists(label, in_script, in_markup, where, render_page):
    script = (STATIC / "js" / "plugin_bodies" / "antibot.js").read_text(encoding="utf-8")
    assert in_script in script, f"{label}: the script no longer uses {in_script}"

    if where == "page":
        markup = render_page(ANTIBOT | {"id": "antibot"}, config=_antibot_config(mode="recaptcha"), settings_body="plugin_bodies/antibot.html")
    else:
        markup = (TEMPLATES / "models" / "multiselect_setting.html").read_text(encoding="utf-8")
    assert in_markup in markup, f"{label}: the script looks for {in_script} and nothing renders {in_markup}"


def test_the_body_script_never_disables_or_detaches_a_field():
    """The one thing the script must never do. Clearing, disabling or removing an input stops it
    posting while its key stays in `postable_scope`, which deletes the row. Hiding is the only
    permitted way to take a group off screen."""
    script = (STATIC / "js" / "plugin_bodies" / "antibot.js").read_text(encoding="utf-8")
    for forbidden in (".remove()", ".disabled = true", 'removeAttribute("name")', '.value = ""', "detach("):
        assert forbidden not in script, f"the body script does {forbidden}, which stops a field posting"


def test_the_body_renders_at_global_scope_too(render_page):
    """One body, both routes -- /global-settings/plugins/antibot renders the same file with no
    service id, and every antibot setting is multisite so all 33 are in play there as well."""
    config = _antibot_config(mode="hcaptcha")
    html = render_page(ANTIBOT | {"id": "antibot"}, config=config, service_id="", settings_body="plugin_bodies/antibot.html")
    assert set(ANTIBOT_SETTINGS) <= _parse(html).posted
    assert "OLD_SERVER_NAME" not in html, "the global page must not post the service list"


# --------------------------------------------------------------------------------------
# access control: blacklist + whitelist + greylist + country
# --------------------------------------------------------------------------------------
#
# Four plugins decide one thing -- who gets in -- through 50 settings the generic grid rendered as
# four undifferentiated columns. They stay FOUR pages because a per-plugin settings page may only
# post its own plugin's keys (`postable_scope` is built from the one `plugin_data` the route
# resolved), so what they share is layout and a read-only decision-order banner, never a control.
# Design and the alternatives weighed: .cache/results-2026-08-31/L3-pages-access-report.md.

ACCESS_CONTROL_BODIES = ("blacklist", "whitelist", "greylist", "country")
# The three that render the kind matrix. `country` is the fourth stage of the same decision but has
# no kinds of its own -- its two lists ARE the matching rule.
LIST_BODIES = ("blacklist", "whitelist", "greylist")
# The runtime's order, from core/order.json's `access` list (and its identical `preread` twin):
# ssl, whitelist, letsencrypt, blacklist, greylist, country. A whitelist match returns OK, which
# breaks the plugin loop in confs/server-http/access-lua.conf:184-192.
DECISION_ORDER = ("whitelist", "blacklist", "greylist", "country")


def _kinds_from_manifest(plugin):
    """The matching kinds the body must derive, computed here the way the template computes them.

    Derived on both sides rather than listed on either: the point of the check is that the template
    and the manifest agree, and a hand-copied {IP, RDNS, ASN, USER_AGENT, URI} would only ever be
    as right as the day it was typed.
    """
    prefix = plugin.upper()
    settings = CORE_MANIFESTS[plugin]["settings"]
    start = len(prefix) + 1
    return {
        key[start:]
        for key, data in settings.items()
        if data.get("type") == "multivalue" and key.startswith(f"{prefix}_") and not key.endswith("_URLS") and not key.startswith(f"{prefix}_IGNORE_")
    }


def _rendered_kinds(html):
    return {group.removeprefix("kind-") for group in _access_control_groups(html) if group.startswith("kind-")}


class _Groups(HTMLParser):
    """`data-access-control-group` ids in render order, and whether each is on screen."""

    def __init__(self):
        super().__init__()
        self.groups = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("data-access-control-group") is not None:
            self.groups.append((attributes["data-access-control-group"], "hidden" in attributes))


def _access_control_groups(html):
    parser = _Groups()
    parser.feed(html)
    return [group for group, _hidden in parser.groups]


def _section_of(html, group):
    """The markup of one `data-access-control-group`, up to the next one.

    A slice rather than a parser: the sections are siblings by construction (no group nests inside
    another), so "from this marker to the next marker" is exactly the section.
    """
    start = html.index(f'data-access-control-group="{group}"')
    rest = html.find("data-access-control-group=", start + 1)
    end = rest if rest != -1 else len(html)
    return html[start:end]


def _render_body(plugin, render_page, *, overrides=None, **kwargs):
    manifest = CORE_MANIFESTS[plugin]
    config = _stored_config(manifest["settings"])
    for key, value in (overrides or {}).items():
        config[key]["value"] = value
    return render_page(manifest, config=config, settings_body=f"plugin_bodies/{plugin}.html", **kwargs)


@pytest.mark.parametrize("plugin", ACCESS_CONTROL_BODIES)
def test_every_access_control_body_ships(plugin):
    """The four are one feature. A missing body means one page silently keeps the flat grid while
    its three siblings show the decision order, which is worse than none of them having it."""
    assert plugin_settings_body(plugin) == f"plugin_bodies/{plugin}.html"
    assert plugin in SHIPPED_BODIES


@pytest.mark.parametrize("plugin", ACCESS_CONTROL_BODIES)
@pytest.mark.parametrize("global_page", [False, True], ids=["service", "global"])
def test_an_access_control_body_never_posts_a_key_outside_its_own_plugin(plugin, global_page, render_page):
    """The rule that keeps four pages honest instead of one page that writes four scopes.

    `test_every_shipped_body_posts_exactly_the_declared_scope` already asserts the biconditional
    against `postable_scope`; this states the half that the shared banner could break -- the banner
    names the other three plugins, and turning one of those names into a control would post a key
    the route never authorised. Asserted against the MANIFEST rather than the scope so it still
    holds if `postable_scope` ever widens.
    """
    manifest = CORE_MANIFESTS[plugin]
    html = _render_body(plugin, render_page, service_id="" if global_page else "app.example.com")
    posted = _parse(html).posted - FORM_ONLY

    assert posted <= set(manifest["settings"]), f"{plugin} posts keys it does not own: {sorted(posted - set(manifest['settings']))}"


@pytest.mark.parametrize("plugin", ACCESS_CONTROL_BODIES)
def test_every_access_control_body_shows_the_whole_decision_order(plugin, render_page):
    """The banner is the reason these four pages are worth writing: the order is the runtime's, not
    the sidebar's, and no page can be understood without the other three.

    A link, not a control -- pinned by the no-foreign-key test above."""
    html = _render_body(plugin, render_page)

    for stage in DECISION_ORDER:
        assert f'data-access-control-stage="{stage}"' in html, f"{plugin}: the banner does not name {stage}"
    assert html.index('data-access-control-stage="whitelist"') < html.index('data-access-control-stage="blacklist"')
    assert html.index('data-access-control-stage="blacklist"') < html.index('data-access-control-stage="greylist"')
    assert html.index('data-access-control-stage="greylist"') < html.index('data-access-control-stage="country"')


def test_the_decision_order_matches_the_runtime_not_the_sidebar():
    """The banner claims an order. This is what says the claim is still true.

    `order.json`'s `access` list is the authority; the four access-control plugins appear in it in
    exactly the sequence the banner draws, and `preread` (stream traffic) repeats it.
    """
    order = json.loads((CORE_PLUGINS / "order.json").read_text(encoding="utf-8"))

    for phase in ("access", "preread"):
        assert [plugin for plugin in order[phase] if plugin in DECISION_ORDER] == list(DECISION_ORDER), phase


@pytest.mark.parametrize("plugin", LIST_BODIES)
def test_the_access_control_matrix_derives_every_declared_kind(plugin, render_page):
    """One section per matching kind, and the set comes from the manifest.

    A kind added to blacklist/whitelist/greylist -- or one renamed -- must show up as its own
    section with its whole family. The body derives this; the day the derivation stops matching the
    manifest, a kind is either missing a section or has grown one that means nothing.
    """
    html = _render_body(plugin, render_page)
    expected = {kind.lower() for kind in _kinds_from_manifest(plugin)}

    assert expected, f"{plugin}: the manifest scan found no kind, so this check is vacuous"
    assert _rendered_kinds(html) == expected


@pytest.mark.parametrize("plugin", LIST_BODIES)
def test_every_kind_row_carries_its_whole_declared_family(plugin, render_page):
    """The matrix, in both directions: a kind's row shows the entries, the downloaded lists, the
    exceptions and the rDNS-global switch it declares -- and nothing that belongs to another kind.

    The family is derived from the naming convention the three manifests share, which is what makes
    `*_RDNS_GLOBAL` land on the rDNS row of all three without the template naming rDNS.
    """
    prefix = plugin.upper()
    settings = CORE_MANIFESTS[plugin]["settings"]
    html = _render_body(plugin, render_page)

    for kind in _kinds_from_manifest(plugin):
        family = {
            key
            for key in (f"{prefix}_{kind}", f"{prefix}_{kind}_URLS", f"{prefix}_IGNORE_{kind}", f"{prefix}_IGNORE_{kind}_URLS", f"{prefix}_{kind}_GLOBAL")
            if key in settings
        }
        assert len(family) >= 2, f"{plugin}/{kind}: a kind with no downloaded-list variant is not the shape this body assumes"
        # Inside THIS kind's own section, not merely somewhere on the page. The straggler backstop
        # renders an unplaced key too -- visibly, on purpose -- so a check that only asked "is it on
        # screen" would pass for a family member that fell out of the matrix and into the backstop,
        # which is exactly the regression this test is for.
        section = _section_of(html, f"kind-{kind.lower()}")
        # The LAST kind section slices to end of document, so it swallows the page-owned control
        # keys plugin_settings_page.html emits after the body. They are not the plugin's.
        inside = _parse(section).visible - FORM_ONLY

        assert family <= inside, f"{plugin}/{kind}: not in its own section: {sorted(family - inside)}"
        assert not (inside - family), f"{plugin}/{kind}: another kind's fields are in this section: {sorted(inside - family)}"


@pytest.mark.parametrize("plugin", LIST_BODIES)
def test_a_list_body_hides_nothing_so_every_field_is_reachable(plugin, render_page):
    """These three render no mode switch, so every field is on screen at once -- which is the
    property that lets an operator fill the lists BEFORE enforcement is turned on.

    That two-save order is not a preference: `models/config.py` refuses a save that flips
    USE_GREYLIST to `yes` while every greylist entry list is empty, so the entries have to be
    editable while the plugin is off.
    """
    html = _render_body(plugin, render_page, overrides={f"USE_{plugin.upper()}": "no"})
    parsed = _parse(html)

    assert set(CORE_MANIFESTS[plugin]["settings"]) <= parsed.visible


# --------------------------------------------------------------------------------------
# access control: the greylist lock-out warning
# --------------------------------------------------------------------------------------

GREYLIST_ENTRY_KEYS = sorted(key for key, data in CORE_MANIFESTS["greylist"]["settings"].items() if data.get("type") == "multivalue")


def test_the_greylist_entry_scan_is_not_vacuous():
    """The warning below keys off "no greylist entry anywhere". An empty key set would make it
    unreachable and the two tests after it would pass for the wrong reason."""
    assert GREYLIST_ENTRY_KEYS
    assert "GREYLIST_RDNS_GLOBAL" not in GREYLIST_ENTRY_KEYS, "a `check` feeds no entry and must not count as one"


@pytest.mark.parametrize(
    "overrides,warned",
    [
        ({"USE_GREYLIST": "no"}, False),
        ({"USE_GREYLIST": "yes"}, True),
        ({"USE_GREYLIST": "yes", "GREYLIST_IP": "203.0.113.0/24"}, False),
        ({"USE_GREYLIST": "yes", "GREYLIST_IP_URLS": "https://example.com/list.txt"}, False),
        ({"USE_GREYLIST": "yes", "GREYLIST_IP": "   "}, True),
    ],
)
def test_the_greylist_body_warns_when_an_enabled_greylist_would_deny_everything(overrides, warned, render_page):
    """Greylist is deny-by-default: `core/greylist/greylist.lua:209` returns `get_deny_status()`
    for a request that matched nothing, and `:212` sends stream traffic through the same access().

    The FLIP is already refused server-side (models/config.py's cross-key rule). The state this
    warning covers is the one that guard cannot reach: an ALREADY enabled greylist whose entries
    were emptied by a later save, which is never re-checked because both save paths strip unchanged
    keys from `to_check`. Whitespace counts as empty on both sides.
    """
    html = _render_body("greylist", render_page, overrides=overrides)

    assert ('role="alert"' in html) is warned


def test_only_the_greylist_body_carries_the_lock_out_warning(render_page):
    """Deny-by-default is greylist's alone: blacklist and whitelist default to allowing anything
    they do not match, so the same alert on their pages would be noise that trains the operator to
    ignore it on the one page where it means something."""
    for plugin in ("blacklist", "whitelist"):
        assert 'role="alert"' not in _render_body(plugin, render_page, overrides={f"USE_{plugin.upper()}": "yes"}), plugin


# --------------------------------------------------------------------------------------
# access control: the country picker
# --------------------------------------------------------------------------------------

COUNTRY_LISTS = {"WHITELIST_COUNTRY", "BLACKLIST_COUNTRY"}


@pytest.mark.parametrize(
    "overrides,on_screen,off_screen",
    [
        ({}, set(), COUNTRY_LISTS),
        ({"WHITELIST_COUNTRY": "FR DE"}, {"WHITELIST_COUNTRY"}, {"BLACKLIST_COUNTRY"}),
        ({"BLACKLIST_COUNTRY": "RU"}, {"BLACKLIST_COUNTRY"}, {"WHITELIST_COUNTRY"}),
        ({"WHITELIST_COUNTRY": "FR", "BLACKLIST_COUNTRY": "RU"}, {"WHITELIST_COUNTRY"}, {"BLACKLIST_COUNTRY"}),
    ],
)
def test_the_country_picker_opens_on_the_list_the_runtime_honours(overrides, on_screen, off_screen, render_page):
    """`core/country/country.lua:131-160` processes WHITELIST_COUNTRY first and returns from inside
    that branch either way, so the blacklist at :163 is only reached when the whitelist is empty.

    The last row is the one the flat form got wrong: with both stored, the country blacklist is dead
    configuration, and the page has to open on the whitelist rather than pick either.
    """
    html = _render_body("country", render_page, overrides=overrides)
    parsed = _parse(html)

    assert on_screen <= parsed.visible
    assert not (off_screen & parsed.visible)


@pytest.mark.parametrize(
    "overrides",
    [{}, {"WHITELIST_COUNTRY": "FR"}, {"BLACKLIST_COUNTRY": "RU"}, {"WHITELIST_COUNTRY": "FR", "BLACKLIST_COUNTRY": "RU"}],
)
def test_the_country_body_posts_both_lists_in_every_mode(overrides, render_page):
    """Hiding is not clearing. The list the picker is not showing must still post, or the first
    save in the other mode DELETES it (db_methods/config_save.py:579-585) -- and a 250-entry
    country selection is not something an operator can reconstruct from memory."""
    parsed = _parse(_render_body("country", render_page, overrides=overrides))

    assert COUNTRY_LISTS <= parsed.posted


def test_a_dead_country_blacklist_says_so_and_can_be_cleared(render_page):
    """The known minor on the antibot page, not repeated here: an alert the operator cannot act on
    is a dead end, because re-selecting the value the picker is already on fires no `change`.

    So the conflict alert ships its own clear button, aimed at the list the runtime is ignoring.
    """
    both = _render_body("country", render_page, overrides={"WHITELIST_COUNTRY": "FR", "BLACKLIST_COUNTRY": "RU"})
    one = _render_body("country", render_page, overrides={"WHITELIST_COUNTRY": "FR"})

    assert "data-access-control-country-conflict" in both
    assert 'data-access-control-country-clear="block"' in both
    assert "data-access-control-country-conflict" not in one


def test_the_country_body_picker_posts_nothing_of_its_own(render_page):
    """It is a client-side control. Giving it a `name` would push a key the plugin never declared
    into `request.form.to_dict()`, and every route would have to learn to pop it."""
    html = _render_body("country", render_page)
    start = html.index('id="access-control-country-mode"')
    picker = html[start:][:400]

    assert "name=" not in picker
    assert set(_parse(html).posted) <= set(CORE_MANIFESTS["country"]["settings"]) | FORM_ONLY


# --------------------------------------------------------------------------------------
# access control: the body and its script must agree
# --------------------------------------------------------------------------------------

# Same pairing as antibot's JS_HOOKS and for the same reason: a selector that stops matching is the
# quietest failure this page has -- the markup renders, the fields are all there, and only the
# liveness is gone.
COUNTRY_JS_HOOKS = [
    ("the form", "form[data-plugin-settings-form]", "data-plugin-settings-form", "page"),
    ("the mode picker", "[data-access-control-country-mode]", "data-access-control-country-mode", "page"),
    ("the list wrappers", "[data-access-control-country-list]", "data-access-control-country-list=", "page"),
    ("the exceptions section", "[data-access-control-country-exceptions]", "data-access-control-country-exceptions", "page"),
    ("the conflict alert", "[data-access-control-country-conflict]", "data-access-control-country-conflict", "conflict"),
    ("the conflict clear button", "[data-access-control-country-clear]", "data-access-control-country-clear=", "conflict"),
    # Owned by models/multiselect_setting.html, not by this body: the script clears a list by
    # unchecking its option boxes and firing one `change`, which is the shared widget's own
    # bookkeeping path (settings-widgets.js -> updateMultiselectDisplay).
    ("the multiselect option boxes", ".multiselect-options input[type='checkbox']", "multiselect-options", "widget"),
]


@pytest.mark.parametrize("label,in_script,in_markup,where", COUNTRY_JS_HOOKS, ids=[hook[0] for hook in COUNTRY_JS_HOOKS])
def test_every_hook_the_country_script_reaches_for_exists(label, in_script, in_markup, where, render_page):
    script = (STATIC / "js" / "plugin_bodies" / "country.js").read_text(encoding="utf-8")
    assert in_script in script, f"{label}: the script no longer uses {in_script}"

    if where == "widget":
        markup = (TEMPLATES / "models" / "multiselect_setting.html").read_text(encoding="utf-8")
    else:
        # The conflict alert only renders when both lists are stored, which is exactly the state
        # its two hooks exist for.
        overrides = {"WHITELIST_COUNTRY": "FR", "BLACKLIST_COUNTRY": "RU"} if where == "conflict" else None
        markup = _render_body("country", render_page, overrides=overrides)
    assert in_markup in markup, f"{label}: the script looks for {in_script} and nothing renders {in_markup}"


@pytest.mark.parametrize("script", ["country.js", "antibot.js"])
def test_a_country_picker_script_never_disables_or_detaches_a_field(script):
    """The one thing these scripts must never do. Clearing a value, disabling an input, removing a
    node -- each stops the field posting while its key stays in `postable_scope`, which deletes the
    row. Hiding is the only permitted way to take a group off screen, and that includes the alerts:
    `.remove()` on the conflict banner is the tempting one-liner and it is on this list."""
    source = (STATIC / "js" / "plugin_bodies" / script).read_text(encoding="utf-8")

    for forbidden in (".remove()", ".disabled = true", 'removeAttribute("name")', '.value = ""', "detach("):
        assert forbidden not in source, f"{script} does {forbidden}, which stops a field posting"


@pytest.mark.parametrize("plugin", LIST_BODIES)
def test_a_list_body_ships_no_behaviour_script(plugin):
    """The three list bodies hide nothing and switch nothing, so they need no JS -- and a body that
    needs none must not put a 404 <script> on the page."""
    assert plugin_settings_body_script(plugin) is None


def test_the_country_body_ships_its_script():
    assert plugin_settings_body_script("country") == "js/plugin_bodies/country.js"
    assert (STATIC / "js" / "plugin_bodies" / "country.js").is_file()


def test_the_antibot_conflict_alert_can_now_be_cleared(render_page):
    """The known minor from the antibot round-2 notes, fixed here alongside the country body it
    would otherwise have been copied into.

    With both antibot country lists stored the picker opens on `only`, and re-selecting the value a
    <select> is already on fires no `change` -- so the alert could not be cleared from the control
    it was about. It now ships its own button, aimed at the redundant list, and the handler hides
    the alert rather than detaching it.
    """
    both = render_page(
        ANTIBOT | {"id": "antibot"},
        config=_antibot_config(mode="captcha", overrides={"ANTIBOT_IGNORE_COUNTRY": "FR", "ANTIBOT_ONLY_COUNTRY": "US"}),
        settings_body="plugin_bodies/antibot.html",
    )
    one = render_page(
        ANTIBOT | {"id": "antibot"},
        config=_antibot_config(mode="captcha", overrides={"ANTIBOT_ONLY_COUNTRY": "US"}),
        settings_body="plugin_bodies/antibot.html",
    )
    script = (STATIC / "js" / "plugin_bodies" / "antibot.js").read_text(encoding="utf-8")

    assert 'data-antibot-country-clear="ignore"' in both
    assert "data-antibot-country-conflict" in both
    assert "data-antibot-country-clear" not in one
    assert "[data-antibot-country-clear]" in script, "the markup ships a button no script listens to"
    assert "[data-antibot-country-conflict]" in script
    # Both country lists must still post while the alert is on screen -- the button clears a list
    # through the widget's own bookkeeping, it does not stop the field serialising.
    assert COUNTRY_SETTINGS <= _parse(both).posted


def test_a_readonly_access_control_page_posts_nothing(render_page):
    """`postable_scope` short-circuits to the empty set when the page rendered read-only, so the
    form must post nothing -- at global scope a read-only POST that still claimed the scope would
    wipe the plugin's whole configuration (routes/global_settings.py:257-263). The country body's
    picker and its conflict button are `disabled` for the same reason: neither posts, but a control
    that still looks live on a read-only page is a lie about what Save will do.
    """
    for plugin in ACCESS_CONTROL_BODIES:
        manifest = CORE_MANIFESTS[plugin]
        config = _stored_config(manifest["settings"])
        html = _render_body(plugin, render_page, is_readonly=True)

        assert postable_scope(manifest, config, global_page=False, is_pro_version=False, blacklisted=get_blacklisted_settings(), is_readonly=True) == set()
        enabled = {name for name, _hidden, disabled in _parse(html).controls if not disabled} - FORM_ONLY
        assert enabled == set(), f"{plugin}: read-only page still posts: {sorted(enabled)}"


# --------------------------------------------------------------------------------------
# access control: the one claim the whitelist page must not overstate
# --------------------------------------------------------------------------------------

BAN_RESCUE_KEY = "settings.access_control.whitelist.enforcement.description"
# The four kinds a whitelist matches on that do NOT rescue a banned client. Written out because the
# copy has to name each of them: "a ban is ignored for whitelisted clients" is the sentence this
# test exists to keep out of the page.
KINDS_THAT_DO_NOT_LIFT_A_BAN = ("reverse DNS", "ASN", "user agent", "URI")


def _english_copy(key):
    """The English string for `key`, from whichever catalog currently holds it.

    en.json is the catalog; while a lane is in flight its new keys live in the wave's
    `i18n-keys-*.json` handoff instead, because en.json is merged once at acceptance to keep two
    concurrent UI lanes from corrupting it. Looking in both keeps this check running on both sides
    of that merge; once the keys are in en.json the glob simply finds nothing and the first branch
    answers. Returns None only if the key is in no catalog at all, which the caller reports.
    """
    catalogs = [json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))]
    catalogs += [json.loads(path.read_text(encoding="utf-8")) for path in sorted(REPO_ROOT.glob(".cache/results-*/i18n-keys-*.json"))]
    for catalog in catalogs:
        node = catalog
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if isinstance(node, str):
            return node
    return None


def test_the_whitelist_page_does_not_promise_a_ban_rescue_it_cannot_deliver():
    """A whitelist match lifts an active IP ban ONLY when the match is by IP.

    The ban check at `confs/server-http/access-lua.conf:74` runs before the plugin chain, so the
    flag its fast path reads is still "no" -- `whitelist:access()` has not run. The rescue that
    actually fires is line 84's `is_ip_whitelisted`, and that helper consults `lists["IP"]` and
    nothing else (`bw/lua/bunkerweb/utils.lua`). A client whitelisted by rDNS, ASN, user-agent or
    URI is therefore still denied while banned.

    Both halves are asserted, because either one moving alone makes the page lie:
      * the RUNTIME half fails the day `is_ip_whitelisted` learns another kind -- at which point the
        copy is too narrow and should be widened deliberately, not left stale;
      * the COPY half fails the day someone re-generalises the sentence to "a whitelisted client's
        ban is ignored", which is what the page said before Criticos caught it.
    """
    source = (REPO_ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua").read_text(encoding="utf-8")
    start = source.index("utils.is_ip_whitelisted = function")
    end = source.index("\nutils.", start + 1)
    helper = source[start:end]

    assert 'lists["IP"]' in helper, "is_ip_whitelisted no longer reads the IP list; the page copy is now wrong"
    for kind in ("RDNS", "ASN", "USER_AGENT", "URI"):
        assert f'lists["{kind}"]' not in helper, f"is_ip_whitelisted now rescues on {kind} too -- widen the whitelist page copy"

    copy = _english_copy(BAN_RESCUE_KEY)

    assert copy, f"{BAN_RESCUE_KEY} resolves in no catalog -- merge the lane's i18n keys into en.json"
    assert "IP" in copy, "the whitelist enforcement copy no longer scopes the ban exception to IP"
    for kind in KINDS_THAT_DO_NOT_LIFT_A_BAN:
        assert kind in copy, f"the copy no longer tells the operator that a {kind} match leaves a ban in force"


def test_the_banner_copy_does_not_present_the_default_order_as_fixed():
    """`PLUGINS_ORDER_ACCESS` and `PLUGINS_ORDER_PREREAD` are multisite settings, and
    `access-lua.conf` honours a per-site override -- so the banner draws the DEFAULT chain, not
    necessarily this service's. Saying so costs one clause and stops the "current page" badge from
    vouching for an order the operator may have changed."""
    order_settings = json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8"))

    for setting in ("PLUGINS_ORDER_ACCESS", "PLUGINS_ORDER_PREREAD"):
        assert order_settings[setting]["context"] == "multisite", f"{setting} is no longer per-service; the banner caveat can go"

    copy = _english_copy("settings.access_control.order.description")

    assert copy, "the banner description resolves in no catalog"
    assert "PLUGINS_ORDER_ACCESS" in copy and "PLUGINS_ORDER_PREREAD" in copy, "the banner no longer names the settings that change the order it draws"


def test_the_antibot_conflict_copy_still_says_both_lists_are_live():
    """antibot's two country lists are ORed and BOTH stay live (`antibot.lua:1198-1201`), which is
    the opposite of the country page, where a stored `BLACKLIST_COUNTRY` really is dead config once
    `WHITELIST_COUNTRY` is set. The two pages ship near-identical alerts, so the day someone
    harmonises the copy is the day one of them becomes false."""
    antibot = (CORE_PLUGINS / "antibot" / "antibot.lua").read_text(encoding="utf-8")

    assert "country_ignore_active" in antibot and "country_only_active" in antibot, "antibot no longer keeps the two country lists independent"

    copy = _english_copy("settings.antibot.countries.both_set")

    assert copy, "the antibot conflict copy resolves in no catalog"
    assert "combined" in copy and "not exclusive" in copy, "the antibot conflict copy no longer says the two lists are ORed"


# --------------------------------------------------------------------------------------
# modsecurity: the state machine
# --------------------------------------------------------------------------------------

MODSEC = CORE_MANIFESTS["modsecurity"]
MODSEC_SETTINGS = MODSEC["settings"]
# The body's whole visibility contract in one attribute: `KEY=v1|v2 KEY2=v3`, ANDed. Both the
# template and static/js/plugin_bodies/modsecurity.js evaluate exactly this, which is the only
# reason the server render and the live page cannot drift apart.
WHEN_ATTR = compile_regex(r'data-(modsec|headers)-when="([^"]*)"')


def _modsec_config(use="yes", crs="yes", version="4", engine="On", overrides=None):
    config = _stored_config(MODSEC_SETTINGS)
    config["USE_MODSECURITY"]["value"] = use
    config["USE_MODSECURITY_CRS"]["value"] = crs
    config["MODSECURITY_CRS_VERSION"]["value"] = version
    config["MODSECURITY_SEC_RULE_ENGINE"]["value"] = engine
    for key, value in (overrides or {}).items():
        config[key]["value"] = value
    config |= {
        "SERVER_NAME": {"value": "app.example.com", "method": "ui"},
        "IS_DRAFT": {"value": "no", "method": "ui"},
        "USE_TEMPLATE": {"value": "", "method": "ui"},
        "USE_UI": {"value": "no", "method": "ui"},
    }
    return config


def _render_modsec(render_page, **kwargs):
    global_page = kwargs.pop("global_page", False)
    return render_page(
        MODSEC | {"id": "modsecurity"},
        config=_modsec_config(**kwargs),
        service_id="" if global_page else "app.example.com",
        settings_body="plugin_bodies/modsecurity.html",
    )


# (state, groups that must be on screen, groups that must NOT be). Written out rather than
# derived: this table IS the specification the template's `when` terms implement, and a test that
# re-derives the expectation from the same table the template reads proves only that Jinja works.
MODSEC_STATES = [
    (
        "waf off",
        {"use": "no"},
        {"off", "engine"},
        {"engine-off", "engine-detect", "crs", "crs-v3", "crs-plugins", "audit", "limits", "tuning"},
    ),
    (
        "crs 4",
        {"use": "yes", "crs": "yes", "version": "4"},
        {"engine", "crs", "crs-plugins", "audit", "limits", "tuning", "tuning-crs_plugins_before", "tuning-crs_plugins_after"},
        {"off", "engine-off", "engine-detect", "crs-v3"},
    ),
    (
        "crs 3 -- plugins are not compatible",
        {"use": "yes", "crs": "yes", "version": "3"},
        {"engine", "crs", "crs-v3", "audit", "limits", "tuning"},
        {"off", "crs-plugins", "tuning-crs_plugins_before", "tuning-crs_plugins_after"},
    ),
    (
        "crs off",
        {"use": "yes", "crs": "no", "version": "4"},
        {"engine", "crs", "audit", "limits", "tuning"},
        {"off", "crs-v3", "crs-plugins", "tuning-crs_plugins_before", "tuning-crs_plugins_after"},
    ),
    (
        "rule engine off -- the WAF is loaded and enforces nothing",
        {"use": "yes", "engine": "Off"},
        {"engine", "engine-off", "crs"},
        {"off", "engine-detect"},
    ),
    (
        "detection only",
        {"use": "yes", "engine": "DetectionOnly"},
        {"engine", "engine-detect", "crs"},
        {"off", "engine-off"},
    ),
]


@pytest.mark.parametrize("label,state,on_screen,off_screen", MODSEC_STATES, ids=[case[0] for case in MODSEC_STATES])
def test_the_modsecurity_body_shows_the_groups_that_apply_to_the_state(label, state, on_screen, off_screen, render_page):
    """The reason this page exists. `USE_MODSECURITY` and `MODSECURITY_SEC_RULE_ENGINE` both mean
    "on" and can disagree -- `Off` disables the WAF while `USE_MODSECURITY` still reads `yes`
    (§5.4 of .cache/results-2026-08-24/plugin-pages-candidates.md) -- and `MODSECURITY_CRS_VERSION`
    gates the CRS plugins, whose own help says "Not compatible with CRS version 3" while the flat
    form enforced nothing.
    """
    parsed = _parse(_render_modsec(render_page, **state))
    assert on_screen <= parsed.visible_body_groups, f"{label}: missing from the page: {sorted(on_screen - parsed.visible_body_groups)}"
    assert not (off_screen & parsed.visible_body_groups), f"{label}: on screen and should not be: {sorted(off_screen & parsed.visible_body_groups)}"
    # Every group named in the table exists at all -- a renamed group id would otherwise pass the
    # "not visible" half of every row for the wrong reason.
    assert (on_screen | off_screen) <= parsed.all_body_groups, f"{label}: no such group: {sorted((on_screen | off_screen) - parsed.all_body_groups)}"


@pytest.mark.parametrize("label,state,_on,_off", MODSEC_STATES, ids=[case[0] for case in MODSEC_STATES])
def test_a_hidden_modsecurity_group_still_posts_every_key(label, state, _on, _off, render_page):
    """Hide, never omit -- spelled out for the state that makes it concrete: turn the WAF off,
    save, and the audit-log parts, both body limits and the CRS plugin list must come back."""
    config = _modsec_config(**state)
    html = render_page(MODSEC | {"id": "modsecurity"}, config=config, settings_body="plugin_bodies/modsecurity.html")
    scope = postable_scope(MODSEC, config, global_page=False, is_pro_version=False, blacklisted=get_blacklisted_settings())
    assert scope - _parse(html).posted == set(), f"{label}: these rows are DELETED on save: {sorted(scope - _parse(html).posted)}"


def test_the_crs_plugin_list_survives_a_downgrade_to_crs_3(render_page):
    """The concrete version: CRS 3 cannot load plugins, so the group is off screen -- but the list
    the operator typed under CRS 4 must still post, or switching back finds it gone."""
    stored = "plugin-one plugin-two"
    html = _render_modsec(render_page, use="yes", crs="yes", version="3", overrides={"MODSECURITY_CRS_PLUGINS": stored})
    parsed = _parse(html)
    assert "crs-plugins" not in parsed.visible_body_groups
    assert "MODSECURITY_CRS_PLUGINS" in parsed.posted
    assert stored in html


def test_the_global_crs_switch_is_only_on_the_global_page(render_page):
    """`USE_MODSECURITY_GLOBAL_CRS` is the plugin's only `global`-context setting, so
    `get_filtered_settings` drops it on a service page and `postable_scope` leaves it out of scope
    there. Its group must vanish with it rather than render as a title over an empty row."""
    service = _parse(_render_modsec(render_page, global_page=False))
    assert "global-crs" not in service.all_body_groups
    assert "USE_MODSECURITY_GLOBAL_CRS" not in service.posted

    globally = _parse(_render_modsec(render_page, global_page=True))
    assert "global-crs" in globally.visible_body_groups
    assert "USE_MODSECURITY_GLOBAL_CRS" in globally.posted


def test_the_tuning_band_links_to_every_config_type_a_false_positive_lands_in(render_page):
    """The daily job -- clearing a false positive -- happens in /configs across four types, and
    until this page existed nothing in the settings form said so (§5.4)."""
    html = _render_modsec(render_page)
    for config_type in ("MODSEC_CRS", "MODSEC", "CRS_PLUGINS_BEFORE", "CRS_PLUGINS_AFTER"):
        assert f"type={config_type}" in html, config_type


# --------------------------------------------------------------------------------------
# modsecurity + headers: the body and its script must agree
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plugin,config",
    [("modsecurity", lambda: _modsec_config()), ("headers", lambda: _headers_config())],
)
def test_a_when_term_only_names_a_control_the_page_actually_renders(plugin, config, render_page):
    """`data-*-when` is evaluated server-side against the stored config and client-side against
    live CONTROLS. A term over a key with no `name=` control on the page is therefore live on the
    server and dead in the browser -- the group would freeze in whatever state the render left it.
    Both scripts fail such a term CLOSED (hidden), which is the safe direction and also the one
    nobody would notice, so it is worth asserting no term is in that position.
    """
    manifest = CORE_MANIFESTS[plugin]
    html = render_page(manifest, config=config(), settings_body=f"plugin_bodies/{plugin}.html")
    posted = _parse(html).posted
    terms = [term for _prefix, attr in WHEN_ATTR.findall(html) for term in attr.split()]
    assert terms, f"{plugin}: no `when` term rendered -- this check is vacuous"
    for term in terms:
        key = term.split("=", 1)[0]
        assert key in posted, f"{plugin}: `{term}` conditions on {key}, which this page renders no control for"


BODY_JS_HOOKS = [
    # (plugin, what the SCRIPT must contain, what the MARKUP must contain)
    ("modsecurity", "form[data-plugin-settings-form]", "data-plugin-settings-form"),
    ("modsecurity", "[data-modsec-when]", "data-modsec-when="),
    ("modsecurity", "modsecWhen", "data-modsec-when="),
    ("headers", "form[data-plugin-settings-form]", "data-plugin-settings-form"),
    ("headers", "[data-headers-when]", "data-headers-when="),
    ("headers", "headersWhen", "data-headers-when="),
]


@pytest.mark.parametrize("plugin,in_script,in_markup", BODY_JS_HOOKS, ids=[f"{hook[0]}:{hook[1]}" for hook in BODY_JS_HOOKS])
def test_every_hook_these_body_scripts_reach_for_exists(plugin, in_script, in_markup, render_page):
    """A selector that stops matching is the quietest failure these pages have: the markup renders,
    every field is there, and only the liveness is gone."""
    script = (STATIC / "js" / "plugin_bodies" / f"{plugin}.js").read_text(encoding="utf-8")
    assert in_script in script, f"{plugin}.js no longer uses {in_script}"
    config = _modsec_config() if plugin == "modsecurity" else _headers_config()
    markup = render_page(CORE_MANIFESTS[plugin], config=config, settings_body=f"plugin_bodies/{plugin}.html")
    assert in_markup in markup, f"{plugin}.js looks for {in_script} and nothing renders {in_markup}"


@pytest.mark.parametrize("plugin", ["modsecurity", "headers"])
def test_these_body_scripts_never_disable_or_detach_a_field(plugin):
    """Clearing, disabling or removing an input stops it posting while its key stays in
    `postable_scope`, which deletes the row. Hiding is the only permitted way to take something
    off screen."""
    script = (STATIC / "js" / "plugin_bodies" / f"{plugin}.js").read_text(encoding="utf-8")
    for forbidden in (".remove()", ".disabled = true", 'removeAttribute("name")', '.value = ""', "detach("):
        assert forbidden not in script, f"{plugin}.js does {forbidden}, which stops a field posting"


@pytest.mark.parametrize("plugin", ["modsecurity", "headers"])
def test_a_checkbox_condition_reads_the_value_it_posts(plugin):
    """A checkbox has no `value` attribute in the markup, so `.value` reads "on"; the shared bundle
    rewrites it to "yes" and inserts an explicit "no" only at submit time
    (settings-widgets.js:1716-1745). A `when` term over a `check` setting compares against
    "yes"/"no", so the script has to derive them from `.checked` rather than read `.value`."""
    script = (STATIC / "js" / "plugin_bodies" / f"{plugin}.js").read_text(encoding="utf-8")
    assert 'control.checked ? "yes" : "no"' in script, f"{plugin}.js no longer maps a checkbox to the value it posts"


# --------------------------------------------------------------------------------------
# headers: the interactions that fail silently
# --------------------------------------------------------------------------------------

HEADERS = CORE_MANIFESTS["headers"]
HEADERS_SETTINGS = HEADERS["settings"]
HEADERS_MULTIPLES = sorted(key for key, data in HEADERS_SETTINGS.items() if data.get("multiple"))
# The shadow list is rendered OUTSIDE the translated sentence, so it can be read back exactly.
SHADOWED_ATTR = compile_regex(r'data-headers-shadowed="([^"]*)"')


def _headers_config(overrides=None, suffixed=None):
    config = _stored_config(HEADERS_SETTINGS)
    for key, value in (overrides or {}).items():
        config[key]["value"] = value
    for key, value in (suffixed or {}).items():
        config[key] = {"value": value, "method": "ui", "global": False, "template": ""}
    config |= {
        "SERVER_NAME": {"value": "app.example.com", "method": "ui"},
        "IS_DRAFT": {"value": "no", "method": "ui"},
        "USE_TEMPLATE": {"value": "", "method": "ui"},
        "USE_UI": {"value": "no", "method": "ui"},
    }
    return config


def _render_headers(render_page, **kwargs):
    return render_page(HEADERS | {"id": "headers"}, config=_headers_config(**kwargs), settings_body="plugin_bodies/headers.html")


def test_headers_declares_the_two_multiple_families_this_body_was_written_for():
    """If the manifest ever stops declaring them, the suffixed-row checks below go quiet rather
    than red. `CUSTOM_HEADER` and `COOKIE_FLAGS` are the reason this body delegates to the generic
    multiples block at all."""
    assert HEADERS_MULTIPLES == ["COOKIE_FLAGS", "CUSTOM_HEADER"], HEADERS_MULTIPLES


def test_two_stored_custom_headers_both_survive_a_save_through_this_body(render_page):
    """The single most likely way to break this page, spelled out.

    An operator with three custom headers has CUSTOM_HEADER, CUSTOM_HEADER_1 and CUSTOM_HEADER_2
    stored. `postable_scope` walks the stored config, so all three are in scope
    (routes/services.py:1023-1030), and an in-scope key the POST does not carry has its row DELETED
    (db_methods/config_save.py:579-585). A body that renders only the base field posts only the
    base field: saving anything at all on this page then deletes the other two, and the operator
    finds out when the headers stop being sent.
    """
    suffixed = {
        "CUSTOM_HEADER_1": "X-Frame-Test: one",
        "CUSTOM_HEADER_2": "X-Other-Test: two",
        "COOKIE_FLAGS_1": "* SameSite=Strict",
    }
    config = _headers_config(suffixed=suffixed)
    html = render_page(HEADERS | {"id": "headers"}, config=config, settings_body="plugin_bodies/headers.html")
    parsed = _parse(html)

    assert set(suffixed) <= parsed.posted, f"never posted -> DELETED on save: {sorted(set(suffixed) - parsed.posted)}"
    for key, value in suffixed.items():
        assert value in html, f"{key} renders an input that does not carry its stored value"
    # And the cloner can still add a fourth: the ADD button is the generic block's, keyed on the
    # id scheme components/settings-widgets.js:449-470 walks.
    for multiple in ("custom-headers", "cookie-flags"):
        assert f'id="add-multiple-headers-{multiple}"' in html, multiple
        assert f'id="multiple-headers-{multiple}"' in html, multiple


def test_the_report_only_switch_says_the_policy_is_not_being_enforced(render_page):
    """`CONTENT_SECURITY_POLICY_REPORT_ONLY` is the safety valve for the one setting on this page
    that can break a whole site's JavaScript, and the flat form rendered it as an unrelated
    checkbox three rows away (§5.5). It now sits with the policy, and turning it on says what it
    costs: violations are reported, nothing is blocked."""
    on = _parse(_render_headers(render_page, overrides={"CONTENT_SECURITY_POLICY_REPORT_ONLY": "yes"}))
    off = _parse(_render_headers(render_page, overrides={"CONTENT_SECURITY_POLICY_REPORT_ONLY": "no"}))
    assert "csp-report-only" in on.visible_body_groups
    assert "csp-report-only" not in off.visible_body_groups
    # The note is hidden, not omitted -- the switch itself must keep posting either way.
    assert "CONTENT_SECURITY_POLICY_REPORT_ONLY" in off.posted
    assert "csp-report-only" in off.all_body_groups


@pytest.mark.parametrize(
    "hsts,warned",
    [
        ("max-age=63072000; includeSubDomains; preload", True),
        ("max-age=63072000; includeSubDomains", False),
        ("", False),
    ],
)
def test_the_hsts_preload_warning_fires_only_when_preload_is_in_the_value(hsts, warned, render_page):
    """`preload` is effectively irreversible for months once the domain is submitted, and it is in
    the shipped default. Nothing said so before (§5.5)."""
    html = _render_headers(render_page, overrides={"STRICT_TRANSPORT_SECURITY": hsts})
    marker = english("settings.headers.notice.hsts_preload")
    assert (marker in html) is warned, f"{hsts!r}: preload warning {'missing' if warned else 'fired for nothing'}"


@pytest.mark.parametrize(
    "keep,expected",
    [
        # The shipped default keeps four of the headers this plugin sets, so an upstream that
        # sends its own CSP wins over the one configured here -- exactly the "set a perfect CSP
        # and never see it" trap §5.5 names.
        (None, ["Content-Security-Policy", "Permissions-Policy", "X-Frame-Options"]),
        ("", []),
        ("X-Frame-Options", ["X-Frame-Options"]),
        ("Server", []),
    ],
)
def test_the_upstream_keep_list_says_which_of_our_headers_it_shadows(keep, expected, render_page):
    """`headers:should_keep` (headers.lua:76-79) is a whole-word match on
    KEEP_UPSTREAM_HEADERS; a kept header means BunkerWeb's own value is NOT applied when the
    upstream sends one. The page has to name them: the interaction is invisible otherwise."""
    overrides = {} if keep is None else {"KEEP_UPSTREAM_HEADERS": keep}
    html = _render_headers(render_page, overrides=overrides)
    shadowed = SHADOWED_ATTR.findall(html)
    if expected:
        assert shadowed == [", ".join(expected)], f"{keep!r}: page names {shadowed}, expected {expected}"
        assert english("settings.headers.notice.keep_shadows") in html
    else:
        assert shadowed == [], f"{keep!r}: page names headers it does not shadow: {shadowed}"
        assert english("settings.headers.notice.keep_shadows") not in html
        assert english("settings.headers.notice.keep_all") not in html


def test_the_keep_list_wildcard_is_reported_as_covering_everything(render_page):
    """`*` short-circuits `should_keep` for every header (headers.lua:80), so listing individual
    names would understate it."""
    html = _render_headers(render_page, overrides={"KEEP_UPSTREAM_HEADERS": "*"})
    assert english("settings.headers.notice.keep_all") in html


@pytest.mark.parametrize("keep", ["X-Frame-Options *", "* X-Frame-Options", "*,X-Frame-Options"])
def test_a_star_among_other_names_is_not_the_wildcard(keep, render_page):
    """`should_keep` reads `*` as the wildcard only on `KEEP_UPSTREAM_HEADERS == "*"`
    (headers.lua:80); otherwise it falls through to a whole-word regex on the HEADER NAME
    (:81), and `*` is not a header name. Treating `*` as a member of the list made the page claim
    every header was shadowed when one was -- an over-report that sends the operator hunting a
    problem they do not have.

    `"*,X-Frame-Options"` is the third case on purpose: the runtime's regex is space-delimited, so
    a comma-separated list matches NOTHING there, not everything. The page must not claim more.
    """
    html = _render_headers(render_page, overrides={"KEEP_UPSTREAM_HEADERS": keep})
    assert english("settings.headers.notice.keep_all") not in html, f"{keep!r}: reported as the wildcard"
    expected = ["X-Frame-Options"] if keep != "*,X-Frame-Options" else []
    assert SHADOWED_ATTR.findall(html) == ([", ".join(expected)] if expected else []), f"{keep!r}: wrong shadow list"


def test_report_only_moves_which_header_the_keep_list_shadows(render_page):
    """With report-only on, the policy goes out as Content-Security-Policy-Report-Only
    (headers.lua:96-104), so the keep-list entry that matters is that name, not the enforcing one.
    A note that named the wrong header would send the operator to fix the wrong list."""
    keep = "Content-Security-Policy-Report-Only"
    enforcing = _render_headers(render_page, overrides={"KEEP_UPSTREAM_HEADERS": keep, "CONTENT_SECURITY_POLICY_REPORT_ONLY": "no"})
    reporting = _render_headers(render_page, overrides={"KEEP_UPSTREAM_HEADERS": keep, "CONTENT_SECURITY_POLICY_REPORT_ONLY": "yes"})
    assert SHADOWED_ATTR.findall(reporting) == [keep]
    assert SHADOWED_ATTR.findall(enforcing) == []


def test_a_header_configured_to_empty_is_not_reported_as_shadowed(render_page):
    """An empty value means "remove the header" (headers.lua:87-89): there is nothing of ours for
    the upstream to shadow, so naming it would be noise."""
    html = _render_headers(render_page, overrides={"KEEP_UPSTREAM_HEADERS": "X-Frame-Options", "X_FRAME_OPTIONS": ""})
    assert SHADOWED_ATTR.findall(html) == []


def test_the_headers_body_renders_at_global_scope_too(render_page):
    """One body, both routes. Every headers setting is multisite, so all 13 are in play at
    /global-settings/plugins/headers as well -- the multiples included."""
    config = _headers_config(suffixed={"CUSTOM_HEADER_1": "X-A: 1"})
    html = render_page(HEADERS | {"id": "headers"}, config=config, service_id="", settings_body="plugin_bodies/headers.html")
    posted = _parse(html).posted
    assert set(HEADERS_SETTINGS) <= posted
    assert "CUSTOM_HEADER_1" in posted
    assert "OLD_SERVER_NAME" not in html, "the global page must not post the service list"

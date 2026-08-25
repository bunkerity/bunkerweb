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
        self.groups = []  # (group id, modes attr, classic attr, hidden)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        hidden = "hidden" in attributes
        if attributes.get("data-antibot-group") is not None:
            self.groups.append((attributes["data-antibot-group"], attributes.get("data-antibot-modes"), attributes.get("data-antibot-classic"), hidden))
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
        return f"/{endpoint}"

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
def test_every_shipped_body_places_every_setting_it_declares(plugin, render_page):
    """No body may fall back on its own straggler block for a setting the manifest declares.

    A straggler still posts -- that is the point of the backstop -- but it renders outside every
    group, so it is a setting nobody laid out. Failing here is the signal to give it a home.
    """
    manifest = CORE_MANIFESTS[plugin]
    html = render_page(manifest, config=_stored_config(manifest.get("settings") or {}), settings_body=f"plugin_bodies/{plugin}.html")
    assert "data-plugin-body-unplaced" not in html, f"{plugin}: a declared setting is not placed in any group of templates/plugin_bodies/{plugin}.html"


@pytest.mark.parametrize("plugin", SHIPPED_BODIES)
def test_every_shipped_body_declares_no_multiple_setting_it_cannot_render(plugin):
    """A body renders its own fields, so it renders no `multiple` group unless it writes one.

    `_in_scope` matches a stored `FOO_2` by its BASE name (models/save_scope.py:99-110), so the
    moment a body's plugin declares a `multiple` setting, every suffixed row is inside the
    declared scope -- and a body with no `get_multiples` loop posts none of them, which deletes
    them all. No shipped body needs one today; this is what says so out loud rather than leaving
    it to be discovered by a user losing REVERSE_PROXY_URL_2.
    """
    settings = CORE_MANIFESTS[plugin].get("settings") or {}
    multiples = sorted(key for key, data in settings.items() if data.get("multiple"))
    body = (TEMPLATES / "plugin_bodies" / f"{plugin}.html").read_text(encoding="utf-8")
    if multiples:
        assert "get_multiples" in body, f"{plugin} declares {multiples} but its body renders no multiples loop -- every suffixed row would be deleted on save"


def test_the_shared_bundle_reveals_a_hidden_invalid_control():
    """A hidden control failing its own `pattern=` makes the browser refuse to submit, fail to
    focus the offender, and log to the console only: Save does nothing and says nothing.

    The reveal lives in the SHARED bundle so every body inherits it -- pinning it here rather
    than in each body's script is the difference between a rule and a mechanism. Capture phase
    is load-bearing: `invalid` does not bubble.
    """
    bundle = (STATIC / "js" / "components" / "settings-widgets.js").read_text(encoding="utf-8")
    assert 'addEventListener(\n      "invalid"' in bundle or '"invalid"' in bundle, "the shared bundle no longer listens for invalid"
    handler = bundle[bundle.index('"invalid"') :][:900]
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
    picker = html[html.index('id="antibot-country-mode"') :][:400]
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

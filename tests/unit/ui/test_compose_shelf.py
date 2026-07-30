"""What the compose shelf renders, and -- the whole point of the slice -- what it POSTS.

`Database.save_config` deletes the row for any in-scope key the payload omits
(`db_methods/config_save.py:592`), so the shelf's markup and `shelf_plugin_scope` must agree
exactly: over-claiming destroys data, under-claiming merely preserves it. The anti-drift test
below asserts that biconditional in both directions over the REAL shipped manifests, because
every hand-typed fixture in this chantier so far has been the wrong shape in the one way that
mattered (`country`'s multiselect keys, `redirect`'s `multiple` one, `limit`'s two).
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from app.models.plugin_activation import is_plugin_active_for_service
from app.models.save_scope import control_keys
from app.utils import get_activation_map, get_blacklisted_settings, get_filtered_settings, is_plugin_active

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "src" / "ui" / "app" / "templates"
CORE_PLUGINS = REPO_ROOT / "src" / "common" / "core"

# `shelf_plugin_scope` lives in app/routes/services.py, which cannot be imported bare (see
# test_save_scope.py's loader docstring). Reuse that loader rather than writing a third copy;
# importing the module by name works because pytest puts this directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_save_scope import _import_services_module  # noqa: E402

_services = _import_services_module()
shelf_plugin_scope = _services.shelf_plugin_scope


def _real_plugins():
    """Every shipped plugin in the shape `BW_CONFIG.get_plugins()` returns, `general` included.

    `general` has no plugin.json -- db_methods/initialization.py:320-331 synthesizes it from
    settings.json at boot -- and it is the row that must render "Always on" rather than a
    switch, so leaving it out would skip the one row `_SYNTHESIZED_ALWAYS_ON` exists for.
    """
    plugins = {
        "general": {
            "id": "general",
            "name": "General",
            "description": "The general settings for the server",
            "version": "0.1",
            "stream": "partial",
            "type": "core",
            "settings": json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8")),
        }
    }
    for manifest_path in sorted(CORE_PLUGINS.glob("*/plugin.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plugins[manifest.get("id") or manifest_path.parent.name] = manifest | {"type": "core"}
    return plugins


REAL_PLUGINS = _real_plugins()
# Read off the same manifests rather than transcribed, so a manifest edit shows up as a test
# result instead of as silent drift. Mirrors iter_plugin_activations' extraction.
REAL_ACTIVATION_MAP = {
    plugin_id: data["extensions"]["activation"]
    for plugin_id, data in REAL_PLUGINS.items()
    if isinstance(data.get("extensions"), dict) and data["extensions"].get("activation") is not None
}


def _seeded_config(global_page=False):
    """`config` in the shape the pages actually pass, NOT an empty dict.

    `get_config` seeds every setting from its own default before layering stored values
    (`db_methods/config_read.py:309-316`), and with `service=` set it then drops every
    global-context key (`:411-416`). That matters: `is_plugin_active` defaults an ABSENT key
    to the INACTIVE value (`app/utils.py:372`), so an empty dict silently reports `limit`,
    `blacklist`, `whitelist`, `modsecurity` -- every plugin whose activation key defaults to
    "yes" -- as OFF, and a shelf tested against it would never render the on-by-default rows
    at all.
    """
    config = {}
    for data in REAL_PLUGINS.values():
        for setting, setting_data in (data.get("settings") or {}).items():
            if not global_page and setting_data.get("context") != "multisite":
                continue
            config[setting] = {"value": setting_data.get("default", ""), "method": "default", "global": False}
    return config


def _config(overrides=None, global_page=False):
    return _seeded_config(global_page) | {key: {"method": "ui", "global": False} | value for key, value in (overrides or {}).items()}


PLUGIN_TYPES = {
    "core": {"icon": "<i class='bx bx-shield'></i>", "title-class": " border-dark"},
    "external": {"icon": "<i class='bx bx-plug'></i>"},
    "pro": {"title-class": " border-primary"},
}

# `<input>` never carries an end tag, so it must not move the nesting depth.
VOID_TAGS = {"input", "img", "br", "hr", "meta", "link"}


class _ShelfParser(HTMLParser):
    """Split the rendered page into shelf rows and everything after them.

    stdlib rather than a regex: rows nest spans, anchors and inputs, and the last row is
    immediately followed by the trailing control-key inputs -- a `split()` on the row marker
    would attribute those to the last row and make the anti-drift assertion vacuous.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = {}
        self.outside = []
        self.flat = []
        self._plugin = None
        self._depth = 0
        self._position = 0

    def handle_startendtag(self, tag, attrs):
        # Default would also fire handle_endtag; nothing in the shelf is self-closing, and
        # letting it through would unbalance the depth counter for `<input/>`.
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self._position += 1
        self.flat.append((tag, attributes))
        if self._plugin is None:
            if "data-shelf-row" in attributes:
                self._plugin = attributes.get("data-plugin")
                self.rows[self._plugin] = {"attrs": attributes, "posts": [], "names": [], "tags": [], "position": self._position}
                self._depth = 1
            elif attributes.get("name"):
                self.outside.append((self._position, attributes["name"]))
            return

        row = self.rows[self._plugin]
        row["tags"].append((tag, attributes))
        if attributes.get("name"):
            row["names"].append(attributes["name"])
            if "data-shelf-post" in attributes:
                row["posts"].append(attributes["name"])
        if tag not in VOID_TAGS:
            self._depth += 1

    def handle_endtag(self, tag):
        self.flat.append(("/" + tag, {}))
        if self._plugin is None or tag in VOID_TAGS:
            return
        self._depth -= 1
        if self._depth == 0:
            self._plugin = None


def parse_shelf(html):
    parser = _ShelfParser()
    parser.feed(html)
    return parser


def browser_payload(parser):
    """What `request.form.to_dict()` sees when this markup is submitted untouched.

    Serialises the way a browser does, which is the ONLY view that can prove the two
    properties everything else here is a proxy for: an unchecked checkbox contributes
    NOTHING, a checked one contributes its `value` attribute (not "on", not "yes"), a
    `<select>` with no selected option contributes its FIRST option, and `to_dict()` keeps
    the FIRST value for a repeated name.
    """
    payload = {}
    first_option = {}
    select = None
    for tag, attributes in parser.flat:
        if tag == "select":
            select = attributes.get("name")
            continue
        if tag == "/select":
            select = None
            continue
        if tag == "option" and select:
            first_option.setdefault(select, attributes.get("value", ""))
            if "selected" in attributes:
                payload.setdefault(select, attributes.get("value", ""))
            continue
        if tag == "input" and attributes.get("name"):
            if attributes.get("type") == "checkbox" and "checked" not in attributes:
                continue
            payload.setdefault(attributes["name"], attributes.get("value", ""))
    for name, value in first_option.items():
        payload.setdefault(name, value)
    return payload


@pytest.fixture
def render_shelf():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
        get_filtered_settings=get_filtered_settings,
        is_plugin_active=is_plugin_active,
        is_plugin_active_for_service=is_plugin_active_for_service,
        plugin_types=PLUGIN_TYPES,
    )

    def _render(
        config=None,
        global_page=False,
        is_readonly=False,
        is_pro_version=False,
        service_id="app.example.com",
        plugins=None,
        attachments=None,
        activation_map=None,
    ):
        # `config` is a set of OVERRIDES layered on the seeded defaults, mirroring get_config.
        return env.get_template("models/compose_shelf.html").render(
            plugins=plugins or REAL_PLUGINS,
            config=_config(config, global_page),
            activation_map=REAL_ACTIVATION_MAP if activation_map is None else activation_map,
            shelf_plugin_scope=shelf_plugin_scope,
            control_keys=control_keys,
            blacklisted_settings=get_blacklisted_settings(global_page),
            global_page=global_page,
            is_pro_version=is_pro_version,
            is_readonly=is_readonly,
            service_id="" if global_page else service_id,
            attachments=attachments or {},
        )

    return _render


def _expected_scope(plugin_id, config=None, *, global_page=False, is_pro_version=False, is_readonly=False):
    if is_readonly:
        return set()
    config = _config(config, global_page)
    is_stream = (not global_page) and (config.get("SERVER_TYPE") or {}).get("value", "http") == "stream"
    return shelf_plugin_scope(
        plugin_id,
        REAL_PLUGINS[plugin_id],
        config,
        global_page=global_page,
        is_pro_version=is_pro_version,
        blacklisted=get_blacklisted_settings(global_page),
        is_stream=is_stream,
        activation_map=REAL_ACTIVATION_MAP,
    )


# --------------------------------------------------------------------------------------
# THE anti-drift guard. Everything else in this file is a detail of how the shelf gets here.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        {"id": "empty-service", "config": {}},
        {"id": "stream-service", "config": {"SERVER_TYPE": {"value": "stream", "method": "ui"}}},
        {
            "id": "scheduler-locked",
            "config": {"USE_ANTIBOT": {"value": "captcha", "method": "scheduler"}, "USE_BROTLI": {"value": "yes", "method": "scheduler"}},
        },
        {"id": "global-page", "config": {}, "global_page": True},
        {"id": "readonly", "config": {}, "is_readonly": True},
    ],
    ids=lambda case: case["id"],
)
def test_row_posts_exactly_the_declared_scope(case, render_shelf):
    """A row renders enabled postable inputs IFF `shelf_plugin_scope` is non-empty, and it
    posts EXACTLY that set -- both directions, over every shipped manifest.

    Over-claiming is silent data loss (an in-scope key the form never sends is deleted);
    under-claiming only preserves. Asserting equality catches both, and asserting it per
    plugin rather than over the union catches a row that posts a *neighbour's* key."""
    kwargs = {k: v for k, v in case.items() if k != "id"}
    parser = parse_shelf(render_shelf(**kwargs))
    assert parser.rows, "the settings-driven loop rendered no rows at all"

    for plugin_id, row in parser.rows.items():
        expected = _expected_scope(plugin_id, **kwargs)
        assert set(row["posts"]) == expected, f"{plugin_id}: posts {sorted(row['posts'])}, scope {sorted(expected)}"
        # Nothing may post under a name that is not marked as a shelf key either: an
        # unmarked `name=` would evade the check above while still reaching the payload.
        assert set(row["names"]) == expected, f"{plugin_id}: unmarked posting input(s) {sorted(set(row['names']) - expected)}"
        # One name may be repeated exactly twice, and only as the checkbox + its fallback.
        for name in set(row["posts"]):
            assert row["posts"].count(name) <= 2


NO_OP_CASES = [
    {"id": "empty-service", "config": {}},
    {"id": "stream-service", "config": {"SERVER_TYPE": {"value": "stream", "method": "ui"}}},
    {"id": "everything-on", "config": {"USE_BROTLI": {"value": "yes"}, "USE_ANTIBOT": {"value": "captcha"}, "INJECT_BODY": {"value": "<b>x</b>"}}},
    {"id": "limit-half-off", "config": {"USE_LIMIT_REQ": {"value": "no"}, "USE_LIMIT_CONN": {"value": "yes"}}},
    {"id": "antibot-value-outside-select", "config": {"USE_ANTIBOT": {"value": "legacy-challenge"}}},
    # IS_DRAFT is blacklisted, so `restore_unowned_settings` never puts it back and
    # routes/services.py pops it: a shelf that posts "no" for a drafted service PUBLISHES it.
    # The one control key whose wrong value is silently destructive rather than merely absent.
    {"id": "draft-service", "config": {"IS_DRAFT": {"value": "yes"}}},
    {"id": "global-page", "config": {}, "global_page": True},
    {"id": "readonly", "config": {}, "is_readonly": True},
    # The dual-source hazard: `is_plugin_active` re-reads get_activation_map() internally and
    # returns {} on a scan failure. Whatever the row's map says, the row must stay self-
    # consistent -- a checkbox rendered unchecked beside its own live keys posts the fallback
    # and silently turns the plugin off on a save that touched nothing.
    {"id": "activation-map-lost", "config": {}, "activation_map": {}},
]


@pytest.mark.parametrize("case", NO_OP_CASES, ids=lambda case: case["id"])
def test_an_untouched_save_posts_exactly_what_is_already_stored(case, render_shelf):
    """The property every other test here is a proxy for: submitting this markup without
    touching a single control must write NOTHING new.

    A shelf that silently flips a value on save is worse than one that deletes a row, because
    nothing in the UI reports it. Serialised the way a browser does (see `browser_payload`),
    so it catches the failures the markup-shape assertions cannot: an unchecked box whose keys
    are live, a `<select>` with nothing selected, a fallback that outruns its own box."""
    kwargs = {key: value for key, value in case.items() if key != "id"}
    stored = _config(kwargs.get("config"), kwargs.get("global_page", False))
    payload = browser_payload(parse_shelf(render_shelf(**kwargs)))
    assert payload, "an untouched save that posts nothing at all is not a no-op either"
    for key, value in payload.items():
        # OLD_SERVER_NAME is the rename pair's "before", read off SERVER_NAME by design.
        source = "SERVER_NAME" if key == "OLD_SERVER_NAME" else key
        assert value == stored.get(source, {}).get("value", ""), f"{key} would change from {stored.get(source, {}).get('value')!r} to {value!r}"


def test_a_scan_failure_inside_a_helper_cannot_flip_a_switch(monkeypatch, tmp_path, render_shelf):
    """The dual-source hazard, reproduced in the only direction that bites.

    `get_activation_map()` swallows a scan failure and returns {} (app/utils.py), dropping
    every plugin to the USE_<ID> tier-3 convention -- and `is_plugin_active` /
    `is_plugin_active_for_service` call it INTERNALLY, so a row that took its declaration from
    the context map and its checked state from that helper would disagree with itself. For
    `limit` the helper looks for `USE_LIMIT`, finds nothing, reports inactive: the switch
    renders unchecked beside its own live keys and the adjacent fallback posts
    USE_LIMIT_REQ=no. An untouched save silently disables the request rate limiter.

    Rendering with the context map INTACT while the helper's internal one is empty is the only
    arrangement that exposes it -- an empty context map makes the row render no switch at all
    and the probe goes vacuous."""
    import plugin_extensions  # type: ignore  # on sys.path via the ui conftest

    # All three roots, not just core: the other two point at /etc/bunkerweb/... which is absent
    # in a checkout but PRESENT inside a built image, where leaving them unpatched would make
    # the premise assert below fail rather than the probe run.
    for root in ("CORE_PLUGINS_PATH", "PRO_PLUGINS_PATH", "EXTERNAL_PLUGINS_PATH"):
        monkeypatch.setattr(plugin_extensions, root, str(tmp_path))
    get_activation_map.cache_clear()
    assert get_activation_map() == {}, "probe premise: the helper's internal map must be empty"
    assert REAL_ACTIVATION_MAP["limit"], "probe premise: the context map must still be populated"

    stored = _config(None)
    payload = browser_payload(parse_shelf(render_shelf()))
    for key, value in payload.items():
        source = "SERVER_NAME" if key == "OLD_SERVER_NAME" else key
        assert value == stored.get(source, {}).get("value", ""), f"{key} would change from {stored.get(source, {}).get('value')!r} to {value!r}"


def test_workflows_never_renders_a_row(render_shelf):
    """`workflows` is resource-backed but has zero multisite settings, so the settings-driven
    loop drops it. A hardcoded row list is exactly how it would sneak back in."""
    parser = parse_shelf(render_shelf())
    assert "workflows" not in parser.rows
    for zero_multisite in ("backup", "certificates", "db", "geoip", "jobs", "pro", "redis", "templates", "workflows"):
        assert zero_multisite not in parser.rows


def test_every_shelf_eligible_plugin_renders_a_row(render_shelf):
    """The complement of the test above: the loop must not silently drop a plugin that does
    have multisite settings."""
    parser = parse_shelf(render_shelf())
    expected = {plugin for plugin, data in REAL_PLUGINS.items() if get_filtered_settings(data["settings"], False)}
    assert set(parser.rows) == expected


# --------------------------------------------------------------------------------------
# The control shapes of D2's table, each on the real plugin that has that shape.
# --------------------------------------------------------------------------------------


def test_check_setting_renders_a_switch_with_an_adjacent_inactive_fallback(render_shelf):
    """An unchecked checkbox posts NOTHING, so the fallback is not optional -- and it must sit
    immediately after its own box: `request.form.to_dict()` keeps the FIRST value, so a
    fallback moved to the end of the form would land after the trailing control inputs and a
    switched-off USE_UI would lose to the stale control value."""
    row = parse_shelf(render_shelf()).rows["brotli"]
    tags = [(tag, attrs) for tag, attrs in row["tags"] if attrs.get("name") == "USE_BROTLI"]
    assert len(tags) == 2
    (first_tag, first_attrs), (second_tag, second_attrs) = tags
    assert first_tag == "input" and first_attrs.get("type") == "checkbox"
    assert second_tag == "input" and second_attrs.get("type") == "hidden"
    assert second_attrs["value"] == "no"
    # Adjacent: nothing carrying a name may sit between the two.
    start, stop = row["tags"].index(tags[0]) + 1, row["tags"].index(tags[1])
    assert not [attrs for _, attrs in row["tags"][start:stop] if attrs.get("name")]


def test_switch_is_checked_and_posts_the_current_value_when_already_active(render_shelf):
    """A save that touches nothing must write nothing new, so an already-on switch carries the
    STORED value, not a canonical one."""
    config = {"USE_ANTIBOT": {"value": "no", "method": "ui"}, "USE_BROTLI": {"value": "yes", "method": "ui"}}
    row = parse_shelf(render_shelf(config=config)).rows["brotli"]
    box = next(attrs for tag, attrs in row["tags"] if attrs.get("type") == "checkbox")
    assert "checked" in box
    assert box["value"] == "yes"


def test_switch_is_unchecked_and_offers_the_active_value_when_inactive(render_shelf):
    row = parse_shelf(render_shelf(config={"USE_BROTLI": {"value": "no", "method": "ui"}})).rows["brotli"]
    box = next(attrs for tag, attrs in row["tags"] if attrs.get("type") == "checkbox")
    assert "checked" not in box
    assert box["value"] == "yes"


def test_multi_key_plugin_renders_one_switch_and_posts_every_declared_key(render_shelf):
    """`limit` declares USE_LIMIT_REQ + USE_LIMIT_CONN, both defaulting to "yes". Posting only
    the first would leave the second in scope and unposted -- its row deleted, its "yes"
    default restored, the connection limiter silently back on."""
    row = parse_shelf(render_shelf()).rows["limit"]
    boxes = [attrs for _, attrs in row["tags"] if attrs.get("type") == "checkbox"]
    assert len(boxes) == 1, "one switch per row, whatever the key count"
    assert set(row["posts"]) == _expected_scope("limit")
    siblings = [attrs for _, attrs in row["tags"] if "data-shelf-sibling" in attrs]
    assert siblings, "the non-first declared keys must render as siblings the JS can flip"
    for sibling in siblings:
        assert sibling["data-shelf-inactive"] == REAL_ACTIVATION_MAP["limit"][sibling["name"]]


def test_multiselect_and_multiple_activation_keys_post_nothing(render_shelf):
    """Locked with the PO: a count and a chevron, never a switch. `_in_scope` base-matches, so
    claiming REDIRECT_TO would drag every stored REDIRECT_TO_<n> into scope for a row that
    posts none of them."""
    parser = parse_shelf(
        render_shelf(config={"REDIRECT_TO": {"value": "https://a/", "method": "ui"}, "REDIRECT_TO_1": {"value": "https://b/", "method": "ui"}})
    )
    for plugin_id in ("redirect", "country"):
        assert parser.rows[plugin_id]["posts"] == []
        assert parser.rows[plugin_id]["attrs"]["data-shelf-kind"] == "delegated"


def test_select_with_several_remaining_values_renders_a_picker(render_shelf):
    """USE_ANTIBOT is a 9-value select; a switch cannot express it. The <select> is itself the
    postable input -- a real select always posts, so it needs no fallback."""
    row = parse_shelf(render_shelf(config={"USE_ANTIBOT": {"value": "captcha", "method": "ui"}})).rows["antibot"]
    assert row["attrs"]["data-shelf-kind"] == "picker"
    selects = [attrs for tag, attrs in row["tags"] if tag == "select"]
    assert len(selects) == 1 and selects[0]["name"] == "USE_ANTIBOT"
    options = [attrs for tag, attrs in row["tags"] if tag == "option"]
    assert {option["value"] for option in options} == set(REAL_PLUGINS["antibot"]["settings"]["USE_ANTIBOT"]["select"])
    assert [option for option in options if "selected" in option][0]["value"] == "captcha"


def test_free_text_activation_keys_render_an_opener_and_post_nothing(render_shelf):
    """The §D2/T1 contradiction, resolved at the scope rather than in the markup: `type`/`regex`
    admit every string, so no active value is derivable and the shelf must not invent one.

    Posting the stored value back to keep the keys in scope was the first answer and it was worse
    than the deletion it avoided -- `check_variables` normalises CRLF and `edit_service` trims
    (`common_utils.py:163`; `text` is not in `NO_TRIM_TYPES`), so a multi-line INJECT_BODY comes
    back changed, `_is_default_value` stops matching the global, and config_save materialises a
    real `ui` row that permanently decouples the service from it. `shelf_plugin_scope` now drops
    `text` at source, so the row owns nothing and posts nothing, exactly as §D2 said."""
    config = {"INJECT_BODY": {"value": "<b>hi</b>\r\n", "method": "ui"}, "INJECT_HEAD": {"value": "", "method": "ui"}}
    row = parse_shelf(render_shelf(config=config)).rows["inject"]
    assert row["attrs"]["data-shelf-kind"] == "opener"
    assert row["posts"] == [] == list(_expected_scope("inject", config))
    assert [attrs for _, attrs in row["tags"] if attrs.get("name")] == [], "an opener must emit no named input at all"


# No PRO plugin ships in this repo (`find src -name plugin.json -not -path "src/common/core/*"`
# is empty), so the licence gate at services.py:530-531 and this partial's `pro_locked` have no
# real manifest to exercise. A minimal stand-in is the only way to reach them; it is shaped
# exactly like a core `check` plugin so the ONLY thing under test is the `type: "pro"` gate.
PRO_PLUGIN = {
    "id": "waf_extra",
    "name": "WAF Extra",
    "type": "pro",
    "stream": "yes",
    "version": "1.0",
    "settings": {"USE_WAF_EXTRA": {"id": "use-waf-extra", "context": "multisite", "default": "no", "type": "check", "label": "WAF Extra"}},
}


@pytest.mark.parametrize("licensed", [False, True])
def test_a_pro_plugin_is_postable_only_with_an_active_licence(licensed, render_shelf):
    """Without a licence every field renders disabled, so claiming the key in scope would
    delete its row on the first save. The row must go quiet, not half-quiet."""
    plugins = REAL_PLUGINS | {"waf_extra": PRO_PLUGIN}
    parser = parse_shelf(render_shelf(plugins=plugins, is_pro_version=licensed))
    row = parser.rows["waf_extra"]
    expected = shelf_plugin_scope(
        "waf_extra",
        PRO_PLUGIN,
        _config(None),
        global_page=False,
        is_pro_version=licensed,
        blacklisted=get_blacklisted_settings(False),
        activation_map=REAL_ACTIVATION_MAP,
    )
    assert set(row["posts"]) == expected
    assert expected == ({"USE_WAF_EXTRA"} if licensed else set())
    assert row["attrs"]["data-shelf-kind"] == ("switch" if licensed else "locked")
    # An unlicensed PRO plugin must never read live, whatever its settings say.
    assert row["attrs"]["data-shelf-on"] == "false"


def test_always_on_plugins_render_no_control(render_shelf):
    parser = parse_shelf(render_shelf())
    for plugin_id in ("ssl", "headers", "misc", "sessions", "general"):
        assert parser.rows[plugin_id]["attrs"]["data-shelf-kind"] == "always"
        assert parser.rows[plugin_id]["posts"] == []


def test_stream_service_locks_http_only_plugins(render_shelf):
    """`plugin_data["stream"]` has three values and only the literal "no" excludes; a `partial`
    plugin must keep its switch."""
    parser = parse_shelf(render_shelf(config={"SERVER_TYPE": {"value": "stream", "method": "ui"}}))
    assert parser.rows["brotli"]["attrs"]["data-shelf-kind"] == "locked"
    assert parser.rows["brotli"]["posts"] == []
    assert parser.rows["limit"]["attrs"]["data-shelf-kind"] == "switch"


def test_stream_locked_rows_say_why(render_shelf):
    """`errors` and `headers` declare `extensions.activation: "always"` AND `stream: no`, so
    they are the only case where the stream branch is not redundant with the empty scope:
    without it running FIRST the row would claim "Always on" on an L4 service where the
    plugin's confs are never emitted."""
    for plugin_id in ("errors", "headers"):
        assert REAL_ACTIVATION_MAP[plugin_id] == "always", "fixture premise"
        assert REAL_PLUGINS[plugin_id]["stream"] == "no", "fixture premise"
    parser = parse_shelf(render_shelf(config={"SERVER_TYPE": {"value": "stream", "method": "ui"}}))
    for plugin_id in ("brotli", "errors", "headers"):
        row = parser.rows[plugin_id]
        assert row["attrs"]["data-shelf-kind"] == "locked", f"{plugin_id} is stream: no"
        assert any(attrs.get("data-i18n") == "tooltip.stream_support.no" for _, attrs in row["tags"]), f"{plugin_id} gives no reason"
    # An http service keeps them all, and `partial` is never excluded on either.
    http = parse_shelf(render_shelf())
    assert http.rows["headers"]["attrs"]["data-shelf-kind"] == "always"
    assert not any(attrs.get("data-i18n") == "tooltip.stream_support.no" for _, attrs in http.rows["brotli"]["tags"])


def test_a_non_ui_editable_method_leaves_the_row_unpostable(render_shelf):
    config = {"USE_BROTLI": {"value": "yes", "method": "scheduler"}}
    row = parse_shelf(render_shelf(config=config)).rows["brotli"]
    assert row["posts"] == []
    assert row["attrs"]["data-shelf-kind"] == "locked"


# --------------------------------------------------------------------------------------
# Control keys -- the surface must post them itself, because restore_unowned_settings never
# restores a `restore_skip` key.
# --------------------------------------------------------------------------------------


def test_service_page_posts_every_control_key_after_the_shelf_body(render_shelf):
    """Omitting IS_DRAFT publishes a draft service; omitting SERVER_NAME *and*
    OLD_SERVER_NAME makes edit_service raise IndexError inside the executor thread. They must
    come after the body: first-value-wins is what lets the `ui` plugin's USE_UI switch beat
    the trailing USE_UI fallback."""
    parser = parse_shelf(render_shelf(config={"SERVER_NAME": {"value": "app.example.com"}, "IS_DRAFT": {"value": "yes"}}))
    outside = dict((name, position) for position, name in parser.outside)
    assert set(outside) == set(control_keys(False))
    last_row_position = max(row["position"] for row in parser.rows.values())
    assert min(outside.values()) > last_row_position


def test_global_page_posts_no_control_keys(render_shelf):
    """At global scope SERVER_NAME is the service LIST -- posting it would rewrite it."""
    parser = parse_shelf(render_shelf(global_page=True))
    assert parser.outside == []
    assert control_keys(True) == ()


def test_control_keys_are_emitted_even_when_readonly(render_shelf):
    """A hidden input is not disabled by a readonly page, and a crafted POST that omits
    IS_DRAFT still publishes the service."""
    parser = parse_shelf(render_shelf(is_readonly=True, config={"IS_DRAFT": {"value": "yes"}}))
    assert set(name for _, name in parser.outside) == set(control_keys(False))
    assert not any(row["posts"] for row in parser.rows.values())


def _include_closure(page_name, seen=None):
    """Every template reachable from `page_name` through literal `{% include "..." %}`.

    Transitive on purpose: the established shape is a one-line include of a per-mode partial
    (`service_settings.html:39-45` includes `models/plugins_settings_easy.html` and friends),
    so T7 will almost certainly reach this shelf through a `models/plugins_settings_compose.html`
    rather than directly. A guard that greps the two page files for the literal name would go
    permanently silent on exactly that commit. Only literal includes are followed -- an
    `{% include some_var %}` would escape this, and none exists today.
    """
    seen = seen if seen is not None else set()
    if page_name in seen:
        return seen
    seen.add(page_name)
    path = TEMPLATES / page_name
    if not path.is_file():
        return seen
    for included in re.findall(r"{%-?\s*include\s+[\"']([^\"']+)[\"']", path.read_text(encoding="utf-8")):
        _include_closure(included, seen)
    return seen


def test_the_host_page_must_post_the_shelf_through_a_real_form():
    """A page that reaches this shelf must submit it with a REAL form, and must not hand it to
    the monolith's synthetic one.

    `getFormFromSettings` (static/js/plugins-settings.js:1075) ignores its `elem` argument and
    harvests fixed selectors -- `getTemplateContainer(currentTemplate)` (:1206) and
    `$("div[id^='navs-plugins-']")` (:1216) -- so merely LOADING that file cannot reach the
    shelf, and both host pages already load it for raw mode. The hazard is the TRIGGER: the
    monolith binds `$(".save-settings").on("click", ...)` (:2025), calls `getFormFromSettings`
    (:2200) and submits it natively (:2214). Copy that class onto a compose Save button and
    `currentMode === "compose"` matches no branch (:1203-1325), so the POST carries only
    csrf_token + IS_DRAFT + OLD_SERVER_NAME while routes/services.py:1110-1126 still hands it
    the full shelf scope -- every in-scope key unposted, every one of them deleted.

    Trivially true until T7 wires the shelf in; it bites on exactly the commit that would cause
    the loss, and it is satisfiable in both directions (a plain `type="submit"` button, or a
    page that no longer loads the monolith)."""
    for page_name in ("service_settings.html", "global_settings.html"):
        closure = _include_closure(page_name)
        if "models/compose_shelf.html" not in closure:
            continue
        sources = {name: (TEMPLATES / name).read_text(encoding="utf-8") for name in closure if (TEMPLATES / name).is_file()}
        blob = "\n".join(sources.values())
        assert "<form" in blob, f"{page_name} reaches the shelf but renders no form to post it"
        if "js/plugins-settings.js" in blob:
            offenders = [name for name, source in sources.items() if "save-settings" in source]
            assert (
                not offenders
            ), f"{page_name} loads the monolith and carries save-settings in {offenders}: the shelf would be submitted through getFormFromSettings"


# --------------------------------------------------------------------------------------
# Folding and filters
# --------------------------------------------------------------------------------------


def test_folded_rows_are_hidden_with_display_none_only(render_shelf):
    """Detaching or rebuilding a folded row stops its hidden inputs posting while its keys
    stay in scope, which deletes them. The fold is a style, never a DOM edit."""
    parser = parse_shelf(render_shelf())
    folded = [row for row in parser.rows.values() if "data-shelf-folded" in row["attrs"]]
    assert folded, "an all-defaults service has inactive plugins to fold"
    for row in folded:
        assert row["attrs"]["style"].replace(" ", "") == "display:none"
        assert set(row["attrs"]) & {"hidden", "disabled"} == set()
    # A folded row that is in scope still posts every one of its keys -- `brotli` defaults to
    # "no", so it is folded, and it is the case that would silently lose its row.
    brotli = parser.rows["brotli"]
    assert "data-shelf-folded" in brotli["attrs"]
    assert set(brotli["posts"]) == _expected_scope("brotli")


def test_the_shelf_script_only_ever_hides_rows():
    """The fold and the filter must be `display:none` and nothing else. A `remove()`,
    `detach()` or `innerHTML` rebuild stops a row's hidden inputs posting while its keys stay
    in scope, and `save_config` deletes every in-scope key the form did not post. There is no
    JS test framework in this repo, so this reads the source -- crude, but it fails on exactly
    the edit that would cause the data loss."""
    source = (REPO_ROOT / "src" / "ui" / "app" / "static" / "js" / "components" / "compose-shelf.js").read_text(encoding="utf-8")
    body = "\n".join(line for line in source.splitlines() if not line.strip().startswith("//"))
    assert "row.style.display" in body, "the row visibility pass must be a display change on the row itself"
    for forbidden in (".remove(", ".detach(", "innerHTML", "removeChild", "replaceChildren", ".disabled =", 'setAttribute("disabled', "removeAttribute"):
        assert forbidden not in body, f"the shelf script must not {forbidden} a row"


def test_rows_carry_the_filter_facets(render_shelf):
    config = {"USE_BROTLI": {"value": "yes", "method": "ui"}}
    parser = parse_shelf(render_shelf(config=config))
    assert parser.rows["brotli"]["attrs"]["data-shelf-on"] == "true"
    assert parser.rows["brotli"]["attrs"]["data-shelf-changed"] == "true"
    assert parser.rows["gzip"]["attrs"]["data-shelf-on"] == "false"
    assert parser.rows["gzip"]["attrs"]["data-shelf-changed"] == "false"


def test_shelf_renders_counts_and_the_three_way_filter(render_shelf):
    html = render_shelf()
    assert 'data-shelf-filter="on"' in html and 'data-shelf-filter="all"' in html and 'data-shelf-filter="changed"' in html
    assert 'id="compose-shelf-counts"' in html


def test_attachment_makes_a_resource_backed_plugin_read_live(render_shelf):
    """`is_plugin_active_for_service` short-circuits on an attached resource, so the dot must
    say live even with USE_REVERSE_PROXY=no -- while the switch, which reflects the setting
    itself, stays off so an untouched save writes nothing."""
    attachments = {"upstream": {"items": [{"id": "pool"}], "error": None}}
    row = parse_shelf(render_shelf(attachments=attachments)).rows["reverseproxy"]
    assert row["attrs"]["data-shelf-on"] == "true"
    box = next(attrs for _, attrs in row["tags"] if attrs.get("type") == "checkbox")
    assert "checked" not in box

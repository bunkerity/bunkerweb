"""The request-path strip: what it renders, in what order, and -- first of all -- that it
renders nothing postable.

The strip is included INSIDE the compose form, so a single named control would join the
payload and `Database.save_config` treats a POST as the complete desired state
(`db_methods/config_save.py:592`). `test_the_strip_posts_absolutely_nothing` is therefore the
load-bearing guard here; everything else is about not lying to the operator.

Fixtures are read off the REAL shipped manifests, settings.json and order.json rather than
transcribed, so a manifest edit surfaces as a test result instead of as silent drift.
"""

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from app.models.plugin_activation import is_plugin_active_for_service
from app.utils import get_filtered_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "src" / "ui" / "app" / "templates"
CORE_PLUGINS = REPO_ROOT / "src" / "common" / "core"

ORDER_JSON = json.loads((CORE_PLUGINS / "order.json").read_text(encoding="utf-8"))
SETTINGS_JSON = json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8"))
ACCESS_DEFAULT = SETTINGS_JSON["PLUGINS_ORDER_ACCESS"]["default"].split()
PREREAD_DEFAULT = SETTINGS_JSON["PLUGINS_ORDER_PREREAD"]["default"].split()

SERVICE = "app.example.com"


def _real_plugins():
    """Every shipped plugin in `BW_CONFIG.get_plugins()` shape, `general` included.

    `general` has no plugin.json (db_methods/initialization.py synthesizes it from
    settings.json at boot) and is force-active through `_SYNTHESIZED_ALWAYS_ON`, so leaving
    it out would skip the one row the strip's by-name carve-out exists for.
    """
    plugins = {
        "general": {
            "id": "general",
            "name": "General",
            "version": "0.1",
            "stream": "partial",
            "type": "core",
            "settings": SETTINGS_JSON,
        }
    }
    for manifest_path in sorted(CORE_PLUGINS.glob("*/plugin.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plugins[manifest.get("id") or manifest_path.parent.name] = manifest | {"type": "core"}
    return plugins


REAL_PLUGINS = _real_plugins()


def _seeded_config(stream=False):
    """`config` in the shape the service page actually passes.

    `get_config` seeds every setting from its own default before layering stored values and
    then drops every global-context key for a service. That matters twice over: an empty dict
    would report every on-by-default plugin (`whitelist`, `blacklist`, `dnsbl`, `limit`,
    `modsecurity`) as OFF, and `PLUGINS_ORDER_ACCESS` -- the strip's whole ordering source --
    would be absent.
    """
    config = {}
    for data in REAL_PLUGINS.values():
        for setting, setting_data in (data.get("settings") or {}).items():
            if setting_data.get("context") != "multisite":
                continue
            config[setting] = {"value": setting_data.get("default", ""), "method": "default", "global": False}
    if stream:
        config["SERVER_TYPE"] = {"value": "stream", "method": "ui", "global": False}
    return config


def _config(overrides=None, stream=False):
    return _seeded_config(stream) | {key: {"method": "ui", "global": False} | value for key, value in (overrides or {}).items()}


def _upstream(pool_id, name, protocol, attachments):
    """An upstream row in `db_methods/upstreams.py:_upstream_dict` shape.

    No top-level `match_path` -- the path lives on each attachment under `services`, and
    `get_upstreams(service_id=...)` filters the ROWS, never the nested list, so a row can
    legitimately carry another service's attachment.
    """
    return {
        "id": pool_id,
        "name": name,
        "protocol": protocol,
        "servers": [],
        "services": [{"service_id": service_id, "match_path": match_path} for service_id, match_path in attachments],
    }


def _attachments(**families):
    return {family: {"items": families.get(family) or [], "error": None} for family in ("upstream", "certificate", "redirect", "workflow")}


class _StripParser(HTMLParser):
    """Collect the strip's nodes in document order, plus every attribute it emitted."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []  # [(data-request-node, data-request-node-kind)]
        self.tags = []  # [(tag, attrs)]
        self.terminal_kind = None
        self.strip_attrs = {}
        self._node = None
        self.text = {}  # node -> concatenated text

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if "data-request-path" in attributes:
            self.strip_attrs = attributes
        if "data-request-node" in attributes:
            self._node = attributes["data-request-node"]
            self.nodes.append((self._node, attributes.get("data-request-node-kind")))
            if "data-request-terminal" in attributes:
                self.terminal_kind = attributes["data-request-terminal"]

    def handle_data(self, data):
        if self._node and data.strip():
            self.text.setdefault(self._node, "")
            self.text[self._node] += data.strip() + " "


@pytest.fixture
def render_strip():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(
        get_filtered_settings=get_filtered_settings,
        is_plugin_active_for_service=is_plugin_active_for_service,
    )

    def _render(config=None, *, stream=False, plugins=None, attachments=None, service_id=SERVICE, is_pro_version=False, plugin_order=None):
        html = env.get_template("models/request_path_strip.html").render(
            plugins=plugins or REAL_PLUGINS,
            config=_config(config, stream),
            service_id=service_id,
            attachments=attachments if attachments is not None else _attachments(),
            is_pro_version=is_pro_version,
            **({"plugin_order": plugin_order} if plugin_order is not None else {}),
        )
        parser = _StripParser()
        parser.feed(html)
        parser.html = html
        return parser

    return _render


def _kind(parser, kind):
    return [node for node, node_kind in parser.nodes if node_kind == kind]


# --------------------------------------------------------------------------------------
# THE guard. The strip lives inside the compose form; anything postable here changes a save.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        {"id": "stock", "kwargs": {}},
        {"id": "stream", "kwargs": {"stream": True}},
        {"id": "with-pool", "kwargs": {"attachments": _attachments(upstream=[_upstream("u1", "api", "http", [(SERVICE, "/")])])}},
        {"id": "inline-proxy", "kwargs": {"config": {"USE_REVERSE_PROXY": {"value": "yes"}, "REVERSE_PROXY_HOST": {"value": "http://app:8080"}}}},
        {"id": "nothing-served", "kwargs": {"config": {"SERVE_FILES": {"value": "no"}}}},
    ],
    ids=lambda case: case["id"],
)
def test_the_strip_posts_absolutely_nothing(case, render_strip):
    """No form control, no `name`, no nested `<form>` -- in every terminal branch.

    A stray named input joins `request.form.to_dict()`, and an in-scope key whose value the
    strip decided is a silent config rewrite; a nested `<form>` is invalid HTML and detaches
    the shelf's controls from the compose payload entirely.
    """
    parser = render_strip(**case["kwargs"])
    assert parser.nodes, "the strip rendered no nodes at all"
    for tag, attributes in parser.tags:
        assert tag not in ("input", "select", "textarea", "form", "button"), f"the strip emitted a <{tag}>"
        assert "name" not in attributes, f"<{tag}> carries name={attributes['name']!r}"


def test_the_strip_is_suppressed_when_there_is_no_service(render_strip):
    """`/services/new` passes `service_id=""` and the GLOBAL config -- there is no request
    path to trace, and the SERVER_NAME there is the service LIST, not this service."""
    parser = render_strip(service_id="")
    assert parser.nodes == []


# --------------------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------------------


def test_ordered_nodes_follow_the_phase_setting_and_only_the_active_ones(render_strip):
    """`PLUGINS_ORDER_ACCESS` is the runtime's FIRST pass (helpers.lua:174-182) and is
    `context: multisite`, so it is already on the page. Its shipped default even disagrees
    with order.json (bunkernet/crowdsec swapped), so order.json alone would be wrong about
    two nodes on every stock service."""
    parser = render_strip()
    ordered = _kind(parser, "ordered")

    assert ordered == [plugin for plugin in ACCESS_DEFAULT if plugin in ordered]
    # Active-by-default access plugins are there; the off-by-default ones are not.
    assert {"ssl", "whitelist", "blacklist", "dnsbl", "limit", "misc"} <= set(ordered)
    assert "antibot" not in ordered and "authbasic" not in ordered
    assert parser.strip_attrs.get("data-request-phase") == "access"
    assert parser.strip_attrs.get("data-request-order-source") == "PLUGINS_ORDER_ACCESS"


def test_a_service_that_reorders_its_access_phase_reorders_the_strip(render_strip):
    """The order is per-service data, not a constant: `PLUGINS_ORDER_ACCESS` is multisite and
    pass 1 beats order.json, so a strip that hardcoded the file would be silently wrong here."""
    parser = render_strip({"PLUGINS_ORDER_ACCESS": {"value": "limit whitelist ssl"}})
    assert _kind(parser, "ordered") == ["limit", "whitelist", "ssl"]
    # Everything else active keeps a position -- appended, never dropped.
    assert {"blacklist", "dnsbl", "misc"} <= set(_kind(parser, "unordered"))


def test_plugin_order_fills_the_gap_a_partial_setting_override_leaves(render_strip):
    """Runtime pass 2: the ids from order.json not already claimed by the setting. Supplied by
    the page as `plugin_order`; absent, those plugins fall to the alphabetical tail instead."""
    override = {"PLUGINS_ORDER_ACCESS": {"value": "antibot"}, "USE_ANTIBOT": {"value": "captcha"}}
    with_order = render_strip(override, plugin_order=ORDER_JSON)
    ordered = _kind(with_order, "ordered")
    assert ordered[0] == "antibot"
    assert ordered[1:] == [plugin for plugin in ORDER_JSON["access"] if plugin in ordered[1:]]
    assert "ssl" in ordered and "misc" in ordered

    without_order = render_strip(override)
    assert _kind(without_order, "ordered") == ["antibot"]
    assert {"ssl", "misc"} <= set(_kind(without_order, "unordered"))


def test_a_stream_service_renders_the_preread_phase(render_strip):
    """`access` does not exist for a stream server; `preread` is the TCP analogue, and it is a
    strictly smaller list -- `ssl`, `misc`, `limit` and `antibot` are access-only."""
    parser = render_strip(stream=True)
    assert parser.strip_attrs.get("data-request-phase") == "preread"
    assert parser.strip_attrs.get("data-request-order-source") == "PLUGINS_ORDER_PREREAD"
    ordered = _kind(parser, "ordered")
    assert ordered == [plugin for plugin in PREREAD_DEFAULT if plugin in ordered]
    assert set(ordered) <= set(PREREAD_DEFAULT)
    assert "ssl" not in ordered and "misc" not in ordered


def test_an_active_plugin_with_no_position_is_appended_alphabetically_not_dropped(render_strip):
    """An external or PRO plugin can never be in order.json (a shipped file) and lands in
    runtime pass 3: appended to the phase, sorted alphabetically. So does every core plugin
    that ships only `confs/` and no Lua -- `modsecurity` above all, which an operator would
    otherwise see nowhere despite it inspecting every request."""
    plugins = REAL_PLUGINS | {
        "zeta": {
            "id": "zeta",
            "name": "Zeta",
            "type": "external",
            "stream": "yes",
            "settings": {"USE_ZETA": {"context": "multisite", "type": "check", "default": "yes"}},
        },
        "alpha": {
            "id": "alpha",
            "name": "Alpha",
            "type": "external",
            "stream": "yes",
            "settings": {"USE_ALPHA": {"context": "multisite", "type": "check", "default": "yes"}},
        },
    }
    parser = render_strip({"USE_ZETA": {"value": "yes"}, "USE_ALPHA": {"value": "yes"}}, plugins=plugins)
    unordered = _kind(parser, "unordered")

    assert "modsecurity" in unordered
    assert "alpha" in unordered and "zeta" in unordered
    assert unordered.index("alpha") < unordered.index("zeta")
    assert unordered == sorted(unordered)
    # And they come AFTER every ordered node, which is what "appended" means.
    kinds = [kind for _, kind in parser.nodes if kind in ("ordered", "unordered")]
    assert kinds == sorted(kinds, key=lambda kind: kind == "unordered")


def test_an_inactive_plugin_is_not_a_node(render_strip):
    """`antibot` off by default, on when its select leaves the inactive value."""
    assert "antibot" not in [node for node, _ in render_strip().nodes]
    assert "antibot" in _kind(render_strip({"USE_ANTIBOT": {"value": "captcha"}}), "ordered")


def test_a_pro_plugin_without_a_licence_is_not_a_node(render_strip):
    """Same `pro_locked` test the shelf's row uses: no licence, not running, not a node."""
    plugins = REAL_PLUGINS | {
        "shield": {
            "id": "shield",
            "name": "Shield",
            "type": "pro",
            "stream": "yes",
            "settings": {"USE_SHIELD": {"context": "multisite", "type": "check", "default": "yes"}},
        }
    }
    on = {"USE_SHIELD": {"value": "yes"}}
    assert "shield" not in [node for node, _ in render_strip(on, plugins=plugins).nodes]
    assert "shield" in _kind(render_strip(on, plugins=plugins, is_pro_version=True), "unordered")


def test_workflows_reaches_the_strip_through_an_attachment_alone(render_strip):
    """`workflows` has ZERO multisite settings, so it renders no shelf row and its settings can
    never report it active -- yet it sits at `access` index 16. Only
    `is_plugin_active_for_service`'s attachment lookup finds it, which is why the strip
    iterates `plugins` rather than the shelf's rows."""
    assert "workflows" not in [node for node, _ in render_strip().nodes]
    attached = render_strip(attachments=_attachments(workflow=[{"id": "w1", "name": "policy", "services": [SERVICE]}]))
    assert "workflows" in _kind(attached, "ordered")


def test_a_plugin_with_no_multisite_setting_and_no_position_is_not_a_node(render_strip):
    """`pro` declares `"activation": "always"` so it always reads active, but it has no
    multisite setting and no place in any request phase -- it is not part of THIS service's
    path. Same for the synthesized `general` settings bag."""
    nodes = [node for node, _ in render_strip().nodes]
    assert "pro" not in nodes
    assert "general" not in nodes


# --------------------------------------------------------------------------------------
# The terminal
# --------------------------------------------------------------------------------------


def test_terminal_prefers_the_pool_at_root_and_ignores_other_services_attachments(render_strip):
    """Rows come back in `Resources.name` order, the nested list in `(service_id, match_path)`
    order and generation uses `(creation_date, name)` -- none of them "by path". And
    `get_upstreams(service_id=...)` filters the rows, NOT the nested list, so a row can carry
    another service's attachment and reading it without the `service_id` filter names the
    wrong backend.

    The row order below is deliberately adversarial: the foreign pool is ALSO at "/" and comes
    first, so dropping the filter changes the answer; and the surviving root pool comes LAST,
    so dropping the sort changes it too.
    """
    parser = render_strip(
        attachments=_attachments(
            upstream=[
                _upstream("u1", "foreign-pool", "http", [("other.example.com", "/")]),
                _upstream("u2", "api-pool", "http", [(SERVICE, "/api")]),
                _upstream("u3", "root-pool", "http", [("other.example.com", "/api"), (SERVICE, "/")]),
            ]
        )
    )
    assert parser.terminal_kind == "pool"
    assert "root-pool" in parser.text["terminal"]
    assert "foreign-pool" not in parser.text["terminal"]
    assert "api-pool" not in parser.text["terminal"]


def test_terminal_takes_the_first_pool_by_path_when_none_is_at_root(render_strip):
    """Insertion order is pool-NAME order (`get_upstreams` orders by `Resources.name`), so the
    pool listed first is not the one at the shallowest path."""
    parser = render_strip(
        attachments=_attachments(
            upstream=[
                _upstream("u1", "aaa-pool", "http", [(SERVICE, "/b")]),
                _upstream("u2", "zzz-pool", "http", [(SERVICE, "/a")]),
            ]
        )
    )
    assert parser.terminal_kind == "pool"
    assert "zzz-pool" in parser.text["terminal"], "picked by pool name instead of by path"


def test_a_stream_pool_terminal_has_no_path(render_strip):
    """`attach_upstream` stores `match_path = ""` for a stream pool by construction, so a
    `== "/"` test never matches one."""
    parser = render_strip(
        stream=True,
        attachments=_attachments(upstream=[_upstream("u1", "tcp-pool", "stream", [(SERVICE, "")])]),
    )
    assert parser.terminal_kind == "pool"
    assert "tcp-pool" in parser.text["terminal"]


def test_an_http_service_ignores_a_stream_pool_and_vice_versa(render_strip):
    http_only = render_strip(attachments=_attachments(upstream=[_upstream("u1", "tcp-pool", "stream", [(SERVICE, "")])]))
    assert http_only.terminal_kind == "root"
    stream_only = render_strip(stream=True, attachments=_attachments(upstream=[_upstream("u1", "web-pool", "http", [(SERVICE, "/")])]))
    assert stream_only.terminal_kind == "none"


def test_terminal_falls_back_to_the_inline_backend_when_nothing_is_attached(render_strip):
    """`REVERSE_PROXY_HOST` is `"multiple": "reverse-proxy"`, so the commonest shape in the
    field is a suffixed inline host with NO attachment at all -- the case D5's wording has no
    node for. The suffixed URL picks the same way the pools do."""
    parser = render_strip(
        {
            "USE_REVERSE_PROXY": {"value": "yes"},
            "REVERSE_PROXY_HOST": {"value": "http://api:8080"},
            "REVERSE_PROXY_URL": {"value": "/api"},
            "REVERSE_PROXY_HOST_1": {"value": "http://web:8080"},
            "REVERSE_PROXY_URL_1": {"value": "/"},
        }
    )
    assert parser.terminal_kind == "inline"
    assert "http://web:8080" in parser.text["terminal"]


def test_a_stream_service_does_not_render_plugins_that_declare_stream_no(render_strip):
    """`stream: no` in the manifest means the plugin does nothing on a stream server. The compose
    shelf on this very page reads the same field and renders "Does not support STREAM mode", so a
    strip that lists them makes the two panels of one page contradict each other."""
    named = ["modsecurity", "headers", "errors"]
    assert all(REAL_PLUGINS[plugin].get("stream") == "no" for plugin in named), "fixture premise: these declare stream:no"

    # `PLUGINS_ORDER_PREREAD` is operator-settable, and naming a plugin there is what puts it in
    # the ordered segment -- so this is a reachable configuration, not a contrived one. Each of
    # the three is ACTIVE on a stream service (all are always-on or on-by-default), which is what
    # makes the assertion below attributable to the stream filter rather than to inactivity:
    # without the filter all four render, with it only `whitelist` does.
    order = {"PLUGINS_ORDER_PREREAD": {"value": "whitelist " + " ".join(named)}}
    stream_config = _config(order, stream=True)
    for plugin in named:
        assert is_plugin_active_for_service(plugin, REAL_PLUGINS[plugin].get("name", plugin), stream_config, {}), f"control: {plugin} must be active"

    parser = render_strip(order, stream=True)
    nodes = set(_kind(parser, "ordered") + _kind(parser, "tail"))
    assert nodes & {"whitelist"}, "control: a stream-capable plugin named in the same setting must still render"
    assert not nodes & set(named), f"stream:no plugins on a stream path: {sorted(nodes & set(named))}"


def test_an_attached_pool_does_not_hide_an_inline_backend(render_strip):
    """Pools and inline hosts are ONE candidate set. `upstream_resolver.py:19-23` -- inline
    settings keep their suffixes and their NGINX precedence, pools take the ones left over -- and
    `_attach_location` aborts only on a duplicated path, so inline-at-"/" beside a pool-at-"/api"
    is an ordinary configuration. Preferring pools wholesale named the pool as the terminal for
    "/", which is simply the wrong host."""
    parser = render_strip(
        {"USE_REVERSE_PROXY": {"value": "yes"}, "REVERSE_PROXY_HOST": {"value": "http://legacy:8080"}, "REVERSE_PROXY_URL": {"value": "/"}},
        attachments=_attachments(upstream=[_upstream("u1", "api-pool", "http", [(SERVICE, "/api")])]),
    )
    assert parser.terminal_kind == "inline"
    assert "http://legacy:8080" in parser.text["terminal"]

    # The mirror image, so this cannot pass by preferring inline wholesale instead.
    reversed_depth = render_strip(
        {"USE_REVERSE_PROXY": {"value": "yes"}, "REVERSE_PROXY_HOST": {"value": "http://legacy:8080"}, "REVERSE_PROXY_URL": {"value": "/legacy"}},
        attachments=_attachments(upstream=[_upstream("u1", "root-pool", "http", [(SERVICE, "/")])]),
    )
    assert reversed_depth.terminal_kind == "pool"
    assert "root-pool" in reversed_depth.text["terminal"]


def test_a_disabled_reverse_proxy_does_not_become_the_terminal(render_strip):
    """A stored REVERSE_PROXY_HOST with USE_REVERSE_PROXY=no is dead config -- the templates emit
    no proxy_pass for it -- so the service still serves files locally. Without the `use_key` gate
    the strip would name a backend that nothing routes to."""
    parser = render_strip({"USE_REVERSE_PROXY": {"value": "no"}, "REVERSE_PROXY_HOST": {"value": "http://backend:8080"}, "REVERSE_PROXY_URL": {"value": "/"}})
    assert parser.terminal_kind == "root"
    assert "http://backend:8080" not in parser.text["terminal"]


def test_a_grpc_only_service_terminates_on_its_grpc_backend(render_strip):
    """`upstream_resolver` writes `USE_GRPC`, not `USE_REVERSE_PROXY`, for a gRPC backend, so
    a terminal keyed off `reverseproxy`'s activation verdict would find nothing here."""
    parser = render_strip({"USE_GRPC": {"value": "yes"}, "GRPC_HOST": {"value": "grpc://svc:9000"}, "GRPC_URL": {"value": "/"}})
    assert parser.terminal_kind == "inline"
    assert "grpc://svc:9000" in parser.text["terminal"]


def test_terminal_is_the_local_root_when_nothing_proxies(render_strip):
    """misc/confs/server-http/serve-files.conf: `ROOT_FOLDER` when set, else
    /var/www/html/<first server name>."""
    default_root = render_strip()
    assert default_root.terminal_kind == "root"
    assert f"/var/www/html/{SERVICE}" in default_root.text["terminal"]

    custom_root = render_strip({"ROOT_FOLDER": {"value": "/srv/site"}})
    assert custom_root.terminal_kind == "root"
    assert "/srv/site" in custom_root.text["terminal"]


def test_terminal_says_nothing_is_served_rather_than_inventing_a_root(render_strip):
    """`SERVE_FILES=no` with no backend renders `root /nowhere;` -- the service terminates on
    nothing, and the strip must say so. Asserted on the rendered badge as well as the marker
    attribute: two copies of that condition could disagree, and the badge is what an operator
    reads."""
    served = render_strip({"SERVE_FILES": {"value": "no"}})
    assert served.terminal_kind == "none"
    assert "Nothing served" in served.text["terminal"] and "/var/www/html" not in served.text["terminal"]

    stream = render_strip(stream=True)
    assert stream.terminal_kind == "none"
    assert "Nothing served" in stream.text["terminal"] and "/var/www/html" not in stream.text["terminal"]


# --------------------------------------------------------------------------------------
# Honesty of the label
# --------------------------------------------------------------------------------------


def test_the_strip_names_the_source_of_its_order(render_strip):
    """order.json and `PLUGINS_ORDER_<PHASE>` are plugin EXECUTION order, which is request
    order for the access phase and no more precise than that. The card names which setting and
    which phase it read rather than implying a per-request trace."""
    html = render_strip().html
    assert 'data-i18n="request_path.source"' in html
    assert "PLUGINS_ORDER_ACCESS" in html and "access phase" in html
    assert "not a per-request trace" in html

    stream_html = render_strip(stream=True).html
    assert "PLUGINS_ORDER_PREREAD" in stream_html and "preread phase" in stream_html


def test_every_i18n_key_the_strip_uses_exists_in_en_json(render_strip):
    import re

    locales = json.loads((REPO_ROOT / "src" / "ui" / "app" / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
    html = "".join(
        render_strip(**kwargs).html
        for kwargs in (
            {},
            {"stream": True},
            {"attachments": _attachments(upstream=[_upstream("u1", "api", "http", [(SERVICE, "/")])])},
            {"config": {"SERVE_FILES": {"value": "no"}}},
        )
    )
    keys = {key for key in re.findall(r'data-i18n="([^"]+)"', html) if key.startswith("request_path.")}
    assert keys, "the strip declared no i18n keys at all"
    for key in keys:
        node = locales
        for part in key.split("."):
            assert isinstance(node, dict) and part in node, f"missing en.json key: {key}"
            node = node[part]
        assert isinstance(node, str)

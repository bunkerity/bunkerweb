"""T7 -- page assembly and chrome: what the compose PANE posts, and which pane each page renders.

The shelf's own contract is pinned in test_compose_shelf.py. This file guards the layer above it,
where the two failures are:

* something that posts renders OUTSIDE the form, or in the wrong ORDER inside it.
  ``request.form.to_dict()`` keeps the FIRST value for a repeated name and the shelf emits its
  control-key fallbacks LAST, so every real control has to come first -- and on /services/new the
  fallback would otherwise post the GLOBAL config's SERVER_NAME, which is the SERVICE LIST;
* a pill that points at a pane the page does not render, or a pane no pill reaches. The old
  path-substring gate already got this wrong for a service named ``templates.example.com``.
"""

import ast
import re
import sys
from urllib.parse import parse_qs, urlparse
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, meta, nodes

from app.models.plugin_activation import is_plugin_active_for_service
from app.models.save_scope import control_keys
from app.utils import get_blacklisted_settings, get_filtered_settings, is_editable_method, is_plugin_active

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "src" / "ui" / "app" / "templates"
ROUTES = REPO_ROOT / "src" / "ui" / "app" / "routes"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_compose_shelf import PLUGIN_TYPES, REAL_ACTIVATION_MAP, REAL_PLUGINS, _config, browser_payload, parse_shelf  # noqa: E402
from test_save_scope import _import_services_module  # noqa: E402

_services = _import_services_module()
shelf_plugin_scope = _services.shelf_plugin_scope

SERVICE = "app.example.com"
# What `get_global_settings` hands /services/new: SERVER_NAME there is the SERVICE LIST, not a
# service name. The single most destructive thing this page can post.
SERVICE_LIST = "app.example.com other.example.com third.example.com"


class _Args(dict):
    def to_dict(self):
        return dict(self)


class _Request:
    """Only what the templates touch: `request.args.to_dict()` for the form action."""

    def __init__(self, args=None, blueprint="services"):
        self.args = _Args(args or {})
        self.blueprint = blueprint
        self.is_secure = True


@pytest.fixture
def render_pane():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
        csrf_token=lambda: "csrf-value",
        get_filtered_settings=get_filtered_settings,
        is_plugin_active=is_plugin_active,
        is_plugin_active_for_service=is_plugin_active_for_service,
        is_editable_method=is_editable_method,
        plugin_types=PLUGIN_TYPES,
    )

    def _render(
        config=None,
        *,
        plugins=None,
        global_page=False,
        service_id=SERVICE,
        is_readonly=False,
        is_pro_version=False,
        args=None,
        templates=None,
        service_method="ui",
        is_draft="no",
        clone=None,
        current_template="low",
    ):
        rendered = _config(config, global_page)
        if global_page:
            service_id = ""
        elif not service_id:
            # /services/new renders against the GLOBAL config -- SERVER_NAME is the service list.
            rendered["SERVER_NAME"] = {"value": SERVICE_LIST, "method": "ui", "global": True}
        return env.get_template("models/compose_pane.html").render(
            request=_Request(args, blueprint="global_settings" if global_page else "services"),
            plugins=REAL_PLUGINS if plugins is None else plugins,
            config=rendered,
            activation_map=REAL_ACTIVATION_MAP,
            shelf_plugin_scope=shelf_plugin_scope,
            control_keys=control_keys,
            blacklisted_settings=get_blacklisted_settings(global_page),
            global_page=global_page,
            service_id=service_id,
            is_readonly=is_readonly,
            user_readonly=False,
            is_pro_version=is_pro_version,
            attachments={},
            plugin_order={},
            templates=templates if templates is not None else {"low": {}, "medium": {}, "ui": {}},
            current_endpoint="new" if (not global_page and not service_id) else service_id,
            service_method=service_method,
            is_draft=is_draft,
            clone=clone,
            current_template=current_template,
        )

    return _render


class _FormParser(HTMLParser):
    """Everything with a `name`, in document order, split by whether it is inside the form."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form_attrs = None
        self.inside = []  # [(tag, attrs)]
        self.outside = []
        self.buttons = []
        self._depth = 0

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.form_attrs = attributes
            self._depth += 1
            return
        if tag == "button":
            self.buttons.append(attributes)
        if attributes.get("name") or tag in ("input", "select"):
            (self.inside if self._depth else self.outside).append((tag, attributes))

    def handle_endtag(self, tag):
        if tag == "form" and self._depth:
            self._depth -= 1


def _form(html):
    parser = _FormParser()
    parser.feed(html)
    return parser


def _names(pairs):
    return [attrs["name"] for _, attrs in pairs if attrs.get("name")]


def _payload(html):
    return browser_payload(parse_shelf(html))


# --------------------------------------------------------------------------------------
# The form itself
# --------------------------------------------------------------------------------------


def test_the_pane_is_one_real_post_form_and_nothing_postable_sits_outside_it(render_pane):
    html = render_pane()
    parser = _form(html)
    assert parser.form_attrs is not None, "the compose pane renders no form"
    assert parser.form_attrs.get("method", "").upper() == "POST"
    assert html.count("<form") == 1, "a nested form would make the browser close the outer one early"
    assert _names(parser.outside) == [], "a named control outside the form never reaches the POST"
    assert _names(parser.inside), "the form posts nothing at all"


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({}, {"mode": "compose"}),
        ({"mode": "raw"}, {"mode": "compose"}),
        ({"clone": "other.example.com"}, {"clone": "other.example.com", "mode": "compose"}),
        ({"type": "core", "mode": "easy"}, {"type": "core", "mode": "compose"}),
    ],
)
def test_the_action_declares_compose_and_carries_every_other_query_arg(args, expected, render_pane):
    """`resolve_save_mode` falls back to the PRESERVING branch for an absent mode, so a compose
    payload has to say `mode=compose` itself or it is saved with no scope -- and, worse, the
    reverse: any other pane's payload must never inherit compose's scope. The remaining args are
    read on POST too; dropping `clone` makes /services/new?clone=x create an empty service
    (routes/services.py reads it in the POST branch)."""
    action = _form(render_pane(args=args)).form_attrs["action"]
    assert action.startswith("?")
    query = dict(pair.split("=", 1) for pair in action[1:].split("&"))
    assert {key: value.replace("%2E", ".") for key, value in query.items()} == expected


def test_readonly_disables_the_submit_button(render_pane):
    save = [button for button in _form(render_pane(is_readonly=True)).buttons if button.get("type") == "submit"]
    assert save and all("disabled" in button for button in save)
    save = [button for button in _form(render_pane()).buttons if button.get("type") == "submit"]
    assert save and not any("disabled" in button for button in save)


def test_the_save_button_is_a_submit_and_never_the_monolith_class(render_pane):
    """`$(".save-settings").on("click")` (plugins-settings.js:2025) builds a synthetic form whose
    `currentMode === "compose"` matches no branch, so it would post neither the shelf nor the
    control keys while the route still declares the full shelf scope."""
    parser = _form(render_pane())
    submits = [button for button in parser.buttons if button.get("type") == "submit"]
    assert len(submits) == 1
    assert "save-settings" not in " ".join(button.get("class", "") for button in parser.buttons)


def test_csrf_token_posts_from_inside_the_form_without_claiming_the_shared_id(render_pane):
    """The raw pane owns `id="csrf_token"` and service-resources.js reads it by id for its own
    detach form; a second element with that id is an invalid document for no gain."""
    inside = {attrs["name"]: attrs for _, attrs in _form(render_pane()).inside if attrs.get("name")}
    assert inside["csrf_token"]["value"] == "csrf-value"
    assert "id" not in inside["csrf_token"]


# --------------------------------------------------------------------------------------
# Order: first-value-wins, and the /services/new landmine
# --------------------------------------------------------------------------------------


def test_new_service_posts_the_typed_server_name_never_the_global_service_list(render_pane):
    """THE test for this slice. On /services/new `config` is the GLOBAL config, whose SERVER_NAME
    is the space-separated SERVICE LIST -- and SERVER_NAME is a control key the shelf emits a
    trailing fallback for. Without a real input rendered first, creating a service posts every
    existing service's name as the new one's, and `edit_service` splits on the first."""
    html = render_pane(service_id="")
    payload = _payload(html)
    assert payload["SERVER_NAME"] == "", f"the new page posts {payload['SERVER_NAME']!r}"
    assert payload["OLD_SERVER_NAME"] == ""
    typed = [attrs for tag, attrs in _form(html).inside if tag == "input" and attrs.get("name") == "SERVER_NAME"]
    assert typed and typed[0].get("type") == "text" and "required" in typed[0]


def test_new_service_offers_a_template_and_it_wins_over_the_shelf_fallback(render_pane):
    """The resources band owns the template picker on an existing service and does not render on
    /services/new (it has nothing to attach to), so without one here a service could only ever be
    created with no template at all."""
    payload = _payload(render_pane(service_id="", templates={"low": {}, "medium": {}, "ui": {}}))
    assert payload["USE_TEMPLATE"] == "low"
    assert "ui" not in [attrs.get("value") for tag, attrs in _form(render_pane(service_id="")).inside if tag == "option"]


def test_new_service_honours_the_template_selected_by_the_gallery(render_pane):
    assert _payload(render_pane(service_id="", current_template="medium"))["USE_TEMPLATE"] == "medium"


def test_the_draft_input_is_inside_the_form_and_precedes_the_shelf_fallback(render_pane):
    """`.toggle-draft` mutates `#is-draft` in place (plugins-settings.js:2217). Left outside the
    form the toggle would be a no-op, and `variables.pop("IS_DRAFT", "no")` publishes a draft
    service whenever the payload omits it."""
    html = render_pane(is_draft="yes")
    inside = [attrs for _, attrs in _form(html).inside if attrs.get("name") == "IS_DRAFT"]
    assert len(inside) == 2, "expected the live input plus the shelf's trailing fallback"
    assert inside[0].get("id") == "is-draft"
    assert _payload(html)["IS_DRAFT"] == "yes"


def test_every_service_control_key_is_posted_exactly_once_by_value(render_pane):
    payload = _payload(render_pane())
    for key in control_keys():
        assert key in payload, f"{key} is in restore_skip and is therefore never restored: omitting it destroys it"


def test_exactly_one_use_template_input_so_the_band_picker_stays_wired(render_pane):
    """service-resources.js writes the chosen template into `$('[name="USE_TEMPLATE"]')` and greys
    itself unless it finds EXACTLY one (static/js/pages/service-resources.js:66,88). USE_TEMPLATE
    is in the service `restore_skip`, so posting it twice and not posting it at all are both
    destructive. On an existing service the only one is the shelf's trailing control input; on
    /services/new the pane renders its own picker and the band does not render at all."""
    for service_id, expected in ((SERVICE, 1), ("", 2)):
        names = _names(_form(render_pane(service_id=service_id)).inside)
        assert names.count("USE_TEMPLATE") == expected, f"service_id={service_id!r}: {names.count('USE_TEMPLATE')}"


def test_an_existing_service_posts_its_stored_server_name(render_pane):
    """The value, not merely the key. `get_service(service, full=True)` unprefixes the service's
    OWN row (db_methods/config_read.py:411-416), so SERVER_NAME here is the service -- and
    `edit_service(old_server_name, variables)` treats a different one as a RENAME. A fixture
    seeded from settings.json alone leaves the plugin default `www.example.com` there, which is
    how a browser run first surfaced this."""
    stored = {"SERVER_NAME": {"value": SERVICE, "method": "ui", "global": False}}
    payload = _payload(render_pane(stored))
    assert payload["SERVER_NAME"] == SERVICE
    assert payload["OLD_SERVER_NAME"] == SERVICE, "the rename pair must agree, or the save renames the service"


# --------------------------------------------------------------------------------------
# Global scope
# --------------------------------------------------------------------------------------


def test_the_global_pane_posts_the_override_control_and_no_service_control_keys(render_pane):
    """`control_keys(True)` is empty on purpose: SERVER_NAME at global scope is the service list.
    OVERRIDE_NON_GLOBAL_SERVICES is a form control that global_settings.py pops before anything
    reads it, and this is now its only producer."""
    payload = _payload(render_pane(global_page=True))
    assert payload["OVERRIDE_NON_GLOBAL_SERVICES"] == "no"
    assert "SERVER_NAME" not in payload
    assert "IS_DRAFT" not in payload
    assert "USE_TEMPLATE" not in payload


def test_the_service_pane_does_not_render_the_override_control(render_pane):
    assert "OVERRIDE_NON_GLOBAL_SERVICES" not in _payload(render_pane())


def test_an_empty_plugin_map_renders_no_form_at_all(render_pane):
    """`main.py` parks `plugins = {}` whenever the per-request `get_plugins()` raises, and the
    SAVE recomputes the shelf scope from its own fresh call -- so a page rendered with zero rows
    would post nothing while the route claimed every activation key, and in scope + unposted
    means DELETED. The page has to refuse to submit, not submit an empty shelf."""
    html = render_pane(plugins={})
    assert "<form" not in html
    assert 'id="compose-unavailable"' in html
    assert _names(_form(html).outside) == [], "a control rendered outside the refused form still posts"


def test_the_request_path_strip_renders_only_on_a_service(render_pane):
    assert "data-request-path" in render_pane()
    assert "data-request-path" not in render_pane(global_page=True)
    assert "data-request-path" not in render_pane(service_id=""), "there is no service to trace on /services/new"


# --------------------------------------------------------------------------------------
# The context contract -- the partial documents that NOTHING here may be defaulted
# --------------------------------------------------------------------------------------

# Registered by src/ui/main.py (jinja_env.globals) or injected into every template by its
# context processor, so no route has to pass them.
_PROVIDED_BY_MAIN = {
    "url_for",
    "csrf_token",
    "request",
    "get_filtered_settings",
    "get_blacklisted_settings",
    "is_editable_method",
    "is_plugin_active",
    "is_plugin_active_for_service",
    "plugin_types",
    "plugins",
    "is_readonly",
    "user_readonly",
    "is_pro_version",
    "current_endpoint",
    "theme",
    "pro_diamond_url",
}
# Set by the host page inside `{% block content %}`, above the include.
_SET_BY_THE_HOST_PAGE = {"blacklisted_settings", "service_method", "is_draft"}
# What the ROUTE must hand render_template. Both host pages need all of it except the
# service-only entries; a name that appears here and in neither route is the failure this pair of
# tests exists to catch.
REQUIRED_FROM_ROUTE = {"config", "shelf_plugin_scope", "activation_map", "control_keys", "global_page", "service_id"}
SERVICE_ONLY_FROM_ROUTE = {"templates", "clone", "attachments", "plugin_order", "current_template"}


def _locally_bound(tree):
    """Names the template binds itself -- `{% set %}`, namespace targets and loop variables.

    `meta.find_undeclared_variables` reports a name assigned inside a branch or a loop as
    undeclared, because at parse time it cannot know the branch runs. Both partials set dozens of
    them, so without this the contract below would be pure noise.
    """
    bound = set()
    for node in tree.find_all((nodes.Assign, nodes.AssignBlock, nodes.For)):
        target = node.target
        candidates = [target] if isinstance(target, (nodes.Name, nodes.NSRef)) else list(getattr(target, "items", []))
        for candidate in candidates:
            if isinstance(candidate, (nodes.Name, nodes.NSRef)):
                bound.add(candidate.name)
    return bound


def _needed_names():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    needed = set()
    for name in ("models/compose_pane.html", "models/compose_shelf.html", "models/request_path_strip.html"):
        tree = env.parse((TEMPLATES / name).read_text(encoding="utf-8"))
        needed |= meta.find_undeclared_variables(tree) - _locally_bound(tree)
    return needed


def test_the_compose_pane_needs_exactly_the_documented_context():
    """Derived from the templates, not transcribed: a partial that grows a new required variable
    fails here until it is classified and, if it comes from the route, wired into BOTH pages.
    The shelf's header is explicit that a silently missing one renders a shelf posting the wrong
    set, which is the failure the whole slice exists to prevent."""
    unclassified = _needed_names() - _PROVIDED_BY_MAIN - _SET_BY_THE_HOST_PAGE - REQUIRED_FROM_ROUTE - SERVICE_ONLY_FROM_ROUTE
    assert unclassified == set(), f"unclassified context names: {sorted(unclassified)}"
    assert REQUIRED_FROM_ROUTE <= _needed_names(), "REQUIRED_FROM_ROUTE lists a name the pane no longer uses"


def _render_call(route_file, template_name):
    """The keyword names of the `render_template("<template_name>", ...)` call in a route file."""
    tree = ast.parse((ROUTES / route_file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or getattr(node.func, "id", "") != "render_template":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == template_name:
            return {keyword.arg for keyword in node.keywords}
    raise AssertionError(f"no render_template({template_name!r}) call in {route_file}")


def test_both_routes_pass_every_context_name_the_pane_needs():
    service = _render_call("services.py", "service_settings.html")
    assert REQUIRED_FROM_ROUTE | SERVICE_ONLY_FROM_ROUTE <= service, f"service page misses {sorted((REQUIRED_FROM_ROUTE | SERVICE_ONLY_FROM_ROUTE) - service)}"
    global_page = _render_call("global_settings.py", "global_settings.html")
    assert REQUIRED_FROM_ROUTE <= global_page, f"global page misses {sorted(REQUIRED_FROM_ROUTE - global_page)}"


# --------------------------------------------------------------------------------------
# Panes and pills
# --------------------------------------------------------------------------------------

HOST_PAGES = ("service_settings.html", "global_settings.html")


_JINJA_COMMENT_RX = re.compile(r"{#.*?#}", re.DOTALL)


def _page(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("page_name", HOST_PAGES)
def test_host_pages_render_compose_and_raw_only(page_name):
    panes = set(re.findall(r'id="navs-modes-([a-z]+)"', _page(page_name)))
    assert panes == {"compose", "raw"}, f"{page_name} renders {sorted(panes)}"


@pytest.mark.parametrize("page_name", HOST_PAGES)
def test_host_pages_load_the_shelf_script(page_name):
    assert "js/components/compose-shelf.js" in _page(page_name)


def test_the_pills_are_gated_on_the_blueprint_not_on_a_path_substring():
    """Service ids are hostnames. `"templates" in request.path` is true for a service called
    templates.example.com -- which already renders that service with the wrong pills today -- and
    `"services" in request.path` for services.example.com."""
    head = _JINJA_COMMENT_RX.sub("", _page("dashboard.html"))
    start = head.index("{% block page_head %}")
    end = head.index("{% endblock %}")
    pill_block = head[start:end]
    assert "request.blueprint" in pill_block
    assert "in request.path" not in pill_block, "a path substring still decides which pills render"


def test_every_pill_target_is_a_pane_some_page_renders():
    """A pill pointing at a pane no page renders is a dead tab; a pane no pill reaches is
    unreachable configuration. Both pill shapes count: since S3.5 the service and global pills
    are LINKS carrying a `mode`, and only the templates page still tabs to a `data-bs-target`."""
    pills = _page("models/mode_pills.html")
    targets = set(re.findall(r'data-bs-target="#navs-modes-([a-z]+)"', pills))
    targets |= {_pill_mode(href) for href in re.findall(r'href="\?{{ ([a-z_]+) \| urlencode }}"', pills)}
    assert targets == {"compose", "easy", "raw"}, f"pill targets are {sorted(targets)}"
    rendered = set()
    for page_name in HOST_PAGES + ("template_edit.html",):
        rendered |= set(re.findall(r'id="navs-modes-([a-z]+)"', _page(page_name)))
    assert targets <= rendered, f"pills point at panes nothing renders: {sorted(targets - rendered)}"
    assert rendered <= targets, f"panes no pill can reach: {sorted(rendered - targets)}"


def _pill_mode(query_var):
    """`compose_query` / `raw_query` -> the pane that href lands on."""
    return query_var.removesuffix("_query")


def test_the_easy_pill_is_the_templates_blueprint_only():
    pills = _page("models/mode_pills.html")
    matches = list(re.finditer(r'data-bs-target="#navs-modes-easy"', pills))
    assert matches, "no easy pill found at all -- this test would pass vacuously"
    for match in matches:
        preceding = pills[: match.start()]
        assert 'pane_blueprint == "templates"' in preceding
        branch = preceding[preceding.rindex('pane_blueprint == "templates"') :]  # noqa: E203
        assert "{% else %}" not in branch


# --------------------------------------------------------------------------------------
# S3.5 -- the pills navigate, so the pane on screen and the save branch cannot disagree
# --------------------------------------------------------------------------------------


@pytest.fixture
def render_pills():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)

    def _render(*, blueprint="services", mode="compose", args=None):
        return env.get_template("models/mode_pills.html").render(
            request=_Request(args, blueprint=blueprint),
            pane_blueprint=blueprint,
            mode=mode,
            pill_ul_class="nav nav-pills",
            pill_first_li_class="nav-item",
            pill_icon_size="bx-xs",
            pill_label_class="don-jose",
        )

    return _render


def _hrefs(html):
    return re.findall(r'href="([^"]*)"', html)


@pytest.mark.parametrize("blueprint", ("services", "global_settings"))
def test_the_service_and_global_pills_are_links_not_tabs(render_pills, blueprint):
    """A client-side tab switch left the raw editor showing the text the server rendered at page
    load -- unsaved compose edits were invisible in it, and saving from raw wrote that stale twin
    back over them. Navigating re-renders both panes from the database instead."""
    html = render_pills(blueprint=blueprint)
    assert 'data-bs-toggle="tab"' not in html
    assert "data-bs-target=" not in html
    assert 'role="tablist"' not in html
    assert len(_hrefs(html)) == 2, _hrefs(html)


def test_the_templates_pills_stay_tabs(render_pills):
    """/templates/<id> renders BOTH its panes itself and switches between them client-side
    (template_edit.js, its own view_mode). Different feature, same chrome."""
    html = render_pills(blueprint="templates", mode="easy")
    assert 'data-bs-toggle="tab"' in html
    assert 'role="tablist"' in html
    assert _hrefs(html) == []
    assert "navs-modes-easy" in html and "navs-modes-raw" in html


def test_the_raw_pill_routes_a_raw_save_to_the_raw_branch(render_pills):
    """THE REGRESSION THIS SLICE CLOSES. The raw editor posts to `window.location.href`
    (settings-raw.js), so the pill's href IS the save's `mode`. Between T7 and S3.5 nothing
    emitted `mode=raw`, `resolve_save_mode` fell back to `easy`, and easy's indiscriminate
    re-injection put back every key the raw text no longer held -- deleting a line became a
    no-op. Asserted through the real route function, not against a literal."""
    raw_href = [href for href in _hrefs(render_pills(mode="compose")) if "mode=raw" in href]
    assert raw_href, "no pill carries mode=raw"
    query = parse_qs(urlparse(raw_href[0]).query)
    assert _services.resolve_save_mode(query["mode"][0], "easy") == "raw"


def test_the_compose_pill_declares_no_mode_at_all(render_pills):
    """Compose is the GET default on both pages, so the pill omits `mode` rather than setting
    `mode=compose`. Only the compose FORM may declare compose (models/compose_pane.html builds
    its own action): a declared compose hands the payload the shelf's full scope, and an in-scope
    key the payload did not post is DELETED."""
    hrefs = _hrefs(render_pills(mode="raw"))
    compose_href = [href for href in hrefs if "mode=raw" not in href]
    assert len(compose_href) == 1, hrefs
    assert "mode" not in parse_qs(urlparse(compose_href[0]).query)
    assert _services.resolve_save_mode(None, "easy") != "compose"


@pytest.mark.parametrize("arg,value", (("clone", "other.example.com"), ("type", "core")))
def test_the_pills_preserve_every_other_query_argument(render_pills, arg, value):
    """Dropping `clone` on /services/new silently creates an EMPTY service instead of a copy
    (routes/services.py reads it on POST)."""
    for href in _hrefs(render_pills(args={arg: value})):
        assert parse_qs(urlparse(href).query).get(arg) == [value], href


@pytest.mark.parametrize("mode,expected", (("raw", "raw"), ("compose", "compose"), ("easy", "compose"), ("advanced", "compose")))
def test_the_active_pill_is_the_pane_the_page_renders(render_pills, mode, expected):
    """The panes activate on `mode != 'raw'` (service_settings.html / global_settings.html), so a
    bookmarked `mode=easy` renders compose and the pill must agree with it."""
    html = render_pills(mode=mode)
    active = re.findall(r'href="([^"]*)"[^>]*aria-current', html.replace("\n", " "))
    assert len(active) == 1, html
    landed = "raw" if "mode=raw" in active[0] else "compose"
    assert landed == expected


def test_the_chrome_still_includes_the_pills():
    """Every other test in this block renders `models/mode_pills.html` directly, so all of them
    stay green if dashboard.html simply stops including it and the switcher vanishes. That is the
    shape of the regression T7 shipped -- markup deleted out from under a contract nothing
    re-checked. The include must also stay INSIDE the blueprint gate: outside it, the service and
    template LIST pages grow a mode switcher for panes they do not render."""
    head = _page("dashboard.html")
    start = head.index("{% block page_head %}")
    block = head[start : head.index("{% endblock %}", start)]  # noqa: E203
    assert block.count('{% include "models/mode_pills.html" %}') == 2, "the floating and desktop menus both render it"
    gate = block.index("{% if pane_blueprint %}")
    assert all(m > gate for m in _find_all(block, '{% include "models/mode_pills.html" %}'))


def _find_all(haystack, needle):
    start = 0
    while (found := haystack.find(needle, start)) != -1:
        yield found
        start = found + 1


def test_the_pills_never_hardcode_an_absolute_path():
    """A hardcoded /services/... breaks when the UI is mounted behind REVERSE_PROXY_URL, and the
    misdirected request carries the `__Host-` session cookie and a valid CSRF token with it."""
    for href in re.findall(r'href="([^"]*)"', _page("models/mode_pills.html")):
        assert href.startswith("?"), href


def test_the_compose_form_warns_before_a_navigation_discards_it():
    """The pills stopped being tabs, so leaving compose now drops every unsaved switch, control
    key and template choice. Without the guard that is silent."""
    script = (REPO_ROOT / "src" / "ui" / "app" / "static" / "js" / "components" / "compose-shelf.js").read_text(encoding="utf-8")
    assert 'getElementById("compose-form")' in script
    registration = script.index('addEventListener("beforeunload"')
    assert "returnValue" in script[registration:], "beforeunload without returnValue is ignored by older engines"
    assert 'addEventListener("submit"' in script[:registration], "a Save would warn about its own navigation"


# --------------------------------------------------------------------------------------
# The save fallback stays the preserving branch, on purpose
# --------------------------------------------------------------------------------------


def test_the_save_fallback_is_deliberately_not_the_default_pane():
    """Both pages now RENDER compose by default, and both still RESOLVE an absent mode to their
    preserving branch. Making the two agree is the tempting cleanup and it is a data-loss bug:
    the compose form declares `mode=compose` in its own action, so the fallback only ever sees a
    payload compose did not produce -- and handing that the shelf's scope deletes every in-scope
    key it did not post (db_methods/config_save.py:592)."""
    assert _services.resolve_save_mode(None, "easy") == "easy"
    assert _services.resolve_save_mode("", "advanced") == "advanced"
    assert _services.resolve_save_mode("nonsense", "easy") == "easy"
    assert _services.resolve_save_mode("compose", "easy") == "compose"
    # Bound to the assignment, not to the bare call: both routes read `mode` twice (the GET
    # default and the post-save redirect's `requested_mode`), so a substring match on the call
    # alone stays green when only one of them changes -- which a mutation run proved.
    service = (ROUTES / "services.py").read_text(encoding="utf-8")
    assert 'mode = request.args.get("mode", "compose")' in service, "the service page's GET default is no longer compose"
    assert 'requested_mode = request.args.get("mode", "compose")' in service, "the post-save redirect no longer lands on compose"
    assert 'resolve_save_mode(request.args.get("mode"), "easy")' in service, "the service page's SAVE fallback changed"
    global_source = (ROUTES / "global_settings.py").read_text(encoding="utf-8")
    assert 'mode = request.args.get("mode", "compose")' in global_source, "the global page's GET default is no longer compose"
    assert 'request.args.get("mode", "compose") != "compose"' in global_source, "the post-save redirect no longer lands on compose"
    assert 'resolve_save_mode(request.args.get("mode"), "advanced")' in global_source


def test_core_plugin_order_reads_the_shipped_file():
    """The strip fills its second pass from this map; `{}` is a supported value but it silently
    drops every plugin whose phase order comes only from order.json into the unordered group."""
    order = _services.core_plugin_order()
    assert order["access"][0] == "ssl"
    assert "preread" in order

"""A list template may only read keys the API actually emits.

This exists because `/configs` rendered **every** custom config as *Global* — its href, its Service
cell, and the service its delete, convert and export buttons carried. Nothing was wrong in the
database: `src/api/app/routers/configs.py:86` does

    data["service"] = data.pop("service_id", None) or "global"

and `configs.html` still read `config['service_id']`. `pop` removes the key, Jinja has no
`StrictUndefined` here, so the dead key evaluated to `Undefined`, which is falsy, and every row
collapsed to `global`. `/cache` had the same defect twice over — the API emits `service` and
`plugin`, the template read `service_id` and `plugin_id` — and there the empty plugin segment made
`/cache/global//<job>/<file>` unroutable rather than merely mislabelled.

**`tests/unit/ui/test_row_actions.py` rendered both templates throughout and stayed green**, because
its fixtures carried `"service_id": None` — the one value for which a dead key and a live one render
identically. A fixture that pins the payload a test wishes the API returned is not a test of the
contract; it is a second copy of the contract, free to drift the same way. So nothing here is
hand-written: the emitted keys are read out of the API router (and, where the router spreads a
database row, out of the database method it spreads), and the keys a template reads are read out of
the Jinja AST.

Both defects are fixed as of 2026-08-20 — the PO chose to move the templates onto the keys the API
emits — so every covered page is green today. **If a row goes red, a template is reading a key the
API stopped sending; fix the template or the router, never this file.** `/jobs` is the control: its
API returns `get_jobs()` verbatim, its rows still carry `service_id`, and it has passed throughout. A
guard that could not tell the clean page from the broken ones would be worth nothing.

One consequence of that fix deserves stating, because it is the kind of thing a later "cleanup"
reverts: the API sends the **literal string `"global"`**, never `None`, for a global row. Every
truthiness test on `service` is therefore a constant, and each such site had to become an explicit
`!= 'global'` comparison. `cache.html`'s KPI band is the sharp edge — `rejectattr('service_id')`
counted globals by their falsiness, and its faithful-looking translation
`rejectattr('service', 'eq', 'global')` counts the exact opposite set.

**A sibling guard for the JS-built tables is not feasible and was investigated and rejected — do not
re-derive it.** The `serverSide` tables build their rows in `render(data, type, row)` callbacks, so
the read side would have to resolve `row.foo` out of template literals and helper closures with no
type information; a column extractor written for that returned 7 of 7 keys on `services.js`, 0 of 9
on `bans.js` and 1 of 20 on `reports.js` — under-collecting **silently**, which reads as *clean*. The
premise was wrong as well as the mechanics: those callbacks sit on a UI-to-UI boundary, where the
fetch route and the JS ship together. The boundary that broke twice is `API router -> UI fetch
route`, which is Python on both sides and already reachable from here.

Scope note: the API routers are not importable from this suite — `fastapi` is not in
`tests/unit/requirements.txt` and adding it to run one guard is a bigger change than the guard. The
routers are therefore read as source rather than executed. That is still derivation from the source
of truth; what it is not is a second list of keys maintained by hand, which is the failure mode this
exists to end.
"""

import ast
from pathlib import Path

import pytest
from jinja2 import Environment, nodes

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"
UI_ROUTES = ROOT / "src" / "ui" / "app" / "routes"
API_ROUTERS = ROOT / "src" / "api" / "app" / "routers"
DB_METHODS = ROOT / "src" / "common" / "db" / "db_methods"

# Only *locations* are listed, never keys. Each page's template, UI route and API router share a
# name, and the list endpoint, the API-sourced template variables and every key on both sides are
# derived below. Adding a page here is the whole cost of covering it.
PAGES = ("configs", "cache", "jobs")


# --------------------------------------------------------------------------------------
# What the API emits
# --------------------------------------------------------------------------------------
def _module(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dict_literal_keys(node):
    """Every string key of every dict literal inside `node`, response envelopes excluded.

    `JSONResponse(content={"status": ..., "configs": out})` is a dict literal too, and its keys are
    the envelope's, not a row's. Skipping it keeps `status` out of the emitted set.
    """
    envelopes = {
        keyword.value
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        for keyword in call.keywords
        if keyword.arg == "content" and isinstance(keyword.value, ast.Dict)
    }
    return {
        key.value
        for dict_node in ast.walk(node)
        if isinstance(dict_node, ast.Dict) and dict_node not in envelopes
        for key in dict_node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _db_method_keys(method_name):
    """The string keys of every dict literal the named database method builds, plus those of the
    same-file helpers it calls.

    The one-hop follow is not optional. Several DB methods return a pagination envelope and delegate
    the row itself to a sibling — `get_redirects` returns
    `{"items": [self._redirect_dict(...) ...], "total": ..., "offset": ..., "limit": ...}` — so
    reading only the method's own literals yields the *envelope's* four keys and makes every field
    the template legitimately reads look dead. That is a false alarm, which is the worse direction
    for a guard to err in: it teaches people the guard cries wolf. Unioning the helper's literals
    over-approximates instead, which can only ever cost a missed drift, never a false accusation.

    Followed to closure rather than one hop, because the chain is genuinely that long:
    `get_upstreams` -> `_pool_servers` -> `_server_dict`, and the template's nested
    `{% for server in pool.servers %}` reads exactly the keys of that last one. Stopping at one hop
    reported `host`, `backup` and `down` as drift, which is a false accusation. The walk is bounded
    to `self.` calls resolvable in the same file and starting from the list method, so what it
    reaches is the row-building chain and not the module.
    """
    for path in sorted(DB_METHODS.glob("*.py")):
        module = _module(path)
        for node in ast.walk(module):
            if not (isinstance(node, ast.FunctionDef) and node.name == method_name):
                continue
            siblings = {n.name: n for n in ast.walk(module) if isinstance(n, ast.FunctionDef)}
            keys, seen, pending = set(), set(), [node]
            while pending:  # to closure, not one hop -- see the docstring
                current = pending.pop()
                keys |= _dict_literal_keys(current)
                for helper in _self_calls(current) - seen:
                    seen.add(helper)
                    if helper in siblings:
                        pending.append(siblings[helper])
            return keys
    raise AssertionError(f"no database method named {method_name!r} under {DB_METHODS}")


def _self_calls(function):
    """`self._redirect_dict(...)` -> `_redirect_dict`. One hop, deliberately: two would start
    dragging in unrelated shapes and the over-approximation would stop being meaningful."""
    return {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
    }


def _list_endpoint(router_module):
    """The function serving `@router.get("")` — the one that returns the rows a list page renders."""
    for node in ast.walk(router_module):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "get"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and decorator.args[0].value == ""
            ):
                return node
    raise AssertionError('no @router.get("") endpoint found')


def _db_calls(function):
    """Database methods the endpoint calls: `db.x(...)` or `get_db().x(...)`."""
    return {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and _is_db_receiver(node.func.value)
    }


def _is_db_receiver(node):
    if isinstance(node, ast.Name) and node.id == "db":
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get_db"


def _subscript_assignments(function):
    """Keys the endpoint adds with `row["k"] = ...`."""
    return {
        target.slice.value
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str)
    }


def _popped(function):
    """Keys the endpoint removes with `row.pop("k")` — how `service_id` disappears."""
    return {
        node.args[0].value
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pop"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }


def _spread_comprehension(function):
    """The `{k: v for k, v in row.items() if k != "data"}` that copies a database row forward.

    Its presence is the discriminator: a router that spreads the row inherits every database key, and
    a router that builds a fresh dict literal inherits none of them. `/configs` spreads, `/cache`
    does not, and reading `/cache` as if it did is exactly how a guard would miss the defect there.
    """
    for node in ast.walk(function):
        if isinstance(node, ast.DictComp) and any(
            isinstance(gen.iter, ast.Call) and isinstance(gen.iter.func, ast.Attribute) and gen.iter.func.attr == "items" for gen in node.generators
        ):
            return node
    return None


def _comprehension_exclusions(comp):
    """Keys a spread drops inline: the `"data"` of `if k != "data"`."""
    return {
        comparator.value
        for generator in comp.generators
        for condition in generator.ifs
        if isinstance(condition, ast.Compare) and any(isinstance(op, ast.NotEq) for op in condition.ops)
        for comparator in condition.comparators
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
    }


def _route_injected_keys(page, template):
    """Keys the UI route adds to a row after the API handed it over.

    Two shapes, both real and both narrow enough to read exactly:

        certificates.py:30   certificate["orphan_state"] = orphan_states.get(cert_name) ...
        resource_groups.py:72  rows = [{"id": group_id, **details} for group_id, details in ...]

    A field the route puts there is a field the template may legitimately read, and counting it as
    drift blames the API for something the UI did to its own rows. Only subscript assignments and
    dict literals that actually splat an existing mapping are taken, and only writes onto a name the
    route derived from the API. Counting *every* subscript assignment in a route was tried first and
    it is too blunt: `templates.py` is 23 KB and happens to assign some `["id"]` somewhere, which
    absorbed a genuine dead key on `/templates` and reported the page clean.
    """
    view = _page_function(_module(UI_ROUTES / f"{page}.py"), template)
    rows = _api_sourced_locals(view)
    injected = {
        target.slice.value
        for node in ast.walk(view)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and isinstance(target.slice.value, str)
        and isinstance(target.value, ast.Name)
        and target.value.id in rows
    }
    for node in ast.walk(view):
        # `{"id": group_id, **details}` counts only when `details` is itself an API row. Accepting
        # any `**` splat swept in 13 unrelated keys from `templates.py`'s settings dicts, `id` among
        # them, and reported `/templates` clean while it reads a key the API has never emitted.
        if not (isinstance(node, ast.Dict) and any(key is None for key in node.keys)):
            continue
        splatted = [value for key, value in zip(node.keys, node.values) if key is None]
        if any(isinstance(value, ast.Name) and value.id in rows for value in splatted):
            injected |= {key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    return injected


def emitted_keys(page, template=None):
    """Every key the API's list endpoint for `page` can put on a row, plus what the route adds."""
    template = template or page
    endpoint = _list_endpoint(_module(API_ROUTERS / f"{page}.py"))
    from_db = set()
    for method in _db_calls(endpoint):
        from_db |= _db_method_keys(method)

    spread = _spread_comprehension(endpoint)
    if spread is not None:
        # Spreads the database row: inherits its keys, minus whatever the spread drops inline.
        base = from_db - _comprehension_exclusions(spread)
    elif _dict_literal_keys(endpoint):
        # Builds rows fresh: the literal is the whole contract, database keys are not inherited.
        base = _dict_literal_keys(endpoint)
    else:
        # Returns the database result untouched.
        base = from_db

    return ((base | _subscript_assignments(endpoint)) - _popped(endpoint)) | _route_injected_keys(page, f"{template}.html")


# --------------------------------------------------------------------------------------
# What the template reads
# --------------------------------------------------------------------------------------
def _page_function(route_module, template):
    """The view function that renders `template`.

    Everything below is scoped to it, because Python names are. Running the flow analysis over the
    whole route module let one function's local grow another's: in `templates.py`, 23 KB across a
    dozen views, the API-sourced set spread to thirty-odd names and swallowed a real dead key.
    """
    for node in ast.walk(route_module):
        if not isinstance(node, ast.FunctionDef):
            continue
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "render_template"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == template
            ):
                return node
    raise AssertionError(f"no view function renders {template!r}")


def _api_sourced_locals(route_module):
    """Local names that hold API data, followed to a fixpoint rather than one assignment deep.

    The prevailing shape in these routes is two hops —

        result = API_CLIENT.get_redirects(limit=500)
        redirect_rows = result.get("redirects", [])
        return render_template("redirects.html", redirects=redirect_rows, ...)

    — so a one-hop rule sees `redirects` as unrelated to the API and derives an empty read set,
    which then reads as a clean page. Following the flow is not a loosening: a name qualifies only
    by being assigned from `API_CLIENT` or from another name that already qualifies.
    """
    known = set()
    for _ in range(10):  # these routes chain 2 deep; 10 is a stop, not a limit
        grown = set(known)
        for node in ast.walk(route_module):
            if not isinstance(node, ast.Assign):
                continue
            if not (_mentions_api_client(node.value) or _mentions_any(node.value, known)):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    grown.add(target.id)
                elif isinstance(target, ast.Tuple):  # `rows, total = [], 0` and its API-fed sibling
                    grown |= {element.id for element in target.elts if isinstance(element, ast.Name)}
        # `for certificate in certificate_rows:` binds a row, and the route then writes to it.
        for node in ast.walk(route_module):
            if isinstance(node, (ast.For, ast.comprehension)):
                iterable = node.iter
                if _mentions_api_client(iterable) or _mentions_any(iterable, grown):
                    target = node.target
                    if isinstance(target, ast.Name):
                        grown.add(target.id)
                    elif isinstance(target, ast.Tuple):
                        grown |= {element.id for element in target.elts if isinstance(element, ast.Name)}
        if grown == known:
            return known
        known = grown
    raise AssertionError("route data flow did not settle")


def _api_sourced_variables(page, template):
    """Template variables the UI route fills from the API client, for one `render_template` call."""
    view = _page_function(_module(UI_ROUTES / f"{page}.py"), template)
    known = _api_sourced_locals(view)
    rendered = set()
    for node in ast.walk(view):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "render_template"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == template):
            continue
        for keyword in node.keywords:
            if keyword.arg and (_mentions_api_client(keyword.value) or _mentions_any(keyword.value, known)):
                rendered.add(keyword.arg)
    return rendered


def _mentions_api_client(node):
    return any(isinstance(sub, ast.Name) and sub.id == "API_CLIENT" for sub in ast.walk(node))


def _mentions_any(node, names):
    return any(isinstance(sub, ast.Name) and sub.id in names for sub in ast.walk(node))


def _root_name(node):
    """The variable a template expression ultimately hangs off: `job_data['cache']` -> `job_data`."""
    while isinstance(node, (nodes.Getitem, nodes.Getattr)):
        node = node.node
    if isinstance(node, nodes.Call):
        return _root_name(node.node)
    return node.name if isinstance(node, nodes.Name) else None


def _row_variables(template_ast, seeds):
    """Loop targets that iterate over API-sourced data, directly or through one.

    `{% for cache in job_data['cache'] %}` only carries API rows because `job_data` does, so this
    runs to a fixpoint instead of looking one level deep.
    """
    known = set(seeds)
    targets = set()
    for _ in range(10):  # depth of nesting in these templates is 2; 10 is a stop, not a limit
        grown = set(known)
        for loop in template_ast.find_all(nodes.For):
            if _root_name(loop.iter) in known:
                target = loop.target
                names = {item.name for item in getattr(target, "items", [target]) if isinstance(item, nodes.Name)}
                grown |= names
                targets |= names
        if grown == known:
            # The seeds are *collections* — `configs`, `caches`, `jobs`. Only what a loop binds out
            # of one is a row, and only rows have the keys this compares. Returning the seeds too
            # made every API-derived aggregate passed to the same template look like a row:
            # `certificates.py` builds `status_counts = Counter(...)` from the rows, so
            # `status_counts.get("expired", 0)` was being read as a certificate field that the API
            # fails to emit. It is a tally of them.
            return targets
        known = grown
    raise AssertionError("template loop nesting did not settle")


def keys_read(page, template=None):
    """Every constant key the template reads off a row: `row['k']`, `row.k`, `row.get('k')`."""
    template = template or page
    source = (TEMPLATES / f"{template}.html").read_text(encoding="utf-8")
    template_ast = Environment(autoescape=True).parse(source)
    rows = _row_variables(template_ast, _api_sourced_variables(page, f"{template}.html"))

    def on_row(node):
        """True only for an access made *directly* on a row variable.

        Deliberately not `_root_name`: `cache['file_name'].startswith(...)` hangs off a row but
        `startswith` is a method of the value, not a key of the row. Accepting it would have added
        `replace` and `startswith` to every page's read set — including the control's, which would
        have made `/jobs` fail for a reason that has nothing to do with the contract.
        """
        return isinstance(node, nodes.Name) and node.name in rows

    read = set()
    for node in template_ast.find_all(nodes.Getitem):
        if on_row(node.node) and isinstance(node.arg, nodes.Const) and isinstance(node.arg.value, str):
            read.add(node.arg.value)
    for node in template_ast.find_all(nodes.Getattr):
        if on_row(node.node):
            read.add(node.attr)
    for node in template_ast.find_all(nodes.Call):
        if (
            isinstance(node.node, nodes.Getattr)
            and node.node.attr == "get"
            and on_row(node.node.node)
            and node.args
            and isinstance(node.args[0], nodes.Const)
            and isinstance(node.args[0].value, str)
        ):
            read.add(node.args[0].value)
    # `row.get('k')` also registers `get` itself as an attribute read; it is a method, not a key.
    return read - {"get", "items", "keys", "values"}


# --------------------------------------------------------------------------------------
# Which pages this covers, and why the rest it does not
# --------------------------------------------------------------------------------------
# Discovered, not listed: a candidate is any view that renders a template with at least one kwarg
# fed by `API_CLIENT`, whose page has a same-named API router with a `@router.get("")` list
# endpoint. A page added tomorrow is checked tomorrow, or it fails
# `test_every_candidate_is_checked_or_excused` until someone writes down why not.
#
# Pages that never reach candidacy, recorded here so none is silently omitted:
#   /bans, /reports   DataTables `serverSide`. The template has no row loop at all; rows are built
#                     in JS from a JSON endpoint, so there is no template/API contract to pin.
#   /instances        rows arrive as `Instance` objects from `InstancesUtils.get_instances()`, not
#                     as API dicts. Its constructor pins the API's keys positionally
#                     (`instance["hostname"]`, ...), so a rename there raises KeyError rather than
#                     failing silently — the failure mode this guard exists for cannot occur.
#   /plugins          `plugins` is injected by the global context processor in `main.py:1461`, from
#                     `BW_CONFIG.get_plugins()`, not from the route and not from an API list router.
#   /web-cache        `routers/web_cache.py` has no `@router.get("")`; the page is assembled in the
#                     route from `get_web_cache_status()` + `get_web_cache_metrics()` and reshaped.
NOT_COVERABLE = {
    ("cache", "cache_view.html"): "single cache file, not a row list",
    ("configs", "config_edit.html"): "one config in a form, not a row list",
    ("global_settings", "global_settings.html"): "`config` is a settings mapping keyed by setting name, not rows",
    ("global_settings", "plugin_settings_page.html"): "settings mapping, not rows",
    ("services", "service_settings.html"): "settings mapping for one service, not rows",
    ("services", "plugin_settings_page.html"): "settings mapping, not rows",
    ("services", "template_settings_page.html"): "settings mapping, not rows",
}


def _candidates():
    """Every (page, template) a view renders with API-fed data and a same-named list endpoint."""
    found = set()
    for route in sorted(UI_ROUTES.glob("*.py")):
        if route.name in ("__init__.py", "utils.py"):
            continue
        router = API_ROUTERS / route.name
        if not router.exists():
            continue
        try:
            _list_endpoint(_module(router))
        except AssertionError:
            continue
        module = _module(route)
        for function in [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)]:
            known = _api_sourced_locals(function)
            for call in ast.walk(function):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "render_template"):
                    continue
                if not (call.args and isinstance(call.args[0], ast.Constant)):
                    continue
                if any(kw.arg and (_mentions_api_client(kw.value) or _mentions_any(kw.value, known)) for kw in call.keywords):
                    found.add((route.stem, call.args[0].value))
    return found


COVERED = sorted((page, template) for page, template in _candidates() if (page, template) not in NOT_COVERABLE)
PAGE_IDS = [f"{page}:{template}" for page, template in COVERED]


# --------------------------------------------------------------------------------------
# The guard
# --------------------------------------------------------------------------------------
def test_every_candidate_is_checked_or_excused():
    """A page may not be quietly left out. Adding a list page makes this fail until it is either
    covered or given a reason in `NOT_COVERABLE`; deleting one makes the stale excuse fail."""
    candidates = _candidates()
    unexplained = sorted(candidates - set(COVERED) - set(NOT_COVERABLE))
    stale = sorted(set(NOT_COVERABLE) - candidates)

    assert not unexplained, f"candidate pages neither covered nor excused: {unexplained}"
    assert not stale, f"NOT_COVERABLE names pages that are no longer candidates: {stale}"


def test_the_discovery_found_pages_to_cover():
    """RULE 13 floor, `>=` because growth is COLLABORATION here: every new list page that gains an
    API fetch route should join `COVERED` automatically, and a lane adding one must not have to
    touch this number.

    Measured rather than assumed: emptying `_candidates()` already gives `2 failed, 2 skipped`, so
    this guard survived the mutant on its own. The floor is still stated explicitly, because the
    catch was incidental — it fell out of the "at least one page is clean" control below rather than
    from anything that says an empty discovery is a bug."""
    assert len(COVERED) >= 5, f"the page discovery collapsed to {len(COVERED)}: {PAGE_IDS}"
    assert len(PAGE_IDS) == len(COVERED), "PAGE_IDS drifted from COVERED"


def test_at_least_one_covered_page_is_clean():
    """The control, as a test rather than as a habit. If every covered page were drifted, a guard
    that simply always failed would look identical to this one from the outside."""
    clean = [f"{page}:{template}" for page, template in COVERED if not (keys_read(page, Path(template).stem) - emitted_keys(page, Path(template).stem))]

    assert clean, "no covered page is clean; this guard can no longer be told apart from one that always fails"


@pytest.mark.parametrize(("page", "template"), COVERED, ids=PAGE_IDS)
def test_the_derivation_finds_something_on_both_sides(page, template):
    """Anti-vacuity, per page. An empty set on either side makes the subset check below pass for
    free, and that is exactly how a broken derivation looks like a clean page."""
    stem = Path(template).stem

    assert emitted_keys(page, stem), f"derived no emitted keys for /{page}; the derivation is broken, not the page"
    assert keys_read(page, stem), f"derived no keys read by {template}; the derivation is broken, not the page"


@pytest.mark.parametrize(("page", "template"), COVERED, ids=PAGE_IDS)
def test_the_template_only_reads_keys_the_api_emits(page, template):
    """Green since the Option A fix landed (2026-08-20, ~11:00). This docstring previously read
    "FAILS ON /configs, /cache AND /templates BY DESIGN"; it named three real dead keys and said
    they would go green when the fix landed. They did — the templates now read `service` and
    `plugin`, the keys the API actually emits. Corrected rather than deleted so the next reader can
    see what the guard was written against."""
    stem = Path(template).stem
    emitted = emitted_keys(page, stem)
    dead = sorted(keys_read(page, stem) - emitted)

    assert not dead, (
        f"{template} reads keys the API does not emit: {dead}\n"
        f"  emitted by src/api/app/routers/{page}.py: {sorted(emitted)}\n"
        "  a dead key is Undefined in Jinja, which is falsy, so it renders as empty or as the "
        "fallback branch rather than raising"
    )

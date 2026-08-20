"""`url_for` in a template must never quietly become `"#"` for a route that exists.

The UI wraps `url_for` so a template can name a *page* by its short name: `url_for("bans")` means
`bans.bans_page`. An endpoint that is already fully qualified and is not a page does not fit that
convention — expanding `onboarding.onboarding_state` gives
`onboarding.onboarding_state.onboarding.onboarding_state_page`, which cannot build — and the wrapper
used to answer `"#"` and log it at DEBUG.

`"#"` is not an inert placeholder. `fetch("#")` re-requests **the current page**, so the onboarding
drawer, which asks for its state on every page in the UI, was pulling a second full server render of
every page: ~118 KB and a complete render thrown away, per visit, silently. Five endpoints in the
templates resolve this way — `onboarding.onboarding_state`, `whats_new.update_whats_new_state`,
`plugins.plugin_icon`, `services.services_resource_attach`, `threatmap.threatmap_data`.

The resolver is read out of `main.py` rather than imported: it is defined inside
`with app.app_context():`, and importing that module builds the whole application — database, API
client and all. Reading the source keeps the test on the code that actually ships.
"""

import ast
import re
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask import Flask
from flask import url_for as flask_url_for

REPO = Path(__file__).resolve().parents[3]
MAIN = REPO / "src" / "ui" / "main.py"
TEMPLATES = REPO / "src" / "ui" / "app" / "templates"


def _resolver():
    """The resolver lifted out of `main.py`, with `url_for` and `LOGGER` supplied.

    `_build_url` does the resolving; `custom_url_for` adds the warning and the `"#"`, and
    `endpoint_exists` asks the same question without the warning. All three come across together —
    the point of the split is that the two callers share one notion of what resolves.
    """
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    wanted = ("_build_url", "custom_url_for", "endpoint_exists", "ENDPOINTS_WITHOUT_A_PAGE_SUFFIX")
    nodes = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.FunctionDef) and node.name in wanted)
        or (isinstance(node, ast.Assign) and any(getattr(target, "id", None) in wanted for target in node.targets))
    ]

    assert len(nodes) == 4, f"expected the resolver, its two callers and the allow-list in main.py, found {[getattr(n, 'name', 'assign') for n in nodes]}"

    namespace = {"url_for": flask_url_for, "LOGGER": Mock(), "BuildError": sys.modules["werkzeug.routing.exceptions"].BuildError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=sorted(nodes, key=lambda n: n.lineno), type_ignores=[])), str(MAIN), "exec"), namespace)
    return namespace["custom_url_for"], namespace["LOGGER"], namespace["endpoint_exists"]


@pytest.fixture
def resolve():
    """The resolver, bound to an app whose url_map has one of each shape the UI uses."""
    app = Flask(__name__)
    app.add_url_rule("/bans", endpoint="bans.bans_page", view_func=lambda: "")
    app.add_url_rule("/onboarding/state", endpoint="onboarding.onboarding_state", view_func=lambda: "")
    app.add_url_rule("/plugins/<name>/icon", endpoint="plugins.plugin_icon", view_func=lambda name: "")
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "")
    custom_url_for, logger, _ = _resolver()
    with app.test_request_context("/"):
        yield custom_url_for, logger


def test_a_page_is_still_named_by_its_short_name(resolve):
    """The convention the wrapper exists for, and the reason it cannot simply be deleted."""
    custom_url_for, _ = resolve

    assert custom_url_for("bans") == "/bans"


def test_a_fully_qualified_non_page_endpoint_resolves(resolve):
    """The regression. Every one of these used to render as `"#"`, and `fetch("#")` is a second
    full render of whatever page the template was on."""
    custom_url_for, _ = resolve

    assert custom_url_for("onboarding.onboarding_state") == "/onboarding/state"
    assert custom_url_for("plugins.plugin_icon", name="antibot") == "/plugins/antibot/icon"


def test_an_allow_listed_endpoint_is_not_expanded(resolve):
    custom_url_for, _ = resolve

    assert custom_url_for("loading") == "/loading"


def test_an_endpoint_that_really_does_not_exist_still_yields_a_placeholder_and_says_so(resolve):
    """`"#"` remains the answer when there is nothing to resolve — a plugin page that is not
    installed still has to render. What changes is that it is no longer silent: DEBUG is not a
    level anyone reads, and this failure is invisible in the rendered page."""
    custom_url_for, logger = resolve

    assert custom_url_for("nothing.at_all") == "#"
    assert logger.warning.called, "a '#' reaching a template is a bug and has to be visible above DEBUG"


# Both quote styles, and the backreference so `url_for('x.y")` is not read as a call. Matching only
# one style is the same failure mode as hardcoding the list: whatever is written the other way is
# invisible for a reason that has nothing to do with whether it works.
DOTTED_ENDPOINT = re.compile(r"""url_for\((['"])([a-z_]+\.[a-z_]+)\1""")

# Distinct dotted endpoints in the templates today. A floor, not an inventory — adding a page only
# ever raises it, and a *drop* means the scan stopped seeing a form it used to see, which is the
# failure this test exists to prevent. Tighter than the equivalent floor in `test_t_placeholders.py`
# because the set is two orders of magnitude smaller, so slack would hide exactly what it must catch.
DOTTED_ENDPOINTS_TODAY = 19


def _dotted_endpoints():
    found = set()
    for path in TEMPLATES.rglob("*.html"):
        found |= {match[1] for match in DOTTED_ENDPOINT.findall(path.read_text(encoding="utf-8"))}
    return found


def test_every_dotted_endpoint_in_the_templates_names_a_real_view():
    """The other half: the resolver can only resolve what exists.

    Scanned rather than listed — a hardcoded tuple would not have covered `whats_new` or
    `threatmap`, which were added later and broke the same way.
    """
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (REPO / "src" / "ui" / "app" / "routes").glob("*.py"))
    endpoints = _dotted_endpoints()

    assert endpoints, "no dotted endpoints found; the scan is looking at the wrong thing"
    missing = [endpoint for endpoint in sorted(endpoints) if f"def {endpoint.split('.')[1]}(" not in sources]

    assert not missing, f"these templates name views that do not exist, so they render as '#': {missing}"


def test_the_scan_has_not_quietly_stopped_seeing_call_sites():
    """A scan that matches less than it used to reports "all clear" for the wrong reason.

    This test was written single-quote-only and missed `global_settings.global_settings_plugin_page`
    and `services.services_plugin_page` — both fine, both invisible. Neither was a defect; the point
    is that nothing said the covered set had shrunk.
    """
    endpoints = _dotted_endpoints()

    assert len(endpoints) >= DOTTED_ENDPOINTS_TODAY, (
        f"the scan sees {len(endpoints)} dotted endpoints, down from {DOTTED_ENDPOINTS_TODAY}: "
        f"either a page was deliberately removed (raise the floor) or a call site is written in a form the regex misses"
    )


@pytest.fixture
def probe():
    """`endpoint_exists`, bound to the same url_map."""
    app = Flask(__name__)
    app.add_url_rule("/bans", endpoint="bans.bans_page", view_func=lambda: "")
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "")
    custom_url_for, logger, endpoint_exists = _resolver()
    with app.test_request_context("/"):
        yield custom_url_for, logger, endpoint_exists


def test_asking_whether_an_endpoint_exists_does_not_warn_about_it(probe):
    """`menu.html` decides how to link a plugin by asking whether it has a page of its own. Asked as
    `url_for(plugin) == "#"` that was one warning per pageless plugin per page render — 358 of them
    in an hour on the perf stack, 17 per render, none of them a problem. A warning that fires on
    purpose trains everyone to ignore the ones that do not.
    """
    _, logger, endpoint_exists = probe

    assert endpoint_exists("bans") is True
    assert endpoint_exists("antibot") is False
    assert endpoint_exists("") is False
    logger.warning.assert_not_called()


def test_the_probe_and_the_url_agree_on_what_resolves(probe):
    """Two callers, one notion of resolvable — or the menu links one thing and the href says
    another."""
    custom_url_for, _, endpoint_exists = probe

    for endpoint in ("bans", "loading", "antibot", "", "nope.nope_page"):
        assert endpoint_exists(endpoint) is (custom_url_for(endpoint) != "#"), endpoint


def test_no_template_asks_the_question_with_the_warning_attached():
    """The shape that caused it, kept out rather than fixed twice.

    Both forms count. `menu.html` compared the call directly; `breadcrumb.html` assigned it first
    and compared the variable a few lines later, which the first version of this test did not see —
    so `/global-config` kept logging a warning on every visit after the menu was fixed. A template
    that treats `"#"` as an expected answer has asked a question, and questions go through
    `endpoint_exists`.
    """
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        source = path.read_text(encoding="utf-8")
        direct = list(re.finditer(r'url_for\([^)]*\)\s*[!=]=\s*"#"', source))
        indirect = list(re.finditer(r'[!=]=\s*"#"', source)) if "url_for(" in source else []
        if not direct and not (indirect and "endpoint_exists" not in source):
            continue
        line = (direct or indirect)[0].start()
        offenders.append(f"{path.relative_to(TEMPLATES)}:{source[:line].count(chr(10)) + 1}")

    assert not offenders, f"these ask whether a route exists by building it; use endpoint_exists(): {offenders}"

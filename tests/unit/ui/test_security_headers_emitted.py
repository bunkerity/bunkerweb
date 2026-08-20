"""What `set_security_headers` actually PUTS ON THE RESPONSE, not what main.py's text contains.

``test_webauthn.py::test_permissions_policy_allows_webauthn`` reads main.py as a string and asserts
substrings. That is a presence marker: it survives every realistic weakening of this header except
deleting the literal. It cannot see a malformed value, a duplicated directive, or a grant that is
present in the source but not in what the browser receives.

The header is one long comma-separated literal, so the failure that matters is not deletion — it is
a value that still contains ``publickey-credentials-get=(self)`` while being wrong somewhere else.
One missing comma merges two directives into a name a browser drops silently, taking WebAuthn with
it, and the substring assertions all still pass.

So this runs the real function against a real ``Response`` and parses what comes out.
"""

from ast import FunctionDef, parse, unparse
from pathlib import Path
from re import fullmatch
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

flask = pytest.importorskip("flask")

MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"

# Everything is denied except these four, which the threatmap and passkey login need.
GRANTED = {"fullscreen", "screen-wake-lock", "publickey-credentials-create", "publickey-credentials-get"}


def _load_handler():
    """Compile `set_security_headers` alone, with its module globals stubbed.

    Importing main.py boots the whole UI. The function is self-contained apart from a handful of
    module-level names, so lifting it out by AST is enough to exercise the real body — and it stays
    honest, because the body is the shipped one rather than a copy.
    """
    tree = parse(MAIN.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, FunctionDef) and n.name == "set_security_headers")
    fn.decorator_list = []  # @app.after_request needs the real app

    namespace = {
        "g": SimpleNamespace(script_nonce="test-nonce", request_id="rid"),
        "token_urlsafe": lambda _n: "generated-nonce",
        "request": SimpleNamespace(path="/home", method="GET", headers={}, cookies={}, is_secure=False),
        "perf": SimpleNamespace(server_timing=lambda: "", totals=lambda: (0, 0.0, 0.0)),
        "LOGGER": Mock(),
        "app": SimpleNamespace(config={"AFTER_REQUEST_HOOKS": []}),
        # Read off main.py rather than invented. If a future edit adds another free name, the exec
        # below raises NameError rather than quietly testing less -- which is not hypothetical:
        # this stub said STATIC_PATH_PREFIXES until cluster J replaced that call site with
        # is_static_path(), and these six tests went red the same minute.
        "is_static_path": lambda path, *extra: path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/") + extra)
        or path == "/favicon.ico",
    }
    exec(compile(unparse(fn), str(MAIN), "exec"), namespace)  # noqa: S102
    return namespace["set_security_headers"]


def _headers(path="/home"):
    """Run the real handler over one request path and hand back what reached the response."""
    handler = _load_handler()
    handler.__globals__["request"] = SimpleNamespace(path=path, method="GET", headers={}, cookies={}, is_secure=False)
    return handler(flask.Response("ok")).headers


def _policy():
    return _headers().get("Permissions-Policy")


# RULE 13 floor. Every test below reasons over this list, and an empty one makes half of them
# vacuously true -- `bad == []` and `denied == names - GRANTED` both pass over nothing. `>=` and not
# `==` deliberately: the list grows whenever anyone syncs the header with Chromium again, and that
# growth is collaboration, not a regression. The one place growth IS the defect -- an extra granted
# feature -- is asserted exactly, in test_exactly_the_four_needed_features_are_granted.
MINIMUM_DIRECTIVES = 81


def _directives(policy):
    parsed = [d.strip() for d in policy.split(",")]
    assert len(parsed) >= MINIMUM_DIRECTIVES, f"only {len(parsed)} directives parsed -- the tests below would be vacuous"
    return parsed


def test_the_header_is_emitted_at_all():
    assert _policy(), "no Permissions-Policy reached the response"


def test_every_directive_is_well_formed():
    """A single missing comma merges two directives into a name the browser drops in silence."""
    bad = [d for d in _directives(_policy()) if not fullmatch(r"[a-z0-9-]+=\((self)?\)", d)]

    assert bad == [], f"malformed directives: {bad}"


def test_no_directive_is_declared_twice():
    names = [d.split("=")[0] for d in _directives(_policy())]

    assert len(names) == len(set(names)), f"duplicated: {sorted({n for n in names if names.count(n) > 1})}"


def test_exactly_the_four_needed_features_are_granted_and_only_to_self():
    """Both directions. An extra grant widens the surface; a missing one kills the feature."""
    granted = {d.split("=")[0] for d in _directives(_policy()) if d.endswith("=(self)")}

    assert granted == GRANTED


def test_everything_else_is_denied_outright():
    denied = {d.split("=")[0] for d in _directives(_policy()) if d.endswith("=()")}
    names = {d.split("=")[0] for d in _directives(_policy())}

    assert denied == names - GRANTED


def test_the_chromium_sync_is_present_and_not_silently_shrunk():
    """The list went 44 -> 81 with the Chromium resync; a revert to the old list is a weakening."""
    names = {d.split("=")[0] for d in _directives(_policy())}

    assert len(names) >= 81, f"only {len(names)} directives -- did the Chromium sync get reverted?"
    assert "ch-ua-wow64" in names, "the digit-bearing name the setting's regex had to be widened for"
    assert "unload" in names and "shared-storage" in names


def test_the_handler_is_still_registered_as_an_after_request_hook():
    """The body above can be perfect and never run. Presence of the decorator is the other half."""
    tree = parse(MAIN.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, FunctionDef) and n.name == "set_security_headers")

    assert any(unparse(d) == "app.after_request" for d in fn.decorator_list)


def test_no_later_hook_overwrites_the_header():
    """The realistic neutering: leave the literal alone and stamp the header again downstream."""
    source = MAIN.read_text(encoding="utf-8")

    assert source.count('headers["Permissions-Policy"]') == 1, "a second write to this header exists -- read it"


# --------------------------------------------------------------------------------------
# The headers ported from dev 4264af5c3, and the two exemptions that make one of them safe
# --------------------------------------------------------------------------------------
def test_the_panel_is_kept_out_of_search_indexes():
    """robots.txt stops a crawler *fetching*; it does not stop a URL discovered elsewhere from
    being indexed. Only this header does, and it is the half that survives a misconfigured proxy."""
    assert _headers().get("X-Robots-Tag") == "noindex, nofollow"


def test_the_cross_origin_relationship_is_severed():
    """COOP puts the UI in its own browsing-context group; CORP refuses cross-origin embedding."""
    headers = _headers()

    assert headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert headers.get("Cross-Origin-Resource-Policy") == "same-origin"


def test_coep_is_absent_and_that_is_the_decision():
    """Not an oversight, and not a set to be completed later. `require-corp` would demand a CORP
    header (or CORS) from every subresource, including the third-party origins the CSP explicitly
    allows -- they would stop loading, with a console error and no server-side symptom at all."""
    assert "Cross-Origin-Embedder-Policy" not in _headers()


def test_a_page_is_not_left_in_the_browser_cache():
    """The back button after a logout is the case: without this the browser redraws the panel,
    with its data, from its own cache, and no request reaches a server that would refuse it."""
    assert _headers("/home").get("Cache-Control") == "no-store"


def test_a_static_asset_keeps_its_own_caching():
    """The guard is not decoration. `no-store` here would re-download core.css, every font and
    every locale on every page load -- the static handler's far-future max-age is the point."""
    assert _headers("/css/core.css").get("Cache-Control") is None


def test_a_route_that_already_answered_this_wins():
    """`setdefault`, not assignment. Three routes set their own and each would be flattened:
    /plugins/<p>/icon (private, max-age=3600), the log streams (no-cache), logout (a *stricter*
    no-store, no-cache, must-revalidate, max-age=0). The icon one is the visible regression --
    every plugin icon would be refetched on every render of the plugins page."""
    handler = _load_handler()
    handler.__globals__["request"] = SimpleNamespace(path="/plugins/antibot/icon", method="GET", headers={}, cookies={}, is_secure=False)
    response = flask.Response("ok")
    response.headers["Cache-Control"] = "private, max-age=3600"

    assert handler(response).headers.get("Cache-Control") == "private, max-age=3600"

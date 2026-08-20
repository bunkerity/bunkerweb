"""Which paths skip the request pipeline — and that nothing reaches around the one function.

`is_static_path` decides whether a request bypasses the UIData lock, the CSP nonce, `get_metadata`,
the session-revocation check and — at `app/models/biscuit.py:157` — the **Biscuit authorization
middleware**. So the interesting case is not "does /css/ pass", it is what ELSE slips through.

The port that introduced it (dev `94df1eb2b`) exists precisely because the previous shape listed
`/favicon.ico` among tuples that every consumer feeds to `str.startswith`, which exempts
`/favicon.icoX` and `/favicon.ico/anything` as well. That intermediate state was never applied here;
this pins the reason it must not be.

RULE 14b: the behaviour is "these paths bypass the pipeline", and it has five call sites. Testing
the function alone would leave a sixth call site free to reintroduce the raw `startswith`, so the
last test asserts nobody does.
"""

from pathlib import Path
from re import findall

import pytest

UI = Path(__file__).resolve().parents[3] / "src" / "ui"

is_static_path = pytest.importorskip("app.utils", reason="src/ui on sys.path").is_static_path
STATIC_PATH_PREFIXES = pytest.importorskip("app.utils").STATIC_PATH_PREFIXES
STATIC_EXACT_PATHS = pytest.importorskip("app.utils").STATIC_EXACT_PATHS


def test_the_module_under_test_is_importable_at_all():
    """RULE 15: `importorskip` turns a broken sys.path into a file full of SILENT SKIPS, and CI
    renders `14 skipped` and `14 passed` identically. This test never skips, so the day `src/ui`
    stops being importable the suite says so in red instead of quietly testing nothing.

    `find_spec` rather than an import: it answers the question without the side effects.
    """
    from importlib.util import find_spec

    assert (
        find_spec("app.utils") is not None
    ), "src/ui is not on sys.path -- every behavioural test in this file skipped and the static-path exemption has ZERO coverage"


# RULE 13 floor. `>=`: both lists grow when a new asset family is served, which is collaboration.
MINIMUM_PREFIXES = 7
MINIMUM_EXACT = 5


def test_the_source_lists_have_not_emptied_out():
    assert len(STATIC_PATH_PREFIXES) >= MINIMUM_PREFIXES
    assert len(STATIC_EXACT_PATHS) >= MINIMUM_EXACT


@pytest.mark.parametrize("path", ["/css/app.css", "/img/logo.png", "/js/main.js", "/locales/en.js", "/favicon.ico"])
def test_the_real_static_assets_are_exempt(path):
    assert is_static_path(path)


@pytest.mark.parametrize("path", ["/robots.txt", "/security.txt", "/.well-known/security.txt", "/.well-known/change-password"])
def test_the_public_by_contract_paths_are_exempt(path):
    """Ported from dev `2eb795fad` / `4264af5c3`. These are fetched by scanners and password
    managers with no account, often before one exists; answering with a login redirect is the
    failure. What makes the exemption safe is asserted below, not here."""
    assert is_static_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/favicon.icoX",  # the prefix-vs-exact bug this function exists to prevent
        "/favicon.ico/anything",
        "/favicon.ico/../global-config",
        "/robots.txtX",
        "/security.txt/../global-config",
        "/.well-known/security.txtX",
        "/.well-known/change-password/../../global-config",
        "/.well-known/",  # not a prefix: nothing under /.well-known/ is exempt by default
        "/home",
        "/global-config",
        "/css",  # the prefixes carry their trailing slash on purpose
    ],
)
def test_nothing_else_is_exempt(path):
    assert not is_static_path(path), f"{path} would skip authorization, revocation and the host check"


def test_extra_prefixes_widen_only_for_the_caller_that_passes_them():
    """The Biscuit middleware exempts /logout as well; that must not leak into the other callers."""
    assert is_static_path("/logout", "/logout")
    assert not is_static_path("/logout")


def test_every_consumer_goes_through_the_function():
    """RULE 14b: one behaviour, five call sites. A sixth writing its own startswith is the bypass.

    The failure this prevents is not deletion — it is a new call site added with
    `request.path.startswith(STATIC_PATH_PREFIXES)`, which is green, reads as idiomatic, and
    silently drops the exact-match half.
    """
    offenders = []
    for source in list((UI / "app").rglob("*.py")) + [UI / "main.py"]:
        if source.name == "utils.py" and source.parent.name == "app":
            continue  # the definition itself
        text = source.read_text(encoding="utf-8")
        for hit in findall(r"startswith\(\s*STATIC_PATH_PREFIXES", text):
            offenders.append(str(source.relative_to(UI)))

    assert offenders == [], f"these bypass is_static_path(): {sorted(set(offenders))}"


def test_nothing_privileged_was_added_to_the_exact_list():
    """The cost side of this tuple, asserted rather than assumed.

    Adding a path here does not just skip the static fast-path: it skips the Host allowlist, the
    session-revocation check and the Biscuit authorization middleware, for that exact URL. So every
    entry must be answerable by something that holds nothing back -- either a file under
    `static/`, or a route in `main.py` carrying no `@login_required`.

    A privileged path added to this tuple is silently public, with no error and a 200 that looks
    entirely normal. That is the failure this test exists to make loud.
    """
    from ast import Call, Constant, FunctionDef, parse, unparse

    # The rule string is read off the decorator's first argument, not matched in the unparsed text:
    # `ast.unparse` normalises to single quotes, so `f'"{exact}"' in rendered` finds nothing and the
    # whole scan reports "unrouted" for every route that exists. It did, on the first run.
    tree = parse((UI / "main.py").read_text(encoding="utf-8"))
    routed = {}
    for node in tree.body:
        if not isinstance(node, FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (isinstance(decorator, Call) and unparse(decorator.func) == "app.route" and decorator.args):
                continue
            rule = decorator.args[0]
            if isinstance(rule, Constant) and rule.value in STATIC_EXACT_PATHS:
                routed[rule.value] = [unparse(d) for d in node.decorator_list]

    unanswerable, protected = [], []
    for exact in STATIC_EXACT_PATHS:
        if exact in routed:
            if any("login_required" in d for d in routed[exact]):
                protected.append(exact)
        elif not (UI / "app" / "static" / exact.lstrip("/")).is_file():
            unanswerable.append(exact)

    assert protected == [], f"these are exempt from authorization AND behind a login -- one of the two is wrong: {protected}"
    assert unanswerable == [], f"these are exempt from the pipeline but nothing serves them; an exempt 404 is a hole with no upside: {unanswerable}"

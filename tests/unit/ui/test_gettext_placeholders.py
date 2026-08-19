"""A `_()` call must pass every variable its message interpolates, or the page 500s.

Jinja's i18n extension does not do what `flask_babel.gettext` does. `flask_babel` formats only when
variables are passed (`s if not variables else s % variables`); Jinja's `_gettext_alias` ends with
an unconditional `return rv % variables`. So inside a template, `_("tooltip.button.ping_instance")`
on a message that reads `Ping Instance %(hostname)s` raises `KeyError: 'hostname'` and takes the
whole request with it.

Seven of those shipped in the Lot C template conversion — three on `/cache`, four on `/instances`,
every one an `aria-label` whose sibling tooltip passed the variable correctly. Both pages returned
500 to every user with at least one row.

**Why the existing suite could not catch it.** All seven sit inside a row loop, so a page rendered
with an empty list never reaches them. Every render test did exactly that, stayed green, and the
first thing to notice was a browser driving a real stack.

The check here is static rather than a render, deliberately: a render only exercises the branches
its fixture happens to reach, and these lived in the one branch no fixture reached. Reading the
source covers every call site on every page, including the ones no test renders at all.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "src" / "ui" / "app" / "templates"
CATALOG = TEMPLATES.parent / "static" / "locales" / "en.json"

# `_("some.key")` with nothing between the key and the closing paren — no variables passed.
BARE_CALL = re.compile(r'_\(\s*"([a-z][a-z0-9_.]*)"\s*\)')
# `{{name}}` in the JSON catalog becomes `%(name)s` in the compiled gettext catalog.
PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _messages():
    def flatten(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flatten(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}", value

    return dict(flatten(json.loads(CATALOG.read_text(encoding="utf-8"))))


def test_no_template_calls_a_placeholder_message_without_its_variables():
    """The static half: every bare `_()` in every template, checked against the catalog.

    This needs no render, so it covers the call sites a render test cannot reach — inside a row
    loop, inside a branch that needs particular state, inside a macro nobody calls in tests.
    """
    messages = _messages()
    offenders = []

    for path in sorted(TEMPLATES.rglob("*.html")):
        source = path.read_text(encoding="utf-8")
        for match in BARE_CALL.finditer(source):
            key = match.group(1)
            variables = PLACEHOLDER.findall(messages.get(key, ""))
            if variables:
                line = source[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(TEMPLATES)}:{line} _({key!r}) needs {variables}")

    assert not offenders, "these calls raise KeyError at render:\n  " + "\n  ".join(offenders)


def test_the_scan_would_actually_catch_one():
    """The check above passes trivially if its regex or its catalog lookup is wrong, and a scan
    that silently matches nothing is worse than no scan. This pins both ends against a message
    that really does carry a placeholder."""
    messages = _messages()
    key = "tooltip.button.ping_instance"

    assert PLACEHOLDER.findall(messages[key]) == ["hostname"], "the catalog entry changed shape"
    assert BARE_CALL.findall(f'aria-label="{{{{ _("{key}") }}}}"') == [key], "the bare-call pattern no longer matches"
    assert not BARE_CALL.findall(f'_("{key}", hostname=x)'), "a call that passes variables must not be flagged"

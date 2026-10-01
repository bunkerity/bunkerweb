"""The `/redirects` and `/upstreams` create forms check the server's own rules in the browser.

Two things can silently disable that check:

- drift: the HTML pattern stops agreeing with the rule the API enforces (the redirect plugin's
  REDIRECT_FROM / REDIRECT_TO regexes, the upstream name / server / fail_timeout regexes);
- the browser compiles `pattern` with the `v` flag, which refuses an unescaped `{`, `}`, `(`, `)`,
  `[`, `/`, `|` or a lone `-` inside a character class — and an invalid pattern is simply ignored.
  The old upstream name pattern `[A-Za-z0-9_-]+` was exactly that, so "qa up!" reached the server.
"""

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _constants(path: Path) -> dict:
    """String constants assigned at module level, plus the pattern of every `NAME = re_compile(r"...")`."""
    found = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign) or not isinstance(node.targets[0], ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Call) and value.args:
            value = value.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            found[node.targets[0].id] = value.value
    return found


REDIRECT_ROUTE = _constants(ROOT / "src" / "ui" / "app" / "routes" / "redirects.py")
UPSTREAM_ROUTE = _constants(ROOT / "src" / "ui" / "app" / "routes" / "upstreams.py")
UPSTREAM_DB = _constants(ROOT / "src" / "common" / "db" / "db_methods" / "upstreams.py")
REDIRECT_PLUGIN = {
    key: value.get("regex", "") for key, value in json.loads((ROOT / "src" / "common" / "core" / "redirect" / "plugin.json").read_text())["settings"].items()
}

CASES = [
    (
        REDIRECT_ROUTE["FROM_PATH_PATTERN"],
        REDIRECT_PLUGIN["REDIRECT_FROM"],
        ["/", "/old", "no-slash", "~ ^/api", "= /exact", "^~ /img", "~*", "=", "/a b", "/a;b", "/a{1}", "~ "],
    ),
    (
        REDIRECT_ROUTE["TO_URL_PATTERN"],
        REDIRECT_PLUGIN["REDIRECT_TO"],
        ["https://example.org/qa", "http://a.b/c?d=e&f=(g)", "https://h:8443/$x", "not a url", "ftp://x", "https://", "https://x y"],
    ),
    (UPSTREAM_ROUTE["NAME_PATTERN"], UPSTREAM_DB["UPSTREAM_NAME_RE"], ["qa-up", "pool_1", "qa up!", "a.b", "-"]),
    (
        UPSTREAM_ROUTE["SERVER_PATTERN"],
        UPSTREAM_DB["UPSTREAM_SERVER_RE"],
        ["10.0.0.1:8080", "backend", "[::1]:443", "a-b.example", "http://x", "x:0", "x:", "-x", "x y"],
    ),
    (UPSTREAM_ROUTE["FAIL_TIMEOUT_PATTERN"], UPSTREAM_DB["UPSTREAM_FAIL_TIMEOUT_RE"], ["10s", "500ms", "3", "1h", "s", "10 s", "-1"]),
]


@pytest.mark.parametrize("pattern,rule,samples", CASES)
def test_the_form_pattern_agrees_with_the_server_rule(pattern, rule, samples):
    # The browser anchors `pattern` as ^(?:pattern)$, i.e. a full match; an empty field is not checked.
    for sample in samples:
        assert bool(re.fullmatch(pattern, sample)) == bool(re.fullmatch(rule, sample)), sample


def _v_flag_hazards(pattern: str) -> list[str]:
    hazards, in_class, index, start = [], False, 0, 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if not in_class:
            if char == "[":
                in_class, start = True, index + (2 if pattern[index + 1 : index + 2] == "^" else 1)
        elif char == "]":
            in_class = False
        elif char in "(){}[/|":
            hazards.append(f"unescaped {char!r} in a class at {index}")
        elif char == "-" and (index == start or pattern[index + 1 : index + 2] == "]"):
            hazards.append(f"lone '-' in a class at {index}")
        index += 1
    return hazards


@pytest.mark.parametrize("pattern", [case[0] for case in CASES])
def test_the_form_pattern_compiles_with_the_browser_v_flag(pattern):
    assert not _v_flag_hazards(pattern), pattern


def test_the_hazard_scan_catches_the_patterns_that_were_silently_ignored():
    assert _v_flag_hazards("[A-Za-z0-9_-]+")
    assert _v_flag_hazards(REDIRECT_PLUGIN["REDIRECT_FROM"])

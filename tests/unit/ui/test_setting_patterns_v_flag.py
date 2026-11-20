"""Plugin setting regexes reach the browser as a `pattern` it really checks.

Browsers compile `pattern` with the `v` flag and silently ignore one they refuse, so a field
whose regex has a bare `-` or `{` in a class, or a Python-only escape such as `\\"`, was never
checked client-side (REDIRECT_FROM, the reverse-proxy / gRPC header and host settings, ...).
`v_safe_pattern` (templates) and its twin `vSafePattern` (setting_controls.js) respell the
literals only. Over every regex shipped in settings.json and the core plugin.json files this
checks, through the real JS in node, that:

- both twins give the same output;
- that output compiles with `new RegExp(p, "v")` (and without flags, for the page scripts
  that re-test `pattern` themselves);
- the browser's full match agrees with Python `re.fullmatch` on a sample corpus.

Corpus limit, on purpose: ASCII only. Under the `v` flag `\\w`, `\\d` and `\\b` are ASCII, in
Python `re` they are Unicode; that engine gap predates this transform and a `\\p{...}` spelling
would break the page scripts that compile `pattern` without a flag.
"""

import json
import re
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

from app.html_pattern import v_safe_pattern

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / "src" / "ui"
TEMPLATES = UI / "app" / "templates"
SETTING_CONTROLS = UI / "app" / "static" / "js" / "modules" / "setting_controls.js"

requires_node = pytest.mark.skipif(which("node") is None, reason="node is not installed")


def _shipped_settings() -> dict[str, dict]:
    found = {}
    for path in [ROOT / "src" / "common" / "settings.json", *sorted((ROOT / "src" / "common" / "core").glob("*/plugin.json"))]:
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, setting in (data if path.name == "settings.json" else data.get("settings", {})).items():
            if isinstance(setting, dict) and setting.get("regex"):
                found[f"{path.relative_to(ROOT)}:{name}"] = setting
    return found


SHIPPED = _shipped_settings()
SHIPPED_REGEXES = sorted({setting["regex"] for setting in SHIPPED.values()})

# Shipped regexes that get no `pattern`, with the reason. Empty today: every one can be respelled.
WITHOUT_PATTERN: dict[str, str] = {}

# Branches no shipped regex reaches today; both twins must still agree on them.
SYNTHETIC = [
    r"(?P<n>a)\1",
    r"a{,3}",
    r"a{2,}",
    r"a{}",
    r"{a}",
    r"a*+",
    r"(?i)abc",
    r"(?>a)",
    r"(?#c)a",
    r"[\w-a]",
    r"[\w-]",
    r"[]a]",
    r"[^]a]",
    r"[a-c-e]",
    r"[--/]",
    r"[\b-x]",
    r"[\x41-\x5a]",
    r"\é",
    "a\U0001f600",
    r"\Z",
    r"[\B]",
    r"a\/b\-c\"d\#",
    r"[&&!!##]",
    r"[\n\t ]+",
    r"(?<=a)b(?<!c)",
    r"[a",
    "",
]

_BASE_SAMPLES = [
    "",
    " ",
    "a",
    "abc",
    "A1",
    "_",
    "-",
    "a-b",
    "a_b.c",
    "0",
    "1",
    "80",
    "443",
    "65535",
    "65536",
    "8080",
    "1.5",
    "yes",
    "no",
    "on",
    "off",
    "true",
    "10s",
    "5m",
    "1h",
    "30d",
    "100k",
    "10M",
    "2G",
    "/",
    "/path",
    "/a/b",
    "no-slash",
    "~ ^/api",
    "= /exact",
    "^~ /img",
    "~*",
    "=",
    "/a b",
    "/a;b",
    "/a{1}",
    "a{b}",
    "http://x",
    "https://example.org/qa",
    "https://h:8443/$x",
    "ftp://x",
    "https://",
    "grpc://h:50051",
    "127.0.0.1",
    "10.0.0.0/8",
    "::1",
    "fe80::1",
    "2001:db8::/32",
    "1.2.3.4 5.6.7.8",
    "1.1.1.1 1.1.1.1",
    "256.1.1.1",
    "www.example.com",
    "app1.example.com app2.example.com",
    ".example.com",
    "-bad.example",
    "X-Header value",
    "X-Header value; Y-Other v2",
    "Host",
    "Host X-Real-IP",
    "$var value",
    "$upstream_addr x",
    "GET|POST|HEAD",
    "|GET",
    "GET||POST",
    "TLSv1.2 TLSv1.3",
    "ECDHE-RSA-AES128-GCM-SHA256:ECDHE",
    "x25519:secp384r1",
    '"q"',
    "'q'",
    "#",
    "a#b",
    "\\",
    "a\\b",
    "|",
    "[",
    "]",
    "()",
    "(",
    "{",
    "}",
    ";",
    "&",
    "!",
    "%",
    "@",
    "`",
    "~",
    "^",
    "$",
    ".",
    "*",
    "+",
    "?",
    "a,b",
    "a:b",
    "a=b",
    "<a>",
    "a  b",
    " a",
    "a ",
    "abc123def",
    "/C=FR/O=Org/",
    "/CN=x/",
    "2026-09-25T10:00:00Z",
    "2026-13-01T00:00:00Z",
    "self",
    '(self "https://a.b")',
    "geolocation=(self)",
    "camera=()",
]
_MUTANTS = [" ", "-", "{", "}", ";", "/", "\\", '"', "'", "#", "|", "[", "]", "(", ")", ".", "*", "?", "$", "&", "!", "%", "@", "a", "0", "_"]


def _samples(setting: dict) -> list[str]:
    samples, defaults = set(_BASE_SAMPLES), set()
    for value in (setting.get("default"), *setting.get("select", ())):
        if isinstance(value, str) and value.isascii() and "\n" not in value:
            defaults.add(value)
            value = value[:12]
            samples.update((value[1:], value[:-1], f"{value} {value}"))
            middle = len(value) // 2
            for char in _MUTANTS:
                samples.update((value + char, char + value, value[:middle] + char + value[middle:]))
    # Near misses stay short: several shipped regexes backtrack exponentially on a long one
    # (CORS_EXPOSE_HEADERS takes minutes, in both engines, on a 30-character near miss).
    return sorted(defaults | {sample for sample in samples if len(sample) <= 24})


NODE_RUNNER = r"""
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [modulePath, inputPath] = process.argv.slice(1);
const { vSafePattern } = await import(pathToFileURL(modulePath).href);
const { transform, check, literal } = JSON.parse(readFileSync(inputPath, "utf8"));
const compiles = (pattern, flags) => {
  try { new RegExp(pattern, flags); return true; } catch { return false; }
};
const out = { transformed: {}, invalid: [], matches: {}, literal: {} };
for (const regex of transform) out.transformed[regex] = vSafePattern(regex);
for (const [pattern, samples] of check) {
  if (!compiles(`^(?:${pattern})$`, "v") || !compiles(pattern, "")) { out.invalid.push(pattern); continue; }
  const browser = new RegExp(`^(?:${pattern})$`, "v");
  out.matches[pattern] = samples.map((sample) => browser.test(sample));
}
for (const pattern of literal) out.literal[pattern] = compiles(`^(?:${pattern})$`, "v");
process.stdout.write(JSON.stringify(out));
"""

_TEMPLATE_PATTERN = re.compile(r'pattern="([^"]*)"')


def _template_patterns() -> dict[str, list[str]]:
    """Every `pattern="..."` in the UI templates, by `file:line`."""
    found: dict[str, list[str]] = {}
    for path in sorted(TEMPLATES.rglob("*.html")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in _TEMPLATE_PATTERN.findall(line):
                found.setdefault(pattern, []).append(f"{path.relative_to(ROOT)}:{number}")
    return found


@pytest.fixture(scope="module")
def node_results(tmp_path_factory):
    transformed = {regex: v_safe_pattern(regex) for regex in SHIPPED_REGEXES}
    check, expected = [], {}
    for key, setting in SHIPPED.items():
        pattern = transformed[setting["regex"]]
        if pattern and pattern not in expected:
            samples = _samples(setting)
            check.append((pattern, samples))
            expected[pattern] = (setting["regex"], samples, key)
    literal = [pattern for pattern in _template_patterns() if "{{" not in pattern and "{%" not in pattern]
    payload = tmp_path_factory.mktemp("vflag") / "input.json"
    payload.write_text(json.dumps({"transform": SHIPPED_REGEXES + SYNTHETIC, "check": check, "literal": literal}), encoding="utf-8")
    result = run(["node", "--input-type=module", "-e", NODE_RUNNER, str(SETTING_CONTROLS), str(payload)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), transformed, expected


@requires_node
def test_the_python_and_js_twins_give_the_same_pattern(node_results):
    results, _, _ = node_results
    differ = {regex: (v_safe_pattern(regex), results["transformed"][regex]) for regex in SHIPPED_REGEXES + SYNTHETIC}
    assert {regex: pair for regex, pair in differ.items() if pair[0] != pair[1]} == {}


@requires_node
def test_every_shipped_regex_gets_a_pattern_the_browser_compiles(node_results):
    results, transformed, _ = node_results
    assert results["invalid"] == []
    assert {regex: WITHOUT_PATTERN.get(regex, "?") for regex, pattern in transformed.items() if not pattern} == WITHOUT_PATTERN


@requires_node
def test_the_browser_accepts_exactly_what_the_server_regex_accepts(node_results):
    results, _, expected = node_results
    disagreements = []
    for pattern, (regex, samples, key) in expected.items():
        for sample, browser in zip(samples, results["matches"][pattern]):
            if browser != bool(re.fullmatch(regex, sample)):
                disagreements.append((key, sample, browser))
    assert disagreements == []


@requires_node
def test_every_literal_template_pattern_compiles_with_the_v_flag(node_results):
    results, _, _ = node_results
    locations = _template_patterns()
    refused = {pattern: locations[pattern] for pattern, ok in results["literal"].items() if not ok}
    assert {pattern: places for pattern, places in refused.items() if places} == {}


def test_no_template_or_script_emits_a_raw_setting_regex():
    raw = []
    for pattern, places in _template_patterns().items():
        if "regex" in pattern and "v_safe_pattern" not in pattern:
            raw.extend(places)
    for number, line in enumerate(SETTING_CONTROLS.read_text(encoding="utf-8").splitlines(), 1):
        if 'setAttribute("pattern"' in line and "regex" in line:
            raw.append(f"{SETTING_CONTROLS.relative_to(ROOT)}:{number}")
    assert raw == []


@pytest.mark.parametrize(
    "regex,pattern",
    [
        (r"^[A-Za-z0-9_-]+$", r"^[A-Za-z0-9_\-]+$"),
        (r"^$|^[^\s\"'\;{}#]+$", r"^$|^[^\s" + "\"'" + r"\;\{\}\#]+$"),
        (r"^/[^/]+/$", r"^/[^\/]+/$"),
        (r"a\-b\"c", 'a-b"c'),
        (r"a{,3}", "a{0,3}"),
        (r"a{}", r"a\{\}"),
        (r"(?P<n>a)", "(?<n>a)"),
        (r"(?i)a", ""),
        (r"a*+", ""),
        (r"[\w-a]", ""),
        (r"[a", ""),
        (None, ""),
    ],
)
def test_v_safe_pattern_respells_literals_only(regex, pattern):
    assert v_safe_pattern(regex) == pattern

"""The editor's serialiser against the canonical validator.

The rule ladder holds a view of the definition, not the definition: NOT is unary in the
schema ({"op": "not", "node": ...}) but reads as a "None of" group on screen, so the editor
rewrites it in both directions. If that rewrite drifts from workflow_schema.py every save
fails at once, which is why it is checked here rather than left to the browser.

Runs the real JS through node — no DOM, no jsdom: the module exports its model layer on
window.BW_WORKFLOW_MODEL precisely so this needs nothing but two stub globals.
"""

from html.parser import HTMLParser
from json import dumps, loads
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

from workflow_schema import validate_definition  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
EDITOR = ROOT / "src" / "ui" / "app" / "static" / "js" / "pages" / "workflow_editor.js"

# One tree per shape the rewrite has to survive: a plain combinator, a nested one, the NOT
# group, and each leaf kind including the two that are not value lists.
CONDITION = {
    "op": "all",
    "nodes": [
        {"op": "uri", "match": "prefix", "value": "/login"},
        {
            "op": "any",
            "nodes": [
                {"op": "country", "values": ["FR", "BE"]},
                {"op": "asn", "values": [16509]},
                {"op": "group", "kind": "ip", "group_id": "office"},
            ],
        },
        {"op": "not", "node": {"op": "any", "nodes": [{"op": "method", "values": ["GET"]}]}},
        {"op": "not", "node": {"op": "ip", "values": ["203.0.113.0/24"]}},
    ],
}

DEFINITION = {
    "schema_version": 1,
    "rules": [
        {
            "id": "r1",
            "name": "Challenge logins from flagged networks",
            "enabled": True,
            "condition": CONDITION,
            "threshold": {"count": 10, "window": 60, "key": "ip"},
            "action": {"type": "challenge", "provider": "hcaptcha"},
        },
        {
            "id": "r2",
            "name": "Cap the rest",
            "enabled": False,
            "condition": {"op": "any", "nodes": [{"op": "uri", "match": "regex", "value": "^/api/v[0-9]+/"}]},
            "threshold": None,
            "action": {"type": "block"},
        },
    ],
}

GROUP_INDEX = {"office": {"ip": ["203.0.113.0/24"]}}

HARNESS = """
globalThis.window = globalThis;
globalThis.document = { addEventListener() {} };
require(process.argv[2]);
const model = globalThis.window.BW_WORKFLOW_MODEL;
const definition = JSON.parse(process.argv[3]);
process.stdout.write(
  JSON.stringify({
    schema_version: 1,
    rules: definition.rules.map((rule) => ({
      id: rule.id,
      name: rule.name,
      enabled: rule.enabled,
      condition: model.toSchema(model.fromSchema(rule.condition)),
      threshold: rule.threshold,
      action: rule.action,
    })),
  }),
);
"""


@pytest.fixture(scope="module")
def node():
    binary = which("node")
    if not binary:
        pytest.skip("node is not installed")
    return binary


def _round_trip(node, tmp_path, definition):
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    result = run([node, str(harness), str(EDITOR), dumps(definition)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return loads(result.stdout)


def test_the_editor_serialises_a_definition_the_validator_accepts(node, tmp_path):
    _, errors = validate_definition(DEFINITION, group_index=GROUP_INDEX)
    assert errors == []

    once = _round_trip(node, tmp_path, DEFINITION)
    canonical, errors = validate_definition(once, group_index=GROUP_INDEX)
    assert errors == [], errors

    # Loading the ladder and serialising it again must be a fixed point. Valid-once is not
    # enough: a rewrite that kept drifting would still validate every time while quietly
    # rewriting the operator's rules on every visit.
    twice = _round_trip(node, tmp_path, once)
    again, errors = validate_definition(twice, group_index=GROUP_INDEX)
    assert errors == [], errors
    assert again == canonical

    # Everything the rewrite does not touch comes back byte-identical.
    original, _ = validate_definition(DEFINITION, group_index=GROUP_INDEX)
    assert canonical["rules"][1] == original["rules"][1]


def test_a_not_leaf_survives_as_a_not_group(node, tmp_path):
    """not(<leaf>) has no group to show, so it becomes not(any([leaf])) — the same meaning."""
    definition = _round_trip(node, tmp_path, DEFINITION)
    negations = [node for node in definition["rules"][0]["condition"]["nodes"] if node["op"] == "not"]
    assert len(negations) == 2
    for negation in negations:
        assert negation["node"]["op"] == "any"


CONVERT_HARNESS = """
globalThis.window = globalThis;
globalThis.document = { addEventListener() {} };
require(process.argv[2]);
const model = globalThis.window.BW_WORKFLOW_MODEL;
const cases = JSON.parse(process.argv[3]);
process.stdout.write(
  JSON.stringify(cases.map((c) => model.convertLeaf(c.node, c.op))),
);
"""


def _convert(node, tmp_path, cases):
    harness = tmp_path / "convert.js"
    harness.write_text(CONVERT_HARNESS, encoding="utf-8")
    result = run([node, str(harness), str(EDITOR), dumps(cases)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return loads(result.stdout)


def test_changing_a_predicate_type_keeps_the_values_it_can(node, tmp_path):
    """Switching type used to call newLeaf() and drop everything the operator had typed."""
    forty = [f"203.0.113.{octet}" for octet in range(40)]
    converted = _convert(
        node,
        tmp_path,
        [
            {"node": {"op": "ip", "values": forty}, "op": "asn"},
            {"node": {"op": "country", "values": ["FR", "BE"]}, "op": "method"},
            # uri holds one string and group holds a reference: neither is a value list, so
            # nothing carries and the editor announces the loss instead of hiding it.
            {"node": {"op": "ip", "values": forty}, "op": "uri"},
            {"node": {"op": "uri", "match": "prefix", "value": "/login"}, "op": "ip"},
        ],
    )

    assert converted[0]["op"] == "asn" and converted[0]["values"] == forty
    assert converted[1]["op"] == "method" and converted[1]["values"] == ["FR", "BE"]
    assert converted[2]["op"] == "uri" and "values" not in converted[2]
    assert converted[3]["op"] == "ip" and converted[3]["values"] == []


# Enough of a DOM to run the editor's DOMContentLoaded path and capture what it draws. The
# ladder is built by string concatenation into innerHTML, so a mangled quote in one of the
# ~30 aria-label/title attributes produces markup no unit test would otherwise see.
RENDER_HARNESS = """
const store = {};
function el(id) {
  return store[id] || (store[id] = {
    id, value: "", innerHTML: "", textContent: "", disabled: false, on: {},
    classList: { toggle(){}, add(){}, remove(){}, contains(){return false} },
    addEventListener(ev, cb){ (this.on[ev] = this.on[ev] || []).push(cb) },
    querySelector(){return null},
    querySelectorAll(){return []}, closest(){return null},
    setAttribute(){}, removeAttribute(){}, focus(){}, appendChild(){},
    getBoundingClientRect(){return {top:0,bottom:0}},
  });
}
let ready;
globalThis.window = globalThis;
globalThis.addEventListener = function(){};
globalThis.CSS = { escape: (s) => String(s) };
globalThis.document = {
  addEventListener(ev, cb) { if (ev === "DOMContentLoaded") ready = cb; },
  getElementById: el,
  querySelector(){ return null },
  querySelectorAll(){ return [] },
  createElement(){ return el("tmp") },
};
require(process.argv[2]);
el("wf-readonly").value = "no";
el("wf-groups").value = JSON.stringify({});
el("wf-definition").value = process.argv[3];
ready();
process.stdout.write(el("wf-rules").innerHTML + "\\n<!--CAP-->\\n" + el("wf-cap").innerHTML);
"""


class _Balance(HTMLParser):
    VOID = {"input", "img", "br", "hr", "meta", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.unbalanced, self.elements = [], [], []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.unbalanced.append(f"</{tag}> closes {self.stack[-1] if self.stack else 'nothing'}")
        else:
            self.stack.pop()


def _render(node, tmp_path, definition):
    harness = tmp_path / "render.js"
    harness.write_text(RENDER_HARNESS, encoding="utf-8")
    result = run([node, str(harness), str(EDITOR), dumps(definition)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.split("\n<!--CAP-->\n")


def test_the_ladder_renders_well_formed_markup(node, tmp_path):
    """A rule name carrying quotes must not break out of the attributes that hold it."""
    definition = {
        "schema_version": 1,
        "rules": [dict(DEFINITION["rules"][0], name='Challenge "odd" logins'), DEFINITION["rules"][1]],
    }
    ladder, _ = _render(node, tmp_path, definition)

    parser = _Balance()
    parser.feed(ladder)
    assert parser.unbalanced == [], parser.unbalanced
    assert parser.stack == [], f"unclosed: {parser.stack}"
    assert len(parser.elements) > 40

    # A botched concatenation leaves the tail of a JS expression in the attribute value.
    for tag, attrs in parser.elements:
        for name in ("aria-label", "title", "placeholder"):
            value = attrs.get(name)
            if value is None:
                continue
            assert value.strip(), f"empty {name} on <{tag}>"
            assert '" +' not in value and "' +" not in value, f"{name}={value!r}"


# Same stub DOM, driven through the run button instead of read for markup. rsplit rather
# than replace: the render tail contains escaped newlines that do not survive re-quoting.
TESTER_HARNESS = (
    RENDER_HARNESS.rsplit("process.stdout.write", 1)[0].replace(
        "require(process.argv[2]);",
        """const posts = [];
globalThis.fetch = function(url, init) {
  posts.push({ url, body: JSON.parse(init.body) });
  return Promise.resolve({ json: () => Promise.resolve({ status: "success", valid: true, outcome: { type: "no_match" }, workflows: [] }) });
};
require(process.argv[2]);""",
    )
    + """
el("wf-test-url").value = "/workflows/wf-1/test";
el("wf-test-asn").value = process.argv[4];
el("wf-test-country").value = "FR";
el("wf-test-uri").value = "/login";
(el("wf-test-run").on.click || []).forEach((cb) => cb({ preventDefault(){} }));
// The editor also validates on its own; only the tester's call is of interest here.
const posted = posts.filter((post) => /\\/test$/.test(post.url)).pop() || null;
process.stdout.write(JSON.stringify({ posted, panel: el("wf-test-result").innerHTML }));
"""
)


def _run_tester(node, tmp_path, asn):
    harness = tmp_path / "tester.js"
    harness.write_text(TESTER_HARNESS, encoding="utf-8")
    result = run([node, str(harness), str(EDITOR), dumps(DEFINITION), asn], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return loads(result.stdout)


def test_a_typed_asn_reaches_the_api_as_a_number(node, tmp_path):
    payload = _run_tester(node, tmp_path, "64496")
    assert payload["posted"]["body"]["request"]["asn"] == 64496
    assert payload["posted"]["url"].endswith("/test")


def test_a_non_numeric_asn_is_refused_instead_of_becoming_a_failed_lookup(node, tmp_path):
    """Number("AS64496") is NaN, which serialises to null — and null means "the lookup
    failed", so a typo would come back as a confident UNKNOWN rather than an error."""
    payload = _run_tester(node, tmp_path, "AS64496")
    assert payload["posted"] is None
    assert "number" in payload["panel"]


def test_the_first_paint_interpolates_its_own_fallbacks(node, tmp_path):
    """The editor is deferred and draws before i18next finishes initialising, so the fallback
    path is a normal first paint. It must substitute {{n}} itself or the operator reads the
    placeholder."""
    ladder, cap = _render(node, tmp_path, DEFINITION)
    assert "{{" not in ladder, [m for m in ladder.split() if "{{" in m][:5]
    assert "{{" not in cap
    assert 'aria-label="Name of rule 1"' in ladder

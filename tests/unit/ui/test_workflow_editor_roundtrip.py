"""The editor's serialiser against the canonical validator.

The rule ladder holds a view of the definition, not the definition: NOT is unary in the
schema ({"op": "not", "node": ...}) but reads as a "None of" group on screen, so the editor
rewrites it in both directions. If that rewrite drifts from workflow_schema.py every save
fails at once, which is why it is checked here rather than left to the browser.

Runs the real JS through node — no DOM, no jsdom: the module exports its model layer on
window.BW_WORKFLOW_MODEL precisely so this needs nothing but two stub globals.
"""

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

"""Validation, canonicalisation and summary of security workflow definitions.

The validator is the only thing standing between an operator's form and a fail-closed
compiler that aborts the whole config push, so the cases below focus on what must be
*refused* — and, for group references, on the fact that a missing one is an error rather
than a silently empty list (which would turn a security rule into a no-op).
"""

import json
from pathlib import Path

from workflow_schema import (  # type: ignore
    CHALLENGE_PROVIDERS,
    MAX_RULES_PER_WORKFLOW,
    MAX_TREE_DEPTH,
    canonical_json,
    collect_group_refs,
    rule_stats,
    summarize_rule,
    validate_definition,
)

ROOT = Path(__file__).resolve().parents[3]

GROUPS = {"g-office": {"ip": ["203.0.113.0/24"], "country": []}, "g-empty": {}}


def _rule(rule_id="r1", condition=None, action=None, **extra):
    return {
        "id": rule_id,
        "name": extra.pop("name", "rule"),
        "condition": condition or {"op": "country", "values": ["FR"]},
        "action": action or {"type": "block"},
        **extra,
    }


def _validate(rules, groups=None):
    return validate_definition({"schema_version": 1, "rules": rules}, group_index=GROUPS if groups is None else groups)


def _errors(rules, groups=None):
    definition, errors = _validate(rules, groups)
    assert definition is None, "expected the definition to be refused"
    return {error["code"] for error in errors}, errors


# --- the two worked examples from the design ------------------------------------------


def test_worked_example_country_and_uri_over_a_threshold_challenges():
    definition, errors = _validate(
        [
            _rule(
                "5f1c",
                name="Login flood challenge",
                condition={"op": "all", "nodes": [{"op": "country", "values": ["fr"]}, {"op": "uri", "match": "prefix", "value": "/login"}]},
                action={"type": "challenge", "provider": "hcaptcha"},
                threshold={"count": 10, "window": 60},
            )
        ]
    )
    assert errors == []
    rule = definition["rules"][0]
    assert rule["condition"]["nodes"][0]["values"] == ["FR"]  # normalised to upper case
    assert rule["threshold"] == {"count": 10, "window": 60, "key": "ip"}  # key defaulted
    assert rule["action"] == {"type": "challenge", "provider": "hcaptcha"}
    assert rule["enabled"] is True


def test_over_the_rate_block_else_challenge_is_two_ordered_rules():
    """There is no ``else``: the second rule wins only while the first is under its gate."""
    uri = {"op": "uri", "match": "prefix", "value": "/login"}
    definition, errors = _validate(
        [
            _rule("aa11", condition=uri, action={"type": "block", "status": 429}, threshold={"count": 10, "window": 60}),
            _rule("bb22", condition=uri, action={"type": "challenge", "provider": "hcaptcha"}, threshold=None),
        ]
    )
    assert errors == []
    # Rule order is semantic and must survive canonicalisation untouched.
    assert [rule["id"] for rule in definition["rules"]] == ["aa11", "bb22"]
    assert definition["rules"][0]["threshold"]["count"] == 10
    assert definition["rules"][1]["threshold"] is None


# --- canonical form -------------------------------------------------------------------


def test_canonical_json_is_stable_and_compact():
    assert canonical_json({"b": 1, "a": [2, 1]}) == '{"a":[2,1],"b":1}'


def test_value_lists_are_sorted_and_deduped_so_the_artefact_hash_is_stable():
    first, _ = _validate([_rule(condition={"op": "country", "values": ["FR", "BE", "FR"]})])
    second, _ = _validate([_rule(condition={"op": "country", "values": ["be", "FR"]})])
    assert first["rules"][0]["condition"]["values"] == ["BE", "FR"]
    assert canonical_json(first) == canonical_json(second)


def test_leaf_values_are_normalised():
    definition, _ = _validate(
        [
            _rule(
                condition={
                    "op": "all",
                    "nodes": [
                        {"op": "ip", "values": ["203.0.113.7/24", "2001:db8::/32"]},
                        {"op": "asn", "values": ["AS64496", 64497]},
                        {"op": "method", "values": ["post"]},
                    ],
                }
            )
        ]
    )
    nodes = definition["rules"][0]["condition"]["nodes"]
    # Host inside a subnet is normalised to its network; the order is lexicographic, which
    # is arbitrary but stable — and stability is what the artefact hash depends on.
    assert nodes[0]["values"] == ["2001:db8::/32", "203.0.113.0/24"]
    assert nodes[1]["values"] == [64496, 64497]
    assert nodes[2]["values"] == ["POST"]


# --- refusals -------------------------------------------------------------------------


def test_a_missing_group_is_an_error_not_an_empty_list():
    codes, _ = _errors([_rule(condition={"op": "group", "kind": "ip", "group_id": "nope"})])
    assert codes == {"group_missing"}


def test_a_group_without_an_entry_of_that_kind_is_refused():
    codes, _ = _errors([_rule(condition={"op": "group", "kind": "country", "group_id": "g-office"})])
    assert codes == {"group_kind_empty"}
    codes, _ = _errors([_rule(condition={"op": "group", "kind": "ip", "group_id": "g-empty"})])
    assert codes == {"group_kind_empty"}


def test_empty_combinators_are_refused():
    for op in ("all", "any"):
        codes, _ = _errors([_rule(condition={"op": op, "nodes": []})])
        assert codes == {"group_empty"}


def test_depth_beyond_the_cap_is_refused_and_the_path_points_at_the_node():
    node = {"op": "country", "values": ["FR"]}
    for _ in range(MAX_TREE_DEPTH):
        node = {"op": "all", "nodes": [node]}
    codes, errors = _errors([_rule(condition=node)])
    assert codes == {"depth_exceeded"}
    assert errors[0]["path"].startswith("rules[0].condition.nodes[0]")


def test_a_broken_regex_is_reported_with_its_path():
    codes, errors = _errors([_rule(condition={"op": "uri", "match": "regex", "value": "([unclosed"})])
    assert codes == {"regex_invalid"}
    assert errors[0]["path"] == "rules[0].condition.value"


def test_a_uri_predicate_refuses_a_query_string_and_a_relative_path():
    assert _errors([_rule(condition={"op": "uri", "match": "prefix", "value": "/x?y=1"})])[0] == {"uri_query_string"}
    assert _errors([_rule(condition={"op": "uri", "match": "exact", "value": "login"})])[0] == {"uri_not_absolute"}


def test_invalid_leaf_values_are_refused():
    assert _errors([_rule(condition={"op": "ip", "values": ["not-an-ip"]})])[0] == {"ip_invalid"}
    assert _errors([_rule(condition={"op": "country", "values": ["FRA"]})])[0] == {"country_invalid"}
    assert _errors([_rule(condition={"op": "asn", "values": ["banana"]})])[0] == {"asn_invalid"}
    assert _errors([_rule(condition={"op": "unknown"})])[0] == {"op_invalid"}


def test_actions_are_constrained():
    assert _errors([_rule(action={"type": "challenge", "provider": "nope"})])[0] == {"provider_invalid"}
    assert _errors([_rule(action={"type": "redirect", "url": "ftp://x", "status": 302})])[0] == {"redirect_url_invalid"}
    assert _errors([_rule(action={"type": "redirect", "url": "https://x", "status": 418})])[0] == {"redirect_status_invalid"}
    # Anything other than 429 belongs in the deny-status setting, not in a rule.
    assert _errors([_rule(action={"type": "block", "status": 418})])[0] == {"block_status_invalid"}
    assert _errors([_rule(action={"type": "log"})])[0] == {"action_invalid"}


def test_a_block_without_a_status_defers_to_the_instance_deny_status():
    definition, _ = _validate([_rule(action={"type": "block"})])
    assert definition["rules"][0]["action"] == {"type": "block"}


def test_thresholds_are_constrained():
    assert _errors([_rule(threshold={"count": 0, "window": 60})])[0] == {"threshold_count_invalid"}
    assert _errors([_rule(threshold={"count": 1, "window": 0})])[0] == {"threshold_window_invalid"}
    assert _errors([_rule(threshold={"count": 1, "window": 60, "key": "session"})])[0] == {"threshold_key_invalid"}
    assert _errors([_rule(threshold={"count": "many", "window": 60})])[0] == {"threshold_invalid"}


def test_rule_identity_is_required_and_unique():
    assert _errors([_rule("")])[0] == {"id_missing"}
    assert _errors([_rule("same"), _rule("same")])[0] == {"id_duplicate"}


def test_the_rule_count_and_schema_version_are_capped():
    codes, _ = _errors([_rule(f"r{index}") for index in range(MAX_RULES_PER_WORKFLOW + 1)])
    assert codes == {"rules_exceeded"}
    definition, errors = validate_definition({"schema_version": 99, "rules": []}, group_index=GROUPS)
    assert definition is None and errors[0]["code"] == "schema_version_unsupported"


def test_nothing_is_stored_when_one_rule_is_invalid():
    """Partial acceptance would let the compiler abort the whole push later instead."""
    definition, errors = _validate([_rule("ok"), _rule("bad", condition={"op": "country", "values": ["nope"]})])
    assert definition is None and errors


# --- derived views --------------------------------------------------------------------


def test_collect_group_refs_walks_the_whole_tree():
    definition, _ = _validate(
        [
            _rule(
                condition={
                    "op": "any",
                    "nodes": [{"op": "not", "node": {"op": "group", "kind": "ip", "group_id": "g-office"}}, {"op": "country", "values": ["FR"]}],
                }
            )
        ]
    )
    assert collect_group_refs(definition) == {("g-office", "ip")}


def test_rule_stats_counts_predicates_and_skips_disabled_rules_by_default():
    definition, _ = _validate(
        [
            _rule(
                "on",
                condition={"op": "all", "nodes": [{"op": "country", "values": ["FR"]}, {"op": "uri", "match": "regex", "value": "^/a"}]},
            ),
            _rule("off", enabled=False),
        ]
    )
    assert rule_stats(definition) == {"rules": 1, "predicates": 2, "pcre": 1}
    assert rule_stats(definition, enabled_only=False)["rules"] == 2


def test_summarize_rule_reads_as_a_sentence():
    definition, _ = _validate(
        [
            _rule(
                condition={"op": "all", "nodes": [{"op": "country", "values": ["FR"]}, {"op": "uri", "match": "prefix", "value": "/login"}]},
                action={"type": "challenge", "provider": "hcaptcha"},
                threshold={"count": 10, "window": 60},
            )
        ]
    )
    assert summarize_rule(definition["rules"][0]) == (
        "If (country is FR and URI starts with /login), over 10 requests per 60s per IP, then show the hcaptcha challenge"
    )


def test_challenge_providers_match_the_antibot_plugin():
    """Anti-drift: the providers a workflow may request are USE_ANTIBOT's, minus "no"."""
    settings = json.loads(ROOT.joinpath("src", "common", "core", "antibot", "plugin.json").read_text())["settings"]["USE_ANTIBOT"]
    assert set(CHALLENGE_PROVIDERS) == set(settings["select"]) - {"no"}

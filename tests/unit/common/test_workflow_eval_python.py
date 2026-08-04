"""The Python evaluator behind the rule tester: three-valued algebra, leaves and the ladder.

The corpus in test_workflow_tester_parity.py proves this agrees with the real Lua runtime.
This file proves the same rules in isolation, because "cell ALL(U,F) expected F got U" is a
diagnosis and "corpus case 7 disagrees" is a search.
"""

from workflow_eval import (  # type: ignore
    F,
    STATE_DISABLED,
    STATE_FALSE,
    STATE_GATE_CLOSED,
    STATE_MATCH,
    STATE_UNKNOWN,
    STATE_UNREACHED,
    T,
    U,
    Outcome,
    _run,
    evaluate,
    inline_groups,
    prepare_ladder,
    request_from_input,
)

VALUES = (F, T, U)


def _req(**overrides):
    base = {
        "remote_addr": "203.0.113.7",
        "uri": "/login",
        "request_method": "GET",
        "country": "FR",
        "country_ok": True,
        "asn_number": 64496,
        "asn_ok": True,
        "request_number": 1,
        "whitelisted": False,
    }
    base.update(overrides)
    return base


def _run_with(node, request=None):
    return _run(node, request or _req(), "condition", [])


# --- the algebra ----------------------------------------------------------------------


def test_all_and_any_match_the_lua_truth_table():
    """Same table test_workflow_eval.py asserts against eval.lua, evaluated the other way."""
    request = _req()
    # ip leaves standing in for fixed verdicts: a value that is in the list, one that is not,
    # and an unparseable list which the runtime degrades to UNKNOWN.
    fixed = {
        F: {"op": "ip", "values": ["198.51.100.0/24"]},
        T: {"op": "ip", "values": ["203.0.113.0/24"]},
        U: {"op": "ip", "values": ["not-an-address"]},
    }
    expected_all = {
        (F, F): F,
        (F, T): F,
        (F, U): F,
        (T, F): F,
        (T, T): T,
        (T, U): U,
        (U, F): F,
        (U, T): U,
        (U, U): U,
    }
    expected_any = {
        (F, F): F,
        (F, T): T,
        (F, U): U,
        (T, F): T,
        (T, T): T,
        (T, U): T,
        (U, F): U,
        (U, T): T,
        (U, U): U,
    }
    for left in VALUES:
        for right in VALUES:
            nodes = [fixed[left], fixed[right]]
            assert _run({"op": "all", "nodes": nodes}, request, "c", []) == expected_all[(left, right)], ("all", left, right)
            assert _run({"op": "any", "nodes": nodes}, request, "c", []) == expected_any[(left, right)], ("any", left, right)


def test_not_negates_true_and_false_and_leaves_unknown_alone():
    for inner, expected in ((["203.0.113.0/24"], F), (["198.51.100.0/24"], T), (["nonsense"], U)):
        assert _run_with({"op": "not", "node": {"op": "ip", "values": inner}}) == expected


def test_the_trace_omits_children_the_engine_never_walked():
    """ALL exits on the first FALSE. The rest must render as not-evaluated, never as FALSE."""
    trace = []
    node = {
        "op": "all",
        "nodes": [
            {"op": "ip", "values": ["198.51.100.0/24"]},  # FALSE, settles it
            {"op": "country", "values": ["FR"]},  # would be TRUE, never reached
        ],
    }
    assert _run(node, _req(), "condition", trace) == F
    walked = {entry["path"] for entry in trace}
    assert "condition.nodes[0]" in walked
    assert "condition.nodes[1]" not in walked, "a skipped child must not appear in the trace"


def test_unknown_never_short_circuits():
    """Exiting on UNKNOWN would turn a knowable FALSE into UNKNOWN — a silently disabled rule."""
    trace = []
    node = {
        "op": "all",
        "nodes": [
            {"op": "ip", "values": ["nonsense"]},  # UNKNOWN
            {"op": "ip", "values": ["198.51.100.0/24"]},  # FALSE — still settles the ALL
        ],
    }
    assert _run(node, _req(), "condition", trace) == F
    assert "condition.nodes[1]" in {entry["path"] for entry in trace}


# --- the leaves -----------------------------------------------------------------------


def test_a_private_address_has_no_asn_which_is_false_not_unknown():
    """Conflating the two would let "NOT in these ASNs" match local traffic."""
    local = _req(country="local", asn_number=None, asn_ok=True)
    assert _run_with({"op": "asn", "values": [64496]}, local) == F
    assert _run_with({"op": "not", "node": {"op": "asn", "values": [64496]}}, local) == T


def test_a_failed_lookup_is_unknown_not_false():
    blind = _req(country_ok=False, asn_ok=False)
    assert _run_with({"op": "country", "values": ["FR"]}, blind) == U
    assert _run_with({"op": "asn", "values": [64496]}, blind) == U


def test_one_unparseable_value_poisons_the_whole_ip_leaf():
    """ipmatcher.new() refuses the entire list, so the leaf degrades rather than skipping it."""
    node = {"op": "ip", "values": ["203.0.113.0/24", "not-an-address"]}
    assert _run_with(node) == U


def test_uri_matches_run_on_bytes_like_ngx_re():
    """PCRE without the u flag: \\w is ASCII and . counts bytes."""
    accented = _req(uri="/café")
    assert _run_with({"op": "uri", "match": "regex", "value": r"^/\w+$"}, accented) == F
    assert _run_with({"op": "uri", "match": "prefix", "value": "/caf"}, accented) == T
    assert _run_with({"op": "uri", "match": "exact", "value": "/café"}, accented) == T


def test_an_uncompilable_pattern_never_matches():
    assert _run_with({"op": "uri", "match": "regex", "value": "([unclosed"}) == U


# --- groups ---------------------------------------------------------------------------


def test_group_references_are_inlined_like_the_compiler_does():
    index = {"office": {"ip": ["203.0.113.0/24"], "country": [], "asn": []}}
    inlined = inline_groups({"op": "group", "kind": "ip", "group_id": "office"}, index)
    assert inlined == {"op": "ip", "values": ["203.0.113.0/24"]}
    assert _run_with(inlined) == T


def test_an_unusable_group_reference_is_unknown():
    assert _run_with(inline_groups({"op": "group", "kind": "ip", "group_id": "ghost"}, {})) == U


# --- the ladder -----------------------------------------------------------------------


def _rule(rule_id, *, enabled=True, values=("203.0.113.0/24",), threshold=None, action=None):
    return {
        "id": rule_id,
        "name": rule_id,
        "enabled": enabled,
        "condition": {"op": "ip", "values": list(values)},
        "threshold": threshold,
        "action": action or {"type": "block"},
    }


def _wf(workflow_id, *rules):
    return {"id": workflow_id, "name": workflow_id, "definition": {"rules": list(rules)}}


def test_the_first_match_wins_and_everything_below_is_unreached():
    ladder = prepare_ladder([_wf("wf1", _rule("r1"), _rule("r2"))], {})
    outcome, reported = evaluate(ladder, _req())
    assert outcome["type"] == Outcome.MATCH and outcome["rule_id"] == "r1"
    states = [rule["state"] for rule in reported[0]["rules"]]
    assert states == [STATE_MATCH, STATE_UNREACHED]


def test_a_closed_gate_does_not_win_and_evaluation_continues():
    """The threshold is a match gate, not an action: below it the rule loses outright."""
    gated = _rule("r1", threshold={"count": 10, "window": 60, "key": "ip"})
    ladder = prepare_ladder([_wf("wf1", gated, _rule("r2"))], {})
    outcome, reported = evaluate(ladder, _req(request_number=1))
    assert [rule["state"] for rule in reported[0]["rules"]] == [STATE_GATE_CLOSED, STATE_MATCH]
    assert outcome["rule_id"] == "r2"

    # request_number IS the runtime's count, so the gate opens strictly above the threshold.
    outcome, reported = evaluate(ladder, _req(request_number=11))
    assert reported[0]["rules"][0]["state"] == STATE_MATCH and outcome["rule_id"] == "r1"
    outcome, _ = evaluate(ladder, _req(request_number=10))
    assert outcome["rule_id"] == "r2", "count == threshold must still be closed"


def test_disabled_rules_are_skipped_and_an_empty_workflow_drops_out():
    """Missing the second shifts every reported position below it."""
    ladder = prepare_ladder([_wf("empty", _rule("r0", enabled=False)), _wf("wf1", _rule("r1"))], {})
    assert [workflow["id"] for workflow in ladder] == ["wf1"]

    ladder = prepare_ladder([_wf("wf1", _rule("r0", enabled=False), _rule("r1"))], {})
    _, reported = evaluate(ladder, _req())
    assert [rule["state"] for rule in reported[0]["rules"]] == [STATE_DISABLED, STATE_MATCH]


def test_a_workflow_later_in_the_order_is_reached_when_the_first_does_not_match():
    ladder = prepare_ladder([_wf("wf1", _rule("miss", values=("198.51.100.0/24",))), _wf("wf2", _rule("hit"))], {})
    outcome, reported = evaluate(ladder, _req())
    assert outcome["workflow_id"] == "wf2" and outcome["rule_id"] == "hit"
    assert reported[0]["rules"][0]["state"] == STATE_FALSE


def test_no_rule_matched_is_a_real_answer():
    ladder = prepare_ladder([_wf("wf1", _rule("r1", values=("198.51.100.0/24",)))], {})
    outcome, _ = evaluate(ladder, _req())
    assert outcome["type"] == Outcome.NO_MATCH


def test_an_unknown_rule_reports_unknown_and_cannot_match():
    ladder = prepare_ladder([_wf("wf1", _rule("r1", values=("nonsense",)))], {})
    outcome, reported = evaluate(ladder, _req())
    assert reported[0]["rules"][0]["state"] == STATE_UNKNOWN
    assert outcome["type"] == Outcome.NO_MATCH


def test_a_challenge_does_not_terminate_the_chain():
    """antibot takes over and the rest of the access phase still runs."""
    ladder = prepare_ladder([_wf("wf1", _rule("r1", action={"type": "challenge", "provider": "hcaptcha"}))], {})
    outcome, _ = evaluate(ladder, _req())
    assert outcome["terminates"] is False

    ladder = prepare_ladder([_wf("wf1", _rule("r1", action={"type": "block"}))], {})
    outcome, _ = evaluate(ladder, _req())
    assert outcome["terminates"] is True


def test_a_whitelisted_client_skips_every_rule():
    ladder = prepare_ladder([_wf("wf1", _rule("r1"))], {})
    outcome, reported = evaluate(ladder, _req(whitelisted=True))
    assert outcome["type"] == Outcome.WHITELISTED
    assert reported[0]["rules"][0]["state"] == STATE_UNREACHED


# --- the form mapping -----------------------------------------------------------------


def test_geo_states_map_onto_the_runtime_facts():
    resolved, error = request_from_input({"uri": "/", "geo": "resolved", "country": "fr", "asn": 64496})
    assert error is None and resolved["country"] == "FR" and resolved["country_ok"] and resolved["asn_ok"]

    local, error = request_from_input({"uri": "/", "geo": "local"})
    assert error is None and local["country"] == "local" and local["asn_ok"] and local["asn_number"] is None

    blind, error = request_from_input({"uri": "/", "geo": "unavailable"})
    assert error is None and not blind["country_ok"] and not blind["asn_ok"]

    # A global address whose lookup succeeded always has an ASN, so a blank one means the
    # lookup failed — UNKNOWN, not "no ASN".
    partial, error = request_from_input({"uri": "/", "geo": "resolved", "country": "FR", "asn": ""})
    assert error is None and partial["country_ok"] and not partial["asn_ok"]


def test_a_query_string_is_refused_because_uri_never_carries_one():
    _, error = request_from_input({"uri": "/search?q=1"})
    assert error and "query string" in error
    _, error = request_from_input({"uri": "login"})
    assert error and error.startswith("The URI must start with /")


def test_the_request_number_starts_at_one():
    # geo=local so the country check does not fire first and mask this one.
    _, error = request_from_input({"uri": "/", "geo": "local", "request_number": 0})
    assert error and "starts at 1" in error
    request, error = request_from_input({"uri": "/", "geo": "local"})
    assert error is None and request["request_number"] == 1

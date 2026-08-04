#!/usr/bin/env python3
"""Evaluate a workflow ladder against a synthetic request — the engine behind the rule tester.

This is a **second implementation** of what ``workflows.lua`` and ``eval.lua`` do on the
request path, and that is the whole risk: an evaluator that disagrees with the runtime is
worse than no evaluator, because it answers confidently. Every divergence here is a bug, and
``tests/unit/common/test_workflow_tester_parity.py`` runs a shared corpus through both this
module and the real Lua under plain ``lua`` to keep them honest.

Two properties are load-bearing and easy to lose:

* **Three-valued, and UNKNOWN is never folded into FALSE.** A rule whose tree resolves to
  UNKNOWN cannot match, but that is a different fact from "it did not match", and the UI has
  to be able to say so — an UNKNOWN rule is a security control that is silently off.
* **The trace records only what the engine actually walked.** ALL exits early on FALSE and
  ANY on TRUE, so the children after that point are never evaluated. They must render as
  "not evaluated", never as FALSE, or the tester teaches the operator a wrong mental model of
  their own policy.

Unlike its neighbour ``workflow_schema`` this module is not stdlib-only: it imports ``regex``
for PCRE-compatible URI matching. Only the API process imports it — the compiler and the
scheduler never do, and neither pins ``regex``.
"""

from functools import lru_cache
from ipaddress import ip_address, ip_network
from typing import Any, Dict, List, Optional, Tuple

import regex  # type: ignore

# Same encoding as eval.lua:9 — kept numeric so the parity corpus can compare them directly.
F, T, U = 0, 1, 2
NAMES = {F: "F", T: "T", U: "U"}
NEGATE = {F: T, T: F, U: U}

# PCRE answers a runaway match with its match limit, which ngx.re surfaces as an error and
# workflows.lua reads as UNKNOWN. The timeout is the semantic mirror of that limit — and,
# because this runs server-side on an operator-supplied pattern, it is also the ReDoS bound.
REGEX_TIMEOUT = 0.05


class Outcome:
    """Why the ladder stopped. ``MATCH`` carries the rule that won."""

    MATCH = "match"
    NO_MATCH = "no_match"
    WHITELISTED = "whitelisted"


# Per-rule verdicts. Six, not two: "matched", "would have matched but the gate is closed",
# "did not match", "could not be decided", "never reached" and "disabled" are six different
# things an operator needs to tell apart.
STATE_MATCH = "match"
STATE_GATE_CLOSED = "true_gate_closed"
STATE_FALSE = "false"
STATE_UNKNOWN = "unknown"
STATE_UNREACHED = "unreached"
STATE_DISABLED = "disabled"


@lru_cache(maxsize=256)
def _compile(pattern: str):
    """Compile to **bytes**, never str.

    ``ngx.re`` runs PCRE over bytes with no ``u`` flag, so ``.`` is one byte and ``\\d``,
    ``\\w``, ``\\s``, ``\\b`` are ASCII-only. A str pattern silently makes them Unicode-aware
    and disagrees with the runtime on any non-ASCII path.
    """
    return regex.compile(pattern.encode("utf-8"))


def _uri_leaf(node: Dict[str, Any], uri: str) -> int:
    value, match = node.get("value", ""), node.get("match")
    if match == "exact":
        return T if uri == value else F
    if match == "prefix":
        return T if uri.startswith(value) else F
    try:
        compiled = _compile(value)
    except regex.error:
        # A pattern the runtime cannot compile never matches; workflows.lua:146-150 probes it
        # once at load and degrades the leaf to always(UNKNOWN).
        return U
    try:
        return T if compiled.search(uri.encode("utf-8"), timeout=REGEX_TIMEOUT) else F
    except TimeoutError:
        return U


def _ip_leaf(values: List[str], remote_addr: str) -> int:
    try:
        address = ip_address(remote_addr)
    except ValueError:
        return U
    try:
        networks = [ip_network(value, strict=False) for value in values]
    except ValueError:
        # ipmatcher.new() refuses the WHOLE list when any single entry is unparseable, so the
        # leaf degrades rather than skipping the bad value: one bad group entry poisons it.
        return U
    return T if any(address.version == net.version and address in net for net in networks) else F


def _leaf(node: Dict[str, Any], request: Dict[str, Any]) -> int:
    op = node.get("op")
    if op == "uri":
        return _uri_leaf(node, request["uri"])
    if op == "method":
        return T if request["request_method"] in (node.get("values") or []) else F
    if op == "ip":
        return _ip_leaf(node.get("values") or [], request["remote_addr"])
    if op == "country":
        # country_ok separates "resolved to nothing" from "the database could not answer".
        if not request.get("country_ok"):
            return U
        return T if request.get("country") in (node.get("values") or []) else F
    if op == "asn":
        if not request.get("asn_ok"):
            return U
        # A private address resolves fine and simply has no ASN. That is a FACT, so FALSE —
        # conflating it with UNKNOWN would let "NOT in these ASNs" match local traffic.
        # workflows.lua:96-98.
        if request.get("asn_number") is None:
            return F
        return T if request["asn_number"] in (node.get("values") or []) else F
    # An unusable group reference and an unknown op both land here. Never matching is the only
    # safe reading of "I cannot evaluate this"; workflows.lua:180-195 agrees.
    return U


def _run(node: Dict[str, Any], request: Dict[str, Any], path: str, trace: List[Dict[str, Any]]) -> int:
    """Mirror of ``eval.lua:26-53`` with a trace sink."""
    op = node.get("op")

    if op == "not":
        value = NEGATE[_run(node["node"], request, f"{path}.node", trace)]
        trace.append({"path": path, "op": "not", "value": NAMES[value], "decided_by": f"{path}.node"})
        return value

    if op not in ("all", "any"):
        value = _leaf(node, request)
        trace.append({"path": path, "op": op, "value": NAMES[value], "decided_by": None})
        return value

    children = node.get("nodes") or []
    # The one value that lets this combinator exit early — and the only one that may.
    settles = F if op == "all" else T
    unknown = False
    for index, child in enumerate(children):
        child_path = f"{path}.nodes[{index}]"
        value = _run(child, request, child_path, trace)
        if value == settles:
            # Children after this one are never walked, so they never enter the trace: the UI
            # renders them "not evaluated", never FALSE.
            trace.append({"path": path, "op": op, "value": NAMES[settles], "decided_by": child_path})
            return settles
        if value == U:
            # Deliberately NOT an early exit. A later FALSE still settles an ALL and a later
            # TRUE still settles an ANY; exiting here would turn a knowable FALSE into an
            # UNKNOWN, and an UNKNOWN rule never matches — a silently disabled rule.
            unknown = True

    value = U if unknown else (T if op == "all" else F)
    trace.append({"path": path, "op": op, "value": NAMES[value], "decided_by": None})
    return value


def inline_groups(node: Dict[str, Any], group_index: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    """Rewrite group references into their kind leaf, exactly as ``compiler.py:121-124`` does.

    Done before evaluation so the evaluator is a pure function of ``(rules, request)`` and
    never has to know what a group is.
    """
    op = node.get("op")
    if op in ("all", "any"):
        return {"op": op, "nodes": [inline_groups(child, group_index) for child in (node.get("nodes") or [])]}
    if op == "not":
        return {"op": "not", "node": inline_groups(node["node"], group_index)}
    if op != "group":
        return node
    values = (group_index.get(str(node.get("group_id") or "")) or {}).get(str(node.get("kind") or ""))
    # The compiler refuses to ship an unusable reference, so reaching this is a hand-edited or
    # concurrently-deleted group: an op nothing answers, which _leaf reads as UNKNOWN.
    return {"op": node.get("kind"), "values": list(values)} if values else {"op": "unusable"}


def prepare_ladder(
    workflows: List[Dict[str, Any]],
    group_index: Dict[str, Dict[str, List[str]]],
) -> List[Dict[str, Any]]:
    """Drop what the compiler drops, so positions and verdicts line up with the artefact.

    Two eliminations, and missing the second silently shifts every reported position below it:
    disabled rules never reach the runtime (``compiler.py:86``), and a workflow left with no
    enabled rules is omitted from the service order entirely (``compiler.py:87-90``).
    """
    prepared = []
    for workflow in workflows:
        rules = []
        for rule in workflow.get("definition", {}).get("rules") or []:
            if not rule.get("enabled", True):
                rules.append({"id": rule.get("id"), "disabled": True})
                continue
            rules.append(
                {
                    "id": rule.get("id"),
                    "name": rule.get("name") or "",
                    "disabled": False,
                    "condition": inline_groups(rule.get("condition") or {}, group_index),
                    "threshold": rule.get("threshold"),
                    "action": rule.get("action") or {},
                }
            )
        if not any(not rule["disabled"] for rule in rules):
            continue
        prepared.append({"id": workflow.get("id"), "name": workflow.get("name") or "", "rules": rules})
    return prepared


def evaluate(ladder: List[Dict[str, Any]], request: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Walk the ladder the way ``workflows:access()`` does.

    Returns ``(outcome, workflows)``, where every rule carries its own verdict — including the
    ones evaluation never reached, so the UI can dim them rather than leave them blank.
    """
    if request.get("whitelisted"):
        # workflows:access() returns before any rule when the client is whitelisted.
        return ({"type": Outcome.WHITELISTED}, [_all_unreached(workflow) for workflow in ladder])

    outcome: Dict[str, Any] = {"type": Outcome.NO_MATCH}
    reported: List[Dict[str, Any]] = []
    stopped = False

    for position, workflow in enumerate(ladder):
        rules = []
        for index, rule in enumerate(workflow["rules"]):
            if stopped:
                rules.append(_unreached(rule))
                continue
            if rule["disabled"]:
                rules.append({"id": rule["id"], "index": index, "state": STATE_DISABLED, "value": None, "trace": [], "gate": None})
                continue

            trace: List[Dict[str, Any]] = []
            value = _run(rule["condition"], request, "condition", trace)
            gate = None

            if value != T:
                state = STATE_UNKNOWN if value == U else STATE_FALSE
            else:
                threshold = rule.get("threshold")
                if not threshold:
                    state = STATE_MATCH
                else:
                    # request_number IS the runtime's count: ratelimit.incr returns the value
                    # including the current request, which is what the operator's field means.
                    # So the gate is a pure comparison, not a guess about a live counter.
                    open_gate = request["request_number"] > threshold["count"]
                    gate = {
                        "request_number": request["request_number"],
                        "count": threshold["count"],
                        "window": threshold["window"],
                        "key": threshold.get("key", "ip"),
                        "open": open_gate,
                    }
                    # Under the threshold the rule loses and evaluation carries on — which is
                    # how "block over 10r/m, otherwise challenge" is two ordered rules.
                    state = STATE_MATCH if open_gate else STATE_GATE_CLOSED

            rules.append(
                {
                    "id": rule["id"],
                    "index": index,
                    "state": state,
                    "value": NAMES[value],
                    "decided_by": trace[-1]["decided_by"] if trace else None,
                    "trace": trace,
                    "gate": gate,
                }
            )

            if state == STATE_MATCH:
                stopped = True
                action = rule["action"]
                outcome = {
                    "type": Outcome.MATCH,
                    "workflow_id": workflow["id"],
                    "workflow_name": workflow["name"],
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "rule_index": index,
                    "action": action,
                    # A challenge hands the request to antibot and returns no status and no
                    # redirect, so the rest of the access chain still runs. Saying "blocked"
                    # there would be a lie. workflows.lua:284-289.
                    "terminates": action.get("type") != "challenge",
                }

        reported.append({"id": workflow["id"], "name": workflow["name"], "position": position, "rules": rules})

    return outcome, reported


def _unreached(rule: Dict[str, Any]) -> Dict[str, Any]:
    state = STATE_DISABLED if rule["disabled"] else STATE_UNREACHED
    return {"id": rule["id"], "index": None, "state": state, "value": None, "trace": [], "gate": None}


def _all_unreached(workflow: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": workflow["id"],
        "name": workflow["name"],
        "position": None,
        "rules": [_unreached(rule) for rule in workflow["rules"]],
    }


def request_from_input(raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Map the tester form onto the ``bw`` facts the runtime reads. Returns ``(request, error)``.

    GeoIP is asked, never derived from the address: ``utils.ip_is_global`` is a hand-written
    30-CIDR table in Lua that already disagrees with Python's ``is_global`` (on
    ``192.88.99.0/24``), so deriving it would invent a divergence the parity corpus
    structurally cannot catch — the corpus contract starts at ``bw``.
    """
    uri = str(raw.get("uri") or "")
    if not uri.startswith("/"):
        return None, "The URI must start with /"
    if "?" in uri:
        # $uri carries the normalised path only, so accepting a query string here would give a
        # confidently wrong answer. Same wording the rule validator uses.
        return None, "A URI predicate matches the path only, without a query string"

    geo = raw.get("geo") or "resolved"
    if geo not in ("resolved", "local", "unavailable"):
        return None, "Unknown GeoIP state"

    country = str(raw.get("country") or "").strip().upper()
    asn_raw = raw.get("asn")

    if geo == "unavailable":
        # No database: both leaves are UNKNOWN and can never match.
        country_ok, asn_ok, asn_number, country = False, False, None, ""
    elif geo == "local":
        # helpers.lua:418-424 — a private address resolves to the "local" country and no ASN.
        country_ok, asn_ok, asn_number, country = True, True, None, "local"
    else:
        if not country:
            return None, "A resolved lookup needs a country code"
        country_ok = True
        if asn_raw in (None, ""):
            # A global address whose lookup succeeded always has an ASN, so a blank one here
            # means the lookup failed — UNKNOWN, not "no ASN".
            asn_ok, asn_number = False, None
        else:
            try:
                asn_number = int(asn_raw)
            except (TypeError, ValueError):
                return None, "The ASN must be a number"
            asn_ok = True

    # Not `or 1`: 0 is falsy, so an explicit 0 would silently become 1 instead of being
    # refused — and 0 is exactly the off-by-one an operator reaches for first.
    raw_number = raw.get("request_number")
    try:
        request_number = 1 if raw_number in (None, "") else int(raw_number)
    except (TypeError, ValueError):
        return None, "The request number must be a number"
    if request_number < 1:
        return None, "The request number starts at 1"

    return (
        {
            "remote_addr": str(raw.get("remote_addr") or ""),
            "uri": uri,
            "request_method": str(raw.get("request_method") or "GET").upper(),
            "country": country,
            "country_ok": country_ok,
            "asn_number": asn_number,
            "asn_ok": asn_ok,
            "request_number": request_number,
            "whitelisted": bool(raw.get("whitelisted")),
        },
        None,
    )


def assumptions(request: Dict[str, Any], ladder: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """What the answer takes on faith. Shown next to the verdict, never buried."""
    facts = [{"code": "rate_counter", "detail": {"request_number": request["request_number"]}}]
    if not request.get("whitelisted"):
        facts.append({"code": "not_whitelisted"})
    if any(_has_regex(rule["condition"]) for workflow in ladder for rule in workflow["rules"] if not rule["disabled"]):
        # The budget is instance-wide over every workflow on the box and cannot be known from
        # one service's ladder, so it is declared rather than modelled.
        facts.append({"code": "regex_budget"})
    return facts


def _has_regex(node: Dict[str, Any]) -> bool:
    op = node.get("op")
    if op in ("all", "any"):
        return any(_has_regex(child) for child in (node.get("nodes") or []))
    if op == "not":
        return _has_regex(node["node"])
    return op == "uri" and node.get("match") == "regex"

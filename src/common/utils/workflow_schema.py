#!/usr/bin/env python3
"""Canonical schema, validation and human summary for security workflow definitions.

Single source of truth shared by the DB mixin (on write), the API router (on
validate-without-save), the compiler (before emitting the artefact) and the UI editor
(which renders the returned error paths inline). Pure and stdlib-only on purpose: no ORM,
no plugin imports, so the compiler and a unit test can call it without a database.

A definition is a list of ordered rules. A rule pairs a typed condition tree with an
optional rate threshold — a *match gate*, never an action — and exactly one terminal
action. Evaluation is three-valued (see ``eval.lua``): a rule matches only when its tree
resolves to TRUE **and**, when it carries a threshold, the counter is over the limit.
"""

from ipaddress import ip_network
from json import dumps
from re import compile as re_compile, error as re_error
from typing import Any, Dict, List, Optional, Set, Tuple

SCHEMA_VERSION = 1

# Depth is what bounds recursion in the Lua evaluator; the other caps bound the artefact
# and the per-request cost. Per-service aggregates are checked by the compiler, which is
# the only layer that sees every workflow attached to one service at once.
MAX_TREE_DEPTH = 5
MAX_RULES_PER_WORKFLOW = 50
MAX_PREDICATES_PER_RULE = 32
MAX_VALUES_PER_PREDICATE = 1000
MAX_ACTIVE_RULES_PER_SERVICE = 100
MAX_PREDICATES_PER_SERVICE = 500
# Half of OpenResty's default lua_regex_cache_max_entries (1024 per worker), which is shared
# with blacklist, greylist, dnsbl, antibot, limit and country. Overflow does not raise:
# ngx.re silently recompiles on every call, an instance-wide CPU cliff.
MAX_PCRE_PER_SERVICE = 50
MAX_ARTEFACT_BYTES = 1048576
MAX_RULE_NAME_LENGTH = 128

COMBINATOR_OPS = ("all", "any", "not")
LEAF_OPS = ("ip", "country", "asn", "method", "uri", "group")
URI_MATCHES = ("exact", "prefix", "regex")
# The subset of RESOURCE_KINDS_ENUM a group leaf may reference. Narrower than the enum on
# purpose: these three are plain set membership on a fact the request context already
# carries, with no regex and no I/O. The three left out are deferred rather than forgotten —
# ``rdns`` needs a DNS round-trip on the request path, and ``user_agent``/``uri`` groups are
# regex lists that would spend the shared PCRE budget invisibly. Accepting them here and
# failing to evaluate them at runtime would make a rule silently stop matching, which is the
# one failure mode a policy engine must never have.
GROUP_KINDS = ("ip", "country", "asn")

ACTION_TYPES = ("block", "redirect", "challenge")
# The Antibot modes a workflow may request. Source of truth is the USE_ANTIBOT regex in
# src/common/core/antibot/plugin.json ("no" excluded — it is the absence of a challenge);
# a unit test asserts the two never drift.
CHALLENGE_PROVIDERS = ("cookie", "javascript", "captcha", "recaptcha", "hcaptcha", "turnstile", "mcaptcha", "capjs")
# What a service must already have configured for a challenge provider to render. Lives here
# rather than in the compiler because both sides need it: the compiler refuses to ship a rule
# whose provider cannot render, and the DB layer refuses the *write* that would create one —
# without the write-time check, the compiler's refusal aborts the whole config push instead of
# telling the operator, in the form, that the service lacks the credentials.
# The secrets themselves are never read for their value, only for their presence.
PROVIDER_REQUIREMENTS = {
    "recaptcha": ("ANTIBOT_RECAPTCHA_SITEKEY", "ANTIBOT_RECAPTCHA_SECRET"),
    "hcaptcha": ("ANTIBOT_HCAPTCHA_SITEKEY", "ANTIBOT_HCAPTCHA_SECRET"),
    "turnstile": ("ANTIBOT_TURNSTILE_SITEKEY", "ANTIBOT_TURNSTILE_SECRET"),
    "mcaptcha": ("ANTIBOT_MCAPTCHA_SITEKEY", "ANTIBOT_MCAPTCHA_SECRET", "ANTIBOT_MCAPTCHA_URL"),
    "capjs": ("ANTIBOT_CAPJS_SITEKEY", "ANTIBOT_CAPJS_SECRET"),
}


def challenge_providers(definition: Dict[str, Any], *, enabled_only: bool = True) -> Set[str]:
    """Every challenge provider an enabled rule of this definition asks for."""
    providers = set()
    for rule in definition.get("rules") or []:
        if enabled_only and not rule.get("enabled", True):
            continue
        action = rule.get("action") or {}
        if action.get("type") == "challenge" and action.get("provider"):
            providers.add(str(action["provider"]))
    return providers
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
# A block rule normally returns the instance's configured deny status, which is why status
# is optional. 429 is the single documented override, for a rule whose whole purpose is to
# cap a rate; anything else belongs in the deny-status setting, not in a rule.
BLOCK_STATUSES = (429,)
# Only key supported in v1. The counter is scoped service + rule + client IP, deliberately
# not Limit's historical service/IP/URI key.
THRESHOLD_KEYS = ("ip",)
MAX_THRESHOLD_WINDOW = 86400

_COUNTRY_RX = re_compile(r"^[A-Z]{2}$")
_METHOD_RX = re_compile(r"^[A-Z]+$")
_REDIRECT_URL_RX = re_compile(r"^(https?://[^\s]+|/[^\s]*)$")


def canonical_json(obj: Any) -> str:
    """Stable serialisation: same logical definition, same bytes, on every engine.

    The artefact checksum and the golden-artefact tests depend on this, so it must never
    grow whitespace or a timestamp.
    """
    return dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class _Ctx:
    """Accumulator for one validation pass."""

    def __init__(self, group_index: Dict[str, Dict[str, List[str]]]):
        self.group_index = group_index
        self.errors: List[Dict[str, str]] = []
        self.predicates = 0
        self.pcre = 0
        self.group_refs: Set[Tuple[str, str]] = set()

    def fail(self, path: str, code: str, message: str) -> None:
        self.errors.append({"path": path, "code": code, "message": message})


def _sorted_unique(values: List[Any]) -> List[Any]:
    """Order-insensitive lists are sorted and deduped so the canonical form is stable."""
    return sorted(set(values), key=lambda item: (str(type(item)), item))


def _validate_ip_leaf(node: Dict[str, Any], path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    raw = node.get("values")
    if not isinstance(raw, list) or not raw:
        ctx.fail(path, "values_required", "An IP predicate needs at least one address or network")
        return None
    values = []
    for index, value in enumerate(raw):
        try:
            # strict=False so 203.0.113.7/24 is accepted and normalised to its network,
            # which is what an operator typing a host inside a subnet means.
            values.append(str(ip_network(str(value), strict=False)))
        except ValueError:
            ctx.fail(f"{path}.values[{index}]", "ip_invalid", f"{value!r} is not a valid IP address or CIDR network")
    return {"op": "ip", "values": _sorted_unique(values)} if values else None


def _validate_country_leaf(node: Dict[str, Any], path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    raw = node.get("values")
    if not isinstance(raw, list) or not raw:
        ctx.fail(path, "values_required", "A country predicate needs at least one country code")
        return None
    values = []
    for index, value in enumerate(raw):
        code = str(value).strip().upper()
        if not _COUNTRY_RX.match(code):
            ctx.fail(f"{path}.values[{index}]", "country_invalid", f"{value!r} is not an ISO 3166-1 alpha-2 country code")
            continue
        values.append(code)
    return {"op": "country", "values": _sorted_unique(values)} if values else None


def _validate_asn_leaf(node: Dict[str, Any], path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    raw = node.get("values")
    if not isinstance(raw, list) or not raw:
        ctx.fail(path, "values_required", "An ASN predicate needs at least one AS number")
        return None
    values = []
    for index, value in enumerate(raw):
        try:
            number = int(str(value).upper().removeprefix("AS"))
        except ValueError:
            ctx.fail(f"{path}.values[{index}]", "asn_invalid", f"{value!r} is not an AS number")
            continue
        if number < 1:
            ctx.fail(f"{path}.values[{index}]", "asn_invalid", "An AS number must be greater than zero")
            continue
        values.append(number)
    return {"op": "asn", "values": _sorted_unique(values)} if values else None


def _validate_method_leaf(node: Dict[str, Any], path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    raw = node.get("values")
    if not isinstance(raw, list) or not raw:
        ctx.fail(path, "values_required", "A method predicate needs at least one HTTP method")
        return None
    values = []
    for index, value in enumerate(raw):
        method = str(value).strip().upper()
        if not _METHOD_RX.match(method):
            ctx.fail(f"{path}.values[{index}]", "method_invalid", f"{value!r} is not an HTTP method")
            continue
        values.append(method)
    return {"op": "method", "values": _sorted_unique(values)} if values else None


def _validate_uri_leaf(node: Dict[str, Any], path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    match = str(node.get("match") or "").strip()
    value = str(node.get("value") or "").strip()
    if match not in URI_MATCHES:
        ctx.fail(f"{path}.match", "uri_match_invalid", f"URI match must be one of {', '.join(URI_MATCHES)}")
        return None
    if not value:
        ctx.fail(f"{path}.value", "uri_required", "A URI predicate needs a value")
        return None
    if "?" in value:
        # $uri carries the normalised path only, so a rule holding a query string could
        # never match. Refusing is kinder than silently never firing.
        ctx.fail(f"{path}.value", "uri_query_string", "A URI predicate matches the path only, without a query string")
        return None
    if match == "regex":
        try:
            re_compile(value)
        except re_error as exc:
            ctx.fail(f"{path}.value", "regex_invalid", f"Invalid regular expression: {exc}")
            return None
        ctx.pcre += 1
    elif not value.startswith("/"):
        ctx.fail(f"{path}.value", "uri_not_absolute", "An exact or prefix URI must start with /")
        return None
    return {"op": "uri", "match": match, "value": value}


def _validate_group_leaf(node: Dict[str, Any], path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    group_id = str(node.get("group_id") or "").strip()
    kind = str(node.get("kind") or "").strip()
    if not group_id:
        ctx.fail(f"{path}.group_id", "group_required", "A group predicate needs a resource group")
        return None
    if kind not in GROUP_KINDS:
        ctx.fail(f"{path}.kind", "group_kind_invalid", f"Group kind must be one of {', '.join(GROUP_KINDS)}")
        return None
    group = ctx.group_index.get(group_id)
    if group is None:
        # Never degrade a missing reference into an empty list: that turns a security
        # control into a rule which silently matches nothing.
        ctx.fail(f"{path}.group_id", "group_missing", f"Resource group {group_id} does not exist")
        return None
    if not group.get(kind):
        ctx.fail(f"{path}.kind", "group_kind_empty", f"Resource group {group_id} holds no {kind} entry")
        return None
    ctx.group_refs.add((group_id, kind))
    return {"op": "group", "group_id": group_id, "kind": kind}


_LEAF_VALIDATORS = {
    "ip": _validate_ip_leaf,
    "country": _validate_country_leaf,
    "asn": _validate_asn_leaf,
    "method": _validate_method_leaf,
    "uri": _validate_uri_leaf,
    "group": _validate_group_leaf,
}


def _validate_node(node: Any, path: str, depth: int, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if not isinstance(node, dict):
        ctx.fail(path, "node_invalid", "A condition node must be an object")
        return None
    if depth > MAX_TREE_DEPTH:
        ctx.fail(path, "depth_exceeded", f"A condition tree cannot nest deeper than {MAX_TREE_DEPTH} levels")
        return None

    op = str(node.get("op") or "").strip()
    if op in ("all", "any"):
        children = node.get("nodes")
        if not isinstance(children, list) or not children:
            # An empty ALL is vacuously true and an empty ANY vacuously false; both are
            # almost certainly an unfinished edit, so neither is accepted.
            ctx.fail(path, "group_empty", f"An {op.upper()} node needs at least one child")
            return None
        validated = [_validate_node(child, f"{path}.nodes[{index}]", depth + 1, ctx) for index, child in enumerate(children)]
        if any(child is None for child in validated):
            return None
        return {"op": op, "nodes": validated}
    if op == "not":
        # Exactly one child, enforced structurally by a singular key.
        child = _validate_node(node.get("node"), f"{path}.node", depth + 1, ctx)
        return {"op": "not", "node": child} if child else None
    if op in LEAF_OPS:
        ctx.predicates += 1
        raw_values = node.get("values")
        if isinstance(raw_values, list) and len(raw_values) > MAX_VALUES_PER_PREDICATE:
            ctx.fail(path, "values_too_many", f"A predicate cannot hold more than {MAX_VALUES_PER_PREDICATE} values")
            return None
        return _LEAF_VALIDATORS[op](node, path, ctx)

    ctx.fail(f"{path}.op", "op_invalid", f"Unknown condition {op!r}")
    return None


def _validate_threshold(raw: Any, path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        ctx.fail(path, "threshold_invalid", "A threshold must be an object or null")
        return None
    try:
        count = int(str(raw.get("count", "")))
        window = int(str(raw.get("window", "")))
    except (TypeError, ValueError):
        ctx.fail(path, "threshold_invalid", "A threshold needs a numeric count and window")
        return None
    if count < 1:
        ctx.fail(f"{path}.count", "threshold_count_invalid", "A threshold count must be at least 1")
        return None
    if window < 1 or window > MAX_THRESHOLD_WINDOW:
        ctx.fail(f"{path}.window", "threshold_window_invalid", f"A threshold window must be between 1 and {MAX_THRESHOLD_WINDOW} seconds")
        return None
    key = str(raw.get("key") or "ip").strip()
    if key not in THRESHOLD_KEYS:
        ctx.fail(f"{path}.key", "threshold_key_invalid", f"A threshold key must be one of {', '.join(THRESHOLD_KEYS)}")
        return None
    return {"count": count, "window": window, "key": key}


def _validate_action(raw: Any, path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        ctx.fail(path, "action_required", "A rule needs exactly one terminal action")
        return None
    action_type = str(raw.get("type") or "").strip()
    if action_type not in ACTION_TYPES:
        ctx.fail(f"{path}.type", "action_invalid", f"An action must be one of {', '.join(ACTION_TYPES)}")
        return None

    if action_type == "challenge":
        provider = str(raw.get("provider") or "").strip()
        if provider not in CHALLENGE_PROVIDERS:
            ctx.fail(f"{path}.provider", "provider_invalid", f"A challenge provider must be one of {', '.join(CHALLENGE_PROVIDERS)}")
            return None
        return {"type": "challenge", "provider": provider}

    if action_type == "redirect":
        url = str(raw.get("url") or "").strip()
        if not _REDIRECT_URL_RX.match(url):
            ctx.fail(f"{path}.url", "redirect_url_invalid", "A redirect target must be an http(s) URL or an absolute path")
            return None
        try:
            status = int(raw.get("status", 302))
        except (TypeError, ValueError):
            status = 0
        if status not in REDIRECT_STATUSES:
            ctx.fail(f"{path}.status", "redirect_status_invalid", f"A redirect status must be one of {', '.join(str(s) for s in REDIRECT_STATUSES)}")
            return None
        return {"type": "redirect", "url": url, "status": status}

    if "status" not in raw or raw["status"] is None:
        return {"type": "block"}  # runtime uses the instance's configured deny status
    try:
        status = int(raw["status"])
    except (TypeError, ValueError):
        status = 0
    if status not in BLOCK_STATUSES:
        ctx.fail(f"{path}.status", "block_status_invalid", f"A block status may only be {', '.join(str(s) for s in BLOCK_STATUSES)}, or left unset")
        return None
    return {"type": "block", "status": status}


def _validate_rule(raw: Any, path: str, ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        ctx.fail(path, "rule_invalid", "A rule must be an object")
        return None

    rule_id = str(raw.get("id") or "").strip()
    if not rule_id:
        # Ids are stable and never reused: metrics, counters and the compiled artefact all
        # key on them, so minting one belongs to whoever creates the rule, not here (this
        # module must stay deterministic).
        ctx.fail(f"{path}.id", "id_missing", "A rule needs a stable id")
        return None

    name = str(raw.get("name") or "").strip()
    if len(name) > MAX_RULE_NAME_LENGTH:
        ctx.fail(f"{path}.name", "name_too_long", f"A rule name cannot exceed {MAX_RULE_NAME_LENGTH} characters")
        return None

    before = ctx.predicates
    condition = _validate_node(raw.get("condition"), f"{path}.condition", 1, ctx)
    if condition is None:
        return None
    if ctx.predicates - before > MAX_PREDICATES_PER_RULE:
        ctx.fail(f"{path}.condition", "predicates_exceeded", f"A rule cannot hold more than {MAX_PREDICATES_PER_RULE} predicates")
        return None

    action = _validate_action(raw.get("action"), f"{path}.action", ctx)
    if action is None:
        return None
    threshold = _validate_threshold(raw.get("threshold"), f"{path}.threshold", ctx)
    if raw.get("threshold") is not None and threshold is None:
        return None

    return {
        "id": rule_id,
        "name": name,
        "enabled": bool(raw.get("enabled", True)),
        "condition": condition,
        "threshold": threshold,
        "action": action,
    }


def validate_definition(raw: Any, *, group_index: Dict[str, Dict[str, List[str]]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, str]]]:
    """Validate and canonicalise a workflow definition.

    Returns ``(canonical_definition, errors)``. ``errors`` entries carry ``path``, ``code``
    and ``message``; the path addresses the offending node (``rules[0].condition.nodes[1]``)
    so the editor can anchor the message inline. On any error the definition is ``None`` —
    a partially valid definition is never stored, because the compiler is fail-closed and
    would abort the whole config push later instead.

    ``group_index`` maps resource group **id** to ``{kind: [values]}``. Ids, never ``@name``
    aliases: a rename must not silently repoint a security rule.
    """
    ctx = _Ctx(group_index)
    if not isinstance(raw, dict):
        ctx.fail("", "definition_invalid", "A workflow definition must be an object")
        return None, ctx.errors

    version = raw.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        ctx.fail("schema_version", "schema_version_unsupported", f"Unsupported workflow schema version {version!r} (expected {SCHEMA_VERSION})")
        return None, ctx.errors

    rules = raw.get("rules", [])
    if not isinstance(rules, list):
        ctx.fail("rules", "rules_invalid", "Rules must be a list")
        return None, ctx.errors
    if len(rules) > MAX_RULES_PER_WORKFLOW:
        ctx.fail("rules", "rules_exceeded", f"A workflow cannot hold more than {MAX_RULES_PER_WORKFLOW} rules")
        return None, ctx.errors

    seen: Set[str] = set()
    validated = []
    for index, rule in enumerate(rules):
        result = _validate_rule(rule, f"rules[{index}]", ctx)
        if result is None:
            continue
        if result["id"] in seen:
            ctx.fail(f"rules[{index}].id", "id_duplicate", f"Rule id {result['id']} is used twice")
            continue
        seen.add(result["id"])
        validated.append(result)

    if ctx.errors:
        return None, ctx.errors
    # Rule order is semantic — first effective match wins — so it is preserved as authored.
    return {"schema_version": SCHEMA_VERSION, "rules": validated}, []


def collect_group_refs(definition: Dict[str, Any]) -> Set[Tuple[str, str]]:
    """Every ``(group_id, kind)`` a definition references, for the usage table."""
    refs: Set[Tuple[str, str]] = set()

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        op = node.get("op")
        if op in ("all", "any"):
            for child in node.get("nodes") or []:
                walk(child)
        elif op == "not":
            walk(node.get("node"))
        elif op == "group":
            refs.add((str(node.get("group_id")), str(node.get("kind"))))

    for rule in definition.get("rules") or []:
        walk(rule.get("condition"))
    return refs


def rule_stats(definition: Dict[str, Any], *, enabled_only: bool = True) -> Dict[str, int]:
    """Counts the compiler aggregates per service to enforce the runtime budgets."""
    stats = {"rules": 0, "predicates": 0, "pcre": 0}

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        op = node.get("op")
        if op in ("all", "any"):
            for child in node.get("nodes") or []:
                walk(child)
        elif op == "not":
            walk(node.get("node"))
        else:
            stats["predicates"] += 1
            if op == "uri" and node.get("match") == "regex":
                stats["pcre"] += 1

    for rule in definition.get("rules") or []:
        if enabled_only and not rule.get("enabled", True):
            continue
        stats["rules"] += 1
        walk(rule.get("condition"))
    return stats


def _summarize_node(node: Dict[str, Any]) -> str:
    op = node.get("op")
    if op in ("all", "any"):
        joiner = " and " if op == "all" else " or "
        parts = [_summarize_node(child) for child in node.get("nodes") or []]
        return parts[0] if len(parts) == 1 else "(" + joiner.join(parts) + ")"
    if op == "not":
        return f"not {_summarize_node(node.get('node') or {})}"
    if op == "uri":
        verbs = {"exact": "is", "prefix": "starts with", "regex": "matches"}
        return f"URI {verbs[node['match']]} {node['value']}"
    if op == "group":
        return f"{node['kind'].replace('_', ' ')} is in group {node['group_id']}"
    values = node.get("values") or []
    label = {"ip": "IP", "country": "country", "asn": "ASN", "method": "method"}[str(op)]
    rendered = ", ".join(str(value) for value in values)
    return f"{label} is {rendered}" if len(values) == 1 else f"{label} is one of {rendered}"


def summarize_rule(rule: Dict[str, Any]) -> str:
    """One-line English rendering of a rule, shown in the editor before saving.

    English only in v1; templating it from the i18n catalogue is a follow-up.
    """
    parts = [f"If {_summarize_node(rule['condition'])}"]
    threshold = rule.get("threshold")
    if threshold:
        parts.append(f"over {threshold['count']} requests per {threshold['window']}s per {threshold['key'].upper()}")
    action = rule["action"]
    if action["type"] == "challenge":
        parts.append(f"then show the {action['provider']} challenge")
    elif action["type"] == "redirect":
        parts.append(f"then redirect to {action['url']} ({action['status']})")
    else:
        parts.append(f"then block with {action['status']}" if action.get("status") else "then block")
    return ", ".join(parts)

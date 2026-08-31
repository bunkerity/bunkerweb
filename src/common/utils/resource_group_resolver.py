#!/usr/bin/env python3
"""Resolve ``@name`` resource-group references inside list settings.

A list setting may reference a resource group by token, e.g.
``WHITELIST_IP=@office 203.0.113.5``. Groups are the source of truth in the DB,
but the Lua request path and the plugin jobs only ever consume *flat* values.
This module expands the tokens into the group's entries **of the matching kind**
just before configuration is materialized for those consumers — the ``@name``
tokens stay untouched in the DB (so the UI keeps showing the reference and a
group edit re-propagates on the next generation).

It is deliberately dependency-light (no ORM import): callers hand it a ``db``
object exposing ``get_resource_groups()`` (the real shared Database, available
both in the config generator and in the worker). A group lookup error never
breaks config generation, but unresolved non-country references are removed so
they cannot poison a runtime list consumer.
"""

from re import compile as re_compile
from typing import Any, Dict, List, Optional, Set

from resource_validation import RESOURCE_GROUP_RESERVED_ALIASES  # type: ignore

# Base setting id -> resource kind. Only settings whose value is a user-curated
# list of resources appear here (NOT their ``*_URLS`` downloader variants).
# Keep in sync with the covered plugins (whitelist/blacklist/greylist/country/
# realip/dnsbl/antibot) and RESOURCE_KINDS_ENUM in src/common/db/model.py.
RESOURCE_LIST_SETTINGS: Dict[str, str] = {
    # whitelist
    "WHITELIST_IP": "ip",
    "WHITELIST_RDNS": "rdns",
    "WHITELIST_ASN": "asn",
    "WHITELIST_USER_AGENT": "user_agent",
    "WHITELIST_URI": "uri",
    "WHITELIST_COUNTRY": "country",
    # blacklist
    "BLACKLIST_IP": "ip",
    "BLACKLIST_RDNS": "rdns",
    "BLACKLIST_ASN": "asn",
    "BLACKLIST_USER_AGENT": "user_agent",
    "BLACKLIST_URI": "uri",
    "BLACKLIST_COUNTRY": "country",
    "BLACKLIST_IGNORE_IP": "ip",
    "BLACKLIST_IGNORE_RDNS": "rdns",
    "BLACKLIST_IGNORE_ASN": "asn",
    "BLACKLIST_IGNORE_USER_AGENT": "user_agent",
    "BLACKLIST_IGNORE_URI": "uri",
    # greylist
    "GREYLIST_IP": "ip",
    "GREYLIST_RDNS": "rdns",
    "GREYLIST_ASN": "asn",
    "GREYLIST_USER_AGENT": "user_agent",
    "GREYLIST_URI": "uri",
    # realip
    "REAL_IP_FROM": "ip",
    # dnsbl
    "DNSBL_IGNORE_IP": "ip",
    # antibot ignore lists
    "ANTIBOT_IGNORE_IP": "ip",
    "ANTIBOT_IGNORE_RDNS": "rdns",
    "ANTIBOT_IGNORE_ASN": "asn",
    "ANTIBOT_IGNORE_USER_AGENT": "user_agent",
    "ANTIBOT_IGNORE_URI": "uri",
    "ANTIBOT_IGNORE_COUNTRY": "country",
}

_GROUP_TOKEN_RX = re_compile(r"(?<!\S)@[A-Za-z0-9_-]+(?!\S)")

# Composite (AND) rule families. Unlike every other entry above, a rule setting has no single
# kind: the kind lives in each term's prefix, so these are resolved term by term.
RULE_SETTINGS = frozenset(("GREYLIST_RULE", "WHITELIST_RULE", "BLACKLIST_RULE"))

# Term kind -> resource kind. "ua" is the grammar's spelling, "user_agent" the resource kind's.
RULE_TERM_KINDS: Dict[str, str] = {
    "ip": "ip",
    "country": "country",
    "asn": "asn",
    "rdns": "rdns",
    "ua": "user_agent",
    "user_agent": "user_agent",
    "uri": "uri",
}

# Kinds whose value is a PCRE regex. A group expands to an alternation for these and to a
# comma-separated list for the others -- a comma is legal inside a quantifier like {1,3}, so
# splitting a regex on it would corrupt the pattern.
_RULE_REGEX_KINDS = frozenset(("ua", "user_agent", "uri"))

_RULE_SEPARATOR = " AND "
_RULE_TERM_RX = re_compile(r"^(NOT )?([A-Za-z_]+):(.+)$")


def is_rule_key(key: str) -> bool:
    """True for a ``<LIST>_RULE`` / ``<LIST>_RULE_<n>`` key, multisite prefix included."""
    for base in RULE_SETTINGS:
        if key == base or key.endswith("_" + base):
            return True
        head, _, suffix = key.rpartition("_")
        if suffix.isdigit() and (head == base or head.endswith("_" + base)):
            return True
    return False


def _split_rule_terms(value: str):
    """Yield ``(negation, kind, term_value)`` per term, or None if the rule does not parse.

    Deliberately the same split as ``src/bw/lua/bunkerweb/rules.lua``: on the literal
    separator, no escaping. A rule that does not parse here is left untouched -- the setting's
    own regex is what refuses it at save time, and silently rewriting a malformed rule would
    hide the refusal.
    """
    terms = []
    for segment in value.split(_RULE_SEPARATOR):
        match = _RULE_TERM_RX.match(segment)
        if not match:
            return None
        negation, kind, term_value = match.groups()
        if kind.lower() not in RULE_TERM_KINDS:
            return None
        terms.append((negation or "", kind, term_value))
    return terms


def group_tokens(setting_id: str, value: str) -> Set[str]:
    """``@token`` references held by a setting value.

    A flat list holds them as bare space-separated tokens; a composite rule holds them as a
    term value (``ip:@office``), which ``value.split()`` would never find. Callers that scan
    stored settings for references to a group must go through this, not through ``split()``.
    """
    if not isinstance(value, str) or "@" not in value:
        return set()
    if is_rule_key(setting_id):
        return {term_value for _negation, _kind, term_value in (_split_rule_terms(value) or ()) if term_value.startswith("@")}
    return {token for token in value.split() if token.startswith("@")}


def kind_for_key(key: str) -> Optional[str]:
    """Return the resource kind for a config key, accounting for the optional
    multisite ``<server>_`` prefix. ``None`` if the key is not a list setting."""
    for setting_id, kind in RESOURCE_LIST_SETTINGS.items():
        if key == setting_id or key.endswith("_" + setting_id):
            return kind
    return None


def value_for_validation(base_setting_id: str, value: str) -> str:
    """Strip @group tokens from a resource-list setting value before regex validation.

    A list setting's regex validates literal values; group references are validated
    separately (and may be unknown built-ins such as the country @EU token). Removing the
    @tokens leaves a value the setting's own ``^( *(ITEM) *)*$`` / ``.*`` regex still
    accepts. The stored value is unchanged — this only affects the validation check.
    """
    if not isinstance(value, str) or base_setting_id not in RESOURCE_LIST_SETTINGS:
        return value
    return _GROUP_TOKEN_RX.sub("", value)


def build_group_index(db: Any) -> Dict[str, Dict[str, List[str]]]:
    """Build ``{group_name: {kind: [values...]}}`` from the database."""
    index: Dict[str, Dict[str, List[str]]] = {}
    for group in db.get_resource_groups().values():
        by_kind: Dict[str, List[str]] = {}
        for entry in group.get("entries", []):
            by_kind.setdefault(entry["kind"], []).append(entry["value"])
        index[group["name"]] = by_kind
    return index


def _validate_group_token(token: str, kind: str, key: str, group_index: Dict[str, Dict[str, List[str]]]) -> Optional[str]:
    alias = token[1:]
    group = group_index.get(alias)
    if group is None:
        if kind == "country" and alias.upper() in RESOURCE_GROUP_RESERVED_ALIASES:
            return None
        return f"Unknown resource group @{alias} referenced by {key}"
    if not group.get(kind):
        return f"Resource group @{alias} has no {kind} entries required by {key}"
    return None


def validate_resource_group_refs(config: Dict[str, Any], group_index: Dict[str, Dict[str, List[str]]]) -> Optional[str]:
    """Return an error when a resource-list setting references an unusable group."""
    for key, value in config.items():
        if not isinstance(value, str) or "@" not in value:
            continue
        if is_rule_key(key):
            # A rule term carries its own kind, so each @token is validated against the kind
            # of the term it sits in. A rule that does not parse is left to the setting regex.
            for _negation, term_kind, term_value in _split_rule_terms(value) or ():
                if not term_value.startswith("@"):
                    continue
                error = _validate_group_token(term_value, RULE_TERM_KINDS[term_kind.lower()], key, group_index)
                if error:
                    return error
            continue
        kind = kind_for_key(key)
        if kind is None:
            continue

        for token in value.split():
            if not token.startswith("@"):
                continue
            error = _validate_group_token(token, kind, key, group_index)
            if error:
                return error
    return None


def _expand_rule(value: str, group_index: Dict[str, Dict[str, List[str]]]) -> Optional[str]:
    """Expand the ``@name`` tokens of one composite rule, or None to kill the rule.

    A term value that is a group token becomes the group's entries of that term's kind: a
    comma-separated list, or a ``(?:a|b)`` alternation for the regex kinds. Both mean OR
    *inside* one term, which is what a group is.

    An unresolvable reference kills the WHOLE rule rather than dropping the term. Dropping a
    term from an AND rule loosens it -- ``ip:@office AND ua:^Bot`` would become ``ua:^Bot``
    and whitelist every client running that agent. A flat list can afford to shrink; a
    conjunction cannot.

    So does an expansion that would not parse. Expansion is a third transform on top of the two
    validation gates, and neither of them sees its output: the setting regex ran on the rule
    *before* expansion, and a group entry is validated against its own kind's regex, which knows
    nothing about the rule separator. A group entry holding " and " in any casing would therefore
    produce a stored rule ``rules.parse`` refuses at load time, i.e. a rule that is silently gone
    with one error-log line behind it.
    """
    terms = _split_rule_terms(value)
    if terms is None:
        return value
    out = []
    for negation, kind, term_value in terms:
        if term_value.startswith("@"):
            resource_kind = RULE_TERM_KINDS[kind.lower()]
            alias = term_value[1:]
            group = group_index.get(alias)
            if group is None and resource_kind == "country" and alias.upper() in RESOURCE_GROUP_RESERVED_ALIASES:
                # Legacy built-in country alias whose seeded group is absent: keep it, the
                # country plugin expands @EU and friends itself.
                out.append(f"{negation}{kind}:{term_value}")
                continue
            entries = [] if group is None else group.get(resource_kind, [])
            if not entries:
                return None
            if kind.lower() in _RULE_REGEX_KINDS:
                term_value = "(?:" + "|".join(entries) + ")"
            else:
                term_value = ",".join(entries)
            # An expanded rule must still parse. ``rules.parse`` refuses any term whose value
            # holds " and " in any casing -- that is the separator, and there is no escaping
            # syntax -- so a group entry carrying one would produce a rule the runtime drops with
            # only an error-log line to show for it. Neither gate sees this: the setting regex
            # validated the rule *before* expansion, and the group entry's own kind regex never
            # looks for the rule separator. Kill the rule instead, the same fail-closed answer an
            # unresolvable reference gets -- dropping just the term would widen the conjunction.
            # Lowercased and padded on the right only, so a trailing " and" is caught while a
            # value merely *starting* with "and" is not -- byte for byte what ``rules.parse``
            # does with `value:lower() .. " "`.
            if _RULE_SEPARATOR.lower() in (term_value + " ").lower():
                return None
        out.append(f"{negation}{kind}:{term_value}")
    return _RULE_SEPARATOR.join(out)


def expand_resource_group_refs(config: Dict[str, Any], group_index: Dict[str, Dict[str, List[str]]], logger: Any = None) -> Dict[str, Any]:
    """Return a copy of ``config`` with ``@name`` tokens in list settings expanded.

    Tokens are replaced by the referenced group's entries of the setting's kind;
    literal values are kept; the result is de-duplicated preserving order. An
    unknown group (or a group with no entry of that kind) contributes nothing.
    Values without an ``@`` are left untouched (fast path).
    """
    out = config.copy()
    for key, value in config.items():
        if not isinstance(value, str) or "@" not in value:
            continue
        if is_rule_key(key):
            expanded = _expand_rule(value, group_index)
            if expanded is None:
                if logger is not None:
                    logger.warning(f"{key} references a resource group that does not expand into a usable rule, rule dropped: {value}")
                expanded = ""
            out[key] = expanded
            continue
        kind = kind_for_key(key)
        if kind is None:
            continue

        resolved: List[str] = []
        seen: set = set()
        for token in value.split():
            if token.startswith("@"):
                alias = token[1:]
                group = group_index.get(alias)
                if group is None and kind == "country" and alias.upper() in RESOURCE_GROUP_RESERVED_ALIASES:
                    # Keep legacy built-in country aliases when their seeded group is absent.
                    if token not in seen:
                        seen.add(token)
                        resolved.append(token)
                    continue
                # Unknown and wrong-kind references are invalid legacy values. Drop them
                # defensively instead of feeding them to Lua list consumers.
                if group is None:
                    continue
                for entry_value in group.get(kind, []):
                    if entry_value not in seen:
                        seen.add(entry_value)
                        resolved.append(entry_value)
            elif token not in seen:
                seen.add(token)
                resolved.append(token)

        out[key] = " ".join(resolved)

    return out


def expand_config_groups(config: Dict[str, Any], db: Any, logger: Any = None) -> Dict[str, Any]:
    """Convenience wrapper: build the index from ``db`` and expand ``config``.

    If groups cannot be read, unresolved references are removed defensively while
    legacy built-in country aliases are preserved.
    """
    if db is None:
        return expand_resource_group_refs(config, {}, logger)
    try:
        group_index = build_group_index(db)
    except Exception as exc:  # noqa: BLE001 - never break config generation over groups
        if logger is not None:
            logger.warning(f"Could not expand resource group references: {exc}")
        return expand_resource_group_refs(config, {}, logger)
    return expand_resource_group_refs(config, group_index, logger)

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
from typing import Any, Dict, List, Optional

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


def validate_resource_group_refs(config: Dict[str, Any], group_index: Dict[str, Dict[str, List[str]]]) -> Optional[str]:
    """Return an error when a resource-list setting references an unusable group."""
    for key, value in config.items():
        if not isinstance(value, str) or "@" not in value:
            continue
        kind = kind_for_key(key)
        if kind is None:
            continue

        for token in value.split():
            if not token.startswith("@"):
                continue
            alias = token[1:]
            group = group_index.get(alias)
            if group is None:
                if kind == "country" and alias.upper() in RESOURCE_GROUP_RESERVED_ALIASES:
                    continue
                return f"Unknown resource group @{alias} referenced by {key}"
            if not group.get(kind):
                return f"Resource group @{alias} has no {kind} entries required by {key}"
    return None


def expand_resource_group_refs(config: Dict[str, Any], group_index: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
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
        return expand_resource_group_refs(config, {})
    try:
        group_index = build_group_index(db)
    except Exception as exc:  # noqa: BLE001 - never break config generation over groups
        if logger is not None:
            logger.warning(f"Could not expand resource group references: {exc}")
        return expand_resource_group_refs(config, {})
    return expand_resource_group_refs(config, group_index)

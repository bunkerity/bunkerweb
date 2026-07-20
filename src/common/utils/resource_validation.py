#!/usr/bin/env python3
"""Per-kind validation/normalization for resource-group entries.

A *resource group* is a named, reusable collection of security primitives
(see the Resource Groups section of the 1.7 roadmap). Each entry is typed by a
``kind`` and carries a single ``value``. This module is the one place that
knows how to validate and normalize a value for a given kind, shared by the
DB layer (entry validator) and any caller that needs the same rules.

Kinds mirror the dimensions already consumed by the whitelist/blacklist/
greylist/country/realip plugins. The rules intentionally stay close to the
``check_line`` logic in the ``*-download.py`` jobs (IP via ``ipaddress``,
digits-only ASN with the ``AS`` prefix stripped, space-free lowercased rDNS)
— ``user_agent`` and ``uri`` are free-form PCRE patterns so they are only
checked for non-emptiness, and they are stored verbatim (no ``\\b`` wrapping,
which is a request-time matching concern, not a storage one).
"""

from ipaddress import ip_address, ip_network
from re import compile as re_compile
from typing import Optional, Tuple

# Canonical kind set — keep in sync with RESOURCE_KINDS_ENUM in src/common/db/model.py.
RESOURCE_KINDS: Tuple[str, ...] = ("ip", "country", "asn", "rdns", "user_agent", "uri")
RESOURCE_GROUP_MAX_ENTRIES = 5000
RESOURCE_GROUP_MAX_VALUE_LENGTH = 8192
RESOURCE_GROUP_MAX_COMMENT_LENGTH = 1000
RESOURCE_GROUP_MAX_DESCRIPTION_LENGTH = 4000

# Resource-group names are embedded in settings as ``@alias`` tokens. Keep the
# grammar aligned with the resolver and the UI so every persisted alias can be
# expanded unambiguously.
RESOURCE_GROUP_ALIAS_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
RESOURCE_GROUP_RESERVED_ALIASES = frozenset(
    {
        "ASEAN",
        "BENELUX",
        "DACH",
        "EEA",
        "EU",
        "FIVE_EYES",
        "G7",
        "GCC",
        "LATAM",
        "NORDICS",
        "SCHENGEN",
        "USMCA",
    }
)

_RESOURCE_GROUP_ALIAS_RX = re_compile(RESOURCE_GROUP_ALIAS_PATTERN)

_COUNTRY_RX = re_compile(r"^[A-Za-z]{2}$")
_ASN_RX = re_compile(r"^\d+$")
_RDNS_RX = re_compile(r"^[^ ]+$")


def validate_resource_group_alias(value: str, *, allow_reserved: bool = False) -> Optional[str]:
    """Return an error for an invalid user-facing ``@alias``, otherwise ``None``."""
    if not _RESOURCE_GROUP_ALIAS_RX.fullmatch(value):
        return "must contain 1 to 64 letters, digits, underscores, or dashes"
    if not allow_reserved and value.upper() in RESOURCE_GROUP_RESERVED_ALIASES:
        return "is reserved by BunkerWeb"
    return None


def validate_resource_value(kind: str, value: str) -> Tuple[bool, str]:
    """Validate ``value`` for ``kind`` and return ``(ok, normalized_value)``.

    On failure returns ``(False, "")``. The normalized value is what should be
    persisted (e.g. uppercased country code, ``AS``-stripped ASN, lowercased
    rDNS suffix); IP / user_agent / uri are returned stripped but otherwise
    unchanged.
    """
    kind = kind.strip().lower()
    value = value.strip()
    if not value:
        return False, ""
    # All consumers split list settings on whitespace. Requiring one atomic
    # token per entry prevents a pattern such as ``Mozilla Firefox`` from
    # silently becoming two broader runtime patterns; regexes can use ``\s``.
    if any(character.isspace() for character in value):
        return False, ""

    if kind == "ip":
        try:
            if "/" in value:
                ip_network(value, strict=False)
            else:
                ip_address(value)
        except ValueError:
            return False, ""
        return True, value

    if kind == "country":
        if _COUNTRY_RX.match(value):
            return True, value.upper()
        return False, ""

    if kind == "asn":
        candidate = value[2:] if value[:2].lower() == "as" else value
        if _ASN_RX.match(candidate):
            return True, candidate
        return False, ""

    if kind == "rdns":
        if _RDNS_RX.match(value):
            return True, value.lower()
        return False, ""

    if kind in ("user_agent", "uri"):
        # Free-form, whitespace-free PCRE patterns.
        return True, value

    return False, ""

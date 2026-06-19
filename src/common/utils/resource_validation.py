#!/usr/bin/env python3
"""Per-kind validation/normalization for resource-group entries.

A *resource group* is a named, reusable collection of security primitives
(see the "Groupes de ressources" 1.7 chantier). Each entry is typed by a
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
from typing import Tuple

# Canonical kind set — keep in sync with RESOURCE_KINDS_ENUM in src/common/db/model.py.
RESOURCE_KINDS: Tuple[str, ...] = ("ip", "country", "asn", "rdns", "user_agent", "uri")

_COUNTRY_RX = re_compile(r"^[A-Za-z]{2}$")
_ASN_RX = re_compile(r"^\d+$")
_RDNS_RX = re_compile(r"^[^ ]+$")


def validate_resource_value(kind: str, value: str) -> Tuple[bool, str]:
    """Validate ``value`` for ``kind`` and return ``(ok, normalized_value)``.

    On failure returns ``(False, "")``. The normalized value is what should be
    persisted (e.g. uppercased country code, ``AS``-stripped ASN, lowercased
    rDNS suffix); IP / user_agent / uri are returned stripped but otherwise
    unchanged.
    """
    kind = (kind or "").strip().lower()
    value = (value or "").strip()
    if not value:
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
        # Free-form PCRE patterns — stored verbatim, only required to be non-empty.
        return True, value

    return False, ""

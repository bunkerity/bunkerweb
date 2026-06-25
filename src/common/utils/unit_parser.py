"""Shared validator + canonicalizer for the ``size`` and ``duration`` setting types.

These setting values feed straight into NGINX directives, so the canonical output
must stay valid NGINX syntax. The parser accepts the full NGINX grammar plus common
human variants, and emits a single canonical form.

``duration`` -> NGINX ``ngx_parse_time``:
    units ``ms s m h d w M y``, compound (e.g. ``1h30m``), bare integer = seconds.
    Single-letter units are case-SENSITIVE: ``m`` is minutes, ``M`` is months,
    ``ms`` is milliseconds. Word aliases (``min``, ``month`` ...) are case-insensitive.
    (The previous per-plugin regex ``^\\d+(ms?|[shdwMy])?$`` only allowed a single
    unit group, so it rejected NGINX-valid compound forms like ``1h30m`` — this is a
    capability upgrade, not just tolerance.)
``size`` -> NGINX ``ngx_parse_size``:
    units ``k m g`` (case-insensitive), bare integer = bytes. No compound, no fraction.

The empty string is NOT accepted: the prior unit regexes required digits, and empty
defaults bypass value validation, so rejecting empty user input preserves behaviour.
Canonicalization is idempotent — ``normalize_unit(k, normalize_unit(k, v)) ==
normalize_unit(k, v)`` for every valid ``v``.
"""

from re import compile as re_compile
from typing import Optional

# --- duration -------------------------------------------------------------------

# Canonical units, matched case-SENSITIVELY so that ``m`` (minutes) and ``M`` (months)
# never collapse into one another.
_DURATION_CANONICAL_UNITS = frozenset(("ms", "s", "m", "h", "d", "w", "M", "y"))

# Multi-character / word aliases -> canonical unit, matched case-INSENSITIVELY.
_DURATION_WORD_ALIASES = {
    "msec": "ms",
    "msecs": "ms",
    "millisecond": "ms",
    "milliseconds": "ms",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "min": "m",
    "mins": "m",
    "minute": "m",
    "minutes": "m",
    "hr": "h",
    "hrs": "h",
    "hour": "h",
    "hours": "h",
    "day": "d",
    "days": "d",
    "week": "w",
    "weeks": "w",
    "mo": "M",
    "month": "M",
    "months": "M",
    "yr": "y",
    "yrs": "y",
    "year": "y",
    "years": "y",
}

# A ``<number><unit>`` group, tolerating whitespace around the unit (so ``30 s`` and
# ``1h 30m`` work) but NOT inside a unit word (so ``30 sec onds`` stays invalid).
_DURATION_TOKEN_RX = re_compile(r"(\d+)\s*([A-Za-z]+)\s*")

# Magnitude rank per canonical unit. NGINX (ngx_parse_time) requires the units of a
# compound duration to appear in STRICTLY DECREASING magnitude with no repeats —
# ``1h30m`` is valid but ``30m1h``, ``1h1h`` and ``1h1d`` are rejected. We enforce the
# same so a value that passes here can never break an NGINX reload.
_DURATION_UNIT_RANK = {"ms": 0, "s": 1, "m": 2, "h": 3, "d": 4, "w": 5, "M": 6, "y": 7}

# --- size -----------------------------------------------------------------------

_SIZE_ALIASES = {
    "k": "k",
    "kb": "k",
    "kib": "k",
    "m": "m",
    "mb": "m",
    "mib": "m",
    "g": "g",
    "gb": "g",
    "gib": "g",
}
_SIZE_RX = re_compile(r"^(\d+)\s*([A-Za-z]+)$")


def _resolve_duration_unit(unit: str) -> Optional[str]:
    # Case-sensitive canonical units first so ``m`` (minutes) != ``M`` (months).
    if unit in _DURATION_CANONICAL_UNITS:
        return unit
    return _DURATION_WORD_ALIASES.get(unit.lower())


def _canonicalize_duration(value: str) -> Optional[str]:
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.isdigit():
        return stripped  # bare integer = seconds
    parts = []
    pos = 0
    prev_rank = None
    for match in _DURATION_TOKEN_RX.finditer(stripped):
        if match.start() != pos:
            return None  # gap / leftover (fractional, stray chars, split word)
        unit = _resolve_duration_unit(match.group(2))
        if unit is None:
            return None
        rank = _DURATION_UNIT_RANK[unit]
        if prev_rank is not None and rank >= prev_rank:
            return None  # units must strictly decrease in magnitude (no repeats), like NGINX
        prev_rank = rank
        parts.append(match.group(1) + unit)
        pos = match.end()
    if pos != len(stripped) or not parts:
        return None
    return "".join(parts)


def _canonicalize_size(value: str) -> Optional[str]:
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.isdigit():
        return stripped  # bare integer = bytes
    match = _SIZE_RX.match(stripped)
    if not match:
        return None  # no compound, no fraction
    unit = _SIZE_ALIASES.get(match.group(2).lower())
    if unit is None:
        return None
    return match.group(1) + unit


_CANONICALIZERS = {"duration": _canonicalize_duration, "size": _canonicalize_size}


def normalize_unit(kind: str, value: str) -> Optional[str]:
    """Return the canonical NGINX form of ``value`` for ``kind`` (``"size"`` or
    ``"duration"``), or ``None`` if ``value`` is not a valid value of that kind."""
    if not isinstance(value, str):
        return None
    canonicalizer = _CANONICALIZERS.get(kind)
    if canonicalizer is None:
        return None
    return canonicalizer(value)

"""unit_parser — shared `size`/`duration` validation + canonicalization (Group B / B2).

Pure helpers, no DB/app; ``unit_parser`` is on the path via the root conftest
(``src/common/utils``). Runs once (not engine-parametrized).

These encode the NGINX grammars the values must stay valid against:
- duration -> ngx_parse_time: units ms s m h d w M y, compound, bare int = seconds.
  Single letters are case-SENSITIVE (m=minutes, M=months); word aliases are not.
- size -> ngx_parse_size: units k m g (case-insensitive), bare int = bytes, no
  compound, no fraction.
Empty string is NOT valid (matches the prior regex which required digits).
Canonicalization is idempotent.
"""

import pytest

from unit_parser import normalize_unit  # type: ignore


class TestDurationValid:
    @pytest.mark.parametrize(
        "raw,canon",
        [
            ("30s", "30s"),
            ("15s", "15s"),
            ("0", "0"),  # bare int = seconds
            ("60", "60"),
            ("500ms", "500ms"),
            ("90m", "90m"),  # minutes, NOT recomputed to 1h30m
            ("2h", "2h"),
            ("7d", "7d"),
            ("1w", "1w"),
            ("6M", "6M"),  # months (capital M preserved)
            ("1y", "1y"),
            # compound (rejected by the old single-group regex — capability upgrade)
            ("1h30m", "1h30m"),
            ("1d12h", "1d12h"),
            ("1y6M", "1y6M"),
            ("1h30m15s", "1h30m15s"),
        ],
    )
    def test_canonical_passthrough(self, raw, canon):
        assert normalize_unit("duration", raw) == canon


class TestDurationHumanAliases:
    @pytest.mark.parametrize(
        "raw,canon",
        [
            ("30 s", "30s"),  # whitespace stripped
            ("1h 30m", "1h30m"),
            ("30sec", "30s"),
            ("30secs", "30s"),
            ("30seconds", "30s"),
            ("5min", "5m"),  # minutes
            ("5minutes", "5m"),
            ("2hr", "2h"),
            ("2hours", "2h"),
            ("3day", "3d"),
            ("3days", "3d"),
            ("2week", "2w"),
            ("6month", "6M"),  # months -> capital M
            ("6months", "6M"),
            ("1year", "1y"),
            ("30SEC", "30s"),  # case-insensitive word alias
            ("6MONTH", "6M"),
            ("5MIN", "5m"),
        ],
    )
    def test_alias_canonicalized(self, raw, canon):
        assert normalize_unit("duration", raw) == canon

    def test_minute_vs_month_letter_is_case_sensitive(self):
        assert normalize_unit("duration", "5m") == "5m"  # minutes
        assert normalize_unit("duration", "5M") == "5M"  # months
        # word forms disambiguate regardless of case
        assert normalize_unit("duration", "5minute") == "5m"
        assert normalize_unit("duration", "5Month") == "5M"


class TestDurationInvalid:
    @pytest.mark.parametrize("raw", ["", "   ", "1.5h", "30x", "abc", "h30", "30s30", "1,5h", "-5s", "30 sec onds"])
    def test_rejected(self, raw):
        assert normalize_unit("duration", raw) is None


class TestDurationUnitOrder:
    """NGINX requires compound units in strictly-decreasing magnitude, no repeats.
    A value that violates that must be rejected here so it can never reach NGINX."""

    @pytest.mark.parametrize("raw,canon", [("1h30m", "1h30m"), ("1d12h", "1d12h"), ("1y6M", "1y6M"), ("1y6M3d12h30m15s500ms", "1y6M3d12h30m15s500ms")])
    def test_decreasing_order_accepted(self, raw, canon):
        assert normalize_unit("duration", raw) == canon

    @pytest.mark.parametrize("raw", ["30m1h", "1h1h", "1h1d", "1m1m1m", "30h30h", "1s1h", "500ms1s30m1h"])
    def test_increasing_or_repeated_units_rejected(self, raw):
        # NGINX ngx_parse_time rejects these; our parser must too.
        assert normalize_unit("duration", raw) is None


class TestSizeValid:
    @pytest.mark.parametrize(
        "raw,canon",
        [
            ("64m", "64m"),
            ("64M", "64m"),  # case-insensitive -> lowercase
            ("16k", "16k"),
            ("16K", "16k"),
            ("2g", "2g"),
            ("2G", "2g"),
            ("0", "0"),
            ("131072", "131072"),  # bare int = bytes
            ("64 m", "64m"),  # whitespace stripped
            ("1kb", "1k"),
            ("1KB", "1k"),
            ("1mb", "1m"),
            ("1gb", "1g"),
            ("1kib", "1k"),
        ],
    )
    def test_canonical(self, raw, canon):
        assert normalize_unit("size", raw) == canon


class TestSizeInvalid:
    @pytest.mark.parametrize("raw", ["", "  ", "1.5g", "64m32k", "64x", "k64", "m", "abc", "-5m"])
    def test_rejected(self, raw):
        assert normalize_unit("size", raw) is None


class TestIdempotence:
    @pytest.mark.parametrize("kind,raw", [("duration", "30sec"), ("duration", "1h 30m"), ("duration", "6month"), ("size", "64 M"), ("size", "1KB")])
    def test_canonicalize_twice_equals_once(self, kind, raw):
        once = normalize_unit(kind, raw)
        assert once is not None
        assert normalize_unit(kind, once) == once


class TestUnknownKind:
    def test_unknown_kind_returns_none(self):
        assert normalize_unit("text", "30s") is None

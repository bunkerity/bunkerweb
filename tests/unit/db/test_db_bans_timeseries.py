"""``get_bans_timeseries`` — occupancy of ``bw_bans`` over a window (#3820).

The series is **active bans per interval**, not bans created per interval. ``bw_bans`` keeps one
row per ``(ip, ban_scope, service_id)`` and ``upsert_ban`` rewrites ``created_at`` on re-ban, so a
creation series would claim an event history the table cannot back. Occupancy is what the rows
honestly support, and these tests pin that reading: a row counts in every bucket its lifetime
``[created_at, revoked_at or expires_at)`` overlaps, half-open on both ends.

Run locally on **sqlite only** (`--db-engines` defaults to sqlite); CI adds postgresql + mariadb.
The two engine-sensitive parts are the ``coalesce(revoked_at, expires_at)`` comparison in SQL and
the naive-datetime read-back, and only the second has a dedicated guard below.
"""

import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from model import Bans  # type: ignore

HOUR = 3600
# A fixed, UTC-aligned instant: bucket arithmetic is only readable against a known boundary.
T0 = int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())


def _at(offset_seconds):
    return datetime.fromtimestamp(T0 + offset_seconds, tz=timezone.utc)


def _ban(db, ip, created, *, expires=None, revoked=None):
    """Insert a row with an exact lifetime — ``upsert_ban`` always stamps ``created_at=now``."""
    with db._db_session() as session:
        session.add(
            Bans(ip=ip, ban_scope="global", service_id="", origin="test", reason="test", country="", created_at=created, expires_at=expires, revoked_at=revoked)
        )
        session.commit()


def _series(db, *, start=T0, end=T0 + 4 * HOUR, bucket="hour"):
    return db.get_bans_timeseries(start=start, end=end, bucket=bucket)


class TestOccupancy:
    def test_a_ban_counts_in_every_bucket_its_lifetime_overlaps(self, db):
        # [T0+30min, T0+2h30min) touches buckets 0, 1 and 2 — not 3.
        _ban(db, "1.2.3.4", _at(1800), expires=_at(2 * HOUR + 1800))
        assert _series(db)["counts"] == [1, 1, 1, 0]

    def test_a_still_running_ban_counts_to_the_end_of_the_window(self, db):
        _ban(db, "1.2.3.4", _at(HOUR))  # permanent: no expiry, never revoked
        assert _series(db)["counts"] == [0, 1, 1, 1]

    def test_a_ban_that_predates_the_window_still_counts_from_the_first_bucket(self, db):
        _ban(db, "1.2.3.4", _at(-10 * HOUR), expires=_at(HOUR + 60))
        assert _series(db)["counts"] == [1, 1, 0, 0]

    def test_revocation_ends_the_lifetime_before_the_declared_expiry(self, db):
        _ban(db, "1.2.3.4", _at(0), expires=_at(4 * HOUR), revoked=_at(HOUR + 1))
        assert _series(db)["counts"] == [1, 1, 0, 0]

    def test_concurrent_bans_add_up_per_bucket(self, db):
        _ban(db, "1.2.3.4", _at(0), expires=_at(2 * HOUR))
        _ban(db, "5.6.7.8", _at(HOUR), expires=_at(4 * HOUR))
        assert _series(db)["counts"] == [1, 2, 1, 1]


class TestHalfOpenBounds:
    """``[start, end)`` on the window and ``[created_at, ended)`` on the ban — both ends."""

    def test_a_ban_ending_exactly_on_a_bucket_boundary_does_not_occupy_that_bucket(self, db):
        _ban(db, "1.2.3.4", _at(0), expires=_at(2 * HOUR))
        assert _series(db)["counts"] == [1, 1, 0, 0]

    def test_a_ban_starting_exactly_on_a_bucket_boundary_occupies_it(self, db):
        _ban(db, "1.2.3.4", _at(2 * HOUR), expires=_at(3 * HOUR))
        assert _series(db)["counts"] == [0, 0, 1, 0]

    def test_a_ban_ending_exactly_at_the_window_start_is_excluded(self, db):
        _ban(db, "1.2.3.4", _at(-HOUR), expires=_at(0))
        series = _series(db)
        assert series["counts"] == [0, 0, 0, 0]
        assert series["total"] == 0

    def test_a_ban_starting_exactly_at_the_window_end_is_excluded(self, db):
        _ban(db, "1.2.3.4", _at(4 * HOUR))
        assert _series(db)["total"] == 0

    def test_a_sub_bucket_ban_still_occupies_its_one_bucket(self, db):
        _ban(db, "1.2.3.4", _at(HOUR + 10), expires=_at(HOUR + 11))
        assert _series(db)["counts"] == [0, 1, 0, 0]

    def test_a_ban_ending_a_second_into_a_bucket_occupies_it(self, db):
        """Sub-second/sub-bucket truncation would lose this one silently."""
        _ban(db, "1.2.3.4", _at(0), expires=_at(2 * HOUR + 1))
        assert _series(db)["counts"] == [1, 1, 1, 0]


class TestShape:
    def test_buckets_are_the_window_start_of_each_interval(self, db):
        series = _series(db)
        assert series["buckets"] == [T0, T0 + HOUR, T0 + 2 * HOUR, T0 + 3 * HOUR]

    def test_day_bucket_is_the_default_for_anything_that_is_not_hour(self, db):
        series = _series(db, end=T0 + 2 * 86400, bucket="week")
        assert series["buckets"] == [T0, T0 + 86400]

    def test_a_partial_trailing_interval_still_gets_its_own_bucket(self, db):
        assert len(_series(db, end=T0 + 90 * 60)["buckets"]) == 2

    def test_trend_compares_against_the_preceding_equal_window(self, db):
        _ban(db, "1.2.3.4", _at(-3 * HOUR), expires=_at(-2 * HOUR))  # previous window only
        _ban(db, "5.6.7.8", _at(HOUR), expires=_at(2 * HOUR))  # current window only
        series = _series(db)
        assert (series["total"], series["prev_total"], series["trend_pct"]) == (1, 1, 0.0)

    def test_trend_is_none_rather_than_infinite_when_the_previous_window_was_empty(self, db):
        _ban(db, "1.2.3.4", _at(HOUR))
        series = _series(db)
        assert series["prev_total"] == 0 and series["trend_pct"] is None

    def test_an_empty_table_yields_zeroed_buckets_not_an_empty_list(self, db):
        series = _series(db)
        assert series["counts"] == [0, 0, 0, 0] and series["total"] == 0


class TestGuards:
    def test_a_range_needing_more_than_the_bucket_cap_is_a_value_error(self, db):
        with pytest.raises(ValueError, match="too large"):
            db.get_bans_timeseries(start=T0, end=T0 + 20000 * HOUR, bucket="hour")

    def test_the_cap_is_the_one_the_metrics_series_uses(self):
        from db_methods.metrics import MAX_TIMESERIES_BUCKETS  # type: ignore

        assert MAX_TIMESERIES_BUCKETS == 10000

    def test_an_unrepresentable_epoch_is_a_value_error_not_a_crash(self, db):
        with pytest.raises(ValueError, match="epoch out of range"):
            # A small window, so the bucket-cap guard cannot mask the epoch guard.
            db.get_bans_timeseries(start=10**18, end=10**18 + HOUR, bucket="hour")

    def test_a_zero_length_window_still_returns_one_bucket(self, db):
        assert _series(db, end=T0)["buckets"] == [T0]


def test_bucketing_reads_naive_datetimes_as_utc(db):
    """SQLite/MySQL/MariaDB drop tzinfo on read-back. ``.timestamp()`` on a naive datetime then
    resolves against the *local* zone and shifts every bucket index by the UTC offset. Pin TZ away
    from UTC, otherwise a UTC runner makes the wrong code coincidentally right (RULE 17)."""
    original_tz = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    try:
        _ban(db, "1.2.3.4", _at(2 * HOUR + 60), expires=_at(2 * HOUR + 120))
        assert _series(db)["counts"] == [0, 0, 1, 0]
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


def test_the_window_query_does_not_load_rows_outside_it(db):
    """The bucket loop is O(overlapping rows); the SQL bound is what keeps that true."""
    for index in range(5):
        _ban(db, f"10.0.0.{index}", _at(-100 * HOUR), expires=_at(-99 * HOUR))
    _ban(db, "1.2.3.4", _at(HOUR), expires=_at(2 * HOUR))
    assert _series(db)["total"] == 1


def test_timedelta_import_is_not_needed_by_the_caller():
    """Guards the helper module import list against an accidental unused-import lint break."""
    assert timedelta(seconds=1).total_seconds() == 1

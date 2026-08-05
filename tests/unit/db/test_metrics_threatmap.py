"""DatabaseMetricsMixin.get_metrics_threatmap — the single query behind the /threatmap page.

Everything the map, the counter and the three panels show comes out of this one call, so the
things worth pinning here are the ones a caller cannot see: that the window is half-open, that
the report clause still applies, that the non-ISO country sentinels are counted rather than
dropped, and that ``count`` agrees with the countries actually drawn.
"""

import pytest

# fixed epoch for determinism: 2024-01-01T00:00:00Z
EPOCH = 1704067200
DAY = 86400


def _rec(request_id, *, status=403, security_mode="block", date=EPOCH, **over):
    rec = {
        "id": request_id,
        "date": date,
        "ip": "1.2.3.4",
        "country": "US",
        "method": "GET",
        "url": "/admin",
        "status": status,
        "user_agent": "curl/8",
        "reason": "blacklist",
        "server_name": "app.example.com",
        "data": "",
        "security_mode": security_mode,
    }
    rec.update(over)
    return rec


def _names(facets):
    return [facet["name"] for facet in facets]


class TestWindow:
    def test_the_window_is_half_open(self, db):
        """``end`` is exclusive. A closed upper bound double-counts the boundary row whenever an
        operator pages backwards through consecutive windows."""
        db.batch_upsert_metrics_requests(
            [
                _rec("before", date=EPOCH - 1),
                _rec("start", date=EPOCH),
                _rec("inside", date=EPOCH + 10),
                _rec("end", date=EPOCH + DAY),
            ],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH, end=EPOCH + DAY)

        assert result["count"] == 2
        assert {row["request_id"] for row in result["recent"]} == {"start", "inside"}

    def test_an_absurd_epoch_raises_valueerror_not_oserror(self, db):
        """The API turns ValueError into a 400; anything else would be a 500 on user input."""
        with pytest.raises(ValueError):
            db.get_metrics_threatmap(start=EPOCH, end=10**20)


class TestFacets:
    def test_only_reports_are_counted(self, db):
        """Same report clause as every other metrics read: 4xx, or anything in detect mode. A
        successful request that happened to be recorded must not land on the threat map."""
        db.batch_upsert_metrics_requests(
            [
                _rec("blocked", status=403),
                _rec("detected", status=200, security_mode="detect"),
                _rec("served", status=200, security_mode="block"),
            ],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY)

        assert result["count"] == 2
        assert {row["request_id"] for row in result["recent"]} == {"blocked", "detected"}

    def test_facets_are_sorted_by_count_then_name(self, db):
        """No ORDER BY on a GROUP BY is unspecified across engines, and the page slices the top 5
        off the front — an unsorted list would show a different "top origin" per engine."""
        db.batch_upsert_metrics_requests(
            [_rec(f"fr{i}", country="FR") for i in range(3)]
            + [_rec(f"de{i}", country="DE") for i in range(2)]
            + [_rec("us0", country="US"), _rec("be0", country="BE")],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY)

        # FR(3), DE(2), then the two ties broken alphabetically
        assert _names(result["by_country"]) == ["FR", "DE", "BE", "US"]

    def test_country_sentinels_are_counted_not_dropped(self, db):
        """``local``/``unknown``/"" are legitimate values of a NOT NULL column and never join a
        map polygon. Dropping them here would make the counter exceed the map with no explanation;
        the page buckets them as "not localised" instead."""
        db.batch_upsert_metrics_requests(
            [
                _rec("a", country="US"),
                _rec("b", country="local"),
                _rec("c", country="unknown"),
                _rec("d", country=""),
            ],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY)

        assert result["count"] == 4
        assert set(_names(result["by_country"])) == {"US", "local", "unknown", ""}

    def test_count_is_the_sum_of_the_country_facet(self, db):
        """The TODAY tile and the map are read side by side, so they must be the same number by
        construction rather than by two independent queries that can disagree."""
        db.batch_upsert_metrics_requests(
            [_rec("a", country="US"), _rec("b", country="FR"), _rec("c", country="local")],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY)

        assert result["count"] == sum(facet["count"] for facet in result["by_country"])

    def test_server_and_reason_facets_are_returned(self, db):
        db.batch_upsert_metrics_requests(
            [
                _rec("a", server_name="app.example.com", reason="blacklist"),
                _rec("b", server_name="app.example.com", reason="modsecurity"),
                _rec("c", server_name="api.example.com", reason="blacklist"),
            ],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY)

        assert _names(result["by_server"]) == ["app.example.com", "api.example.com"]
        assert _names(result["by_reason"]) == ["blacklist", "modsecurity"]

    def test_a_service_filter_narrows_every_facet_and_the_count(self, db):
        db.batch_upsert_metrics_requests(
            [_rec("a", server_name="app.example.com"), _rec("b", server_name="api.example.com")],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, filters={"server_name": ["app.example.com"]})

        assert result["count"] == 1
        assert _names(result["by_server"]) == ["app.example.com"]


class TestRecent:
    def test_recent_is_newest_first_and_limited(self, db):
        """The ticker reads this top-down and the arcs are spawned from it, so the ordering is the
        feature, not an incidental."""
        db.batch_upsert_metrics_requests([_rec(f"r{i}", date=EPOCH + i) for i in range(10)], instance_hostname="bw-1")

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, recent_limit=3)

        assert [row["request_id"] for row in result["recent"]] == ["r9", "r8", "r7"]

    def test_the_limit_never_collapses_to_zero(self, db):
        """A 0 or negative limit would silently return an empty ticker rather than an error."""
        db.batch_upsert_metrics_requests([_rec("r0")], instance_hostname="bw-1")

        assert len(db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, recent_limit=0)["recent"]) == 1

    def test_recent_carries_what_the_ticker_renders(self, db):
        db.batch_upsert_metrics_requests([_rec("r0", country="FR", reason="modsecurity")], instance_hostname="bw-1")

        row = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY)["recent"][0]

        assert row["date"] == EPOCH
        assert (row["ip"], row["country"], row["reason"], row["server_name"]) == ("1.2.3.4", "FR", "modsecurity", "app.example.com")


def test_an_empty_window_is_empty_rather_than_absent(db):
    """The page distinguishes "nothing blocked" from "the call failed", so every key must be
    present and falsy rather than missing."""
    result = db.get_metrics_threatmap(start=EPOCH, end=EPOCH + DAY)

    assert result == {
        "count": 0,
        "distinct": {"country": 0, "server": 0, "reason": 0},
        "by_country": [],
        "by_server": [],
        "by_reason": [],
        "recent": [],
    }


class TestFacetTruncation:
    """``facet_limit`` bounds the payload, not the truth.

    One row per distinct service means a 5 000-service deployment ships 5 000 rows on every poll
    of every open board to render five of them. Truncating is the fix; the two things that must
    survive it are the counter and the caller's ability to say what it is hiding.
    """

    def test_the_count_survives_truncation(self, db):
        db.batch_upsert_metrics_requests(
            [_rec(f"r{i}", country=f"C{i}", server_name=f"s{i}.example.com", reason=f"reason-{i}") for i in range(10)],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, facet_limit=3)

        assert result["count"] == 10
        assert len(result["by_server"]) == 3
        assert len(result["by_reason"]) == 3

    def test_distinct_reports_the_pre_truncation_totals(self, db):
        """The panel says "N more not shown"; N comes from here, so it must count what was
        dropped rather than what was returned."""
        db.batch_upsert_metrics_requests(
            [_rec(f"r{i}", server_name=f"s{i}.example.com", reason=f"reason-{i}") for i in range(10)],
            instance_hostname="bw-1",
        )

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, facet_limit=3)

        assert result["distinct"] == {"country": 1, "server": 10, "reason": 10}

    def test_the_country_facet_is_exempt(self, db):
        """The map colours every country it can. Truncating this list would leave polygons blank
        with no way for the page to know they were dropped rather than quiet."""
        db.batch_upsert_metrics_requests([_rec(f"r{i}", country=f"C{i}") for i in range(10)], instance_hostname="bw-1")

        result = db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, facet_limit=3)

        assert len(result["by_country"]) == 10

    def test_the_limit_never_collapses_to_zero(self, db):
        db.batch_upsert_metrics_requests([_rec("r0")], instance_hostname="bw-1")

        assert len(db.get_metrics_threatmap(start=EPOCH - 1, end=EPOCH + DAY, facet_limit=0)["by_server"]) == 1

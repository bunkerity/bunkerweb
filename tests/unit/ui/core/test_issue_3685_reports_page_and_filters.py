"""Reports page regressions in ``InstancesUtils``: a page is filled past discarded Redis entries (#3685), the streaming path keeps
every report so counts match the facets (#3407), and filter values holding ``,`` ``;`` ``&`` ``<`` ``>`` still match (#4013).

Redis is the in-memory ``FakeRedis`` of the core harness, seeded with the exact keys the metrics writer produces.
"""

import json
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest

from app.models.instance import InstancesUtils
from _ui_core_helpers import report, seed
from redis_keys import requests_key  # type: ignore

AWKWARD = "/a,b;c&d<e>"


@pytest.fixture
def utils(redis, routes_utils):
    db = MagicMock()
    db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "100"}
    routes_utils.client = redis
    return InstancesUtils(db)


@pytest.mark.parametrize("order_dir, expected", [("desc", ["r8", "r7", "r6"]), ("asc", ["r2", "r4", "r5"])])
def test_issue_3685_page_is_full_when_entries_in_it_are_discarded(utils, redis, order_dir, expected):
    """A page holding an unreadable entry and a repeated id came back shorter than asked; it must still return ``length`` reports (#3685)."""
    reports = [report(i) for i in range(1, 11)]
    seed(redis, reports)
    entries = redis.lists[requests_key(False)]
    if order_dir == "desc":
        entries[9] = json.dumps(report(8)).encode()  # newest entry repeats r8's id
        entries[8] = b"{broken"
    else:
        entries[0] = b"{broken"  # oldest entry is unreadable, entries[1] is r2
        entries[2] = json.dumps(report(2)).encode()  # repeated id

    out = utils.get_reports_query(start=0, length=3, order_dir=order_dir, include_pane_counts=False)

    assert [r["id"] for r in out["data"]] == expected
    assert len(out["data"]) == 3


@pytest.mark.parametrize("status, mode", [(200, "block"), (502, "block"), (301, "block")])
def test_issue_3407_streamed_reports_keep_non_4xx_entries_so_counts_match_the_facets(utils, redis, status, mode):
    """The streaming path dropped reports that were not 4xx (or detect mode) while the facets counted them, so the table total and
    the filtered counts disagreed for an IP; every streamed report must be kept (#3407)."""
    seed(redis, [report(1, status=status, security_mode=mode), report(2), report(3, status=status, security_mode=mode)], certified=False)

    out = utils.get_reports_query(length=10)

    assert sorted(r["id"] for r in out["data"]) == ["r1", "r2", "r3"]
    assert (out["total"], out["filtered"]) == (3, 3)
    assert sum(entry["count"] for entry in out["pane_counts"]["status"].values()) == out["filtered"]
    assert out["pane_counts"]["status"][str(status)] == {"total": 2, "count": 2}


def test_issue_3407_streamed_status_filter_counts_non_4xx_reports(utils, redis):
    """Filtering the streamed list on a non-4xx status returns those reports and counts them in the pane (#3407)."""
    seed(redis, [report(1, status=200), report(2), report(3, status=200)], certified=False)

    out = utils.get_reports_query(length=10, search_panes="status:200")

    assert sorted(r["id"] for r in out["data"]) == ["r1", "r3"]
    assert out["filtered"] == 2 and out["pane_counts"]["status"]["200"] == {"total": 2, "count": 2}


@pytest.mark.parametrize("certified", [True, False], ids=["fast-facets", "streaming"])
def test_issue_4013_pane_filter_values_with_delimiters_still_match(utils, redis, certified):
    """A pane value containing ``,`` or ``;`` split into several values (and ``&``, ``<``, ``>`` got mangled) so the filter matched nothing;
    the percent-encoded wire format must round-trip them (#4013)."""
    seed(redis, [report(1, url=AWKWARD), report(2, url="/plain"), report(3, url="/a")], certified=certified)
    panes = "url:" + quote(AWKWARD, safe="")

    out = utils.get_reports_query(length=10, search_panes=panes)

    assert [r["id"] for r in out["data"]] == ["r1"]
    assert out["filtered"] == 1 and out["total"] == 3


def test_issue_4013_several_values_of_one_pane_are_all_kept(utils, redis):
    """Two selections of the same pane, one of them with a comma, both stay selected (#4013)."""
    seed(redis, [report(1, url="/x,y"), report(2, url="/plain"), report(3, url="/other")], certified=False)
    panes = "url:" + quote("/x,y", safe="") + "," + quote("/plain", safe="")

    out = utils.get_reports_query(length=10, search_panes=panes)

    assert sorted(r["id"] for r in out["data"]) == ["r1", "r2"]

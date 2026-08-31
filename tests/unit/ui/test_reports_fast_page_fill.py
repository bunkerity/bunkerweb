"""A reports page fills past discarded entries (`4d0ca235f`, issue #3685).

The fast pagination path read exactly one raw window of `length` entries and returned whatever
survived parsing and de-duplication. Anything the loop discarded -- a malformed JSON entry, a
non-dict, a duplicate id -- came off the page, so a page of 25 could render 3 rows while the
table still claimed hundreds of records and the next page skipped nothing.

It now keeps reading forward until the page is full or the scan budget (four raw pages) runs
out, which also bounds the work on a list that is mostly junk.
"""

from json import dumps

from app.models.instance import InstancesUtils


class FakeRedis:
    """`llen` + `lrange` over an in-memory list, which is the whole surface used here."""

    def __init__(self, entries):
        self.entries = entries
        self.ranges = []

    def llen(self, _key):
        return len(self.entries)

    def lrange(self, _key, start, end):
        self.ranges.append((start, end))
        if start < 0 or start >= len(self.entries):
            return []
        stop = end + 1
        return self.entries[start:stop]


def page(entries, *, start=0, length=5, order_dir="desc", max_requests=10_000):
    redis_client = FakeRedis(entries)
    total, reports = InstancesUtils._get_redis_requests_fast_page(
        InstancesUtils.__new__(InstancesUtils),
        redis_client,
        max_requests=max_requests,
        start=start,
        length=length,
        order_dir=order_dir,
    )
    return total, reports, redis_client


def report(idx):
    return dumps({"id": idx, "date": idx})


def test_a_full_page_of_clean_entries_reads_exactly_one_window():
    """The fast path stays fast: no extra round trip when the first window already fills."""
    _, reports, redis_client = page([report(i) for i in range(20)])
    assert [r["id"] for r in reports] == [19, 18, 17, 16, 15]
    assert len(redis_client.ranges) == 1


def test_the_page_fills_past_unparsable_entries():
    """The defect: four junk entries at the head used to leave a one-row page of five."""
    entries = [report(i) for i in range(20)] + ["not json", "not json", "not json", "not json"]
    _, reports, _ = page(entries)
    assert len(reports) == 5
    assert [r["id"] for r in reports] == [19, 18, 17, 16, 15]


def test_the_page_fills_past_duplicate_ids():
    entries = [report(i) for i in range(20)] + [report(19)] * 4
    _, reports, _ = page(entries)
    assert len(reports) == 5
    assert [r["id"] for r in reports] == [19, 18, 17, 16, 15]


def test_ascending_order_fills_the_same_way():
    entries = ["not json"] * 4 + [report(i) for i in range(20)]
    _, reports, _ = page(entries, order_dir="asc")
    assert [r["id"] for r in reports] == [0, 1, 2, 3, 4]


def test_the_scan_is_bounded_when_everything_is_junk():
    """An all-junk list must not turn one page request into a full-list scan."""
    _, reports, redis_client = page(["not json"] * 500, length=5)
    assert reports == []
    # Four raw pages of five, and not one lrange more.
    assert sum(end - start + 1 for start, end in redis_client.ranges) == 20


def test_a_short_tail_still_returns_what_is_there():
    """Fewer surviving entries than a page: return them rather than looping off the list."""
    _, reports, _ = page([report(0), report(1)], length=5)
    assert [r["id"] for r in reports] == [1, 0]

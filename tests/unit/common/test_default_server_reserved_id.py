"""The reserved id, where it must NOT count: the PRO service quota.

The reserved `default-server` row lives in `bw_services` and therefore appears in the global
`SERVER_NAME` roster like any other service. That roster is what the licence quota counts
(`utils/service_classification.py`), so without an exclusion every deployment would silently gain
one billable service the operator never created -- and the one deployment where that matters most
is the one sitting exactly on its limit.
"""

from default_server import DEFAULT_SERVER_ID, is_default_server, strip_default_server  # type: ignore
from service_classification import count_snapshot, split_services  # type: ignore

SNAPSHOT = {
    "SERVER_NAME": f"app1.example.com app2.example.com {DEFAULT_SERVER_ID}",
    "app1.example.com_USE_REVERSE_PROXY": "yes",
    "app2.example.com_USE_REVERSE_PROXY": "yes",
    f"{DEFAULT_SERVER_ID}_SSL_PROTOCOLS": "TLSv1.3",
}


def test_split_services_drops_the_reserved_row():
    assert set(split_services(SNAPSHOT)) == {"app1.example.com", "app2.example.com"}


def test_the_quota_counts_the_operators_services_only():
    counts = count_snapshot(SNAPSHOT)
    assert counts.total == 2
    assert counts.billable == 2


def test_an_explicit_service_list_is_still_honoured():
    """`split_services` takes an explicit `service_names` for callers that already resolved the
    roster; the exclusion belongs to the SERVER_NAME derivation, not to the slicing."""
    assert set(split_services(SNAPSHOT, ["app1.example.com"])) == {"app1.example.com"}


def test_the_helpers_do_not_match_a_lookalike_hostname():
    """A real hostname must never be mistaken for the reserved id -- the refusals keyed on it would
    then lock a service its owner created out of being renamed or deleted."""
    assert is_default_server(DEFAULT_SERVER_ID)
    assert is_default_server(f" {DEFAULT_SERVER_ID} ")  # a roster split can leave whitespace
    assert not is_default_server("default-server.example.com")
    assert not is_default_server("my-default-server")
    assert not is_default_server(None)
    assert strip_default_server(["a", DEFAULT_SERVER_ID, "b"]) == ["a", "b"]

"""The public pane syntax splits separators before decoding each value."""

from urllib.parse import quote
from unittest.mock import Mock

import pytest

from test_metrics_dashboard import _load_router

ROUTER = _load_router()
VALUE = "/path,a;b?x=<tag>&literal=%3B+é"


@pytest.mark.parametrize("value", ["plain+é<>&\"'", "bad%Z1%1%xx"])
def test_plain_or_malformed_percent_values_stay_unchanged(value):
    assert ROUTER._parse_search_panes("url:" + value) == {"url": [value]}


def test_encoded_protocol_stream_alias_is_preserved():
    assert ROUTER._parse_search_panes("protocol:%73tream") == {"protocol": ["tcp", "udp"]}


@pytest.mark.parametrize("endpoint", ["query_metrics_requests", "query_metrics_timeseries", "query_metrics_top_offenders"])
def test_every_report_query_decodes_filters_and_facets(monkeypatch, endpoint):
    db = Mock()
    db.get_metrics_requests.return_value = {"total": 0, "filtered": 0, "data": []}
    db.get_metrics_facets.return_value = {}
    db.get_metrics_timeseries.return_value = {"buckets": [], "counts": []}
    db.get_metrics_top_offenders.return_value = []
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    kwargs = {} if endpoint == "query_metrics_requests" else {"start": 1, "end": 2}
    response = getattr(ROUTER, endpoint)(search_panes="url:" + quote(VALUE, safe=""), **kwargs)
    assert response.status_code == 200
    method = getattr(db, endpoint.replace("query_", "get_"))
    assert method.call_args.kwargs["filters"] == {"url": [VALUE]}
    if endpoint == "query_metrics_requests":
        assert db.get_metrics_facets.call_args.kwargs["filters"] == {"url": [VALUE]}

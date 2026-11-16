"""Pane values must survive the UI, Redis, and instance query paths unchanged."""

from html import escape
from urllib.parse import quote
from unittest.mock import Mock

import pytest

from app.models import instance
import test_bans_time_left_sort_and_30d_pane as bans_tests
import test_reports_dashboard as reports_tests
from flask import Flask

reports_route = reports_tests.reports_route
route_app = reports_tests.route_app
bans_route = bans_tests.bans_route

VALUE = '/path,a;b?x=<tag>&y="quoted"&literal=%3B+é'


def test_pane_codec_round_trip():
    panes = {"url": [VALUE, "other"], "protocol": ["tcp"]}
    encoded = instance.encode_search_panes(panes)
    assert encoded == f"url:{quote(VALUE, safe='')},other;protocol:tcp"
    assert instance.decode_search_panes(encoded) == panes


def test_local_filter_decodes_values_after_splitting():
    utils = object.__new__(instance.InstancesUtils)
    report = {"id": "keep", "url": VALUE}
    assert utils._apply_report_filters([report], "", "url:" + quote(VALUE, safe="")) == [report]


def test_redis_filter_decodes_values_after_splitting(monkeypatch, reports_route):
    from app.routes import utils as route_utils

    monkeypatch.setattr(route_utils, "get_redis_client", lambda: object())
    utils = object.__new__(instance.InstancesUtils)
    utils._get_max_blocked_requests_redis = lambda: 100
    utils._get_redis_scan_window = lambda *_: (0, 2)
    report = {"id": "keep", "url": VALUE, "date": 2}
    utils._iter_redis_requests = lambda *_, **__: iter([report, {"id": "drop", "url": "other", "date": 1}])
    result = utils.get_reports_query(search_panes="url:" + quote(VALUE, safe=""), include_pane_counts=False)
    assert result["data"] == [report]
    assert result["filtered"] == 1


def test_pane_labels_escape_html_but_values_remain_raw(route_app):
    module, _, app = route_app
    with app.test_request_context():
        options = module.build_search_panes_options({"url": {VALUE: {"count": 1, "total": 1}}})
    assert options["url"][0]["value"] == VALUE
    assert options["url"][0]["label"] == escape(VALUE)


@pytest.mark.parametrize("endpoint", ["reports_fetch", "reports_filters"])
def test_reports_posts_encode_each_pane_value(route_app, monkeypatch, endpoint):
    module, _, app = route_app
    query = Mock(return_value={"total": 0, "filtered": 0, "data": [], "pane_counts": {}})
    monkeypatch.setattr(module, "_query_reports", query)
    monkeypatch.setattr(module, "BW_INSTANCES_UTILS", Mock())
    module.REPORTS_FILTERS_CACHE.clear()
    with app.test_request_context("/reports", method="POST", data={"searchPanes[url][0]": VALUE}):
        getattr(module, endpoint).__wrapped__.__wrapped__()
    assert query.call_args.kwargs["search_panes"] == "url:" + quote(VALUE, safe="")


def test_ban_pane_values_stay_raw_and_labels_stay_escaped(bans_route, monkeypatch):
    ban = {**bans_tests._ban(1, 600), "reason": VALUE, "service": VALUE, "ban_scope": "service"}
    monkeypatch.setattr(bans_route, "_collect_all_bans", lambda **_: [ban])
    app = Flask(__name__)
    with app.test_request_context("/bans/fetch", method="POST", data={}):
        payload = bans_route.bans_fetch.__wrapped__.__wrapped__().get_json()
    for field in ("reason", "service"):
        option = payload["searchPanes"]["options"][field][0]
        assert option["value"] == VALUE
        assert option["label"] == escape(VALUE)

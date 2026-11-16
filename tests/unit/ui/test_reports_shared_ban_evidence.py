"""Demand loading preserves durable and legacy evidence contracts."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.api_client import ApiClient
from app.models.instance import InstancesUtils
import test_reports_dashboard as reports_tests

reports_route = reports_tests.reports_route
route_app = reports_tests.route_app

ROOT = Path(__file__).resolve().parents[3]
BAN_ID = "http:" + "x" * 32
SUMMARY = {"ban_id": BAN_ID, "counter": 40, "event_count": 1, "server_name": "summary.example"}
SNAPSHOT = {**SUMMARY, "events": [{"url": "/kept", "server_name": "event.example"}]}


def test_transport_uses_exact_detail_endpoint():
    client = object.__new__(ApiClient)
    client._get = Mock(return_value={"status": "success", "data": SNAPSHOT})
    assert client.get_metrics_request_data("req-1", instance_hostname="one") == SNAPSHOT
    client._get.assert_called_once_with("/metrics/requests/req-1/data", params={"instance_hostname": "one"})


def test_db_snapshot_survives_live_expiry_and_preserves_event_service(monkeypatch, reports_route):
    from app.routes import utils as route_utils

    monkeypatch.setattr(route_utils, "get_redis_client", lambda: None)
    utils = object.__new__(InstancesUtils)
    utils._InstancesUtils__api_client = Mock(get_metrics_request_data=Mock(return_value=SNAPSHOT))
    utils.get_instances = Mock(side_effect=AssertionError("durable snapshot must not scan instances"))
    data = utils.get_report_data("req-1")
    assert data == [{**SUMMARY, **SNAPSHOT["events"][0]}]
    assert data[0]["counter"] == 40


def test_summary_resolves_redis_once_and_missing_keeps_historical_counts():
    utils = object.__new__(InstancesUtils)
    utils.get_instances = Mock(return_value=[])
    redis = Mock(get=Mock(return_value=json.dumps(SNAPSHOT)))
    assert utils._resolve_ban_evidence(SUMMARY, redis)[0]["url"] == "/kept"
    redis.get.assert_called_once_with("requests:ban_evidence:" + BAN_ID)
    redis.get.return_value = None
    assert utils._resolve_ban_evidence(SUMMARY, redis) == {**SUMMARY, "evidence_missing": True}
    legacy = [{"counter": 50, "url": "tcp://legacy"}]
    assert utils._resolve_ban_evidence(legacy, redis) == legacy


def test_durable_legacy_details_do_not_require_live_redis(monkeypatch, reports_route):
    from app.routes import utils as route_utils

    monkeypatch.setattr(route_utils, "get_redis_client", Mock(side_effect=AssertionError("durable details must not require Redis")))
    utils = object.__new__(InstancesUtils)
    utils._InstancesUtils__api_client = Mock(get_metrics_request_data=Mock(return_value={"ids": [942100]}))
    assert utils.get_report_data("req-1") == {"ids": [942100]}


def test_rows_carry_summary_only_and_an_instance_hint(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "BW_INSTANCES_UTILS", Mock())
    monkeypatch.setattr(
        module,
        "_query_reports",
        lambda **_: {"total": 1, "filtered": 1, "pane_counts": {}, "data": [{"id": "r", "instance_hostname": "one", "data": SNAPSHOT}]},
    )
    with app.test_request_context("/reports/fetch", method="POST", data={"draw": "1"}):
        row = module.reports_fetch.__wrapped__.__wrapped__().get_json()["data"][0]
    assert row["data"] == SUMMARY
    assert row["instance_hostname"] == "one"


@pytest.mark.skipif(shutil.which("node") is None, reason="requires Node")
def test_missing_summary_and_capped_stream_inline_render_true_counter():
    source = (ROOT / "src/ui/app/static/js/pages/reports.js").read_text()
    formatter = re.search(r"^  function formatBadBehaviorData\(.*?^  }$", source, re.M | re.S).group()
    result = subprocess.run(
        [
            shutil.which("node"),
            "-e",
            """
const assert=require('node:assert/strict');
const t=(_,fallback)=>fallback, escapeHtml=String;
const getMethodBadgeClass=()=>'', getStatusBadgeClass=()=>'', formatBadBehaviorTimestamp=()=>'';
"""
            + formatter
            + """
const missing=formatBadBehaviorData([], {ban_id:'http:xxx',counter:99,event_count:3,evidence_missing:true});
assert.match(missing,/total-count">99/);
assert.match(missing,/Ban evidence is no longer available/);
assert.doesNotMatch(missing,/<article/);
assert.match(formatBadBehaviorData([{counter:250,url:'tcp://legacy'}]),/total-count">250/);
""",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

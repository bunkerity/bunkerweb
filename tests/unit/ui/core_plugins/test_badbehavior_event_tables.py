"""Badbehavior keeps full history URIs but groups charts by path."""

from datetime import datetime
from json import dumps
from unittest.mock import Mock

import pytest


def test_badbehavior_scoped_history_deduplicates_and_groups_paths(load_plugin):
    first = dict(id="one", date=20, ip="192.0.2.1", server_name="EXAMPLE.TEST", url="/scan?a=1", status=403, ban_time=60, threshold=2, count_time=10)
    second = dict(first, id="two", date="invalid", url="/scan?a=2")
    outside = dict(first, id="three", server_name="other.test")
    instances = Mock()
    instances.get_metrics.return_value = {
        "table_increments": dumps([first, second, outside]),
        "table_increments_other": {"one": [first]},
        "counter_status_500": 99,
    }
    result = load_plugin("badbehavior").pre_render(bw_instances_utils=instances, data={"server_name": " example.test "})
    table = result["list_bad_behavior_history"]["data"]
    assert table["id"] == ["one", "two"]
    assert table["date"] == [datetime.fromtimestamp(20).isoformat(), "invalid"]
    assert table["url"] == ["/scan?a=1", "/scan?a=2"]
    assert table["ban_time"] == ["60", "60"]
    assert table["threshold"] == ["2", "2"]
    assert table["count_time"] == ["10", "10"]
    assert result["top_bad_behavior_status"]["data"] == {"code": ["403"], "count": [2]}
    assert result["top_bad_behavior_ips"]["data"] == {"ip": ["192.0.2.1"], "count": [2]}
    assert result["top_bad_behavior_urls"]["data"] == {"url": ["/scan"], "count": [2]}


def test_badbehavior_without_ids_retains_distinct_events(load_plugin):
    instances = Mock()
    instances.get_metrics.return_value = {"table_increments": [{"url": "?x=1"}, {"url": "?x=2"}]}
    result = load_plugin("badbehavior").pre_render(bw_instances_utils=instances)
    assert result["list_bad_behavior_history"]["data"]["id"] == ["", ""]
    assert result["top_bad_behavior_urls"]["data"] == {"url": ["/"], "count": [2]}
    assert result["top_bad_behavior_status"]["data"] == {"code": ["N/A"], "count": [2]}


def test_badbehavior_counter_fallback_and_no_matching_service(load_plugin):
    instances = Mock()
    instances.get_metrics.return_value = {"counter_status_404": "2", "counter_status_403": 8, "unrelated": 99}
    module = load_plugin("badbehavior")
    assert module.pre_render(bw_instances_utils=instances)["top_bad_behavior_status"]["data"] == {"code": [403, 404], "count": [8, 2]}
    result = module.pre_render(bw_instances_utils=instances, args={"service": "default"})
    assert result["top_bad_behavior_status"]["data"] == {"code": [], "count": []}


@pytest.mark.parametrize("raw,expected", [(None, ""), (" ", ""), ("ALL", ""), ("Any", ""), ("default_server", "_"), ("Default", "_"), ("X.TEST", "x.test")])
def test_badbehavior_service_aliases(load_plugin, raw, expected):
    assert load_plugin("badbehavior")._normalize_service_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [(None, []), ("broken json", []), (3, []), ({"row": {"id": "x"}, "empty": None}, [{"id": "x"}])])
def test_badbehavior_invalid_table_payload(load_plugin, raw, expected):
    assert load_plugin("badbehavior")._flatten_table_increments(raw) == expected


def test_badbehavior_date_fallbacks(load_plugin):
    module = load_plugin("badbehavior")
    assert module._format_increment_date("12.5") == datetime.fromtimestamp(12.5).isoformat()
    assert module._format_increment_date(None) == ""


def test_badbehavior_oversized_timestamp_falls_back_to_epoch(load_plugin):
    module = load_plugin("badbehavior")
    assert module._format_increment_date(1e30) == datetime.fromtimestamp(0).isoformat()


def test_badbehavior_failure_is_reported(load_plugin, caplog):
    instances = Mock()
    instances.get_metrics.side_effect = RuntimeError("no metrics")
    result = load_plugin("badbehavior").pre_render(bw_instances_utils=instances)
    assert result["error"] == "no metrics"
    assert result["list_bad_behavior_history"]["data"] == {}
    assert "Failed to get badbehavior metrics: no metrics" in caplog.text

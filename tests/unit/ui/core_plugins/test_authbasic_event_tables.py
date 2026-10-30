"""Authbasic dashboard values reflect deduplicated, service-scoped events."""

from datetime import datetime
from json import dumps
from unittest.mock import Mock

import pytest


def test_authbasic_filters_and_deduplicates_instance_events(load_plugin):
    module = load_plugin("authbasic")
    success = dict(date=10, ip="192.0.2.1", username="alice", uri="/private", server_name="EXAMPLE.TEST", success=True, reason="ignored")
    failed = dict(date="bad-date", ip="192.0.2.2", username="bob", uri="/private", server_name="example.test", success=False, reason="bad password")
    other = dict(success, username="outside", server_name="other.test")
    instances = Mock()
    instances.get_metrics.return_value = {
        "counter_passed_authbasic": 12,
        "counter_failed_authbasic": 3,
        "table_authentications": dumps([success, failed, other]),
        "table_authentications_instance2": {"rows": [success]},
        "counter_passed_user_alice": "9",
        "counter_passed_user_bob": 2,
    }
    result = module.pre_render(bw_instances_utils=instances, args={"service": " Example.Test "})
    instances.get_metrics.assert_called_once_with("authbasic")
    table = result["list_authbasic_authentications"]["data"]
    assert table["username"] == ["alice", "bob"]
    assert table["success"] == ["✓", "✗"]
    assert table["reason"] == ["", "bad password"]
    assert table["date"] == [datetime.fromtimestamp(10).isoformat(), "bad-date"]
    assert result["top_authbasic_users"]["data"] == {"user": ["alice"], "count": [1]}
    assert result["top_authbasic_failed_ips"]["data"] == {"ip": ["192.0.2.2"], "count": [1]}
    assert result["counter_passed_authbasic"]["value"] == 12
    assert result["counter_failed_authbasic"]["value"] == 3
    assert result["list_authbasic_configured_users"]["data"] == {"scope": ["global", "global"], "username": ["alice", "bob"], "auth_count": [9, 2]}


def test_authbasic_counter_fallback_and_empty_service_filter(load_plugin):
    module = load_plugin("authbasic")
    instances = Mock()
    instances.get_metrics.return_value = {"counter_passed_user_alice": "2", "counter_passed_user_bob": 8}
    assert module.pre_render(bw_instances_utils=instances)["top_authbasic_users"]["data"] == {"user": ["bob", "alice"], "count": [8, 2]}
    result = module.pre_render(bw_instances_utils=instances, data={"server_name": "missing.test"})
    assert result["top_authbasic_users"]["data"] == {"user": [], "count": []}
    assert result["top_authbasic_failed_ips"]["data"] == {"ip": [], "count": []}


@pytest.mark.parametrize(
    "raw,expected", [(None, ""), (" ", ""), ("ALL", ""), (" any ", ""), ("default", "_"), ("DEFAULT_SERVER", "_"), ("EXAMPLE.test", "example.test")]
)
def test_authbasic_service_aliases(load_plugin, raw, expected):
    assert load_plugin("authbasic")._normalize_service_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [(None, []), ("invalid json", []), (7, []), ({"one": {"ip": "x"}, "two": [], "empty": None}, [{"ip": "x"}])])
def test_authbasic_ignores_invalid_table_payload(load_plugin, raw, expected):
    assert load_plugin("authbasic")._flatten_table_data(raw) == expected


def test_authbasic_missing_labels_and_dates(load_plugin):
    module = load_plugin("authbasic")
    assert module._build_counter_data([{}, {"username": ""}, {"username": 5}], "username", "user") == {"user": ["N/A", "5"], "count": [2, 1]}
    assert module._format_date("12.5") == datetime.fromtimestamp(12.5).isoformat()
    assert module._format_date(None) == ""


def test_authbasic_oversized_timestamp_falls_back_to_epoch(load_plugin):
    module = load_plugin("authbasic")
    assert module._format_date(1e30) == datetime.fromtimestamp(0).isoformat()


def test_authbasic_backend_error_preserves_defaults(load_plugin, caplog):
    instances = Mock()
    instances.get_metrics.side_effect = RuntimeError("metrics offline")
    result = load_plugin("authbasic").pre_render(bw_instances_utils=instances)
    assert result["error"] == "metrics offline"
    assert result["counter_failed_authbasic"]["value"] == 0
    assert "Failed to get authbasic metrics: metrics offline" in caplog.text

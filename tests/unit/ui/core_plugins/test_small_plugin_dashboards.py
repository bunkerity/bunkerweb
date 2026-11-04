"""Small core dashboards expose metrics and retain usable defaults on failure."""

from unittest.mock import Mock

import pytest

COUNTERS = [
    ("antibot", "counter_failed_challenges"),
    ("cors", "counter_failed_cors"),
    ("country", "counter_failed_country"),
    ("dnsbl", "counter_failed_dnsbl"),
    ("greylist", "counter_failed_greylist"),
    ("whitelist", "counter_passed_whitelist"),
]


@pytest.mark.parametrize("plugin,key", COUNTERS)
def test_single_counter_value_default_and_failure(load_plugin, plugin, key):
    module = load_plugin(plugin)
    instances = Mock()
    instances.get_metrics.return_value = {key: 7}
    assert module.pre_render(bw_instances_utils=instances)[key]["value"] == 7
    instances.get_metrics.assert_called_once_with(plugin)
    instances.get_metrics.return_value = {}
    assert module.pre_render(bw_instances_utils=instances)[key]["value"] == 0
    instances.get_metrics.side_effect = RuntimeError("offline")
    result = module.pre_render(bw_instances_utils=instances)
    assert result[key]["value"] == 0
    assert result["error"] == "offline"


def test_blacklist_and_misc_populate_each_counter(load_plugin):
    instances = Mock()
    keys = ["counter_failed_uri", "counter_failed_ip", "counter_failed_rdns", "counter_failed_asn", "counter_failed_ua"]
    instances.get_metrics.return_value = dict(zip(keys, range(1, 6)))
    result = load_plugin("blacklist").pre_render(bw_instances_utils=instances)
    assert {key: result[key]["value"] for key in keys} == dict(zip(keys, range(1, 6)))
    instances.get_metrics.return_value = {"counter_failed_default": 11, "counter_failed_method": 22}
    result = load_plugin("misc").pre_render(bw_instances_utils=instances)
    assert result["counter_failed_default"]["value"] == 11
    assert result["counter_failed_method"]["value"] == 22


@pytest.mark.parametrize("plugin", ["blacklist", "misc", "limit", "errors", "reversescan"])
def test_metric_dashboard_failure_returns_error(load_plugin, plugin):
    instances = Mock()
    instances.get_metrics.side_effect = RuntimeError("offline")
    assert load_plugin(plugin).pre_render(bw_instances_utils=instances)["error"] == "offline"


@pytest.mark.parametrize(
    "plugin,metrics,card,expected",
    [
        (
            "limit",
            {"counter_limited_global": "9", "counter_limited_uri_": "3", "counter_limited_uri_/api": "8", "ignored": 99},
            "top_limit",
            {"URL": ["/api", "/"], "count": [8, 3]},
        ),
        ("errors", {"error_404": "2", "error_500": "8"}, "top_errors", {"code": [500, 404], "count": [8, 2]}),
        ("reversescan", {"counter_port_22": "2", "counter_port_443": "8"}, "top_reverse_scan", {"port": [443, 22], "count": [8, 2]}),
    ],
)
def test_ranked_metrics_are_numeric_and_descending(load_plugin, plugin, metrics, card, expected):
    instances = Mock()
    instances.get_metrics.return_value = metrics
    result = load_plugin(plugin).pre_render(bw_instances_utils=instances)
    assert result[card]["data"] == expected
    if plugin == "limit":
        assert result["counter_limited_global"]["value"] == 9


def test_redis_ping_and_metrics_errors_are_separate(load_plugin):
    module = load_plugin("redis")
    instances = Mock()
    instances.get_ping.return_value = {"status": "success"}
    instances.get_metrics.return_value = {"redis_nb_keys": 42}
    result = module.pre_render(bw_instances_utils=instances)
    assert result["ping_status"]["value"] == "success"
    assert result["counter_redis_nb_keys"]["value"] == 42
    instances.get_metrics.side_effect = RuntimeError("metrics offline")
    result = module.pre_render(bw_instances_utils=instances)
    assert result["ping_status"]["value"] == "success"
    assert result["error"] == "metrics offline"
    instances.get_metrics.reset_mock()
    instances.get_ping.side_effect = RuntimeError("ping offline")
    assert module.pre_render(bw_instances_utils=instances)["error"] == "ping offline"
    instances.get_metrics.assert_not_called()


def test_backup_lists_cached_files_and_defaults(load_plugin):
    module = load_plugin("backup")
    db = Mock()
    db.get_job_cache_file.return_value = b'{"date":"2026-10-26","files":["one.zip","two.zip"]}'
    result = module.pre_render(db=db)
    assert result["date_last_backup"]["value"] == "2026-10-26"
    assert result["list_backup_files"]["data"] == {"file name": ["one.zip", "two.zip"]}
    db.get_job_cache_file.assert_called_once_with("backup-data", "backup.json")
    db.get_job_cache_file.return_value = None
    assert module.pre_render(db=db)["date_last_backup"]["value"] == "N/A"
    db.get_job_cache_file.side_effect = RuntimeError("cache offline")
    assert module.pre_render(db=db)["error"] == "cache offline"


@pytest.mark.parametrize("status,connected,color", [("success", "Connected", "success"), ("error", "API unreachable", "warning")])
def test_bunkernet_registered_instance_masks_secret_in_description(load_plugin, status, connected, color):
    instances, db = Mock(), Mock()
    instances.get_ping.return_value = {"status": status, "msg": "using instance ID fixture-id status"}
    db.get_job_cache_file.side_effect = [b"fixture-id", b"192.0.2.1\n2001:db8::1"]
    result = load_plugin("bunkernet").pre_render(bw_instances_utils=instances, db=db)
    assert result["info_instance_id"]["secret"] is True
    assert result["info_instance_id"]["value"] == "fixture-id"
    assert result["info_connectivity"]["value"] == connected
    assert result["info_connectivity"]["svg_color"] == color
    assert result["info_connectivity"]["description"] == "using instance ID *** status"
    assert result["list_bunkernet_ips"]["data"] == {"ip": ["192.0.2.1", "2001:db8::1"]}


def test_bunkernet_unregistered_and_backend_failure(load_plugin):
    instances, db = Mock(), Mock()
    instances.get_ping.return_value = {}
    db.get_job_cache_file.return_value = None
    module = load_plugin("bunkernet")
    result = module.pre_render(bw_instances_utils=instances, db=db)
    assert result["info_connectivity"]["value"] == "Not registered yet"
    assert result["info_instance_id"]["value"] == "Unknown"
    assert "registration runs hourly" in result["info_connectivity"]["description"]
    instances.get_ping.side_effect = RuntimeError("ping failed")
    assert module.pre_render(bw_instances_utils=instances, db=db)["error"] == "ping failed"


def test_crowdsec_status_links_operator_console(load_plugin, ui_env):
    module = load_plugin("crowdsec")
    ui_env.app.add_url_rule("/crowdsec", "crowdsec.crowdsec_page", lambda: "console")
    instances = Mock()
    instances.get_ping.return_value = {"status": "success"}
    with ui_env.app.test_request_context("/"):
        card = module.pre_render(bw_instances_utils=instances)["ping_status"]
        assert card["value"] == "success"
        assert card["action_url"] == "/crowdsec"
        assert card["action_i18n"] == "crowdsec.title"
        instances.get_ping.side_effect = RuntimeError("unreachable")
        result = module.pre_render(bw_instances_utils=instances)
        assert result["ping_status"]["value"] == "error"
        assert result["error"] == "unreachable"

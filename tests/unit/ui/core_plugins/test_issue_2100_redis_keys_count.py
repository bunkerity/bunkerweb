"""The Redis dashboard card read the key count from ``counter_redis_nb_keys``, which the metrics never carry, so it always showed 0.

Pins that the card shows the ``redis_nb_keys`` value the metrics report. Ref: #2100.
"""

from unittest.mock import Mock


def instances(metrics):
    mock = Mock()
    mock.get_ping.return_value = {"status": "success"}
    mock.get_metrics.return_value = metrics
    return mock


def test_the_card_shows_the_reported_key_count(load_plugin):
    result = load_plugin("redis").pre_render(bw_instances_utils=instances({"redis_nb_keys": 5}))

    assert result["counter_redis_nb_keys"]["value"] == 5
    assert result["ping_status"]["value"] == "success" and "error" not in result


def test_the_card_falls_back_to_zero_without_the_metric(load_plugin):
    result = load_plugin("redis").pre_render(bw_instances_utils=instances({}))

    assert result["counter_redis_nb_keys"]["value"] == 0

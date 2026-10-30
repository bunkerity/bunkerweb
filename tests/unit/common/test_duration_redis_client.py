"""REDIS_TIMEOUT reaches the Python Redis client as seconds, whatever suffix it was written with."""

import pytest

import common_utils  # type: ignore
from test_redis_client_memo import _FakeRedis, _fake_redis_package  # noqa: F401


@pytest.mark.parametrize(("value", "seconds"), [("1000.0", 1.0), ("1000", 1.0), ("2s", 2.0), ("500ms", 0.5), ("1m", 60.0), (2500, 2.5)])
def test_redis_timeout_is_parsed_in_milliseconds(_fake_redis_package, value, seconds):  # noqa: F811
    client = common_utils.get_redis_client(use_redis=True, redis_host="redis", redis_timeout=value)
    assert isinstance(client, _FakeRedis)
    assert client.kwargs["socket_timeout"] == seconds
    assert client.kwargs["socket_connect_timeout"] == seconds


def test_an_unparsable_timeout_falls_back_to_one_second(_fake_redis_package):  # noqa: F811
    client = common_utils.get_redis_client(use_redis=True, redis_host="redis", redis_timeout="soon")
    assert client.kwargs["socket_timeout"] == 1.0

"""The Web UI always read Redis database 0 because it looked up ``REDIS_DB`` instead of ``REDIS_DATABASE``.

Pins that a non-zero ``REDIS_DATABASE`` reaches the Redis client the UI builds, so Reports and Bans read the
database the instances write to. Ref: #3046.
"""

import pytest


@pytest.fixture
def redis_calls(h, monkeypatch):
    calls = []
    monkeypatch.setattr(h.utils, "get_common_redis_client", lambda **kwargs: calls.append(kwargs) or "client")
    full = {"USE_REDIS": "yes", "REDIS_HOST": "redis", "REDIS_DATABASE": "7"}

    def get_config(*, filtered_settings=None, **_kwargs):
        # like the real reader: only the requested settings come back
        return {key: value for key, value in full.items() if filtered_settings is None or key in filtered_settings}

    h.config.get_config.side_effect = get_config
    return calls


def test_a_non_zero_redis_database_reaches_the_client(h, redis_calls):
    assert h.utils.get_redis_client() == "client"

    assert redis_calls[0]["redis_db"] == "7"


def test_the_database_defaults_to_zero(h, redis_calls):
    h.config.get_config.side_effect = lambda **_kwargs: {"USE_REDIS": "yes", "REDIS_HOST": "redis"}

    h.utils.get_redis_client()

    assert redis_calls[0]["redis_db"] == "0"

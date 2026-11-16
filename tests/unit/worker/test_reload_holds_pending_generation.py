"""A failed generation remains pending between push-configs lease acquisitions."""

from types import SimpleNamespace

import pytest

from test_delivery_guarantees import BROKER, LOGGER, TASKS
from test_reload_broadcast import _LockRedis, _apis, _with_redis

GENERATION_FLAGS = ("pro_plugins_changed", "external_plugins_changed", "custom_configs_changed", "plugins_config_changed", "instances_changed")


@pytest.mark.parametrize("flag", GENERATION_FLAGS)
def test_pending_generation_without_lease_holds_job_publication(monkeypatch, flag):
    metadata = {flag: {"misc": "watermark"} if flag == "plugins_config_changed" else True}
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: SimpleNamespace(get_metadata=lambda: metadata))
    client, apis = _LockRedis(), _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)
    apis.send_files.assert_not_called()
    apis.send_to_apis.assert_not_called()
    assert client.keys.get(TASKS.RELOAD_OWED_KEY)
    assert TASKS.RELOAD_LOCK_KEY not in client.keys


def test_certificate_acknowledgement_does_not_wait_for_itself(monkeypatch):
    metadata = {"certificates_changed": True, "plugins_config_changed": {}}
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: SimpleNamespace(get_metadata=lambda: metadata))
    client, apis = _LockRedis(), _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)
    apis.send_files.assert_called_once()
    apis.send_to_apis.assert_called_once()


def test_pending_generation_is_checked_again_before_next_round(monkeypatch):
    metadata = {}
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: SimpleNamespace(get_metadata=lambda: metadata))
    client, apis = _LockRedis(), _apis()

    def reload(*args, **kwargs):
        metadata["plugins_config_changed"] = {"misc": "watermark"}
        client.set(TASKS.RELOAD_DIRTY_KEY, "1")
        return True, {}

    apis.send_to_apis.side_effect = reload
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)
    apis.send_files.assert_called_once()
    apis.send_to_apis.assert_called_once()
    assert client.keys.get(TASKS.RELOAD_OWED_KEY)
    assert TASKS.RELOAD_LOCK_KEY not in client.keys

"""The UI's per-instance reload goes through the API, never straight to the instance.

`Instance.reload()` used to call the instance directly, so a reload the operator triggered by hand
never reached the code that records the verdict for the failover banner: the banner a refusal had
raised stayed up forever after the operator fixed things and reloaded. The API route records it
(`POST /instances/{hostname}/reload`), so the UI only has to ask the API and never writes the
metadata itself.
"""

from unittest.mock import Mock

import pytest

from app.api_client import ApiClient, ApiClientError, ApiUnavailableError
from app.models.instance import Instance

INSTANCE_ROW = {
    "hostname": "bw-1",
    "server_name": "bwapi",
    "method": "manual",
    "status": "up",
    "type": "static",
    "creation_date": "2026-10-05T00:00:00",
    "last_seen": "2026-10-05T00:00:00",
}


@pytest.fixture
def api_client():
    client = Mock()
    client.get_instance.return_value = dict(INSTANCE_ROW)
    return client


@pytest.fixture
def instance(api_client):
    inst = Instance.from_hostname("bw-1", api_client)
    inst.apiCaller = Mock()
    return inst


def test_a_reload_asks_the_api_and_never_the_instance(instance, api_client, monkeypatch):
    monkeypatch.delenv("DISABLE_CONFIGURATION_TESTING", raising=False)

    assert instance.reload() == "Instance bw-1 has been reloaded."

    api_client.reload_instance.assert_called_once_with("bw-1", test=True)
    instance.apiCaller.send_to_apis.assert_not_called()


def test_the_configuration_test_can_be_disabled_like_everywhere_else(instance, api_client, monkeypatch):
    monkeypatch.setenv("DISABLE_CONFIGURATION_TESTING", "yes")
    instance.reload()
    api_client.reload_instance.assert_called_once_with("bw-1", test=False)


@pytest.mark.parametrize("error", [ApiUnavailableError("API returned 502"), ApiClientError("nope"), RuntimeError("boom")])
def test_a_refused_or_failed_reload_is_reported_not_raised(instance, api_client, error):
    api_client.reload_instance.side_effect = error

    result = instance.reload()

    assert result.startswith("Can't reload instance bw-1"), result
    instance.apiCaller.send_to_apis.assert_not_called()


def test_the_api_client_posts_to_the_per_instance_route_with_a_reload_sized_budget(monkeypatch):
    client = ApiClient("http://api:8888", "token")
    post = Mock(return_value={"status": "success"})
    monkeypatch.setattr(client, "_post", post)

    assert client.reload_instance("bw-1", test=False) == {"status": "success"}

    (path,), kwargs = post.call_args
    assert path == "/instances/bw-1/reload"
    assert kwargs["params"] == {"test": "false"}
    # A reload runs `nginx -t` and the swap on the instance, then the API's own busy retries: the
    # default (3, 10) client budget would report a healthy reload as failed.
    assert kwargs["timeout"][1] >= 60
    # Not retried by the HTTP session: a reload the API already forwarded must not be sent twice.
    assert kwargs["retry"] is False

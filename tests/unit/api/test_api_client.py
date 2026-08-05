from unittest.mock import Mock

import API as api_module


def test_from_instance_prefers_the_instance_credential(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"status": "success"}
    request = Mock(return_value=response)
    monkeypatch.setattr(api_module, "request", request)

    client = api_module.API.from_instance({"hostname": "bw-1", "credential": "instance-token"}, token="global-token")
    assert client.request("GET", "/ping")[0]

    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer instance-token"


def test_pinned_mode_without_a_fingerprint_fails_before_network(monkeypatch):
    request = Mock()
    monkeypatch.setattr(api_module, "request", request)
    client = api_module.API("https://bw-1:5443", tls_mode="pinned")

    sent, error, status, response = client.request("GET", "/ping")

    assert (sent, status, response) == (False, None, None)
    assert error == "TLS pinning requires a fingerprint"
    request.assert_not_called()

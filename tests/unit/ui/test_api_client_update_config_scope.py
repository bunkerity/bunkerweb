"""``ApiClient.update_config`` must restate the service, or a content edit silently goes global.

``PATCH /configs/{service}/{type}/{name}`` reads the config's NEW scope from the request BODY, not
from the URL: ``ConfigUpdateRequest.service`` defaults to ``None`` and ``None`` means "global"
(``src/api/app/schemas.py:253-263``), and the handler writes exactly that
(``src/api/app/routers/configs.py:278,302``). A caller that passes only ``data=``/``is_draft=``
therefore MOVED the config to global -- injecting a per-service snippet into every server block --
while answering 200.

The live caller is the draft toggle: ``routes/configs.py``'s ``configs_convert`` converts a config to or
from draft with ``update_config(service, type, name, is_draft=...)`` and nothing else, so every
toggle of a service-scoped config was moving it to the global scope. The service-rename path used to
carry the same shape (``routes/services.py``, the per-config re-save the shared rename fix made
redundant); that branch is gone, and this test file is what keeps the client honest for the callers
that remain.

Callers that deliberately move a config pass an explicit ``body`` (``routes/configs.py``'s ``configs_edit``) and
must keep full control of ``service``.
"""

from unittest.mock import Mock

import pytest

from app.api_client import ApiClient


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


def _patched(api_client, monkeypatch):
    patch_mock = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_patch", patch_mock)
    return patch_mock


def test_a_content_edit_keeps_the_config_on_its_service(api_client, monkeypatch):
    """A service-scoped config edited by content only, as `routes/configs.py`'s `configs_convert` saves it."""
    patch_mock = _patched(api_client, monkeypatch)

    api_client.update_config("renamed.example.com", "server_http", "mysnippet", data="# keep me", is_draft=False)

    assert patch_mock.call_args.args[0] == "/configs/renamed.example.com/server_http/mysnippet"
    body = patch_mock.call_args.kwargs["json"]
    assert body["service"] == "renamed.example.com", "the config was silently re-scoped to global"
    assert body["data"] == "# keep me"
    assert body["is_draft"] is False


def test_another_services_config_in_the_same_loop_keeps_its_own_service(api_client, monkeypatch):
    """Every service keeps its own scope: the service travels in the body, so a caller looping over
    several configs cannot flatten them all onto the one in the URL."""
    patch_mock = _patched(api_client, monkeypatch)

    api_client.update_config("other.example.com", "server_http", "theirs", data="# theirs", is_draft=False)

    assert patch_mock.call_args.kwargs["json"]["service"] == "other.example.com"


def test_a_global_config_stays_global(api_client, monkeypatch):
    patch_mock = _patched(api_client, monkeypatch)

    api_client.update_config(None, "http", "globalone", data="# global", is_draft=False)

    assert patch_mock.call_args.args[0] == "/configs/global/http/globalone"
    assert patch_mock.call_args.kwargs["json"]["service"] is None


def test_an_explicit_body_still_wins(api_client, monkeypatch):
    """`routes/configs.py`'s `configs_edit` moves a config on purpose; the body it builds must not be rewritten."""
    patch_mock = _patched(api_client, monkeypatch)

    api_client.update_config(
        "old.example.com",
        "server_http",
        "moving",
        body={"service": None, "type": "http", "name": "moving", "data": "# moved", "is_draft": False},
    )

    assert patch_mock.call_args.kwargs["json"] == {"service": None, "type": "http", "name": "moving", "data": "# moved", "is_draft": False}

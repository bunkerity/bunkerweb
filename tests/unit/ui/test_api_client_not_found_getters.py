"""N-H2: unknown ids returned a bare Werkzeug 500 instead of the designed not-found handling.

Root cause: ``get_template``/``get_config_item`` called ``self._get(...)``, which raises
``ApiClientError`` on any 4xx -- 404 included. Every caller (``routes/templates.py``,
``routes/configs.py``) already had an ``if not details:``/``if not db_config:`` branch for the
not-found case, but it was dead code: the exception escaped before the check ever ran, so Flask
served a bare 500 for ``/templates/<unknown>``, ``/templates/new?clone=<unknown>``,
``/templates/<unknown>/json``, ``/templates/<unknown>/update`` and
``/configs/<service>/<type>/<unknown>``.

Fixed once at the shared getters (mirrors the existing ``get_admin_user`` 404-to-None pattern),
so every caller's dead branch becomes live without touching the route files.
"""

from unittest.mock import Mock

import pytest

from app.api_client import ApiClient, ApiClientError


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


def test_get_template_returns_none_on_404(api_client, monkeypatch):
    monkeypatch.setattr(api_client, "_get", Mock(side_effect=ApiClientError("Template not found", status_code=404)))

    assert api_client.get_template("nope") is None


def test_get_template_reraises_non_404_errors(api_client, monkeypatch):
    monkeypatch.setattr(api_client, "_get", Mock(side_effect=ApiClientError("Forbidden", status_code=403)))

    with pytest.raises(ApiClientError):
        api_client.get_template("forbidden-one")


def test_get_config_item_returns_none_on_404(api_client, monkeypatch):
    monkeypatch.setattr(api_client, "_get", Mock(side_effect=ApiClientError("Config not found", status_code=404)))

    assert api_client.get_config_item("global", "http", "nope") is None


def test_get_config_item_reraises_non_404_errors(api_client, monkeypatch):
    monkeypatch.setattr(api_client, "_get", Mock(side_effect=ApiClientError("Forbidden", status_code=403)))

    with pytest.raises(ApiClientError):
        api_client.get_config_item("global", "http", "forbidden-one")

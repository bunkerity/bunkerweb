"""``PATCH /global_settings`` forwarded a partial payload to ``save_config`` as if it were the whole configuration, which deleted services.

Pins that the route saves only the global overrides plus the patched keys, with service management skipped.
"""

from unittest.mock import Mock

import pytest

from _api_http_helpers import ADMIN_HEADERS, router_client

import app.routers.global_settings as global_settings


@pytest.fixture
def database():
    db = Mock()
    db.get_non_default_settings.return_value = {
        "WORKER_PROCESSES": {"method": "api", "value": "2"},
        "LOG_LEVEL": {"method": "ui", "value": "debug"},
    }
    db.save_config.return_value = ""
    return db


def test_a_partial_patch_never_manages_services(monkeypatch, database):
    client = router_client(monkeypatch, global_settings, database)

    response = client.patch("/global_settings", json={"HTTP_PORT": 8080}, headers=ADMIN_HEADERS)

    assert response.status_code == 200
    database.save_config.assert_called_once()
    saved, method = database.save_config.call_args.args[:2]
    assert (saved, method) == ({"WORKER_PROCESSES": "2", "HTTP_PORT": "8080"}, "api")
    assert database.save_config.call_args.kwargs["skip_service_management"] is True

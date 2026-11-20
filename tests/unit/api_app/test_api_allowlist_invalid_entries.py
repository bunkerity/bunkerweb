"""UB4-5: invalid non-empty IP allowlists deny requests without changing valid policies."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import test_app_http_contract as http_contract

from app.config import api_config

application = http_contract.application


@pytest.mark.parametrize("entries", ["not-an-ip 999.1.1.1", "192.0.2.0/99,2001:db8::/129", ", ,"])
@pytest.mark.parametrize("client_ip", ["192.0.2.5", "127.0.0.1", "::1"])
def test_all_invalid_entries_refuse_every_client(application, monkeypatch, entries, client_ip):
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", "yes")
    monkeypatch.setattr(api_config, "API_WHITELIST_IPS", entries)
    response = TestClient(application.create_app(), client=(client_ip, 5000)).get("/ping")
    assert response.status_code == 403
    assert response.json() == {"status": "error", "message": "forbidden"}


def test_all_invalid_entries_log_one_startup_policy_error(application, monkeypatch):
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", "yes")
    monkeypatch.setattr(api_config, "API_WHITELIST_IPS", "not-an-ip 999.1.1.1")
    error = Mock()
    monkeypatch.setattr(application.LOGGER, "error", error)
    app = application.create_app()
    policy_errors = [call.args[0] for call in error.call_args_list if "API_WHITELIST_IPS" in call.args[0]]
    assert len(policy_errors) == 1
    assert "no valid IP/CIDR" in policy_errors[0]
    assert "all requests will be denied" in policy_errors[0]
    calls_at_startup = error.call_count
    for _ in range(2):
        assert TestClient(app, client=("192.0.2.5", 5000)).get("/ping").status_code == 403
    assert error.call_count == calls_at_startup


@pytest.mark.parametrize("client_ip,expected", [("192.0.2.5", 200), ("2001:db8::1", 200), ("198.51.100.1", 403), ("127.0.0.1", 403)])
def test_mixed_entries_keep_valid_networks(application, monkeypatch, client_ip, expected):
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", "yes")
    monkeypatch.setattr(api_config, "API_WHITELIST_IPS", "invalid,192.0.2.0/24 2001:db8::1 999.1.1.1")
    assert TestClient(application.create_app(), client=(client_ip, 5000)).get("/ping").status_code == expected


@pytest.mark.parametrize("enabled,entries", [("yes", ""), ("yes", " \t\n"), ("no", "invalid"), ("no", "192.0.2.0/24")])
def test_empty_or_disabled_allowlist_keeps_requests_unfiltered(application, monkeypatch, enabled, entries):
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", enabled)
    monkeypatch.setattr(api_config, "API_WHITELIST_IPS", entries)
    error = Mock()
    monkeypatch.setattr(application.LOGGER, "error", error)
    app = application.create_app()
    for client_ip in ("198.51.100.1", "127.0.0.1", "::1"):
        assert TestClient(app, client=(client_ip, 5000)).get("/ping").status_code == 200
    error.assert_not_called()


@pytest.mark.parametrize("entries,expected", [("192.0.2.0/24", 403), ("::ffff:192.0.2.0/120", 200)])
def test_ipv4_mapped_client_requires_an_ipv6_allowlist_entry(application, monkeypatch, entries, expected):
    monkeypatch.setattr(api_config, "API_WHITELIST_ENABLED", "yes")
    monkeypatch.setattr(api_config, "API_WHITELIST_IPS", entries)
    assert TestClient(application.create_app(), client=("::ffff:192.0.2.5", 5000)).get("/ping").status_code == expected

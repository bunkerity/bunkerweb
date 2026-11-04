"""Wizard proposes the bare IPv6 literal (the service name form) and never a truncated authority."""

import pytest


@pytest.mark.parametrize(
    "host,expected",
    [
        ("[2001:db8::1]:7000", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("[::1]:7000", "::1"),
        ("192.0.2.1:7000", "192.0.2.1"),
        ("ui.example.com:7000", "ui.example.com"),
        ("[2001:DB8::1]:7000", "2001:db8::1"),
        ("", "www.example.com"),
    ],
)
def test_setup_host_default(h, monkeypatch, host, expected):
    h.db.get_config.return_value = {"SERVER_NAME": ""}
    h.db.get_ui_user.return_value = None
    for name in ("PRO_LICENSE_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    response = h.client(None).get("/setup", headers={"Host": host})
    assert response.status_code == 200
    assert h.renders[-1][1]["server_name"] == expected

"""Aliases count once on the license path, including its database-error fallback."""

from unittest.mock import Mock

import pytest

from test_billable_service_number import PRO


@pytest.mark.parametrize("multisite,expected", [("no", 1), ("yes", 3)])
@pytest.mark.parametrize("fallback", [False, True])
def test_license_service_count(monkeypatch, multisite, expected, fallback):
    monkeypatch.setenv("MULTISITE", multisite)
    monkeypatch.setenv("SERVER_NAME", "a.example b.example c.example")
    db = Mock()
    if fallback:
        db.get_non_default_settings.side_effect = RuntimeError("database unavailable")
    else:
        db.get_non_default_settings.return_value = {"MULTISITE": multisite, "SERVER_NAME": "a.example b.example c.example"}
    assert PRO._billable_service_number(db) == expected


@pytest.mark.parametrize("fallback", [False, True])
def test_empty_single_site_counts_zero(monkeypatch, fallback):
    monkeypatch.setenv("MULTISITE", "no")
    monkeypatch.setenv("SERVER_NAME", "")
    db = Mock()
    if fallback:
        db.get_non_default_settings.side_effect = RuntimeError("database unavailable")
    else:
        db.get_non_default_settings.return_value = {"MULTISITE": "no", "SERVER_NAME": ""}
    assert PRO._billable_service_number(db) == 0

"""UB4-6: scheduling failures and global settings responses retain their HTTP contract."""

from unittest.mock import Mock

import pytest
from _api_http_helpers import ADMIN_HEADERS, router_client

import app.routers.global_settings as global_settings
import app.routers.jobs as jobs


@pytest.mark.parametrize("result, status", [("", 202), (None, 202), ("db down", 500)])
def test_job_scheduling_reports_database_failure(monkeypatch, result, status):
    database = Mock()
    database.checked_changes.return_value = result
    client = router_client(monkeypatch, jobs, database)
    response = client.post("/jobs/run", json={"jobs": [{"plugin": "dnsbl", "name": "dnsbl-download"}, {"plugin": "blacklist"}]}, headers=ADMIN_HEADERS)
    assert response.status_code == status, response.text
    assert response.json() == {"status": "error" if result else "success", "message": result or "Jobs scheduled"}
    database.checked_changes.assert_called_once_with(["config"], plugins_changes=["dnsbl", "blacklist"], value=True)


def test_empty_jobs_never_schedule_anything(monkeypatch):
    database = Mock()
    client = router_client(monkeypatch, jobs, database)
    response = client.post("/jobs/run", json={"jobs": []}, headers=ADMIN_HEADERS)
    assert response.status_code == 422, response.text
    database.checked_changes.assert_not_called()


def test_list_jobs_returns_database_metadata(monkeypatch):
    database = Mock()
    database.get_jobs.return_value = {"dnsbl-download": {"plugin_id": "dnsbl", "success": True}}
    client = router_client(monkeypatch, jobs, database)
    response = client.get("/jobs", headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "success", "jobs": database.get_jobs.return_value}
    database.get_jobs.assert_called_once_with()


@pytest.mark.parametrize(
    "result, status",
    [("read-only database", 400), ("setting already exists", 400), ("setting doesn't exist", 400), ("db down", 500), ("", 200), (set(), 200), ({"dnsbl"}, 200)],
)
def test_global_patch_maps_database_errors(monkeypatch, result, status):
    database = Mock()
    database.get_non_default_settings.return_value = {"LOG_LEVEL": {"method": "api", "value": "info"}}
    database.save_config.return_value = result
    client = router_client(monkeypatch, global_settings, database)
    response = client.patch("/global_settings", json={"HTTP_PORT": 8080}, headers=ADMIN_HEADERS)
    assert response.status_code == status, response.text
    assert response.json() == ({"status": "error", "message": result} if status != 200 else {"status": "success"})
    database.save_config.assert_called_once_with({"LOG_LEVEL": "info", "HTTP_PORT": "8080"}, "api", changed=True, skip_service_management=True)


@pytest.mark.parametrize("full", [False, True])
@pytest.mark.parametrize("methods", [False, True])
def test_global_get_full_and_methods(monkeypatch, full, methods):
    config = {
        "LOG_LEVEL": {"value": "notice", "method": "default"},
        "HTTP_PORT": {"value": "8080", "method": "api"},
        "USE_GZIP": {"value": "yes", "method": "default", "template": "low"},
    }
    database = Mock()
    database.get_config.return_value = config if methods or not full else {key: meta["value"] for key, meta in config.items()}
    client = router_client(monkeypatch, global_settings, database)
    response = client.get("/global_settings", params={"full": full, "methods": methods}, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    kept = config if full else {key: config[key] for key in ("HTTP_PORT", "USE_GZIP")}
    expected = kept if methods else {key: meta["value"] for key, meta in kept.items()}
    assert response.json() == {"status": "success", "settings": expected}
    database.get_config.assert_called_once_with(global_only=True, methods=methods if full else True)

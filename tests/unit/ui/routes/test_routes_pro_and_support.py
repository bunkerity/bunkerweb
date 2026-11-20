"""The /pro licence pages and the /support downloads (with their administrator gates)."""

import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


# --------------------------------------------------------------------------------------
# pro
# --------------------------------------------------------------------------------------
@pytest.fixture
def pro(h):
    h.db.get_services.return_value = [{"is_draft": False}, {"is_draft": True}, {"is_draft": False}]
    h.db.get_metadata.return_value = {"pro_expire": None}
    h.config.get_config.return_value = {"PRO_LICENSE_KEY": "abc"}
    h.db.set_metadata.return_value = ""
    h.db.checked_changes.return_value = ""
    return h.routes.pro


def test_pro_page_counts_online_and_draft_services(h, pro):
    h.client().get("/pro")

    context = h.renders[-1][1]
    assert (context["online_services"], context["draft_services"], context["pro_license_key"]) == (2, 1, "abc")
    assert context["pro_expires_in"] == "Unknown"


def test_pro_page_expiry_is_relative_to_the_current_utc_day(h, pro):
    h.db.get_metadata.return_value = {"pro_expire": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=10, hours=12)}

    h.client().get("/pro")

    assert "10 days" in h.renders[-1][1]["pro_expires_in"] or "11 days" in h.renders[-1][1]["pro_expires_in"]


def test_pro_page_expired_licence_is_unknown(h, pro):
    h.db.get_metadata.return_value = {"pro_expire": datetime.now(timezone.utc) - timedelta(days=3)}

    h.client().get("/pro")

    assert h.renders[-1][1]["pro_expires_in"] == "Unknown"


def test_pro_key_updates_the_global_setting_and_queues_the_result(h, pro):
    h.db.get_config.return_value = {}
    h.config.check_variables.return_value = {"PRO_LICENSE_KEY": "new"}
    h.config.edit_global_conf.return_value = ("", "")
    client = h.client()

    response = client.post("/pro/key", data={"PRO_LICENSE_KEY": "new"})

    h.config.edit_global_conf.assert_called_once_with({"PRO_LICENSE_KEY": "new"}, check_changes=True)
    assert "message=Updating+license+key" in response.headers["Location"]
    queued = [(item["content"], item["type"]) for item in h.data["TO_FLASH"]]
    assert ("The PRO license key was updated successfully.", "success") in queued
    assert h.data["PRO_LOADING"] is True
    assert "Checking license key." in _flashed(h, client)


def test_pro_key_error_from_the_config_layer_is_shown_as_an_error(h, pro):
    h.db.get_config.return_value = {}
    h.config.check_variables.return_value = {"PRO_LICENSE_KEY": "new"}
    h.config.edit_global_conf.return_value = ("Can't save: nope", True)

    h.client().post("/pro/key", data={"PRO_LICENSE_KEY": "new"})

    assert {"content": "Can't save: nope", "type": "error"} in h.data["TO_FLASH"]


def test_pro_key_equal_to_the_current_one_changes_nothing(h, pro):
    h.db.get_config.return_value = {}
    h.config.check_variables.return_value = {}
    client = h.client()

    response = client.post("/pro/key", data={"PRO_LICENSE_KEY": "same"})

    h.config.edit_global_conf.assert_not_called()
    assert response.headers["Location"].endswith("/pro")
    assert "The license key is the same as the current one." in _flashed(h, client)


def test_pro_key_rejects_an_empty_key(h, pro):
    client = h.client()

    client.post("/pro/key", data={"PRO_LICENSE_KEY": ""})

    h.config.check_variables.assert_not_called()
    assert "Invalid license key" in _flashed(h, client)


@pytest.mark.parametrize("path", ["/pro/key", "/pro/force-check", "/pro/force-update", "/pro/refresh-ui"])
def test_pro_writes_are_refused_in_read_only_mode(h, pro, path):
    h.db.readonly = True
    client = h.client()

    client.post(path, data={"PRO_LICENSE_KEY": "k"})

    h.db.set_metadata.assert_not_called()
    h.db.checked_changes.assert_not_called()
    h.config.edit_global_conf.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)


def test_force_check_schedules_the_pro_check(h, pro):
    response = h.client().post("/pro/force-check")

    h.db.set_metadata.assert_called_once_with({"last_pro_check": None})
    h.db.checked_changes.assert_called_once_with(changes=["config"], plugins_changes={"pro"}, value=True)
    assert h.data["PRO_LOADING"] is True and response.headers["Location"].endswith("/pro")


def test_force_check_stops_at_the_first_database_error(h, pro):
    h.db.set_metadata.return_value = "locked"
    client = h.client()

    client.post("/pro/force-check")

    h.db.checked_changes.assert_not_called()
    assert "locked" in _flashed(h, client) and "PRO_LOADING" not in h.data


def test_force_update_sets_the_force_flag_then_resets_the_date_check(h, pro):
    h.client().post("/pro/force-update")

    assert [call.args[0] for call in h.db.set_metadata.call_args_list] == [{"force_pro_update": True}, {"last_pro_check": None}]
    h.db.checked_changes.assert_called_once()


@pytest.mark.parametrize("failing_call", [1, 2])
def test_force_update_reports_each_database_error(h, pro, failing_call):
    h.db.set_metadata.side_effect = ["locked" if failing_call == 1 else "", "locked"]
    client = h.client()

    client.post("/pro/force-update")

    assert "locked" in _flashed(h, client)
    h.db.checked_changes.assert_not_called()


def test_refresh_ui_clears_the_reload_latch_and_flags_the_plugins(h, pro):
    h.data["IS_RELOADING_PLUGINS"] = True

    h.client().post("/pro/refresh-ui")

    assert h.data["IS_RELOADING_PLUGINS"] is False
    h.db.checked_changes.assert_called_once_with(changes=["ui_plugins"], value=True)


# --------------------------------------------------------------------------------------
# support
# --------------------------------------------------------------------------------------
@pytest.fixture
def support(h, monkeypatch):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com b.example.com"}
    h.config.get_plugins_settings.return_value = {}
    module = h.routes.support
    monkeypatch.setattr(module, "mask_settings", lambda config, settings: config.update({k: "***" for k in config if k.endswith("PASSWORD")}))
    return module


def test_support_page_lists_the_services(h, support):
    h.client().get("/support")

    assert h.renders[-1] == ("support.html", {"services": ["a.example.com", "b.example.com"]})


def test_support_config_masks_secrets_for_everyone_but_an_explicit_admin_request(h, support):
    h.db.get_config.return_value = {"API_PASSWORD": "hunter2", "KEEP": "x"}

    masked = h.client("viewer", admin=False).get("/support/config?mask_passwords=no")

    assert json.loads(masked.get_data()) == {"API_PASSWORD": "***", "KEEP": "x"}


def test_a_non_administrator_cannot_unmask_the_config(h, support):
    h.db.get_config.return_value = {"API_PASSWORD": "hunter2"}

    response = h.client("viewer", admin=False).get("/support/config?mask_passwords=no")

    assert "hunter2" not in response.get_data(as_text=True)


def test_an_administrator_can_ask_for_clear_values(h, support):
    h.db.get_config.return_value = {"API_PASSWORD": "hunter2"}

    response = h.client("root", admin=True).get("/support/config?mask_passwords=no")

    assert json.loads(response.get_data()) == {"API_PASSWORD": "hunter2"}
    assert response.headers["Content-Disposition"].endswith("bunkerweb_config.json")


def test_support_config_for_one_service(h, support):
    h.db.get_config.return_value = {"a.example.com_X": "1"}

    response = h.client().get("/support/config?service=a.example.com")

    h.db.get_config.assert_called_with(methods=True, with_drafts=True, service="a.example.com")
    assert response.headers["Content-Disposition"].endswith("a.example.com_config.json")


def test_support_config_unknown_service_is_a_404(h, support):
    response = h.client().get("/support/config?service=ghost.example.com")

    assert response.status_code == 404 and response.get_data(as_text=True) == "Service not found"


def test_support_logs_without_files_is_a_404(h, support, tmp_path, monkeypatch):
    monkeypatch.setattr(support, "Path", lambda *parts: tmp_path)

    response = h.client().get("/support/logs")

    assert response.status_code == 404 and response.get_data(as_text=True) == "No log files found"


def test_support_logs_zip_has_the_service_domains_redacted(h, support, tmp_path, monkeypatch):
    (tmp_path / "ui.log").write_text("GET https://a.example.com/login ok\nsecond line\n")
    monkeypatch.setattr(support, "Path", lambda *parts: tmp_path)

    response = h.client().get("/support/logs")

    assert response.mimetype == "application/zip"
    archive = ZipFile(BytesIO(response.get_data()))
    content = archive.read("ui.log").decode()
    assert "a.example.com" not in content and "second line" in content


def test_ui_bundle_is_for_administrators_only(h, support, monkeypatch):
    monkeypatch.setattr(support, "build_support_bundle", MagicMock(return_value=b"zip"))

    response = h.client("viewer", admin=False).get("/support/ui_bundle")

    assert response.status_code == 403
    support.build_support_bundle.assert_not_called()


def test_ui_bundle_assembles_the_report_for_an_administrator(h, support, monkeypatch):
    monkeypatch.setattr(support, "build_support_bundle", MagicMock(return_value=b"PK-bundle"))
    monkeypatch.setattr(support, "build_plugins_report", MagicMock(return_value={"plugins": []}))
    monkeypatch.setattr(support, "build_environment", MagicMock(return_value={"env": 1}))
    monkeypatch.setattr(support, "get_integration", lambda: "docker")
    monkeypatch.setattr(support, "alembic_revision", lambda: "rev1")
    h.db.get_plugins.return_value = []
    h.db.get_metadata.return_value = {}
    h.db.get_instances.return_value = []
    h.db.get_services.return_value = [1, 2]
    h.db.sql_engine.dialect.name = "sqlite"

    response = h.client("root", admin=True).get("/support/ui_bundle")

    assert response.get_data() == b"PK-bundle"
    assert response.headers["Content-Disposition"].startswith("attachment; filename=bunkerweb-ui-support-")
    kwargs = support.build_environment.call_args.kwargs
    assert (kwargs["service_count"], kwargs["db_dialect"], kwargs["db_revision"], kwargs["integration"]) == (2, "sqlite", "rev1", "docker")
    assert support.build_support_bundle.call_args.kwargs["plugins"] == {"plugins": []}

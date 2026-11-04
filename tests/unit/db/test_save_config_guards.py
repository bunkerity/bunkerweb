"""``save_config`` refusals and service lifecycle: what it must keep, drop or report.

A guard test proves the refusal (the stored rows are untouched, the warning is logged); each is paired with the
call that shows the same input being applied when the guard does not apply.
"""

import logging

import pytest
from sqlalchemy import func, select

from fixtures.seed import (
    add_custom_config_row,
    add_global_value,
    add_service,
    add_service_setting,
    add_setting,
    make_core_plugin,
    make_general_settings,
    session,
)
from model import Custom_configs, Global_values, Metadata, Services, Services_settings

pytestmark = pytest.mark.multiengine

SERVICES = "app1.example.com app2.example.com"


def _count(db, model, **filters):
    with session(db) as s:
        return s.scalar(select(func.count()).select_from(model).filter_by(**filters))


def _service(db, service_id):
    with session(db) as s:
        row = s.get(Services, service_id)
        return None if row is None else (row.method, row.is_draft)


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), make_core_plugin("alpha"), make_core_plugin("beta")])
    db.initialize_db("1.7.0", "Docker")
    return db


@pytest.fixture
def logs(db, caplog):
    db.logger.propagate = True
    caplog.set_level(logging.DEBUG, logger=db.logger.name)
    return caplog


def _messages(logs, level=None):
    return [r.getMessage() for r in logs.records if level is None or r.levelno == level]


def _publish(db, method="ui", server_name=SERVICES, **extra):
    # a service row exists once the config carries a non-default setting for it
    markers = {f"{service}_ALPHA_MS": "keepalive" for service in server_name.split()}
    config = {"MULTISITE": "yes", "SERVER_NAME": server_name} | markers | extra
    result = db.save_config(config, method)
    assert isinstance(result, set), result
    return result


class TestInputGuards:
    def test_read_only_mode_refuses_and_stores_nothing(self, seeded):
        seeded.readonly = True
        assert seeded.save_config({"ALPHA_GLOBAL": "x"}, "ui", skip_service_management=True) == "The database is read-only, the changes will not be saved"
        seeded.readonly = False
        assert seeded.get_config()["ALPHA_GLOBAL"] == "def"

    def test_a_truncated_pem_value_never_replaces_the_stored_one(self, seeded, logs):
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": "-----BEGIN CERTIFICATE-----\nMIIB"}, "ui", skip_service_management=True), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "def"
        assert any("Ignoring truncated PEM value for ALPHA_GLOBAL" in m for m in _messages(logs, logging.ERROR))
        complete = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----"
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": complete}, "ui", skip_service_management=True), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == complete

    def test_a_truncated_pem_is_also_dropped_from_the_explicit_key_set(self, seeded):
        add_global_value(seeded, setting_id="ALPHA_GLOBAL", value="owned-by-ui", method="ui")
        incoming = {"ALPHA_GLOBAL": "-----BEGIN KEY-----\nabc"}
        assert isinstance(seeded.save_config(incoming, "scheduler", skip_service_management=True, explicit_keys={"ALPHA_GLOBAL"}), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "owned-by-ui"

    def test_a_scheduler_pass_does_not_override_a_ui_value_unless_the_key_is_explicit(self, seeded):
        add_global_value(seeded, setting_id="ALPHA_GLOBAL", value="owned-by-ui", method="ui")
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": "from-env"}, "scheduler", skip_service_management=True), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "owned-by-ui"
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": "from-env"}, "scheduler", skip_service_management=True, explicit_keys={"ALPHA_GLOBAL"}), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "from-env"

    def test_an_explicitly_empty_server_name_never_clears_a_ui_owned_service_list(self, seeded):
        _publish(seeded, "ui", "app1.example.com")
        assert isinstance(seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "scheduler", explicit_keys={"SERVER_NAME"}), set)
        assert _service(seeded, "app1.example.com") == ("ui", False)

    def test_unknown_settings_are_ignored_in_both_modes(self, seeded, logs):
        assert isinstance(seeded.save_config({"NOT_A_SETTING": "x", "ALPHA_GLOBAL": "kept"}, "ui", skip_service_management=True), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "kept" and "NOT_A_SETTING" not in seeded.get_config()
        _publish(seeded, "ui", "app1.example.com", NOT_A_SETTING="x", **{"app1.example.com_ALSO_UNKNOWN": "y"})
        assert "NOT_A_SETTING" not in seeded.get_config()
        text = "\n".join(_messages(logs))
        assert "Setting NOT_A_SETTING does not exist" in text and "Setting ALSO_UNKNOWN does not exist" in text


class TestFileNames:
    def _file_setting(self, db):
        add_setting(db, "ALPHA_FILE", plugin_id="alpha", context="global", type="file")

    def _file_name(self, db):
        return db.get_config(methods=True)["ALPHA_FILE"]["file_name"]

    def test_a_file_name_is_stored_replaced_and_cleared_with_the_value(self, seeded):
        self._file_setting(seeded)
        assert isinstance(seeded.save_config({"ALPHA_FILE": "content"}, "ui", file_names={"ALPHA_FILE": " cert.pem "}, skip_service_management=True), set)
        assert self._file_name(seeded) == "cert.pem"
        assert isinstance(seeded.save_config({"ALPHA_FILE": "content"}, "ui", file_names={"ALPHA_FILE": "other.pem"}, skip_service_management=True), set)
        assert self._file_name(seeded) == "other.pem"
        # a changed value without file name metadata drops the stale file reference
        assert isinstance(seeded.save_config({"ALPHA_FILE": "edited"}, "ui", skip_service_management=True), set)
        assert self._file_name(seeded) == ""

    def test_an_empty_file_name_clears_the_reference(self, seeded):
        self._file_setting(seeded)
        assert isinstance(seeded.save_config({"ALPHA_FILE": "content"}, "ui", file_names={"ALPHA_FILE": "cert.pem"}, skip_service_management=True), set)
        assert isinstance(seeded.save_config({"ALPHA_FILE": "content"}, "ui", file_names={"ALPHA_FILE": ""}, skip_service_management=True), set)
        assert self._file_name(seeded) == ""

    def test_a_file_name_is_ignored_for_a_setting_that_is_not_a_file(self, seeded):
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": "x"}, "ui", file_names={"ALPHA_GLOBAL": "ignored.txt"}, skip_service_management=True), set)
        assert seeded.get_config(methods=True)["ALPHA_GLOBAL"]["file_name"] == ""


class TestServiceListGuards:
    def test_a_ui_save_without_server_name_is_refused_and_keeps_every_service(self, seeded, logs):
        _publish(seeded)
        before = seeded.get_services()
        result = seeded.save_config({"MULTISITE": "yes", "ALPHA_GLOBAL": "x"}, "ui")
        assert isinstance(result, set)
        assert sorted(s["id"] for s in seeded.get_services()) == sorted(s["id"] for s in before)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "def"
        assert any("skipping entire config save to prevent data loss" in m for m in _messages(logs, logging.WARNING))

    def test_a_service_dropped_from_a_non_empty_list_is_deleted_with_everything_it_owns(self, seeded):
        _publish(seeded)
        add_service_setting(seeded, service_id="app2.example.com", setting_id="BETA_MS", value="svc", method="ui")
        add_custom_config_row(seeded, service_id="app2.example.com", type="server_http", name="mine", method="ui")
        _publish(seeded, "ui", "app1.example.com")
        assert _service(seeded, "app2.example.com") is None and _service(seeded, "app1.example.com") == ("ui", False)
        assert _count(seeded, Services_settings, service_id="app2.example.com") == 0
        assert _count(seeded, Custom_configs, service_id="app2.example.com") == 0
        assert seeded.get_metadata()["custom_configs_changed"] is True

    def test_autoconf_with_an_empty_list_removes_services_only_when_all_of_them_are_its_own(self, seeded, logs):
        _publish(seeded, "autoconf", "auto1.example.com")
        add_service(seeded, "manual.example.com", method="manual")
        result = seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "autoconf")
        assert isinstance(result, set)
        assert _service(seeded, "auto1.example.com") == ("autoconf", False) and _service(seeded, "manual.example.com") is not None
        assert any("skipping entire config save to prevent data loss" in m for m in _messages(logs, logging.WARNING))
        with session(seeded) as s:
            s.query(Services).filter_by(id="manual.example.com").delete()
        assert isinstance(seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": ""}, "autoconf"), set)
        assert _service(seeded, "auto1.example.com") is None

    def test_cleanup_disabled_turns_a_removed_autoconf_service_into_a_draft_and_keeps_its_rows(self, seeded):
        _publish(seeded, "autoconf", "auto1.example.com auto2.example.com")
        add_service_setting(seeded, service_id="auto2.example.com", setting_id="BETA_MS", value="kept", method="autoconf")
        add_custom_config_row(seeded, service_id="auto2.example.com", type="server_http", name="mine", method="autoconf")
        result = seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "auto1.example.com"}, "autoconf", disable_cleanup=True)
        assert isinstance(result, set)
        assert _service(seeded, "auto2.example.com") == ("autoconf", True)
        assert _count(seeded, Services_settings, service_id="auto2.example.com", value="kept") == 1
        with session(seeded) as s:
            assert s.query(Custom_configs).filter_by(service_id="auto2.example.com").one().is_draft is True
        assert seeded.get_metadata()["custom_configs_changed"] is True
        assert [s["id"] for s in seeded.get_services()] == ["auto1.example.com"]

    def test_without_the_cleanup_flag_the_same_removal_deletes_the_service(self, seeded):
        _publish(seeded, "autoconf", "auto1.example.com auto2.example.com")
        add_service_setting(seeded, service_id="auto2.example.com", setting_id="BETA_MS", value="gone", method="autoconf")
        assert isinstance(seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "auto1.example.com"}, "autoconf"), set)
        assert _service(seeded, "auto2.example.com") is None
        assert _count(seeded, Services_settings, service_id="auto2.example.com") == 0

    def test_services_marked_as_drafts_are_stored_updated_and_published_again(self, seeded):
        _publish(seeded, "ui", "app1.example.com app2.example.com", **{"app2.example.com_IS_DRAFT": "yes"})
        assert _service(seeded, "app2.example.com") == ("ui", True) and _service(seeded, "app1.example.com") == ("ui", False)
        _publish(seeded, "ui", "app1.example.com app2.example.com", **{"app1.example.com_IS_DRAFT": "yes"})
        assert _service(seeded, "app1.example.com") == ("ui", True) and _service(seeded, "app2.example.com") == ("ui", False)
        _publish(seeded, "ui", "app1.example.com app2.example.com")
        assert _service(seeded, "app1.example.com") == ("ui", False)

    def test_a_draft_that_does_not_exist_yet_is_created_as_a_draft(self, seeded):
        _publish(seeded, "ui", "app1.example.com new.example.com", **{"new.example.com_IS_DRAFT": "yes"})
        assert _service(seeded, "new.example.com") == ("ui", True)

    def test_a_service_owned_by_another_method_is_left_alone(self, seeded):
        add_service(seeded, "manual.example.com", method="manual")
        _publish(seeded, "ui", "app1.example.com")
        assert _service(seeded, "manual.example.com") == ("manual", False)


class TestRenameInsideASave:
    def _setup(self, db):
        _publish(db, "ui", "old.example.com")
        add_service_setting(db, service_id="old.example.com", setting_id="BETA_MS", value="svc", method="ui")
        add_custom_config_row(db, service_id="old.example.com", type="server_http", name="existing", data=b"# old", method="ui")

    def test_the_service_and_its_rows_are_renamed_and_custom_configs_edited_in_one_save(self, seeded):
        self._setup(seeded)
        changes = [
            {"type": "server-http", "name": "existing", "config": {"data": "# edited", "method": "ui", "is_draft": True}},
            {"type": "server_http", "name": "added", "config": {"data": b"# added", "method": "ui"}},
        ]
        result = seeded.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": "new.example.com", "new.example.com_ALPHA_MS": "svc"},
            "ui",
            rename=("old.example.com", "new.example.com"),
            custom_config_changes=changes,
        )
        assert isinstance(result, set), result
        assert _service(seeded, "old.example.com") is None and _service(seeded, "new.example.com") == ("ui", False)
        assert _count(seeded, Custom_configs, service_id="old.example.com") == 0
        with session(seeded) as s:
            rows = {r.name: (r.data, r.is_draft) for r in s.query(Custom_configs).filter_by(service_id="new.example.com")}
        assert rows == {"existing": (b"# edited", True), "added": (b"# added", False)}

    def test_custom_config_changes_without_a_rename_are_refused(self, seeded):
        self._setup(seeded)
        message = seeded.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": "old.example.com"},
            "ui",
            custom_config_changes=[{"type": "http", "name": "x", "config": {"data": "", "method": "ui"}}],
        )
        assert message == "Custom config changes require a service rename"
        assert _count(seeded, Custom_configs, service_id="old.example.com", name="existing") == 1

    def test_a_rename_onto_an_existing_service_is_refused_and_nothing_moves(self, seeded):
        self._setup(seeded)
        add_service(seeded, "taken.example.com", method="ui")
        message = seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": "taken.example.com"}, "ui", rename=("old.example.com", "taken.example.com"))
        assert message == "Service taken.example.com already exists"
        assert _service(seeded, "old.example.com") is not None
        assert _count(seeded, Custom_configs, service_id="old.example.com") == 1

    def test_a_refusing_guard_reports_the_rename_as_not_done(self, seeded):
        self._setup(seeded)
        message = seeded.save_config({"MULTISITE": "yes", "ALPHA_GLOBAL": "x"}, "ui", rename=("old.example.com", "new.example.com"))
        assert message == "Configuration save aborted, service old.example.com was not renamed"
        assert _service(seeded, "old.example.com") is not None and _service(seeded, "new.example.com") is None


class TestSettingsAtTheirDefault:
    def test_a_global_value_set_back_to_its_default_is_removed(self, seeded):
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": "custom"}, "ui", skip_service_management=True), set)
        assert _count(seeded, Global_values, setting_id="ALPHA_GLOBAL") == 1
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": "def"}, "ui", skip_service_management=True), set)
        assert _count(seeded, Global_values, setting_id="ALPHA_GLOBAL") == 0
        assert seeded.get_config()["ALPHA_GLOBAL"] == "def"

    def test_a_service_value_set_back_to_the_inherited_default_is_removed(self, seeded):
        _publish(seeded, "ui", "app1.example.com", **{"app1.example.com_ALPHA_MS": "custom"})
        assert _count(seeded, Services_settings, service_id="app1.example.com", setting_id="ALPHA_MS") == 1
        _publish(seeded, "ui", "app1.example.com", **{"app1.example.com_ALPHA_MS": "msdef"})
        assert _count(seeded, Services_settings, service_id="app1.example.com", setting_id="ALPHA_MS") == 0


def test_the_metadata_flag_follows_the_service_changes(seeded):
    assert seeded.checked_changes(["custom_configs"], value=False) == ""
    _publish(seeded, "ui", "app1.example.com app2.example.com")
    assert seeded.get_metadata()["custom_configs_changed"] is False
    _publish(seeded, "ui", "app1.example.com")
    with session(seeded) as s:
        assert s.get(Metadata, 1).custom_configs_changed is True

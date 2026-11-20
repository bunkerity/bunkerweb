"""Instances, services, jobs and job cache: stored rows before and after, refusals, read-only mode.

The data-loss guards (empty autoconf list, protected custom configs) get a test that proves the refusal.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from fixtures.seed import (
    FIXED_DT,
    add_custom_config_row,
    add_jobs_cache_row,
    add_service,
    add_service_setting,
    seed_minimal,
    session,
)
from model import Custom_configs, Instances, Jobs_cache, Jobs_runs, Metadata, Services, Services_settings

pytestmark = pytest.mark.multiengine

READONLY = "The database is read-only, the changes will not be saved"


def _utc(value):
    """SQLite and MySQL hand back naive datetimes stored as UTC; PostgreSQL hands back aware ones."""
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _count(db, model, **filters):
    with session(db) as s:
        return s.scalar(select(func.count()).select_from(model).filter_by(**filters))


def _meta(db, field):
    with session(db) as s:
        return getattr(s.get(Metadata, 1), field)


def _clear_flags(db):
    assert db.checked_changes(value=False) == ""


@pytest.fixture
def seeded(db):
    seed_minimal(db)
    _clear_flags(db)
    return db


@pytest.fixture
def readonly(seeded):
    seeded.readonly = True
    return seeded


class TestInstances:
    def test_add_instance_rejects_an_invalid_hostname_before_touching_the_database(self, seeded):
        assert seeded.add_instance("not a host!", 5000, "bwapi", "manual") == "Invalid instance hostname: not a host!"
        assert _count(seeded, Instances) == 0

    def test_add_instance_defaults_and_flag(self, seeded):
        assert seeded.add_instance("bw-1", 5000, "bwapi", "manual") == ""
        assert seeded.get_instance("bw-1")["name"] == "manual instance"
        assert _meta(seeded, "instances_changed") is True and _meta(seeded, "last_instances_change") is not None

    def test_add_instance_without_the_changed_flag_leaves_the_metadata_alone(self, seeded):
        assert seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False, name="named") == ""
        assert seeded.get_instance("bw-1")["name"] == "named"
        assert _meta(seeded, "instances_changed") is False

    def test_add_instance_read_only(self, readonly):
        assert readonly.add_instance("bw-1", 5000, "bwapi", "manual") == READONLY
        assert _count(readonly, Instances) == 0

    def test_get_instance_filters_by_method(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual")
        assert seeded.get_instance("bw-1", method="manual")["hostname"] == "bw-1"
        assert seeded.get_instance("bw-1", method="autoconf") == {}

    def test_delete_instance_sets_the_flag_and_removes_only_that_row(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False)
        seeded.add_instance("bw-2", 5000, "bwapi", "manual", changed=False)
        assert seeded.delete_instance("bw-1") == ""
        assert [i["hostname"] for i in seeded.get_instances()] == ["bw-2"]
        assert _meta(seeded, "instances_changed") is True

    def test_delete_instance_without_flag_and_read_only(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False)
        assert seeded.delete_instance("bw-1", changed=False) == ""
        assert _meta(seeded, "instances_changed") is False
        seeded.add_instance("bw-3", 5000, "bwapi", "manual", changed=False)
        seeded.readonly = True
        assert seeded.delete_instance("bw-3") == READONLY
        assert seeded.delete_instances(["bw-3"]) == READONLY
        assert _count(seeded, Instances) == 1

    def test_delete_instances_removes_every_named_row(self, seeded):
        for host in ("a", "b", "c"):
            seeded.add_instance(host, 5000, "bwapi", "manual", changed=False)
        assert seeded.delete_instances(["a", "b", "ghost"]) == ""
        assert [i["hostname"] for i in seeded.get_instances()] == ["c"]
        assert _meta(seeded, "instances_changed") is True

    def test_delete_instances_without_flag(self, seeded):
        seeded.add_instance("a", 5000, "bwapi", "manual", changed=False)
        assert seeded.delete_instances(["a"], changed=False) == ""
        assert _meta(seeded, "instances_changed") is False

    def test_update_instances_replaces_the_method_scope_and_keeps_other_methods(self, seeded):
        seeded.add_instance("manual-1", 5000, "bwapi", "manual", changed=False)
        seeded.add_instance("auto-old", 5000, "bwapi", "autoconf", changed=False)
        incoming = [
            {
                "hostname": "auto-new",
                "name": "n",
                "env": {"API_HTTP_PORT": 6000, "API_LISTEN_HTTPS": "yes", "API_HTTPS_PORT": 6443, "API_SERVER_NAME": "x"},
                "health": False,
                "type": "container",
            }
        ]
        assert seeded.update_instances(incoming, "autoconf") == ""
        by_host = {i["hostname"]: i for i in seeded.get_instances()}
        assert set(by_host) == {"manual-1", "auto-new"}
        assert (by_host["auto-new"]["port"], by_host["auto-new"]["listen_https"], by_host["auto-new"]["https_port"]) == (6000, True, 6443)
        assert (by_host["auto-new"]["status"], by_host["auto-new"]["type"], by_host["auto-new"]["server_name"]) == ("down", "container", "x")
        assert _meta(seeded, "instances_changed") is True

    def test_update_instances_skips_entries_without_a_hostname(self, seeded):
        assert seeded.update_instances([{"env": {}}, {"hostname": "ok", "env": {}}], "manual", changed=False) == ""
        assert [i["hostname"] for i in seeded.get_instances()] == ["ok"]
        assert _meta(seeded, "instances_changed") is False

    def test_update_instances_rejects_an_invalid_hostname_and_keeps_the_rows(self, seeded):
        seeded.add_instance("keep", 5000, "bwapi", "manual", changed=False)
        assert seeded.update_instances([{"hostname": "bad host!", "env": {}}], "manual") == "Invalid instance hostname: bad host!"
        assert [i["hostname"] for i in seeded.get_instances()] == ["keep"]

    def test_the_empty_autoconf_list_guard_logs_and_keeps_the_rows(self, seeded, caplog):
        import logging

        seeded.add_instance("auto-1", 5000, "bwapi", "autoconf", changed=False)
        seeded.logger.propagate = True
        with caplog.at_level(logging.WARNING, logger=seeded.logger.name):
            assert seeded.update_instances([], "autoconf") == ""
        assert [i["hostname"] for i in seeded.get_instances()] == ["auto-1"]
        assert any("skipping deletion to prevent data loss" in r.getMessage() for r in caplog.records)

    def test_an_empty_list_for_another_method_is_a_real_wipe(self, seeded):
        seeded.add_instance("m-1", 5000, "bwapi", "manual", changed=False)
        assert seeded.update_instances([], "manual") == ""
        assert seeded.get_instances() == []

    def test_update_instances_updates_in_place_an_instance_of_another_method(self, seeded):
        seeded.add_instance("shared", 5000, "bwapi", "manual", changed=False)
        incoming = [{"hostname": "shared", "name": "renamed", "env": {"API_HTTP_PORT": 7000}, "method": "autoconf"}]
        assert seeded.update_instances(incoming, "autoconf") == ""
        row = seeded.get_instance("shared")
        assert (row["name"], row["port"], row["method"], row["status"]) == ("renamed", 7000, "autoconf", "up")

    def test_update_instances_read_only(self, readonly):
        assert readonly.update_instances([], "manual") == READONLY

    def test_update_instance_status_refreshes_last_seen_unless_down(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False)
        before = seeded.get_instance("bw-1")["last_seen"]
        assert seeded.update_instance("bw-1", "down") == ""
        row = seeded.get_instance("bw-1")
        assert row["status"] == "down" and row["last_seen"] == before
        assert seeded.update_instance("bw-1", "up") == ""
        assert seeded.get_instance("bw-1")["status"] == "up"
        assert seeded.get_instance("bw-1")["last_seen"] >= before

    def test_update_instance_missing_and_read_only(self, seeded):
        assert seeded.update_instance("ghost", "up") == "Instance ghost does not exist, will not be updated."
        seeded.readonly = True
        assert seeded.update_instance("ghost", "up") == READONLY

    def test_update_instance_fields_changes_only_the_given_fields(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False, name="orig")
        assert seeded.update_instance_fields("bw-1", port=6000, listen_https=True, https_port=6443, server_name="x", method="ui") == ""
        row = seeded.get_instance("bw-1")
        assert (row["name"], row["port"], row["listen_https"], row["https_port"], row["server_name"], row["method"]) == ("orig", 6000, True, 6443, "x", "ui")
        assert _meta(seeded, "instances_changed") is True

    def test_update_instance_fields_name_and_missing_host(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False)
        assert seeded.update_instance_fields("bw-1", name="new", changed=False) == ""
        assert seeded.get_instance("bw-1")["name"] == "new" and _meta(seeded, "instances_changed") is False
        assert seeded.update_instance_fields("ghost", name="x") == "Instance ghost does not exist, will not be updated."

    def test_update_instance_fields_with_nothing_to_change_still_flags(self, seeded):
        seeded.add_instance("bw-1", 5000, "bwapi", "manual", changed=False)
        assert seeded.update_instance_fields("bw-1") == ""
        assert _meta(seeded, "instances_changed") is True

    def test_update_instance_fields_read_only(self, readonly):
        assert readonly.update_instance_fields("bw-1", name="x") == READONLY


class TestDeleteServices:
    def _populate(self, db):
        add_service(db, "app2.example.com")
        for service in ("app1.example.com", "app2.example.com"):
            add_service_setting(db, service_id=service, setting_id="SECURITY_MODE", value="detect")
            add_custom_config_row(db, service_id=service, name=f"cfg-{service}")
            add_jobs_cache_row(db, service_id=service, file_name=f"cache-{service}")

    def test_the_named_services_and_their_rows_go_and_the_others_stay(self, seeded):
        self._populate(seeded)
        assert seeded.delete_services(["app1.example.com"]) == ""
        assert _count(seeded, Services, id="app1.example.com") == 0 and _count(seeded, Services, id="app2.example.com") == 1
        for model in (Services_settings, Custom_configs, Jobs_cache):
            assert _count(seeded, model, service_id="app1.example.com") == 0
            assert _count(seeded, model, service_id="app2.example.com") == 1
        assert _meta(seeded, "custom_configs_changed") is True and _meta(seeded, "last_custom_configs_change") is not None

    def test_an_empty_id_list_changes_nothing(self, seeded):
        self._populate(seeded)
        assert seeded.delete_services([]) == ""
        assert _count(seeded, Services) == 2 and _meta(seeded, "custom_configs_changed") is False

    def test_unknown_ids_are_ignored(self, seeded):
        self._populate(seeded)
        assert seeded.delete_services(["ghost"]) == ""
        assert _count(seeded, Services) == 2

    def test_read_only_mode_refuses_and_keeps_every_row(self, readonly):
        self._populate(readonly)
        assert readonly.delete_services(["app1.example.com"]) == READONLY
        assert _count(readonly, Services) == 2 and _count(readonly, Custom_configs) == 2


class TestRenameService:
    def _populate(self, db):
        add_service_setting(db, service_id="app1.example.com", setting_id="SECURITY_MODE", value="detect")
        add_custom_config_row(db, service_id="app1.example.com", name="cfg")
        add_jobs_cache_row(db, service_id="app1.example.com", file_name="cache")

    def test_everything_the_service_owns_moves_with_it(self, seeded):
        self._populate(seeded)
        assert seeded.rename_service(" app1.example.com ", " renamed.example.com ") == ""
        assert _count(seeded, Services, id="app1.example.com") == 0 and _count(seeded, Services, id="renamed.example.com") == 1
        for model in (Services_settings, Custom_configs, Jobs_cache):
            assert _count(seeded, model, service_id="app1.example.com") == 0
            assert _count(seeded, model, service_id="renamed.example.com") == 1
        assert _meta(seeded, "custom_configs_changed") is True

    def test_refusals_change_nothing(self, seeded):
        self._populate(seeded)
        add_service(seeded, "other.example.com")
        assert seeded.rename_service("", "x") == "Both the current and new service names are required"
        assert seeded.rename_service("app1.example.com", "  ") == "Both the current and new service names are required"
        assert seeded.rename_service("app1.example.com", "app1.example.com") == ""
        assert seeded.rename_service("ghost.example.com", "x.example.com") == "Service ghost.example.com doesn't exist"
        assert seeded.rename_service("app1.example.com", "other.example.com") == "Service other.example.com already exists"
        assert _count(seeded, Services, id="app1.example.com") == 1
        assert _count(seeded, Custom_configs, service_id="app1.example.com") == 1

    def test_read_only_mode_refuses(self, readonly):
        assert readonly.rename_service("app1.example.com", "x.example.com") == READONLY
        assert _count(readonly, Services, id="app1.example.com") == 1

    def test_the_row_helper_checks_its_own_inputs_inside_a_transaction(self, seeded):
        with session(seeded) as s:
            assert seeded._rename_service_rows(s, "", "x") == "Both the current and new service names are required"
            assert seeded._rename_service_rows(s, "ghost", "x") == "Service ghost doesn't exist"


class TestDeleteCustomConfigs:
    def _rows(self, db):
        add_custom_config_row(db, service_id=None, type="http", name="ui-global", method="ui")
        add_custom_config_row(db, service_id="app1.example.com", type="server_http", name="api-one", method="api")
        add_custom_config_row(db, service_id=None, type="http", name="file-owned", method="manual")

    def test_ui_and_api_rows_go_and_manual_ones_are_reported_protected(self, seeded):
        self._rows(seeded)
        keys = {(None, "http", "ui-global"), ("app1.example.com", "server-http", "api-one"), ("global", "http", "file-owned"), (None, "http", "ghost")}
        message, deleted, protected = seeded.delete_custom_configs(keys)
        assert message == ""
        assert deleted == {(None, "http", "ui-global"), ("app1.example.com", "server_http", "api-one")}
        assert protected == {(None, "http", "file-owned")}
        assert _count(seeded, Custom_configs) == 1 and _count(seeded, Custom_configs, name="file-owned") == 1
        assert _meta(seeded, "custom_configs_changed") is True

    def test_nothing_deleted_leaves_the_flag_down(self, seeded):
        self._rows(seeded)
        message, deleted, protected = seeded.delete_custom_configs({(None, "http", "file-owned")})
        assert (message, deleted, protected) == ("", set(), {(None, "http", "file-owned")})
        assert _meta(seeded, "custom_configs_changed") is False

    @pytest.mark.parametrize(
        "key",
        [("only", "two"), "not-a-tuple", (5, "http", "n"), (None, "", "n"), (None, "http", ""), (None, 3, "n"), (None, "http", None)],
    )
    def test_a_malformed_key_is_refused_before_any_delete(self, seeded, key):
        self._rows(seeded)
        message, deleted, protected = seeded.delete_custom_configs({key} if not isinstance(key, str) else {key})
        assert message.startswith("Invalid custom config key") and deleted == set() and protected == set()
        assert _count(seeded, Custom_configs) == 3

    def test_read_only_mode_refuses(self, readonly):
        self._rows(readonly)
        message, deleted, protected = readonly.delete_custom_configs({(None, "http", "ui-global")})
        assert message == READONLY and deleted == set() and protected == set()
        assert _count(readonly, Custom_configs) == 3

    def test_a_database_error_rolls_back_and_reports_the_error(self, seeded, monkeypatch):
        self._rows(seeded)
        original = seeded._db_session

        class Boom:
            def __init__(self, ctx):
                self.ctx = ctx

            def __enter__(self):
                session_ = self.ctx.__enter__()
                monkeypatch.setattr(session_, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
                return session_

            def __exit__(self, *exc):
                return self.ctx.__exit__(*exc)

        monkeypatch.setattr(seeded, "_db_session", lambda: Boom(original()))
        message, deleted, protected = seeded.delete_custom_configs({(None, "http", "ui-global")})
        assert message == "commit failed" and deleted == set() and protected == set()
        monkeypatch.undo()
        assert _count(seeded, Custom_configs, name="ui-global") == 1


class TestJobRunsAndSessions:
    def test_add_job_run_stores_the_row_and_defaults_the_end_date(self, seeded):
        assert seeded.add_job_run("testjob", True, FIXED_DT) == ""
        with session(seeded) as s:
            run = s.scalars(select(Jobs_runs).filter_by(job_name="testjob")).one()
            assert run.success is True and run.end_date is not None

    def test_add_job_run_with_explicit_end_date_and_read_only(self, seeded):
        end = FIXED_DT + timedelta(minutes=5)
        assert seeded.add_job_run("testjob", False, FIXED_DT, end) == ""
        with session(seeded) as s:
            assert s.scalars(select(Jobs_runs).filter_by(job_name="testjob")).one().success is False
        seeded.readonly = True
        assert seeded.add_job_run("testjob", True, FIXED_DT) == READONLY
        assert _count(seeded, Jobs_runs) == 1

    def test_the_oldest_runs_are_trimmed_to_the_cap(self, seeded):
        for index in range(5):
            seeded.add_job_run("testjob", True, FIXED_DT, FIXED_DT + timedelta(minutes=index))
        assert seeded.cleanup_jobs_runs_excess(3) == "Removed 2 excess jobs runs"
        with session(seeded) as s:
            kept = sorted(_utc(run.end_date) for run in s.scalars(select(Jobs_runs)))
        assert kept == [FIXED_DT + timedelta(minutes=index) for index in (2, 3, 4)]

    def test_under_the_cap_nothing_is_removed(self, seeded):
        seeded.add_job_run("testjob", True, FIXED_DT)
        assert seeded.cleanup_jobs_runs_excess(10) == "Removed 0 excess jobs runs"
        assert _count(seeded, Jobs_runs) == 1

    def test_expired_ui_sessions_are_removed_by_their_last_activity(self, seeded):
        from fixtures.seed import add_ui_user
        from model import UserSessions

        add_ui_user(seeded, "bob")
        now = datetime.now(timezone.utc)
        with session(seeded) as s:
            s.add(UserSessions(user_name="bob", ip="1.1.1.1", user_agent="", creation_date=now - timedelta(days=40), last_activity=now - timedelta(days=40)))
            s.add(UserSessions(user_name="bob", ip="2.2.2.2", user_agent="", creation_date=now - timedelta(days=40), last_activity=now))
        assert seeded.cleanup_expired_ui_sessions(30) == "Removed 1 expired UI user sessions"
        assert [s["ip"] for s in seeded.get_ui_user_sessions("bob")] == ["2.2.2.2"]
        seeded.readonly = True
        assert seeded.cleanup_expired_ui_sessions(0) == READONLY


class TestJobCache:
    def test_delete_returns_none_for_no_match_and_empty_string_for_a_deletion(self, seeded):
        add_jobs_cache_row(seeded, file_name="a.txt")
        assert seeded.delete_job_cache("zzz", job_name="testjob") is None
        assert seeded.delete_job_cache("a.txt", job_name="testjob") == ""
        assert _count(seeded, Jobs_cache) == 0

    def test_delete_is_scoped_by_service_and_plugin(self, seeded):
        add_jobs_cache_row(seeded, file_name="a.txt", service_id="app1.example.com")
        add_jobs_cache_row(seeded, file_name="a.txt", service_id=None)
        assert seeded.delete_job_cache("a.txt", job_name="testjob", plugin_id="other-plugin") is None
        assert _count(seeded, Jobs_cache) == 2
        assert seeded.delete_job_cache("a.txt", job_name="testjob", service_id="app1.example.com", plugin_id="general") == ""
        assert _count(seeded, Jobs_cache) == 1 and _count(seeded, Jobs_cache, service_id=None) == 1

    def test_delete_defaults_the_job_name_to_the_running_script(self, seeded, monkeypatch):
        import Database as database_module

        add_jobs_cache_row(seeded, file_name="a.txt")
        monkeypatch.setattr(database_module, "argv", ["testjob.py"])
        assert seeded.delete_job_cache("a.txt") == ""
        assert _count(seeded, Jobs_cache) == 0

    def test_delete_read_only(self, readonly):
        add_jobs_cache_row(readonly, file_name="a.txt")
        assert readonly.delete_job_cache("a.txt", job_name="testjob") == READONLY
        assert _count(readonly, Jobs_cache) == 1

    def test_get_job_cache_file_returns_data_info_or_both(self, seeded):
        add_jobs_cache_row(seeded, file_name="a.txt", data=b"payload")
        assert seeded.get_job_cache_file("testjob", "a.txt") == b"payload"
        info = seeded.get_job_cache_file("testjob", "a.txt", with_info=True, with_data=False)
        assert info["checksum"] == "seedsum" and isinstance(info["last_update"], float) and info["last_update"] > 0 and "data" not in info
        both = seeded.get_job_cache_file("testjob", "a.txt", with_info=True)
        assert both["data"] == b"payload" and both["checksum"] == "seedsum"

    def test_get_job_cache_file_info_carries_the_stored_names(self, seeded):
        # Callers that gate on the name (the API and UI cache routes) classify these, not the spelling they asked with:
        # a case-insensitive collation resolves variants to the stored row.
        add_jobs_cache_row(seeded, file_name="a.txt", data=b"payload")
        for kwargs in ({}, {"plugin_id": "general"}):
            for data_kwargs in ({"with_data": True}, {"with_data": False}):
                info = seeded.get_job_cache_file("testjob", "a.txt", with_info=True, **data_kwargs, **kwargs)
                assert (info["file_name"], info["job_name"], info["plugin_id"]) == ("a.txt", "testjob", "general")
        assert seeded.get_job_cache_file("testjob", "a.txt", with_info=False, with_data=True) == b"payload"

    def test_get_job_cache_file_misses(self, seeded):
        add_jobs_cache_row(seeded, file_name="a.txt")
        assert seeded.get_job_cache_file("testjob", "missing") is None
        assert seeded.get_job_cache_file("testjob", "a.txt", plugin_id="other-plugin") is None
        assert seeded.get_job_cache_file("testjob", "a.txt", plugin_id="general") == b"x"

    def test_get_job_cache_file_for_a_service_scoped_row(self, seeded):
        add_jobs_cache_row(seeded, file_name="a.txt", service_id="app1.example.com", data=b"svc")
        assert seeded.get_job_cache_file("testjob", "a.txt") is None
        assert seeded.get_job_cache_file("testjob", "a.txt", service_id="app1.example.com") == b"svc"

    def test_a_never_updated_row_reports_never(self, seeded):
        with session(seeded) as s:
            s.add(Jobs_cache(job_name="testjob", file_name="never", data=b"d", last_update=None, checksum=None))
        assert seeded.get_job_cache_file("testjob", "never", with_info=True)["last_update"] == "Never"
        assert seeded.get_jobs_cache_files()[0]["last_update"] == "Never"

    def test_list_filters_by_job_and_plugin_and_can_drop_the_data(self, seeded):
        add_jobs_cache_row(seeded, file_name="a.txt", data=b"aa")
        add_jobs_cache_row(seeded, file_name="b.txt", service_id="app1.example.com", data=b"bb")
        rows = {(r["file_name"], r["service_id"]): r for r in seeded.get_jobs_cache_files()}
        assert rows[("a.txt", None)]["data"] == b"aa" and rows[("b.txt", "app1.example.com")]["plugin_id"] == "general"
        assert all("data" not in r for r in seeded.get_jobs_cache_files(with_data=False))
        assert len(seeded.get_jobs_cache_files(job_name="testjob")) == 2 and seeded.get_jobs_cache_files(job_name="other") == []
        assert len(seeded.get_jobs_cache_files(plugin_id="general")) == 2 and seeded.get_jobs_cache_files(plugin_id="other") == []

    def test_data_job_name_loads_the_data_of_that_job_only(self, seeded):
        from model import Jobs

        with session(seeded) as s:
            s.add(Jobs(name="otherjob", plugin_id="general", file_name="o.py", every="hour"))
        add_jobs_cache_row(seeded, job_name="testjob", file_name="a.txt", data=b"aa")
        add_jobs_cache_row(seeded, job_name="otherjob", file_name="o.txt", data=b"oo")
        rows = {r["job_name"]: r for r in seeded.get_jobs_cache_files(data_job_name="otherjob")}
        assert rows["otherjob"]["data"] == b"oo" and "data" not in rows["testjob"]

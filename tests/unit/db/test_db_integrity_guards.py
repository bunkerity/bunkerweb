"""Data-loss and bounded connection-recovery regressions from the dev DB coverage wave."""

from copy import deepcopy
from datetime import timedelta
from threading import Lock, RLock, Thread

import pytest
from sqlalchemy import event, insert, select

import Database as database_module
from db_methods import common
from fixtures.seed import (
    FIXED_DT,
    add_global_value,
    add_service,
    add_service_setting,
    make_core_plugin,
    make_external_plugin,
    make_general_settings,
    seed_minimal,
    session,
)
from model import Global_values, Jobs_runs, Services_settings, Settings, Template_settings


def test_removed_setting_leaves_no_stored_values(db):
    plugin = make_core_plugin()
    assert db.init_tables([make_general_settings(), deepcopy(plugin)]) == (True, "")
    add_service(db, "site.example.com")
    add_global_value(db, setting_id="TESTPLUGIN_MS", value="global", method="ui")
    add_service_setting(db, service_id="site.example.com", setting_id="TESTPLUGIN_MS", value="service", method="ui")
    assert (
        db.create_template("saved", name="Saved", settings={"TESTPLUGIN_MS": "template"}, steps=[{"title": "S", "subtitle": "", "settings": ["TESTPLUGIN_MS"]}])
        == ""
    )
    plugin["settings"].pop("TESTPLUGIN_MS")

    assert db.init_tables([make_general_settings(), plugin]) == (True, "")

    with session(db) as s:
        assert s.get(Settings, "TESTPLUGIN_MS") is None
        for model in (Global_values, Services_settings, Template_settings):
            assert s.scalars(select(model).filter_by(setting_id="TESTPLUGIN_MS")).first() is None, model.__name__


def test_renamed_crs_setting_preserves_values_and_ownership(db):
    old_id, new_id = "MODSECURITY_CRS_PLUGIN_URLS", "MODSECURITY_CRS_PLUGINS"
    spec = {"id": "old-crs-urls", "context": "multisite", "default": "", "help": "h", "label": "L", "regex": "^.*$", "type": "text", "multiple": "crs"}
    plugin = make_core_plugin("modsecurity", settings={old_id: spec})
    assert db.init_tables([make_general_settings(), plugin]) == (True, "")
    add_service(db, "site.example.com")
    with session(db) as s:
        s.add(Global_values(setting_id=old_id, suffix=2, value="global", method="ui"))
        s.add(Services_settings(service_id="site.example.com", setting_id=old_id, suffix=3, value="service", method="api"))
    plugin = make_core_plugin("modsecurity", settings={new_id: spec | {"id": "new-crs-plugins"}})

    assert db.init_tables([make_general_settings(), plugin]) == (True, "")

    with session(db) as s:
        assert s.get(Settings, old_id) is None
        assert list(s.execute(select(Global_values.setting_id, Global_values.suffix, Global_values.value, Global_values.method))) == [
            (new_id, 2, "global", "ui")
        ]
        assert list(s.execute(select(Services_settings.setting_id, Services_settings.suffix, Services_settings.value, Services_settings.method))) == [
            (new_id, 3, "service", "api")
        ]


@pytest.mark.parametrize("fallback", [False, True], ids=["readonly-error", "connection-fallback"])
def test_session_recovery_does_not_deadlock(db, monkeypatch, fallback):
    # A failed bounded probe must not leave the process-wide lock held for later tests.
    monkeypatch.setattr(database_module, "LOCK", Lock() if isinstance(common.LOCK, type(Lock())) else RLock())
    error = ConnectionRefusedError("connection refused") if fallback else RuntimeError("attempt to write a readonly database")
    if fallback:
        db.database_uri_readonly = db.database_uri
    outcome = []

    def fail_session():
        try:
            with db._db_session():
                raise error
        except BaseException as caught:
            outcome.append(caught)

    thread = Thread(target=fail_session, daemon=True)
    thread.start()
    thread.join(3)
    assert not thread.is_alive(), "_db_session holds LOCK while retry_connection acquires it again"
    assert outcome == [error]
    assert db.readonly is True
    with db._db_session() as s:
        assert s.scalar(select(1)) == 1


def test_deleting_pro_plugin_flags_pro_reload(db):
    seed_minimal(db)
    assert db.update_external_plugins([make_external_plugin("proplugin")], _type="pro") == ""
    assert db.checked_changes(["pro_plugins", "ui_plugins"], value=False) == ""

    assert db.delete_plugin("proplugin", "manual") == ""

    metadata = db.get_metadata()
    assert metadata["pro_plugins_changed"] is True
    assert metadata["reload_ui_plugins"] is True


def test_pruning_uses_primary_key_deletes_and_keeps_new_runs(db):
    seed_minimal(db)
    for offset in range(5):
        date = FIXED_DT + timedelta(minutes=offset)
        assert db.add_job_run("testjob", True, date, date) == ""
    deletes = []

    def record_delete(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("DELETE FROM bw_jobs_runs"):
            deletes.append(statement)

    event.listen(db.sql_engine, "before_cursor_execute", record_delete)
    try:
        assert db.cleanup_jobs_runs_excess(2) == "Removed 3 excess jobs runs"
    finally:
        event.remove(db.sql_engine, "before_cursor_execute", record_delete)
    with session(db) as s:
        assert list(s.scalars(select(Jobs_runs.id).order_by(Jobs_runs.id))) == [4, 5]
    assert deletes and all(" IN (" not in sql and "id = " in sql for sql in deletes)


def test_pruning_with_concurrent_insert_under_snapshot_isolation(db, db_engine):
    if db_engine != "mariadb":
        pytest.skip("MariaDB error 1020 is specific to innodb_snapshot_isolation")
    seed_minimal(db)
    for offset in range(5):
        date = FIXED_DT + timedelta(minutes=offset)
        assert db.add_job_run("testjob", True, date, date) == ""
    with db.sql_engine.connect() as conn:
        conn.exec_driver_sql("SET SESSION innodb_snapshot_isolation=ON")
    inserted = []

    def insert_between_select_and_delete(_conn, _cursor, statement, _parameters, _context, _executemany):
        if not inserted and statement.startswith("DELETE FROM bw_jobs_runs"):
            inserted.append(True)
            with db.sql_engine.begin() as writer:
                writer.execute(insert(Jobs_runs).values(job_name="testjob", success=True, start_date=FIXED_DT, end_date=FIXED_DT + timedelta(days=1)))

    event.listen(db.sql_engine, "before_cursor_execute", insert_between_select_and_delete)
    try:
        assert db.cleanup_jobs_runs_excess(2) == "Removed 3 excess jobs runs"
    finally:
        event.remove(db.sql_engine, "before_cursor_execute", insert_between_select_and_delete)
    assert inserted == [True]
    with session(db) as s:
        assert list(s.scalars(select(Jobs_runs.id).order_by(Jobs_runs.id))) == [4, 5, 6]

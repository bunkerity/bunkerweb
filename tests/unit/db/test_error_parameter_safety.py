"""Bound values must stay out of real SQLAlchemy failures returned for logging."""

import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fixtures.seed import add_setting, seed_minimal

SECRET = "dummy-bound-value-must-not-reach-logs"


@pytest.mark.parametrize("retry", [False, True], ids=["initial", "reconnected"])
@pytest.mark.parametrize("operation", ["settings", "custom-configs"])
def test_failed_save_hides_bound_values(db, retry, operation, caplog):
    seed_minimal(db)
    if retry:
        db.retry_connection(log=False)
    if operation == "settings":
        add_setting(db, "API_TOKEN")
        table, column = "bw_global_values", "value"
    else:
        table, column = "bw_custom_configs", "data"
    with db.sql_engine.begin() as conn:
        conn.execute(text(f"CREATE TRIGGER reject_test_secret BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'test write rejected'); END"))
    if operation == "settings":
        error = db.save_config({"API_TOKEN": SECRET}, "autoconf", changed=False, skip_service_management=True)
    else:
        error = db.save_custom_configs([{"value": SECRET, "exploded": (None, "http", "token")}], "autoconf", changed=False)
    assert isinstance(error, str) and "test write rejected" in error
    with caplog.at_level(logging.ERROR):
        logging.getLogger("autoconf-error-boundary").error("Can't save %s in database: %s", operation, error)
    assert SECRET not in caplog.text
    assert "SQL parameters hidden" in error
    with db.sql_engine.connect() as conn:
        assert conn.execute(text(f"SELECT {column} FROM {table}")).all() == []


def test_engine_reconnection_cannot_disable_parameter_hiding(db):
    db.retry_connection(log=False, hide_parameters=False)
    with db.sql_engine.begin() as conn:
        conn.execute(text("CREATE TABLE secret_guard (value TEXT UNIQUE)"))
        conn.execute(text("INSERT INTO secret_guard VALUES (:value)"), {"value": SECRET})
    with db.sql_engine.begin() as conn, pytest.raises(IntegrityError) as raised:
        conn.execute(text("INSERT INTO secret_guard VALUES (:value)"), {"value": SECRET})
    assert SECRET not in str(raised.value)


@pytest.mark.parametrize("method", ["ui", "api", "manual"])
def test_empty_manual_authorization_cannot_bypass_other_owners(db, method):
    seed_minimal(db)
    assert db.save_custom_configs([{"type": "http", "name": "only", "data": "# retained", "method": method}], method) == ""
    assert db.save_custom_configs([], method)
    result = db.save_custom_configs([], method, allow_empty_manual=True)
    if method == "manual":
        assert result == ""
        assert db.get_custom_configs() == []
    else:
        assert result
        assert db.get_custom_config("http", "only")["data"] == b"# retained"

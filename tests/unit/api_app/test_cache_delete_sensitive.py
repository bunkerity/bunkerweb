"""API cache deletion resolves, authorizes and deletes the same rows in one transaction, on a real database.

The lookup follows the database collation (MariaDB/MySQL: case-insensitive), so a request can match rows it did not spell. SQLite
compares `=` as binary unless the column says otherwise: the cache table is rebuilt with the NOCASE collation those engines give
every string column. The route-level behaviour (status codes, who counts as admin) is in test_sensitive_cache.py.
"""

import pytest
from sqlalchemy import text

import _api_http_helpers  # noqa: F401  (prepares the Biscuit key files before app imports)
import app.routers.cache as cache_mod
from fixtures.seed import add_jobs_cache_row, session
from model import Jobs, Plugins  # type: ignore


@pytest.fixture
def nocase_db(db):
    with session(db) as s:
        s.add(Plugins(id="ui_sso", name="SSO", description="d", version="1.0"))
        s.add(Plugins(id="p", name="P", description="d", version="1.0"))
        s.flush()
        s.add_all(
            [Jobs(name="ui-sso-secret", plugin_id="ui_sso", file_name="x.py", every="hour"), Jobs(name="j", plugin_id="p", file_name="j.py", every="hour")]
        )
    with db.sql_engine.begin() as connection:
        connection.execute(text("DROP TABLE bw_jobs_cache"))
        connection.execute(
            text(
                "CREATE TABLE bw_jobs_cache (id INTEGER PRIMARY KEY AUTOINCREMENT, job_name VARCHAR(128) NOT NULL, service_id VARCHAR(256), "
                "file_name VARCHAR(256) COLLATE NOCASE NOT NULL, data BLOB, last_update DATETIME, checksum VARCHAR(128))"
            )
        )
    return db


def _names(db):
    with db.sql_engine.connect() as connection:
        return sorted(row[0] for row in connection.execute(text("SELECT file_name FROM bw_jobs_cache")))


def _delete(db, name, *, job, plugin, admin):
    return cache_mod._delete_cache_rows(db, name, job_name=job, service_id=None, plugin_id=plugin, admin=admin)


def test_a_collation_match_cannot_carry_a_sensitive_row_along(nocase_db):
    # `Secret` is not sensitive (the classifier is exact), the NOCASE column matches `secret` too, which is.
    add_jobs_cache_row(nocase_db, job_name="ui-sso-secret", file_name="Secret", data=b"public")
    add_jobs_cache_row(nocase_db, job_name="ui-sso-secret", file_name="secret", data=b"PLACEHOLDER-BYTES")

    assert _delete(nocase_db, "Secret", job="ui-sso-secret", plugin="ui_sso", admin=False) is cache_mod.RESTRICTED
    assert _names(nocase_db) == ["Secret", "secret"]


def test_an_api_admin_deletes_every_collation_match(nocase_db):
    add_jobs_cache_row(nocase_db, job_name="ui-sso-secret", file_name="Secret", data=b"public")
    add_jobs_cache_row(nocase_db, job_name="ui-sso-secret", file_name="secret", data=b"PLACEHOLDER-BYTES")

    assert _delete(nocase_db, "Secret", job="ui-sso-secret", plugin="ui_sso", admin=True) == ""
    assert _names(nocase_db) == []


def test_an_ordinary_collation_match_is_deleted_for_a_non_admin(nocase_db):
    add_jobs_cache_row(nocase_db, job_name="j", file_name="Notes.txt")
    add_jobs_cache_row(nocase_db, job_name="j", file_name="notes.txt")
    add_jobs_cache_row(nocase_db, job_name="j", file_name="other.txt")

    assert _delete(nocase_db, "NOTES.TXT", job="j", plugin="p", admin=False) == ""
    assert _names(nocase_db) == ["other.txt"]


def test_a_missing_row_and_a_wrong_plugin_delete_nothing(nocase_db):
    add_jobs_cache_row(nocase_db, job_name="j", file_name="notes.txt")

    assert _delete(nocase_db, "zzz", job="j", plugin="p", admin=False) is None
    assert _delete(nocase_db, "notes.txt", job="j", plugin="other", admin=False) is None
    assert _names(nocase_db) == ["notes.txt"]


def test_read_only_mode_deletes_nothing(nocase_db):
    add_jobs_cache_row(nocase_db, job_name="j", file_name="notes.txt")
    nocase_db.readonly = True

    assert "read-only" in _delete(nocase_db, "notes.txt", job="j", plugin="p", admin=True)
    assert _names(nocase_db) == ["notes.txt"]


def _replace_row_on_check(monkeypatch, db, *, old_name, new_name, new_data):
    """Replace the row with the same id, from another connection, right after the check read it (SQLite reuses the id)."""
    real = cache_mod.is_sensitive_job_cache_file

    def classify(*args, **kwargs):
        result = real(*args, **kwargs)
        with db.sql_engine.begin() as connection:
            row_id = connection.execute(text("SELECT id FROM bw_jobs_cache WHERE file_name = :n"), {"n": old_name}).scalar_one()
            connection.execute(text("DELETE FROM bw_jobs_cache WHERE id = :i"), {"i": row_id})
            connection.execute(
                text("INSERT INTO bw_jobs_cache (id, job_name, service_id, file_name, data) VALUES (:i, 'ui-sso-secret', NULL, :n, :d)"),
                {"i": row_id, "n": new_name, "d": new_data},
            )
        monkeypatch.setattr(cache_mod, "is_sensitive_job_cache_file", real)
        return result

    monkeypatch.setattr(cache_mod, "is_sensitive_job_cache_file", classify)


def test_a_row_replaced_between_the_check_and_the_delete_is_not_deleted(nocase_db, monkeypatch):
    add_jobs_cache_row(nocase_db, job_name="ui-sso-secret", file_name="notes.txt", data=b"public")
    _replace_row_on_check(monkeypatch, nocase_db, old_name="notes.txt", new_name="token.secret", new_data=b"PLACEHOLDER-BYTES")

    assert _delete(nocase_db, "notes.txt", job="ui-sso-secret", plugin="ui_sso", admin=False) is None
    assert _names(nocase_db) == ["token.secret"]

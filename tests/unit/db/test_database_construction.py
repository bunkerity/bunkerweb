"""``Database(...)`` start-up: what an operator's environment and connection strings produce.

A mistyped tuning value must fall back to its default with a warning, never abort; an unusable connection string
must stop the start with a message that does not carry the password; an unreachable server with a read-only
fallback configured must come up read-only.
"""

import logging

import pytest

import Database as database_module
from Database import Database, DatabaseInitError

pytestmark = pytest.mark.sqlite

PASSWORD = "pw-secret-value"


@pytest.fixture
def build(tmp_path, quiet_logger, _clean_env, caplog):
    quiet_logger.propagate = True
    caplog.set_level(logging.DEBUG, logger=quiet_logger.name)
    created = []

    def make(uri=None, **kwargs):
        database = Database(quiet_logger, sqlalchemy_string=uri or f"sqlite:///{tmp_path}/db.sqlite3", **kwargs)
        created.append(database)
        return database

    yield make
    for database in created:
        database.close()


def _warnings(caplog):
    return "\n".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)


class TestTuningValues:
    def test_valid_values_are_taken(self, build, monkeypatch):
        monkeypatch.setenv("DATABASE_REQUEST_RETRY_ATTEMPTS", "5")
        monkeypatch.setenv("DATABASE_REQUEST_RETRY_DELAY", "0.5")
        database = build()
        assert (database._request_retry_attempts, database._request_retry_delay) == (5, 0.5)

    @pytest.mark.parametrize("value", ["0", "-3", "many", ""])
    def test_a_bad_retry_attempts_value_keeps_the_default_and_warns(self, build, monkeypatch, caplog, value):
        monkeypatch.setenv("DATABASE_REQUEST_RETRY_ATTEMPTS", value)
        database = build()
        assert database._request_retry_attempts == 2
        assert f"Invalid DATABASE_REQUEST_RETRY_ATTEMPTS value: {value}, using default value (2)" in _warnings(caplog)

    def test_a_bad_retry_delay_keeps_the_default_and_warns(self, build, monkeypatch, caplog):
        monkeypatch.setenv("DATABASE_REQUEST_RETRY_DELAY", "soon")
        database = build()
        assert database._request_retry_delay == 0.25
        assert "Invalid DATABASE_REQUEST_RETRY_DELAY value: soon" in _warnings(caplog)

    def test_a_negative_retry_delay_is_refused_like_any_bad_value(self, build, monkeypatch, caplog):
        monkeypatch.setenv("DATABASE_REQUEST_RETRY_DELAY", "-5")
        assert build()._request_retry_delay == 0.25
        assert "Invalid DATABASE_REQUEST_RETRY_DELAY value: -5" in _warnings(caplog)

    @pytest.mark.parametrize("name", ["DATABASE_POOL_SIZE", "DATABASE_POOL_MAX_OVERFLOW"])
    def test_a_bad_pool_value_warns_and_the_database_still_starts(self, build, monkeypatch, caplog, name):
        monkeypatch.setenv(name, "lots")
        database = build()
        assert f"Invalid {name} value: lots, using default value" in _warnings(caplog)
        assert database.get_metadata()["default"] is True

    def test_a_bad_reset_on_return_value_warns_and_falls_back(self, build, monkeypatch, caplog):
        monkeypatch.setenv("DATABASE_POOL_RESET_ON_RETURN", "sometimes")
        build()
        assert "Invalid DATABASE_POOL_RESET_ON_RETURN value: sometimes" in _warnings(caplog)

    def test_a_bad_retry_timeout_warns_and_uses_sixty_seconds(self, build, monkeypatch, caplog):
        monkeypatch.setenv("DATABASE_RETRY_TIMEOUT", "forever")
        build()
        assert "Invalid DATABASE_RETRY_TIMEOUT value: forever, using default value (60)" in _warnings(caplog)

    def test_the_deprecated_pool_argument_warns(self, build, caplog):
        build(pool=True)
        assert "The pool parameter is deprecated" in _warnings(caplog)

    def test_the_regex_check_can_be_switched_off_from_the_environment(self, build, monkeypatch):
        from fixtures.seed import add_setting, seed_minimal

        database = build()
        database.init_tables([])
        seed_minimal(database)
        add_setting(database, "STRICT", plugin_id="general", context="global", regex="^yes$")
        assert database.is_valid_setting("STRICT", value="no")[0] is False
        database.close()
        monkeypatch.setenv("IGNORE_REGEX_CHECK", "yes")
        relaxed = build(str(database.database_uri))
        assert relaxed.is_valid_setting("STRICT", value="no") == (True, "")


class TestConnectionStrings:
    @pytest.mark.parametrize("uri", ["not-a-uri", "ftp://u:pw@host/db", "postgres://u@h/db"])
    def test_an_unsupported_string_stops_the_start_with_a_message(self, build, uri):
        with pytest.raises(DatabaseInitError, match="Invalid database string provided"):
            build(uri, exit_on_error=False)

    def test_the_failure_message_never_carries_the_password(self, build):
        with pytest.raises(DatabaseInitError) as error:
            build(f"postgresql://bw:{PASSWORD}@127.0.0.1:1/bw", exit_on_error=False)
        message = str(error.value)
        assert PASSWORD not in message and "postgresql+psycopg://bw:***@127.0.0.1:1/bw" in message

    def test_oracle_is_refused(self, build):
        with pytest.raises(DatabaseInitError, match="Oracle database is not supported yet"):
            build("oracle://u:p@127.0.0.1/db", exit_on_error=False)

    def test_the_default_exit_path_ends_the_process_with_status_1(self, build, monkeypatch):
        statuses = []

        def fake_exit(status):
            statuses.append(status)
            raise SystemExit(status)

        monkeypatch.setattr(database_module, "_exit", fake_exit)
        with pytest.raises(SystemExit):
            build("not-a-uri")
        assert statuses == [1]

    def test_a_server_uri_without_a_driver_gets_the_recommended_one(self, build):
        for uri, expected in (
            ("postgresql://bw:x@127.0.0.1:1/bw", "postgresql+psycopg://"),
            ("mysql://bw:x@127.0.0.1:1/bw", "mysql+pymysql://"),
            ("mariadb://bw:x@127.0.0.1:1/bw", "mariadb+pymysql://"),
        ):
            captured = {}

            def spy(_self, uri_, **_kwargs):
                captured["uri"] = uri_
                raise DatabaseInitError("stop here")

            original = Database._create_engine
            Database._create_engine = spy
            try:
                with pytest.raises(DatabaseInitError, match="stop here"):
                    build(uri, exit_on_error=False)
            finally:
                Database._create_engine = original
            assert captured["uri"].startswith(expected)

    def test_a_sqlite_file_gets_its_parent_directory_created(self, build, tmp_path):
        target = tmp_path / "nested" / "deeper" / "db.sqlite3"
        database = build(f"sqlite:///{target}")
        assert target.parent.is_dir() and database.get_metadata()["default"] is True
        assert target.is_file()


class TestReadOnlyFallback:
    def test_an_unreachable_server_with_a_read_only_uri_comes_up_read_only(self, build, monkeypatch, tmp_path, caplog):
        monkeypatch.setenv("DATABASE_URI_READONLY", f"sqlite:///{tmp_path}/replica.sqlite3")
        monkeypatch.setenv("DATABASE_RETRY_TIMEOUT", "1")
        monkeypatch.setattr(database_module, "sleep", lambda _seconds: None)
        database = build(f"postgresql://bw:{PASSWORD}@127.0.0.1:1/bw")
        assert database.readonly is True
        assert database.database_uri_readonly.startswith("sqlite")
        assert PASSWORD not in "\n".join(r.getMessage() for r in caplog.records)

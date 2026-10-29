"""A failed or invalid database connection must not leak the password into the logs, and the DB URI must reach the engine intact.

* #3361: the connection-error and invalid-URI log lines printed the whole DATABASE_URI, password included.
* #3438: the driver was injected into the URI with a string replace, which also rewrote host and database
  names containing ``mysql`` or ``postgresql``.
* #717: the engine had no ``pool_recycle``, so connections the server had dropped while idle were reused.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from _t3_helpers import build_database, recording_logger
from Database import Database, DatabaseInitError  # type: ignore

PASSWORD = "s3cr3t-pw"


def refusing_engine(message="(2003, \"Can't connect to MySQL server on 'db' ([Errno 111] Connection refused)\")"):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception(message))
    return engine


class TestPasswordNeverLogged:
    def test_invalid_uri_error_hides_the_password(self, _clean_env):
        logger, handler = recording_logger()

        with pytest.raises(DatabaseInitError) as raised:
            Database(logger, sqlalchemy_string=f"nosuchdb://bw:{PASSWORD}@db.internal/bw", exit_on_error=False)

        assert PASSWORD not in handler.text
        assert PASSWORD not in str(raised.value)
        assert "db.internal" in handler.text  # the target is still named, only the secret is masked

    def test_unencoded_at_sign_in_the_password_is_masked_too(self, _clean_env):
        logger, handler = recording_logger()

        with pytest.raises(DatabaseInitError):
            Database(logger, sqlalchemy_string="nosuchdb://bw:pa@ss-w0rd@db.internal/bw", exit_on_error=False)

        assert "pa@ss-w0rd" not in handler.text
        assert "ss-w0rd" not in handler.text

    def test_unreachable_server_error_names_the_target_without_the_password(self):
        with pytest.raises(DatabaseInitError) as raised:
            build_database(f"mysql+pymysql://bw:{PASSWORD}@db.internal:3306/bw", engine=refusing_engine())

        assert PASSWORD not in str(raised.value)
        assert "db.internal" in str(raised.value)

    def test_driver_error_text_carrying_the_uri_is_masked(self):
        engine = refusing_engine(f"cannot reach mysql+pymysql://bw:{PASSWORD}@db.internal:3306/bw")

        with pytest.raises(DatabaseInitError) as raised:
            build_database("mysql+pymysql://bw:other@db.internal:3306/bw", engine=engine)

        assert PASSWORD not in str(raised.value)


class TestDriverInjection:
    @pytest.mark.parametrize(
        "uri, expected",
        [
            ("mysql://bw:pw@mysql-host/mysql", "mysql+pymysql://bw:pw@mysql-host/mysql"),
            ("mariadb://bw:pw@mariadb.internal/mariadb", "mariadb+pymysql://bw:pw@mariadb.internal/mariadb"),
            ("postgresql://bw:pw@postgresql-primary/postgresql", "postgresql+psycopg://bw:pw@postgresql-primary/postgresql"),
        ],
        ids=["mysql", "mariadb", "postgresql"],
    )
    def test_only_the_scheme_receives_the_driver(self, uri, expected):
        db, _, create_engine = build_database(uri)

        assert db.database_uri == expected
        assert create_engine.call_args.args[0] == expected

    def test_a_uri_with_a_driver_is_left_alone(self):
        db, _, _ = build_database("mysql+pymysql://bw:pw@mysql-host/mysql")

        assert db.database_uri == "mysql+pymysql://bw:pw@mysql-host/mysql"


class TestPoolRecycle:
    def test_default_recycles_connections_before_the_server_drops_them(self):
        _, _, create_engine = build_database("mysql+pymysql://bw:pw@db/bw")

        assert create_engine.call_args.kwargs.get("pool_recycle") == 1800

    def test_env_override_reaches_the_engine(self, monkeypatch):
        monkeypatch.setenv("DATABASE_POOL_RECYCLE", "90")

        _, _, create_engine = build_database("mysql+pymysql://bw:pw@db/bw")

        assert create_engine.call_args.kwargs.get("pool_recycle") == 90

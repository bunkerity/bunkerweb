"""Connection handling, retry wrapper, credential masking, setting validation and the metadata row.

What a caller relies on: a transient driver error is retried and a hard one is not, a read-only error flips the
database to read-only and still raises, a DSN never reaches a log with its password, a setting is validated
against its stored regex and context, and the metadata flags change exactly as documented.
"""

import logging
import threading

import pytest
from sqlalchemy.exc import DatabaseError, OperationalError

import Database as database_module
from Database import mask_db_uri, retry_on_transient_db_errors
from fixtures.seed import add_setting, seed_minimal, session
from model import Metadata, Plugins

pytestmark = pytest.mark.multiengine

SECRET = "s3cr3t-value"


class TestMaskDbUri:
    @pytest.mark.parametrize(
        "uri",
        [
            f"mariadb+pymysql://bw:{SECRET}@db:3306/bw",
            f"postgresql://bw:{SECRET}@db/bw",
            f"mysql://bw:{SECRET}@db/bw?charset=utf8",
            f"postgresql://bw:p@ss{SECRET}@db/bw",
            f"postgresql://bw:p/ss{SECRET}@db/bw",
            f"postgresql://bw:p%2Fss{SECRET}@db/bw",
            f"postgresql://bw@db/bw?password={SECRET}",
            f"postgresql://bw@db/bw?sslpassword={SECRET}&sslmode=require",
            f"mysql://bw@db/bw?api_key={SECRET}",
            f"OperationalError connecting to postgresql://bw:{SECRET}@db/bw: refused",
        ],
    )
    def test_the_password_never_survives_the_mask(self, uri):
        masked = mask_db_uri(uri)
        assert SECRET not in masked
        assert "***" in masked

    def test_the_rest_of_the_dsn_stays_readable(self):
        masked = mask_db_uri(f"mariadb+pymysql://bw:{SECRET}@db:3306/bw?charset=utf8mb4")
        assert masked.startswith("mariadb+pymysql://bw:***@db:3306/bw") and "charset=utf8mb4" in masked

    @pytest.mark.parametrize("uri", ["", "sqlite:////var/lib/bunkerweb/db.sqlite3", "postgresql://bw@db/bw"])
    def test_a_dsn_without_a_password_is_returned_unchanged(self, uri):
        assert mask_db_uri(uri) == uri

    def test_a_failure_message_that_merely_begins_with_a_uri_keeps_its_reason(self):
        message = f"postgresql://bw:{SECRET}@db/bw\nconnection refused"
        masked = mask_db_uri(message)
        assert SECRET not in masked and "connection refused" in masked


class TestTransientErrorClassification:
    def _error(self, db, text, cls=OperationalError, **attrs):
        error = cls("statement", {}, Exception(text))
        for key, value in attrs.items():
            setattr(error, key, value)
        return error

    def test_the_known_connectivity_messages_are_transient(self, db):
        for text in (
            "Connection refused",
            "Can't connect to server",
            "Lost connection to MySQL",
            "server has gone away",
            "connection reset by peer",
            "timed out",
        ):
            assert db._is_transient_connection_error(self._error(db, text)) is True, text
        assert db._is_transient_connection_error(self._error(db, "boom", cls=DatabaseError)) is False

    def test_other_errors_are_not(self, db):
        assert db._is_transient_connection_error(ConnectionRefusedError()) is True
        assert db._is_transient_connection_error(ValueError("connection refused")) is False
        assert db._is_transient_connection_error(self._error(db, "syntax error")) is False
        assert db._is_transient_connection_error(self._error(db, "anything", connection_invalidated=True)) is True

    def test_an_error_without_driver_text_falls_back_to_its_own_message(self, db):
        error = OperationalError("select 1 timeout", {}, Exception(""))
        assert db._is_transient_connection_error(error) is True


class TestRetryWrapper:
    def _call(self, db, failures, *, attempts=3, kind=ConnectionRefusedError):
        db._request_retry_attempts = attempts
        db._request_retry_delay = 0.0
        calls = []

        @retry_on_transient_db_errors
        def operation(self_):
            calls.append(1)
            if len(calls) <= failures:
                raise kind("connection refused") if kind is ConnectionRefusedError else kind("s", {}, Exception("connection refused"))
            return "ok"

        return operation, calls

    def test_a_transient_error_is_retried_until_it_succeeds(self, db):
        operation, calls = self._call(db, 2)
        assert operation(db) == "ok" and len(calls) == 3

    def test_the_last_attempt_raises(self, db):
        operation, calls = self._call(db, 5)
        with pytest.raises(ConnectionRefusedError):
            operation(db)
        assert len(calls) == 3

    def test_a_hard_error_is_never_retried(self, db):
        db._request_retry_attempts = 5
        calls = []

        @retry_on_transient_db_errors
        def operation(self_):
            calls.append(1)
            raise OperationalError("s", {}, Exception("syntax error near FROM"))

        with pytest.raises(OperationalError):
            operation(db)
        assert len(calls) == 1

    def test_the_delay_is_slept_between_attempts_and_logged(self, db, monkeypatch, caplog):
        slept = []
        monkeypatch.setattr(database_module, "sleep", slept.append)
        db.logger.propagate = True
        caplog.set_level(logging.WARNING, logger=db.logger.name)
        operation, calls = self._call(db, 2, kind=OperationalError)
        db._request_retry_delay = 0.25
        assert operation(db) == "ok"
        assert slept == [0.25, 0.25]
        assert {r.getMessage() for r in caplog.records if "Transient database error in operation" in r.getMessage()} == {
            "Transient database error in operation (attempt 1/3), retrying in 0.25s ...",
            "Transient database error in operation (attempt 2/3), retrying in 0.25s ...",
        }

    def test_a_single_attempt_means_no_retry(self, db):
        operation, calls = self._call(db, 1, attempts=1)
        with pytest.raises(ConnectionRefusedError):
            operation(db)
        assert len(calls) == 1


def _run_bounded(action, seconds=3):
    """Run ``action`` in a daemon thread: (finished, raised exception or None)."""
    outcome = {}

    def target():
        try:
            action()
        except BaseException as error:  # noqa: BLE001 - reported to the caller
            outcome["error"] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    return not thread.is_alive(), outcome.get("error")


class TestSessionFailureHandling:
    @pytest.fixture(autouse=True)
    def fresh_lock(self, monkeypatch):
        # Same kind of lock as the module's own, fresh: a deadlock (see the xfail tests) would otherwise leave the shared one held
        monkeypatch.setattr(database_module, "LOCK", type(database_module.LOCK)())

    # _db_session holds LOCK while it calls retry_connection, which takes LOCK again: LOCK must be re-entrant.
    @pytest.mark.parametrize("text", ["attempt to write a readonly database", "read-only", "command denied to user", "Access denied for user"])
    def test_a_read_only_error_switches_to_read_only_mode_and_still_raises(self, db, text):
        def failing_session():
            with db._db_session():
                raise RuntimeError(text)

        finished, error = _run_bounded(failing_session)
        assert finished, "_db_session did not return"
        assert isinstance(error, RuntimeError) and db.readonly is True

    def test_a_refused_connection_falls_back_to_the_read_only_uri_when_one_is_configured(self, db):
        db.database_uri_readonly = db.database_uri

        def failing_session():
            with db._db_session():
                raise ConnectionRefusedError("connection refused")

        finished, error = _run_bounded(failing_session)
        assert finished, "_db_session did not return"
        assert isinstance(error, ConnectionRefusedError) and db.readonly is True

    def test_an_unrelated_error_does_not_change_the_mode(self, db):
        with pytest.raises(RuntimeError):
            with db._db_session():
                raise RuntimeError("boom")
        assert db.readonly is False

    def test_a_refused_connection_without_a_read_only_uri_stays_read_write(self, db):
        db.database_uri_readonly = ""
        with pytest.raises(ConnectionRefusedError):
            with db._db_session():
                raise ConnectionRefusedError("connection refused")
        assert db.readonly is False

    def test_a_missing_engine_ends_the_process_with_status_1(self, db, monkeypatch):
        exits = []
        monkeypatch.setattr(database_module, "_exit", lambda status: exits.append(status) or (_ for _ in ()).throw(SystemExit(status)))
        db.sql_engine = None
        with pytest.raises(SystemExit):
            with db._db_session():
                pass
        assert exits == [1]


class TestRetryConnectionAndProbes:
    def test_the_read_and_write_probes_leave_no_table_behind(self, db):
        assert db.test_read() is None
        assert db.test_write() is None
        with session(db) as s:
            from sqlalchemy import inspect

            assert [t for t in inspect(s.get_bind()).get_table_names() if t.startswith("test_")] == []

    def test_a_plain_retry_rebuilds_the_engine_and_keeps_serving(self, db):
        before = db.sql_engine
        db.retry_connection()
        assert db.sql_engine is not before
        assert db.get_metadata()["default"] is True
        assert db.last_connection_retry is not None

    def test_a_read_only_retry_only_checks_the_connection(self, db):
        db.retry_connection(readonly=True, log=False)
        assert db.get_metadata()["default"] is True

    def test_the_fallback_needs_a_read_only_uri(self, db):
        db.database_uri_readonly = ""
        with pytest.raises(ValueError, match="read-only database URI is not set"):
            db.retry_connection(fallback=True)

    def test_the_fallback_reconnects_to_the_read_only_uri(self, db):
        db.database_uri_readonly = db.database_uri
        db.retry_connection(fallback=True)
        assert db.get_metadata()["default"] is True


class TestSettingValidation:
    @pytest.fixture
    def seeded(self, db):
        seed_minimal(db)
        return db

    def test_a_missing_setting_a_wrong_context_and_a_wrong_value_are_reported(self, seeded):
        assert seeded.is_valid_setting("NOPE") == (False, "missing")
        assert seeded.is_valid_setting("MULTISITE", multisite=True) == (False, "not multisite")
        ok, error = seeded.is_valid_setting("USE_REVERSE_PROXY", value="maybe", multisite=True)
        assert ok is False and error.startswith("not matching regex")
        assert seeded.is_valid_setting("USE_REVERSE_PROXY", value="yes", multisite=True) == (True, "")

    def test_a_suffixed_key_needs_a_multiple_setting(self, seeded):
        assert seeded.is_valid_setting("REVERSE_PROXY_URL_1", value="/api") == (True, "")
        assert seeded.is_valid_setting("USE_REVERSE_PROXY_1") == (False, "not multiple")

    def test_a_service_prefixed_key_resolves_through_the_stored_services_and_the_extra_list(self, seeded):
        assert seeded.is_valid_setting("app1.example.com_USE_REVERSE_PROXY", value="yes") == (True, "")
        assert seeded.is_valid_setting("app1.example.com_MULTISITE") == (False, "not multisite")
        assert seeded.is_valid_setting("other.example.com_USE_REVERSE_PROXY", extra_services=["other.example.com"]) == (True, "")
        assert seeded.is_valid_setting("other.example.com_USE_REVERSE_PROXY") == (False, "missing")

    def test_an_invalid_stored_regex_is_reported_not_raised(self, seeded):
        add_setting(seeded, "BROKEN_RX", plugin_id="general", context="global", regex="([unclosed")
        ok, error = seeded.is_valid_setting("BROKEN_RX", value="x")
        assert ok is False and error.startswith("invalid regex")

    def test_a_file_setting_matches_across_lines(self, seeded):
        add_setting(seeded, "PEM_FILE", plugin_id="general", context="global", type="file", regex="^-----BEGIN.*-----END.*$")
        assert seeded.is_valid_setting("PEM_FILE", value="-----BEGIN X-----\nabc\n-----END X-----") == (True, "")
        add_setting(seeded, "PLAIN", plugin_id="general", context="global", type="text", regex="^-----BEGIN.*-----END.*$")
        assert seeded.is_valid_setting("PLAIN", value="-----BEGIN X-----\nabc\n-----END X-----")[0] is False

    def test_a_caller_session_is_used_as_given(self, seeded):
        with seeded._db_session() as session_:
            assert seeded.is_valid_setting("SERVER_NAME", value="x", session=session_) == (True, "")


class TestMetadata:
    def test_before_initialisation_the_defaults_are_reported(self, db):
        meta = db.get_metadata()
        assert meta["default"] is True and meta["is_initialized"] is False and meta["scheduler_first_start"] is True
        assert db.get_version() == "1.6.18~rc3"
        assert meta["database_version"] not in ("", None)

    def test_initialisation_stores_the_version_and_integration_and_a_second_call_updates_them(self, db):
        assert db.initialize_db("1.6.18", "Docker") == ""
        meta = db.get_metadata()
        assert (meta["default"], meta["is_initialized"], meta["version"], meta["integration"]) == (False, True, "1.6.18", "Docker")
        assert db.get_version() == "1.6.18"
        assert db.initialize_db("1.7.0", "Linux") == ""
        assert (db.get_version(), db.get_metadata()["integration"]) == ("1.7.0", "Linux")

    def test_initialisation_is_refused_in_read_only_mode(self, db):
        db.readonly = True
        assert db.initialize_db("1.6.18") == "The database is read-only, the changes will not be saved"
        db.readonly = False
        assert db.get_metadata()["default"] is True

    def test_set_metadata_sets_known_keys_and_warns_about_unknown_ones(self, db, caplog):
        assert db.set_metadata({"is_pro": True}) == "The metadata are not set yet, try again"
        db.initialize_db("1.6.18")
        db.logger.propagate = True
        caplog.set_level(logging.WARNING, logger=db.logger.name)
        assert db.set_metadata({"is_pro": True, "pro_status": "active", "nonsense": 1}) == ""
        meta = db.get_metadata()
        assert meta["is_pro"] is True and meta["pro_status"] == "active"
        assert any("Metadata key nonsense does not exist" in r.getMessage() for r in caplog.records)
        db.readonly = True
        assert db.set_metadata({"is_pro": False}) == "The database is read-only, the changes will not be saved"

    def test_checked_changes_before_initialisation_reports_it(self, db):
        assert db.checked_changes() == "The metadata are not set yet, try again"

    def test_checking_the_default_set_clears_the_change_flags_but_not_the_ui_reload_flag(self, db):
        db.initialize_db("1.6.18")
        with session(db) as s:
            row = s.get(Metadata, 1)
            row.custom_configs_changed = row.external_plugins_changed = row.pro_plugins_changed = row.instances_changed = row.reload_ui_plugins = True
        assert db.checked_changes(value=False) == ""
        meta = db.get_metadata()
        assert (meta["custom_configs_changed"], meta["external_plugins_changed"], meta["pro_plugins_changed"], meta["instances_changed"]) == (False,) * 4
        assert meta["first_config_saved"] is True and meta["reload_ui_plugins"] is True

    def test_setting_the_default_set_raises_every_flag_including_the_ui_reload(self, db):
        db.initialize_db("1.6.18")
        assert db.checked_changes(value=True) == ""
        meta = db.get_metadata()
        assert (
            meta["custom_configs_changed"],
            meta["external_plugins_changed"],
            meta["pro_plugins_changed"],
            meta["instances_changed"],
            meta["reload_ui_plugins"],
        ) == (True,) * 5
        assert meta["last_instances_change"] is not None and meta["last_pro_plugins_change"] is not None

    def test_only_the_named_flags_change(self, db):
        db.initialize_db("1.6.18")
        assert db.checked_changes(["instances", "ui_plugins"], value=True) == ""
        meta = db.get_metadata()
        assert meta["instances_changed"] is True and meta["reload_ui_plugins"] is True and meta["custom_configs_changed"] is False
        assert meta["first_config_saved"] is False

    def test_the_plugin_config_flag_follows_the_named_plugins_or_all_of_them(self, db):
        seed_minimal(db)
        with session(db) as s:
            s.add(Plugins(id="other", name="other", description="d", version="1.0"))
        assert db.checked_changes(["config"], plugins_changes={"other"}, value=True) == ""
        assert list(db.get_metadata()["plugins_config_changed"]) == ["other"]
        assert db.checked_changes(["config"], plugins_changes="all", value=True) == ""
        assert sorted(db.get_metadata()["plugins_config_changed"]) == ["general", "other"]
        assert db.checked_changes(["config"], plugins_changes=["general"], value=False) == ""
        assert list(db.get_metadata()["plugins_config_changed"]) == ["other"]
        with session(db) as s:
            assert s.get(Plugins, "general").config_changed is False

    def test_checking_changes_is_refused_in_read_only_mode(self, db):
        db.initialize_db("1.6.18")
        db.readonly = True
        assert db.checked_changes() == "The database is read-only, the changes will not be saved"


class TestEmptyIfNone:
    def test_none_becomes_an_empty_string_through_every_container(self, db):
        assert db._empty_if_none(None) == ""
        assert db._empty_if_none({"a": None, "b": [None, ("x", None)], "c": {"d": None}}) == {"a": "", "b": ["", ("x", "")], "c": {"d": ""}}
        assert db._empty_if_none(0) == 0 and db._empty_if_none("x") == "x"

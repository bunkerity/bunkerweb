"""What `bwcli plugin backup preflight` can prove before anything is mutated.

The conception's rule is absolute: an unvalidated combination is refused BEFORE any mutation,
never discovered halfway through. Two things follow, and both are asserted here rather than
assumed -- a check that cannot prove its answer must DEGRADE the verdict instead of passing,
and the overall verdict must be the worst of them, not the last one.
"""

import sys
from datetime import datetime, timedelta
from json import dumps
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Verbs that mutate. Named so the assertion below says what it is looking for.
WRITE_VERBS = frozenset({"CREATE", "DROP", "ALTER", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REPLACE"})

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKUP = _REPO_ROOT / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import downgrade  # noqa: E402
from downgrade import (  # noqa: E402
    IN_PLACE,
    REFUSE,
    RESTORE_ONLY,
    Check,
    check_backup,
    check_disk,
    check_engine,
    check_irrepresentable,
    check_manifest,
    check_plugins,
    check_versions,
    check_writers,
    count_irrepresentable,
    database_size,
    is_downgrade,
    manifest_row,
    read_alembic_revision,
    read_metadata_version,
    render_report,
    scan_plugins,
    version_key,
    worst,
)

NOW = datetime(2026, 8, 31, 12, 0, 0).astimezone()

# Named so a floor can assert they are still populated: an emptied parametrize list does not
# fail, it collects nothing, and the run still reports "N passed".
ORDERED_VERSIONS = ["1.6.11", "1.6.12", "1.7.0~alpha", "1.7.0~beta", "1.7.0", "1.7.1", "1.8.0"]


def test_the_version_ladder_is_populated():
    assert len(ORDERED_VERSIONS) >= 7, "ORDERED_VERSIONS emptied: the ordering tests collect nothing"


class TestVersionOrdering:
    """BunkerWeb versions are Debian-flavoured: `1.7.0~beta` comes BEFORE `1.7.0`."""

    @pytest.mark.parametrize(("lower", "higher"), list(zip(ORDERED_VERSIONS, ORDERED_VERSIONS[1:])))
    def test_the_ladder_is_strictly_increasing(self, lower, higher):
        assert version_key(lower) < version_key(higher)

    def test_a_tilde_suffix_sorts_before_the_bare_release(self):
        """A PEP 440 parser gets this backwards, and backwards here calls an upgrade a downgrade."""
        assert is_downgrade("1.7.0", "1.7.0~beta")
        assert not is_downgrade("1.7.0~beta", "1.7.0")

    def test_the_same_version_is_not_a_downgrade(self):
        assert not is_downgrade("1.7.0", "1.7.0")

    def test_an_unparsable_component_does_not_raise(self):
        assert version_key("nightly") == ((), 1, "")


class TestOverallVerdict:
    def test_the_worst_check_decides_not_the_last_one(self):
        checks = [Check("a", REFUSE, ""), Check("b", IN_PLACE, ""), Check("c", RESTORE_ONLY, "")]
        assert worst(checks) == REFUSE

    def test_restore_only_beats_in_place(self):
        assert worst([Check("a", IN_PLACE, ""), Check("b", RESTORE_ONLY, "")]) == RESTORE_ONLY

    def test_no_checks_at_all_is_a_refusal(self):
        """A preflight that measured nothing has proven nothing, which is not a pass."""
        assert worst([]) == REFUSE


class TestVersions:
    def test_a_matching_stamped_installation_can_go_back(self):
        assert check_versions("1.7.0", "1.7.0", "abc123", "1.6.12").verdict == IN_PLACE

    def test_a_database_ahead_of_the_code_is_refused(self):
        """Either an upgrade is half-done or older code is looking at a newer database."""
        assert check_versions("1.6.12", "1.7.0", "abc123", "1.6.11").verdict == REFUSE

    def test_going_forward_is_refused(self):
        assert check_versions("1.6.12", "1.6.12", "abc123", "1.7.0").verdict == REFUSE

    def test_going_nowhere_is_refused(self):
        assert check_versions("1.7.0", "1.7.0", "abc123", "1.7.0").verdict == REFUSE

    def test_an_uninitialised_database_is_refused(self):
        assert check_versions("1.7.0", None, "abc123", "1.6.12").verdict == REFUSE

    def test_an_unstamped_schema_degrades_to_restore_only(self):
        """With no stamp there is no proving which migrations ran, and the downgrade path is
        chosen from exactly that."""
        assert check_versions("1.7.0", "1.7.0", None, "1.6.12").verdict == RESTORE_ONLY


class TestManifest:
    ROW = {"from": "1.7.0", "to": "1.6.12", "engine": "postgresql", "mode": "in_place_tested", "data_loss": "none"}

    def test_no_manifest_entry_is_restore_only(self):
        """The CLI consumes the manifest and never infers compatibility from the version number,
        so the absence of a row is the answer, not a reason to guess."""
        assert check_manifest(None, "1.7.0", "1.6.12", "postgresql").verdict == RESTORE_ONLY

    def test_a_tested_lossless_pair_allows_in_place(self):
        assert check_manifest(self.ROW, "1.7.0", "1.6.12", "postgresql").verdict == IN_PLACE

    def test_certain_data_loss_is_restore_only(self):
        row = dict(self.ROW, data_loss="certain")
        assert check_manifest(row, "1.7.0", "1.6.12", "postgresql").verdict == RESTORE_ONLY

    def test_an_unclassified_mode_is_restore_only(self):
        row = dict(self.ROW, mode="restore_only")
        assert check_manifest(row, "1.7.0", "1.6.12", "postgresql").verdict == RESTORE_ONLY

    def test_a_row_that_omits_the_data_loss_is_restore_only(self):
        row = {k: v for k, v in self.ROW.items() if k != "data_loss"}
        assert check_manifest(row, "1.7.0", "1.6.12", "postgresql").verdict == RESTORE_ONLY

    def test_the_lookup_is_per_engine(self):
        """A pair proven on SQLite says nothing about PostgreSQL, which is the whole reason the
        manifest is keyed by engine."""
        manifest = {"releases": [self.ROW]}
        assert manifest_row(manifest, "1.7.0", "1.6.12", "postgresql") == self.ROW
        assert manifest_row(manifest, "1.7.0", "1.6.12", "mariadb") is None
        assert manifest_row(manifest, "1.7.1", "1.6.12", "postgresql") is None

    def test_a_manifest_that_is_not_json_is_ignored_rather_than_fatal(self, tmp_path):
        broken = tmp_path / "downgrade-manifest.json"
        broken.write_text("{not json", encoding="utf-8")
        assert downgrade.load_manifest(broken) is None

    def test_a_missing_manifest_reads_as_none(self, tmp_path):
        assert downgrade.load_manifest(tmp_path / "absent.json") is None

    def test_a_real_manifest_round_trips(self, tmp_path):
        path = tmp_path / "downgrade-manifest.json"
        path.write_text(dumps({"releases": [self.ROW]}), encoding="utf-8")
        assert manifest_row(downgrade.load_manifest(path), "1.7.0", "1.6.12", "postgresql") == self.ROW


class TestEngineAndDisk:
    def test_an_unidentified_engine_is_refused(self):
        assert check_engine("", None, "").verdict == REFUSE

    def test_a_backup_that_would_not_fit_is_refused(self):
        assert check_disk(10_000, 5_000, "/var/lib/bunkerweb/backups").verdict == REFUSE

    def test_room_for_only_one_copy_is_restore_only(self):
        assert check_disk(10_000, 15_000, "/backups").verdict == RESTORE_ONLY

    def test_ample_room_passes(self):
        assert check_disk(10_000, 100_000, "/backups").verdict == IN_PLACE

    def test_unreadable_free_space_is_refused(self):
        """Not knowing whether the mandatory backup fits is not the same as it fitting."""
        assert check_disk(10_000, None, "/backups").verdict == REFUSE

    def test_an_unmeasurable_database_degrades(self):
        assert check_disk(None, 100_000, "/backups").verdict == RESTORE_ONLY


class TestBackupEvidence:
    def test_no_backup_at_all_is_refused(self):
        assert check_backup(None, NOW).verdict == REFUSE

    def test_a_fresh_backup_passes_but_says_it_is_unverified(self):
        check = check_backup(("backup-sqlite-2026-08-31_11-00-00.zip", NOW - timedelta(hours=1)), NOW)
        assert check.verdict == IN_PLACE
        # Restorability cannot be proven read-only: proving it costs a restore, i.e. a mutation.
        assert check.data["restorability"] == "unverified"
        assert "not verified" in check.detail

    def test_a_backup_dated_in_the_future_degrades(self):
        """Age is the only freshness evidence there is, and a negative one answers nothing."""
        assert check_backup(("backup-sqlite-2026-09-30_11-00-00.zip", NOW + timedelta(hours=2)), NOW).verdict == RESTORE_ONLY

    def test_a_stale_backup_degrades(self):
        assert check_backup(("backup-sqlite-2026-08-01_11-00-00.zip", NOW - timedelta(days=30)), NOW).verdict == RESTORE_ONLY


class TestIrrepresentableData:
    def test_an_empty_installation_can_go_back(self):
        assert check_irrepresentable({table: 0 for table in downgrade.IRREPRESENTABLE_TABLES}).verdict == IN_PLACE

    @pytest.mark.parametrize("table", list(downgrade.IRREPRESENTABLE_TABLES) + ["bw_resources"])
    def test_any_populated_1_7_table_forces_a_restore(self, table):
        assert check_irrepresentable({table: 3}).verdict == RESTORE_ONLY

    def test_a_table_that_could_not_be_counted_degrades(self):
        """ "Unknown" is not "empty": what would be lost has to be treated as present."""
        check = check_irrepresentable({"bw_bans": None})
        assert check.verdict == RESTORE_ONLY
        assert "bw_bans" in check.detail

    def test_the_irrepresentable_table_list_is_populated(self):
        assert len(downgrade.IRREPRESENTABLE_TABLES) >= 4, "IRREPRESENTABLE_TABLES emptied: the counting tests prove nothing"
        assert len(downgrade.IRREPRESENTABLE_RESOURCE_TYPES) >= 3


class TestPlugins:
    def test_a_core_only_installation_passes(self):
        """Core plugins ship with the release, so the release manifest already covers them."""
        assert check_plugins([{"id": "antibot", "type": "core", "manifest": False}]).verdict == IN_PLACE

    def test_an_external_plugin_with_no_manifest_is_restore_only(self):
        check = check_plugins([{"id": "clamav", "type": "external", "manifest": False}])
        assert check.verdict == RESTORE_ONLY
        assert "clamav" in check.detail

    def test_a_plugin_that_excludes_the_target_is_restore_only(self):
        check = check_plugins([{"id": "coraza", "type": "pro", "manifest": True, "compatible": False}])
        assert check.verdict == RESTORE_ONLY
        assert "coraza" in check.detail

    def test_a_plugin_declaring_a_compatible_range_passes(self):
        assert check_plugins([{"id": "coraza", "type": "pro", "manifest": True, "compatible": True}]).verdict == IN_PLACE

    def test_the_scan_reads_the_declared_range_off_disk(self, tmp_path):
        external = tmp_path / "external"
        (external / "in-range").mkdir(parents=True)
        (external / "out-of-range").mkdir(parents=True)
        (external / "silent").mkdir(parents=True)
        (external / "in-range" / "plugin.json").write_text(
            dumps({"id": "in-range", "extensions": {"downgrade": {"min_version": "1.6.0", "max_version": "1.8.0"}}}), encoding="utf-8"
        )
        (external / "out-of-range" / "plugin.json").write_text(
            dumps({"id": "out-of-range", "extensions": {"downgrade": {"min_version": "1.7.0"}}}), encoding="utf-8"
        )
        (external / "silent" / "plugin.json").write_text(dumps({"id": "silent"}), encoding="utf-8")

        found = {plugin["id"]: plugin for plugin in scan_plugins("1.6.12", core_root=tmp_path / "none", external_root=external, pro_root=tmp_path / "none")}

        assert found["in-range"]["compatible"] is True
        assert found["out-of-range"]["compatible"] is False
        assert found["silent"]["manifest"] is False
        assert check_plugins(list(found.values())).verdict == RESTORE_ONLY


class TestWriters:
    IDLE = {"reachable": True, "queued": 0, "unacked": 0, "reload_pending": False, "pending_acks": 0}

    def test_an_idle_fleet_passes(self):
        assert check_writers(self.IDLE).verdict == IN_PLACE

    def test_a_queued_job_is_refused(self):
        assert check_writers(dict(self.IDLE, queued=1)).verdict == REFUSE

    def test_a_job_in_flight_is_refused(self):
        assert check_writers(dict(self.IDLE, unacked=1)).verdict == REFUSE

    def test_a_reload_in_flight_is_refused(self):
        assert check_writers(dict(self.IDLE, reload_pending=True)).verdict == REFUSE

    def test_an_undelivered_change_is_refused(self):
        """A deferred acknowledgement means a job's material has NOT reached the instances yet;
        downgrading now loses the change and clears nothing."""
        assert check_writers(dict(self.IDLE, pending_acks=2)).verdict == REFUSE

    def test_an_unreachable_broker_degrades_rather_than_passing(self):
        assert check_writers({"reachable": False, "error": "connection refused"}).verdict == RESTORE_ONLY

    def test_a_broker_that_answers_but_hides_its_depth_degrades(self):
        assert check_writers({"reachable": True, "queued": None, "unacked": None}).verdict == RESTORE_ONLY


class TestReport:
    def test_the_report_names_every_check_and_the_verdict(self):
        result = {
            "installed": "1.7.0",
            "target": "1.6.12",
            "generated_at": NOW.isoformat(),
            "verdict": RESTORE_ONLY,
            "checks": [{"name": "versions", "verdict": IN_PLACE, "detail": "ok", "data": {}}],
        }
        rendered = render_report(result)
        assert "versions" in rendered
        assert RESTORE_ONLY in rendered
        assert "read-only" in rendered

    def test_no_password_reaches_the_report(self):
        """DATABASE_URI carries a password, and an unencoded `@` in it makes a naive parser hand
        the password's tail to the log as part of the hostname."""
        check = check_engine("mariadb", "11.4.2", downgrade.mask_db_uri("mariadb+pymysql://bunkerweb:P@ssw0rd!@db:3306/db"))
        rendered = render_report({"installed": "1.7.0", "target": "1.6.12", "generated_at": "", "verdict": IN_PLACE, "checks": [check.__dict__]})
        assert "P@ssw0rd" not in rendered
        assert "ssw0rd" not in rendered


class TestCollectorsAgainstARealDatabase:
    """The read-only collectors, against a real freshly-created schema."""

    def test_a_fresh_schema_has_no_recorded_version_and_no_stamp(self, db):
        assert read_metadata_version(db) is None
        assert read_alembic_revision(db) is None

    def test_the_1_7_only_tables_are_counted_and_empty(self, db):
        counts = count_irrepresentable(db)
        for table in downgrade.IRREPRESENTABLE_TABLES + ("bw_resources",):
            assert counts[table] == 0, f"{table} was not counted"

    def test_the_database_size_is_measured(self, db):
        engine = downgrade.engine_name(db.database_uri)
        size = database_size(db, engine)
        assert size is None or size >= 0

    def test_the_engine_is_identified(self, db):
        assert downgrade.engine_name(db.database_uri) in ("sqlite", "postgresql", "mariadb", "mysql")

    def test_real_1_7_only_rows_are_found_and_force_a_restore(self, db):
        """The counting query itself, on a real engine -- an empty database proves the plumbing
        runs, not that it can see anything."""
        from model import Bans, Resources  # noqa: PLC0415 - the conftest puts src/common/db on the path

        with db._db_session() as session:
            session.add(Bans(ip="192.0.2.1", ban_scope="global", service_id="", origin="api", reason="", country="", created_at=NOW, created_by=""))
            session.add(Resources(id="r1", type="redirect", name="one", creation_date=NOW, last_update=NOW))
            session.add(Resources(id="r2", type="certificate", name="two", creation_date=NOW, last_update=NOW))
            session.commit()

        counts = count_irrepresentable(db)
        assert counts["bw_bans"] == 1
        # Certificates ARE representable in 1.6.x, so bw_resources is counted per type.
        assert counts["bw_resources"] == 1
        assert check_irrepresentable(counts).verdict == RESTORE_ONLY

    def test_the_preflight_issues_no_write_statement(self, db, tmp_path, monkeypatch):
        """Read-only is the whole contract, and counting rows before and after does not prove it.

        `Database.__init__` probes its connection with `CREATE TABLE IF NOT EXISTS test_<hex>` +
        `DROP TABLE` whenever `self.readonly` is False (`src/common/db/Database.py:373-377`), which
        it is unless DATABASE_URI_READONLY is set. Row counts are identical either side of that
        pair, so the only assertion that catches it is on the statements themselves -- and on
        MariaDB/MySQL that DDL commits implicitly and cannot be rolled back.
        """
        from model import Bans  # noqa: PLC0415

        with db._db_session() as session:
            session.add(Bans(ip="192.0.2.9", ban_scope="global", service_id="", origin="api", reason="", country="", created_at=NOW, created_by=""))
            session.commit()

        seen = []

        @event.listens_for(db.sql_engine, "before_cursor_execute")
        def _record(_conn, _cursor, statement, *_args):
            seen.append(statement)

        try:
            monkeypatch.setenv("CELERY_BROKER_URL", "")
            report = downgrade.preflight("1.6.12", db=db, backup_dir=tmp_path, now=NOW)
        finally:
            event.remove(db.sql_engine, "before_cursor_execute", _record)

        assert report["verdict"] in (IN_PLACE, RESTORE_ONLY, REFUSE)
        assert seen, "no statement was recorded: the listener never fired, so this proves nothing"
        writes = [s for s in seen if s.strip().split() and s.strip().split()[0].upper() in WRITE_VERBS]
        assert writes == [], "the preflight issued write statements:\n  " + "\n  ".join(writes)

    def test_the_preflight_opens_its_own_connection_without_writing_either(self, db, tmp_path, monkeypatch):
        """The blocker this guards is in the branch the test above never takes.

        `test_the_preflight_issues_no_write_statement` hands `preflight()` a connection, so the
        `db is None` path -- the one that used to build a `Database` and issue its CREATE/DROP
        probe -- is not exercised at all, and listening on one engine cannot see DDL another engine
        emits. This listens on the Engine CLASS, so every engine the call creates is observed, and
        lets `preflight()` open its own.
        """
        monkeypatch.setenv("DATABASE_URI", db.database_uri)
        monkeypatch.delenv("DATABASE_URI_READONLY", raising=False)
        monkeypatch.setenv("CELERY_BROKER_URL", "")

        seen = []

        @event.listens_for(Engine, "before_cursor_execute")
        def _record(_conn, _cursor, statement, *_args):
            seen.append(statement)

        try:
            report = downgrade.preflight("1.6.12", backup_dir=tmp_path, now=NOW)
        finally:
            event.remove(Engine, "before_cursor_execute", _record)

        assert report["verdict"] in (IN_PLACE, RESTORE_ONLY, REFUSE)
        assert seen, "no statement was recorded: the listener never fired, so this proves nothing"
        writes = [s for s in seen if s.strip().split() and s.strip().split()[0].upper() in WRITE_VERBS]
        assert writes == [], "opening the database for the preflight issued write statements:\n  " + "\n  ".join(writes)


class TestOpeningTheDatabaseWithoutWriting:
    """`open_read_only` exists precisely because `Database()` cannot be used for this."""

    def test_a_missing_sqlite_database_is_refused_not_created(self, tmp_path, monkeypatch):
        """ "There is no database" is an answer the preflight reports, not a file it makes."""
        missing = tmp_path / "absent.sqlite3"
        monkeypatch.setenv("DATABASE_URI", f"sqlite:///{missing}")
        monkeypatch.delenv("DATABASE_URI_READONLY", raising=False)

        with pytest.raises(FileNotFoundError):
            downgrade.open_read_only()
        assert not missing.exists(), "the preflight created the database it was asked to judge"

    def test_an_existing_sqlite_database_opens(self, tmp_path, monkeypatch):
        present = tmp_path / "db.sqlite3"
        present.write_bytes(b"")
        monkeypatch.setenv("DATABASE_URI", f"sqlite:///{present}")
        monkeypatch.delenv("DATABASE_URI_READONLY", raising=False)

        connection = downgrade.open_read_only()
        try:
            assert connection.database_uri.endswith("db.sqlite3")
        finally:
            connection.close()

    def test_a_read_only_replica_wins_when_one_is_configured(self, tmp_path, monkeypatch):
        """It is the correct target for a question about the database, and cannot be written to."""
        replica = tmp_path / "replica.sqlite3"
        replica.write_bytes(b"")
        monkeypatch.setenv("DATABASE_URI", "postgresql://bw:bw@primary:5432/db")
        monkeypatch.setenv("DATABASE_URI_READONLY", f"sqlite:///{replica}")

        connection = downgrade.open_read_only()
        try:
            assert connection.database_uri == ""
            assert connection.database_uri_readonly.endswith("replica.sqlite3")
        finally:
            connection.close()

    @pytest.mark.parametrize(
        ("uri", "expected"),
        [
            ("postgresql://bw:bw@h/db", "postgresql+psycopg://"),
            ("mariadb://bw:bw@h/db", "mariadb+pymysql://"),
            ("mysql://bw:bw@h/db", "mysql+pymysql://"),
            ("sqlite:////tmp/db.sqlite3", "sqlite:///"),
        ],
    )
    def test_the_recommended_driver_is_injected(self, uri, expected):
        """`create_engine("postgresql://...")` reaches for psycopg2, which is not installed."""
        assert downgrade.with_recommended_driver(uri).startswith(expected)

    def test_an_explicit_driver_is_left_alone(self):
        assert downgrade.with_recommended_driver("postgresql+asyncpg://bw@h/db") == "postgresql+asyncpg://bw@h/db"

    def test_the_driver_map_covers_every_engine_the_product_supports(self):
        assert set(downgrade.RECOMMENDED_DRIVERS) >= {"postgresql", "mysql", "mariadb"}, "RECOMMENDED_DRIVERS lost an engine"

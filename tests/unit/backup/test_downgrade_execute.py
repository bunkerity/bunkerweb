"""`bwcli plugin backup downgrade --execute` -- the gates, and what a failure leaves behind.

Lot D is the only downgrade command that mutates, so almost everything worth asserting about it
is a refusal. The conception's acceptance criteria say it in two lines: an unvalidated
combination is refused BEFORE any mutation, and every failure leaves a startable installation.
Each gate is tested by making every OTHER gate pass, so a test that goes green is testing the
gate it names rather than an earlier refusal standing in for it.
"""

import sqlite3
import sys
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKUP = _REPO_ROOT / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup as backup_module  # noqa: E402
import downgrade  # noqa: E402
from downgrade import (  # noqa: E402
    DOWNGRADED,
    IN_PLACE,
    MANUAL,
    REFUSED,
    RESTORE_ONLY,
    RESTORED,
    execute_downgrade,
    render_execute_report,
    run_alembic_downgrade,
)

REAL_TABLE_COUNTS = downgrade.table_counts
REAL_OPEN_READ_ONLY = downgrade.open_read_only

NOW = datetime(2026, 9, 6, 12, 0, 0).astimezone()
TARGET = "1.6.14"
REVISION = "a526ccfe44b4"
HEAD = "24143b5ba8e0"


class FakeClient:
    """Only `hold_status` reads it, and that is monkeypatched -- this just has to not be None."""


class FakeEngine:
    def connect(self):
        raise AssertionError("table_counts is stubbed in these tests")


class FlakyEngine:
    """An engine whose chosen `connect()` calls die the way a recycled pool does.

    `table_counts` is called twice -- once before the migration, once after it -- and the two are
    named by attempt number so a test can shut exactly one of them. `sa.inspect()` cannot inspect
    this either, which is the honest shape of the situation.
    """

    def __init__(self, fails):
        self.fails = set(fails)
        self.attempts = 0

    def connect(self):
        self.attempts += 1
        if self.attempts in self.fails:
            raise OSError("server closed the connection unexpectedly")
        return nullcontext(None)


class FakeDb:
    def __init__(self, uri="sqlite:////var/lib/bunkerweb/db.sqlite3"):
        self.database_uri = uri
        self.sql_engine = FakeEngine()


class FakeReadOnly(FakeDb):
    """What `open_read_only` returns: a connection the caller owns and closes."""

    def __init__(self, uri="sqlite:////var/lib/bunkerweb/db.sqlite3", readonly_uri=""):
        super().__init__(uri)
        self.database_uri_readonly = readonly_uri
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def rig(monkeypatch, tmp_path):
    """Every gate open and every side effect recorded. Each test then shuts exactly one."""
    calls = {"alembic": [], "backup": [], "restore": [], "opened": []}
    # The database's own state, so "did the fallback land?" is a question the rig can answer
    # wrongly. A constant stub would make `execute_downgrade`'s post-restore check pass for free,
    # which is exactly the check the MANUAL verdict rests on.
    state = {"stamp": HEAD, "version": "1.7.0~beta"}
    calls["state"] = state

    monkeypatch.setattr(downgrade, "hold_status", lambda client: {"target": TARGET, "started_at": "2026-09-06T11:00:00+02:00"})

    def fake_open(uri="", readonly_uri="", prefer_replica=True):
        connection = FakeReadOnly(uri or "sqlite:////var/lib/bunkerweb/db.sqlite3", readonly_uri)
        calls["opened"].append(connection)
        return connection

    monkeypatch.setattr(downgrade, "open_read_only", fake_open)
    monkeypatch.setattr(
        downgrade,
        "preflight",
        lambda target, db=None, client=None, now=None: {
            "verdict": IN_PLACE,
            "installed": "1.7.0~beta",
            "engine": "sqlite",
            "target": target,
            "checks": [],
            "manifest_row": {"mode": "in_place_tested", "alembic": {"to_revision": REVISION}},
        },
    )
    monkeypatch.setattr(downgrade, "load_manifest", lambda *a, **k: {"data_loss_detail": {"tables": {"bw_bans": "conditional"}}})
    monkeypatch.setattr(downgrade, "table_counts", lambda db, tables: {name: 1 for name in sorted(tables)})
    monkeypatch.setattr(downgrade, "read_alembic_revision", lambda db: state["stamp"])
    monkeypatch.setattr(downgrade, "read_metadata_version", lambda db: state["version"])

    def fake_backup(current_time, db=None, backup_dir=None):
        calls["backup"].append(backup_dir)
        path = tmp_path / "backup-sqlite-2026-09-06_12-00-00.zip"
        path.write_bytes(b"safety")
        return FakeDb(), path

    def fake_restore(backup_file, db=None):
        calls["restore"].append(Path(backup_file))
        state.update(stamp=HEAD, version="1.7.0~beta")
        return db

    def fake_alembic(engine, uri, revision, alembic_dir=None, timeout=1800.0):
        calls["alembic"].append((engine, revision))
        state.update(stamp=revision, version=TARGET)
        return 0, "Running downgrade ..."

    monkeypatch.setattr(backup_module, "backup_database", fake_backup)
    monkeypatch.setattr(backup_module, "restore_database", fake_restore)
    monkeypatch.setattr(downgrade, "run_alembic_downgrade", fake_alembic)
    return calls


def run(**kwargs):
    kwargs.setdefault("confirmed", True)
    kwargs.setdefault("client", FakeClient())
    kwargs.setdefault("now", NOW)
    return execute_downgrade(TARGET, **kwargs)


def step(result, name):
    return next((s for s in result["steps"] if s["step"] == name), None)


class TestItRefusesBeforeMutating:
    def test_without_a_confirmation(self, rig):
        result = run(confirmed=False)
        assert result["end_state"] == REFUSED
        assert not rig["alembic"] and not rig["backup"]

    def test_without_a_quiescence_hold(self, rig, monkeypatch):
        monkeypatch.setattr(downgrade, "hold_status", lambda client: None)
        result = run()
        assert result["end_state"] == REFUSED
        assert "quiesce" in step(result, "hold")["detail"]
        assert not rig["alembic"] and not rig["backup"]

    def test_under_a_hold_taken_for_another_target(self, rig, monkeypatch):
        monkeypatch.setattr(downgrade, "hold_status", lambda client: {"target": "1.6.13", "started_at": "x"})
        result = run()
        assert result["end_state"] == REFUSED
        assert not step(result, "hold")["ok"]
        assert not rig["alembic"] and not rig["backup"]

    def test_when_the_broker_client_itself_cannot_be_built(self, rig, monkeypatch):
        """`broker_client()` imports redis and parses a URL; both can raise. A gate that raises
        reports "error" where it means "no", and the caller cannot tell them apart."""
        monkeypatch.setattr(downgrade, "broker_client", lambda *a, **k: (_ for _ in ()).throw(ImportError("no module named redis")))
        result = execute_downgrade(TARGET, confirmed=True, client=None, now=NOW)
        assert result["end_state"] == REFUSED
        assert not rig["alembic"] and not rig["backup"]

    def test_when_the_preflight_itself_raises(self, rig, monkeypatch):
        """It refuses a SQLite database that does not exist rather than creating one, and that is
        a raise. "I could not tell" has to come out as a refusal, not a traceback."""
        monkeypatch.setattr(
            downgrade, "preflight", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("SQLite database /var/lib/bunkerweb/db.sqlite3 does not exist"))
        )
        result = run()
        assert result["end_state"] == REFUSED
        assert not step(result, "preflight")["ok"]
        assert not rig["alembic"] and not rig["backup"]

    def test_when_the_broker_cannot_be_asked(self, rig, monkeypatch):
        def boom(client):
            raise ConnectionError("no route to host")

        monkeypatch.setattr(downgrade, "hold_status", boom)
        result = run()
        assert result["end_state"] == REFUSED
        assert not rig["alembic"] and not rig["backup"]

    @pytest.mark.parametrize("verdict", [RESTORE_ONLY, "refuse"])
    def test_when_the_preflight_it_re_runs_is_not_a_go(self, rig, monkeypatch, verdict):
        """Re-run here on purpose: an operator may have run it an hour ago, or never."""
        monkeypatch.setattr(
            downgrade,
            "preflight",
            lambda target, db=None, client=None, now=None: {
                "verdict": verdict,
                "installed": "1.7.0~beta",
                "engine": "sqlite",
                "target": target,
                "generated_at": NOW.isoformat(),
                "checks": [],
                "manifest_row": {},
            },
        )
        result = run()
        assert result["end_state"] == REFUSED
        assert not rig["alembic"] and not rig["backup"]

    def test_when_the_manifest_does_not_mark_the_pair_in_place_tested(self, rig, monkeypatch):
        """The second gate. It exists because the first one is three functions away."""
        monkeypatch.setattr(
            downgrade,
            "preflight",
            lambda target, db=None, client=None, now=None: {
                "verdict": IN_PLACE,
                "installed": "1.7.0~beta",
                "engine": "mariadb",
                "target": target,
                "checks": [],
                "manifest_row": {"mode": "restore_only", "reason": "error 1553 on an index that backs a foreign key"},
            },
        )
        result = run()
        assert result["end_state"] == REFUSED
        assert "1553" in step(result, "manifest")["detail"]
        assert not rig["alembic"] and not rig["backup"]

    def test_when_the_manifest_names_no_revision_to_land_on(self, rig, monkeypatch):
        monkeypatch.setattr(
            downgrade,
            "preflight",
            lambda target, db=None, client=None, now=None: {
                "verdict": IN_PLACE,
                "installed": "1.7.0~beta",
                "engine": "sqlite",
                "target": target,
                "checks": [],
                "manifest_row": {"mode": "in_place_tested"},
            },
        )
        result = run()
        assert result["end_state"] == REFUSED
        assert not rig["alembic"] and not rig["backup"]

    def test_when_the_pre_downgrade_backup_cannot_be_taken(self, rig, monkeypatch):
        def boom(current_time, db=None, backup_dir=None):
            raise OSError("no space left on device")

        monkeypatch.setattr(backup_module, "backup_database", boom)
        result = run()
        assert result["end_state"] == REFUSED
        assert not rig["alembic"], "the migration must not run when there is nothing to fall back to"


class TestTheHappyPath:
    def test_it_downgrades_and_says_where_it_landed(self, rig):
        result = run()
        assert result["end_state"] == DOWNGRADED
        assert rig["opened"] and all(connection.closed for connection in rig["opened"]), "the primary the gate reads is the caller's to close"
        assert rig["alembic"] == [("sqlite", REVISION)]
        assert not rig["restore"]
        assert result["alembic_version_after"] == REVISION
        assert result["bw_metadata_version_after"] == TARGET

    def test_the_backup_is_taken_before_the_migration_runs(self, rig, monkeypatch):
        order = []
        monkeypatch.setattr(backup_module, "backup_database", lambda t, db=None, backup_dir=None: (order.append("backup"), (FakeDb(), Path("/tmp/b.zip")))[1])
        monkeypatch.setattr(
            downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (order.append("alembic"), rig["state"].update(stamp=r, version=TARGET), (0, ""))[2]
        )
        run()
        assert order == ["backup", "alembic"], "a fallback taken after the mutation is not a fallback"

    def test_it_fingerprints_both_sides_of_the_migration(self, rig):
        """PO-3: non-loss is a measurement in the operator's own database, not a manifest claim."""
        result = run()
        assert result["fingerprint_before"] and result["fingerprint_after"]
        assert set(result["fingerprint_after"]) == set(result["fingerprint_before"])


class TestTheFingerprintNeverCostsTheReport:
    """`table_counts` is a measurement, not a gate. It must not be able to lose the verdict.

    These two run the REAL `table_counts` -- the rig stubs it wholesale everywhere else, which is
    exactly why an unguarded connection inside it went unnoticed.
    """

    @staticmethod
    def _broken_database(rig, monkeypatch, tmp_path, fails):
        engine = FlakyEngine(fails)

        def fake_backup(current_time, db=None, backup_dir=None):
            db = FakeDb()
            db.sql_engine = engine
            rig["backup"].append(backup_dir)
            path = tmp_path / "backup-sqlite-2026-09-06_12-00-00.zip"
            path.write_bytes(b"safety")
            return db, path

        monkeypatch.setattr(downgrade, "table_counts", REAL_TABLE_COUNTS)
        monkeypatch.setattr(backup_module, "backup_database", fake_backup)
        return engine

    def test_a_connection_lost_after_the_migration_still_reports_an_end_state(self, rig, monkeypatch, tmp_path):
        """The migration ran, committed and was verified. Losing the connection while taking a
        cosmetic row count must not turn that into a bare error at the shell -- an operator who
        reads "error" after a downgrade that in fact worked restores the backup and undoes it."""
        engine = self._broken_database(rig, monkeypatch, tmp_path, fails={2})

        result = run()

        assert result["end_state"] == DOWNGRADED
        assert downgrade.EXECUTE_EXIT_CODES[result["end_state"]] == 0, "a downgrade that landed must exit with the success code"
        assert rig["alembic"] == [("sqlite", REVISION)]
        assert not rig["restore"], "nothing failed, so nothing may be restored"
        assert result["fingerprint_before"], "the pre-migration fingerprint succeeded: this test is about the one after it"
        assert result["fingerprint_after"] == {}, "the fingerprint is what is lost, and only the fingerprint"
        assert engine.attempts == 2, "the post-migration fingerprint must have been attempted"
        assert render_execute_report(result)

    def test_a_connection_lost_before_the_migration_does_not_strand_the_backup(self, rig, monkeypatch, tmp_path):
        """The pre-mutation call sits between "backup taken" and "alembic runs". A raise there used
        to leave the operator with a backup on disk, an untouched database and a generic error."""
        engine = self._broken_database(rig, monkeypatch, tmp_path, fails={1})

        result = run()

        assert result["end_state"] == DOWNGRADED
        assert rig["backup"], "the backup was taken before the connection died"
        assert rig["alembic"] == [("sqlite", REVISION)], "the migration must still run: the database was never touched"
        assert result["fingerprint_before"] == {}
        assert engine.attempts == 2, "both fingerprints must be attempted, before and after"


class TestTheGateReadsTheDatabaseItWillMigrate:
    """`open_read_only()` prefers `DATABASE_URI_READONLY`; the migration writes the primary.

    A replica that lags -- or has stopped replicating -- answers "no 1.7-only rows" for rows that
    are on the primary, so the gate opens and `alembic downgrade` destroys them, silently, exit 0.
    """

    @staticmethod
    def _sqlite(path, certificates):
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE bw_certificates (id INTEGER PRIMARY KEY)")
            connection.executemany("INSERT INTO bw_certificates (id) VALUES (?)", [(n,) for n in range(certificates)])
            connection.commit()
        finally:
            connection.close()
        return f"sqlite:///{path}"

    def test_a_replica_with_fewer_rows_does_not_answer_for_the_primary(self, rig, monkeypatch, tmp_path):
        # A different database entirely, with fewer rows -- a stale or broken replica.
        primary_uri = self._sqlite(tmp_path / "primary.sqlite3", certificates=1)
        replica_uri = self._sqlite(tmp_path / "replica.sqlite3", certificates=0)
        monkeypatch.setenv("DATABASE_URI", primary_uri)
        monkeypatch.setenv("DATABASE_URI_READONLY", replica_uri)
        monkeypatch.setattr(downgrade, "open_read_only", REAL_OPEN_READ_ONLY)

        seen = {}

        def counting_preflight(target, db=None, client=None, now=None):
            """The real preflight, reduced to the one check this is about, including its default:
            with no `db` it opens `open_read_only()` -- which is where the replica gets in."""
            opened = None
            if db is None:
                db = opened = downgrade.open_read_only()
            try:
                counts = downgrade.count_irrepresentable(db)
                seen.update(uri=db.database_uri, readonly=db.database_uri_readonly, counts=counts)
                refused = any(counts.values())
                return {
                    "verdict": "refuse" if refused else IN_PLACE,
                    "installed": "1.7.0~beta",
                    "engine": "sqlite",
                    "target": target,
                    "generated_at": NOW.isoformat(),
                    "checks": [],
                    "manifest_row": {"mode": "in_place_tested", "alembic": {"to_revision": REVISION}},
                }
            finally:
                if opened is not None:
                    opened.close()

        monkeypatch.setattr(downgrade, "preflight", counting_preflight)

        result = run()

        assert seen["counts"]["bw_certificates"] == 1, f"the gate read the wrong database: {seen}"
        assert seen["uri"] == primary_uri and not seen["readonly"], "the gate must be pinned to the database the migration writes"
        assert result["end_state"] == REFUSED
        assert not rig["alembic"] and not rig["backup"], "1.7-only rows are on the primary: nothing may be migrated"


class TestEveryFailureLeavesSomethingStartable:
    def test_a_failed_migration_is_rolled_back_from_the_backup_it_just_took(self, rig, monkeypatch):
        monkeypatch.setattr(
            downgrade,
            "run_alembic_downgrade",
            lambda e, u, r, **k: (rig["state"].update(stamp="half-way"), (1, "error 1553: needed in a foreign key constraint"))[1],
        )
        result = run()
        assert result["end_state"] == RESTORED
        assert rig["restore"] == [Path(result["safety_backup"])]
        assert "1553" in result["alembic_log"]

    def test_a_success_that_did_not_land_on_the_revision_counts_as_a_failure(self, rig, monkeypatch):
        """The half-finished state the preflight refuses to start from. Reporting rc=0 does not make it fine."""
        monkeypatch.setattr(
            downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(stamp="somewhere-else", version=TARGET), (0, "ok"))[1]
        )
        result = run()
        assert result["end_state"] == RESTORED
        assert rig["restore"], "a stamp that is not the target must trigger the fallback"

    def test_a_success_that_did_not_land_on_the_version_counts_as_a_failure(self, rig, monkeypatch):
        monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(stamp=r, version="1.6.15~rc1"), (0, "ok"))[1])
        result = run()
        assert result["end_state"] == RESTORED
        assert rig["restore"]

    def test_a_restore_that_complains_but_lands_is_not_a_manual_recovery(self, rig, monkeypatch):
        """`restore_database` ends on a `checked_changes` call that runs 1.7 code against a
        restored 1.6 schema (lot B §3). "It raised" and "it did not restore" are different things,
        and telling an operator to restore by hand when it is already done is a wrong instruction."""
        monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda *a, **k: (1, "boom"))

        def noisy(backup_file, db=None):
            rig["state"].update(stamp=HEAD, version="1.7.0~beta")
            raise RuntimeError("Unknown column 'bw_metadata.certificates_changed' in 'field list'")

        monkeypatch.setattr(backup_module, "restore_database", noisy)
        result = run()
        assert result["end_state"] == RESTORED
        assert step(result, "fallback")["ok"]

    def test_a_failed_fallback_names_the_backup_and_the_command_to_finish_by_hand(self, rig, monkeypatch):
        monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(stamp="half-way"), (1, "boom"))[1])

        def boom(backup_file, db=None):
            raise RuntimeError("the dump is truncated")

        monkeypatch.setattr(backup_module, "restore_database", boom)
        result = run()
        assert result["end_state"] == MANUAL
        detail = step(result, "fallback")["detail"]
        assert result["safety_backup"] in detail
        assert "bwcli plugin backup restore" in detail

    def test_a_restore_that_empties_the_database_is_not_reported_as_restored(self, rig, monkeypatch):
        """`read_alembic_revision` swallows its errors and answers None. On a database the restore
        emptied, a `None == None` comparison would call that a successful rollback."""
        monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(stamp="half-way"), (1, "boom"))[1])

        def wipes_it(backup_file, db=None):
            rig["state"].update(stamp=None, version=None)
            raise SystemExit(1)

        monkeypatch.setattr(backup_module, "restore_database", wipes_it)
        # the pre-downgrade reads must fail too, which is the case this guards
        rig["state"].update(stamp=None, version=None)
        result = run()
        assert result["end_state"] == MANUAL

    def test_a_stamp_that_never_moved_is_not_proof_the_database_came_back(self, rig, monkeypatch):
        """The measured MariaDB/MySQL partial failure leaves alembic_version at the 1.7 head and
        bw_metadata.version already committed to 1.6.15~rc1. Comparing the stamp alone calls that
        hybrid schema "restored" before any restore has run."""
        monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(version="1.6.15~rc1"), (1, "1553"))[1])
        monkeypatch.setattr(backup_module, "restore_database", lambda backup_file, db=None: db)
        result = run()
        assert result["end_state"] == MANUAL, "the stamp was unchanged, but bw_metadata says a version that never ran"

    def test_a_restore_that_returns_quietly_without_moving_the_stamp_is_a_manual_recovery(self, rig, monkeypatch):
        monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(stamp="half-way"), (1, "boom"))[1])
        monkeypatch.setattr(backup_module, "restore_database", lambda backup_file, db=None: db)
        result = run()
        assert result["end_state"] == MANUAL


class TestTheOperatorFacingReport:
    def test_it_renders_every_end_state_without_raising(self, rig, monkeypatch):
        for setup in (
            lambda: None,
            lambda: monkeypatch.setattr(downgrade, "run_alembic_downgrade", lambda e, u, r, **k: (rig["state"].update(stamp="half-way"), (1, "boom"))[1]),
        ):
            setup()
            text = render_execute_report(run())
            assert "Downgrade to 1.6.14" in text

    def test_the_refusal_report_renders_with_no_fingerprint_at_all(self, rig):
        assert "refused" in render_execute_report(run(confirmed=False))


class TestTheCommandLineWrapper:
    """`bwcli/downgrade_execute.py` is a script, not a module, so it is driven as one.

    Its exit code is a contract: `refuse` means a half-finished migration, a database-vs-code
    version mismatch or jobs in flight, and a pipeline gating on this command must not sail past
    that. Without this test the whole branch is unexercised -- a mutation collapsing it to
    `sys_exit(0)` left all 473 unit tests green.
    """

    SCRIPT = _BACKUP / "bwcli" / "downgrade_execute.py"

    def _run(self, args, tmp_path, extra_env=None):
        import os
        import subprocess
        import sys

        database = tmp_path / "empty.sqlite3"
        database.touch()
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{_BACKUP}:{_REPO_ROOT / 'src' / 'common' / 'db'}:{_REPO_ROOT / 'src' / 'common' / 'utils'}:" + env.get("PYTHONPATH", "")
        env["DATABASE_URI"] = f"sqlite:///{database}"
        env["BACKUP_DIRECTORY"] = str(tmp_path / "backups")
        env.update(extra_env or {})
        return subprocess.run([sys.executable, str(self.SCRIPT), *args], capture_output=True, text=True, env=env, timeout=120)

    def test_report_mode_exits_non_zero_when_the_preflight_refuses(self, tmp_path):
        """No /usr/share/bunkerweb/VERSION on a test host, so `check_versions` refuses outright --
        which is exactly the verdict this branch exists for."""
        proc = self._run(["1.6.14"], tmp_path)
        assert "refuse" in (proc.stdout + proc.stderr), f"expected a refusing preflight, got:\n{proc.stdout}\n{proc.stderr}"
        assert proc.returncode == 3, f"a refused preflight must not exit 0 (got {proc.returncode})"

    def test_report_mode_changes_nothing(self, tmp_path):
        proc = self._run(["1.6.14"], tmp_path)
        assert "Nothing was changed" in proc.stdout + proc.stderr
        assert "Pre-downgrade backup taken" not in proc.stdout + proc.stderr

    def test_execute_with_no_terminal_to_confirm_on_refuses(self, tmp_path):
        proc = self._run(["1.6.14", "--execute"], tmp_path)
        assert proc.returncode == 3
        assert "no terminal to confirm on" in proc.stdout + proc.stderr

    def test_the_confirmation_prompt_does_not_read_out_losses_under_a_refusal(self, tmp_path):
        """`render_report` suppresses the uncounted-loss block on a `refuse` verdict, and the prompt
        has to make the same call. It used to print the same content two lines later, headed "which
        no check above counts" -- pointing at a block that had deliberately not been printed, about
        a downgrade that was never going to run. Needs a real terminal: without one the command
        refuses earlier, at the isatty gate, and never reaches the prompt."""
        import os
        import pty
        import subprocess
        import sys

        database = tmp_path / "empty.sqlite3"
        database.touch()
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{_BACKUP}:{_REPO_ROOT / 'src' / 'common' / 'db'}:{_REPO_ROOT / 'src' / 'common' / 'utils'}:" + env.get("PYTHONPATH", "")
        env["DATABASE_URI"] = f"sqlite:///{database}"
        env["BACKUP_DIRECTORY"] = str(tmp_path / "backups")

        controller, terminal = pty.openpty()
        try:
            proc = subprocess.Popen(
                [sys.executable, str(self.SCRIPT), "1.6.14", "--execute"],
                stdin=terminal,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            os.write(controller, b"no\n")
            output = proc.communicate(timeout=120)[0]
        finally:
            os.close(controller)
            os.close(terminal)

        assert "verdict: refuse" in output.lower(), f"expected a refusing preflight, got:\n{output}"
        assert "ALSO destroys" not in output, f"the prompt read out the loss block the report suppressed:\n{output}"
        assert proc.returncode == 3


class TestTheAlembicRunner:
    def test_a_missing_alembic_directory_is_an_error_not_an_exception(self, tmp_path):
        code, log = run_alembic_downgrade("sqlite", "sqlite:///x.db", REVISION, alembic_dir=tmp_path / "nope")
        assert code != 0 and log

    def test_the_database_uri_never_reaches_the_log(self, tmp_path, monkeypatch):
        """Drivers echo the URI back inside their errors, and it carries the password.

        Two earlier versions of this test were vacuous. The first pointed at a non-existent alembic
        directory, so nothing ever connected. The second connected to a refused port -- but
        psycopg's "connection refused" names the host and not the credential, so the assertion held
        with `scrub_db_secret` deleted. The scrubbing is what is under test, so the subprocess is
        stubbed to emit exactly what a driver that DOES echo the URI emits.
        """
        uri = "postgresql+psycopg://bw:sup3rs3cret@db.internal:5432/bunkerweb"

        class Emits:
            returncode = 1
            stdout = ""
            stderr = f"sqlalchemy.exc.OperationalError: could not translate host name\n(Background on this error: {uri})\n"

        import subprocess

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: Emits())
        code, log = run_alembic_downgrade("postgresql", uri, REVISION, alembic_dir=tmp_path)

        assert code == 1
        assert "sup3rs3cret" not in log, "the password reached the log"
        assert "db.internal" in log, "the whole message was dropped instead of scrubbed, which is not what is wanted"

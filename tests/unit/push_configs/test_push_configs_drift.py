"""The worker wipes ``/etc/bunkerweb/configs`` too, and on all-in-one and Linux it is the SAME
folder the operator edits.

``_materialize_custom_configs`` empties every ``CUSTOM_CONFIGS_DIRS`` subtree and re-materializes
it from the database before each push. In the split Docker/Kubernetes layout that folder lives
inside the worker container (``misc/dev/docker-compose.ui.api.yml`` gives ``bw-worker`` only
``bw-worker-storage:/data``), so nobody edits it. In the all-in-one image supervisord runs the
scheduler and the worker in one container, and on Linux they are two systemd units on one host --
there the worker's wipe reaches the operator's file, and it can run at any moment, whereas the
scheduler only rescans on boot and on SIGHUP.

Same two assertions as the scheduler side: the drift is named once under the default policy (and
still overwritten), and ``CUSTOM_CONFIGS_DRIFT=refuse`` keeps the folder. Plus the env-only
no-change proof, because this projection runs before every single push.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"


def _load_definitions():
    """Load definitions only -- the module is a script that pushes configs and exits.

    ``_write_atomic`` is the real behaviour here and not a Mock: what the wipe-and-rewrite does to
    a file that exists only on disk IS what is under test."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger", "jobs", "letsencrypt_consistency")}
    stubs["redis"].Redis = Mock()
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["Database"].Database = Mock()
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["jobs"]._write_atomic = lambda target, data: Path(target).write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    stubs["jobs"].note_deferral = Mock()
    stubs["letsencrypt_consistency"].le_cache_write_lock = Mock()

    module = ModuleType("bw_push_configs_drift")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


@pytest.fixture
def push_configs(tmp_path, monkeypatch):
    import custom_configs_drift  # type: ignore

    module = _load_definitions()
    module.CUSTOM_CONFIGS_PATH = tmp_path.joinpath("configs")
    module.LOGGER = Mock()
    # The manifest lives outside the projected folder in production (/var/lib/bunkerweb); point it
    # somewhere writable for the test.
    monkeypatch.setattr(custom_configs_drift, "PROJECTION_STATE_PATH", tmp_path.joinpath("projection.json"))
    return module


def _project(root, relative, content):
    """Seed a file AND record it as the projection's own output, the way a real pass leaves it."""
    import custom_configs_drift  # type: ignore

    target = _write(root, relative, content)
    custom_configs_drift.write_projection(root)
    return target


def _edit(root, relative, content):
    """Change a projected file behind the projection's back -- this is what drift means."""
    target = Path(root).joinpath(relative)
    target.write_bytes(content)
    return target


def _orphan(root, relative, content):
    """Drop a file the projection never wrote: record the manifest first, then add it."""
    import custom_configs_drift  # type: ignore

    Path(root).mkdir(parents=True, exist_ok=True)
    custom_configs_drift.write_projection(root)
    return _write(root, relative, content)


def _config(name, data, *, method="scheduler", service_id=None, _type="http", is_draft=False):
    return {"service_id": service_id, "type": _type, "name": name, "data": data, "method": method, "is_draft": is_draft, "checksum": "unused"}


def _db(configs):
    db = Mock()
    db.get_custom_configs.return_value = list(configs)
    return db


def _write(root, relative, content):
    target = Path(root).joinpath(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _drift_warnings(module):
    return [call.args[0] for call in module.LOGGER.warning.call_args_list if "Custom config drift" in call.args[0]]


class TestOverwrite:
    def test_the_wipe_names_the_edited_file_before_taking_it(self, push_configs, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        _project(push_configs.CUSTOM_CONFIGS_PATH, "http/envcfg.conf", b"# from env")
        edited = _edit(push_configs.CUSTOM_CONFIGS_PATH, "http/envcfg.conf", b"# OPERATOR EDIT\n")

        push_configs._materialize_custom_configs(_db([_config("envcfg", b"# from env")]))

        drift = _drift_warnings(push_configs)
        assert len(drift) == 1, f"expected exactly one drift warning, got {drift}"
        assert edited.as_posix() in drift[0]
        assert "database method=scheduler" in drift[0]
        assert "CUSTOM_CONFIGS_DRIFT=overwrite" in drift[0]
        assert edited.read_bytes() == b"# from env", "overwrite must still overwrite"

    def test_an_orphan_is_named_before_it_is_deleted(self, push_configs, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        stray = _orphan(push_configs.CUSTOM_CONFIGS_PATH, "modsec/stray.conf", b"# dropped by hand\n")

        push_configs._materialize_custom_configs(_db([]))

        drift = _drift_warnings(push_configs)
        assert len(drift) == 1 and stray.as_posix() in drift[0]
        assert not stray.exists()


class TestRefuse:
    def test_the_folder_is_kept_and_the_error_says_how_to_resolve_it(self, push_configs, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        _project(push_configs.CUSTOM_CONFIGS_PATH, "http/envcfg.conf", b"# from env")
        edited = _edit(push_configs.CUSTOM_CONFIGS_PATH, "http/envcfg.conf", b"# OPERATOR EDIT\n")

        push_configs._materialize_custom_configs(_db([_config("envcfg", b"# from env"), _config("other", b"# other", method="ui")]))

        assert edited.read_bytes() == b"# OPERATOR EDIT\n"
        assert not push_configs.CUSTOM_CONFIGS_PATH.joinpath("http", "other.conf").exists()
        errors = [call.args[0] for call in push_configs.LOGGER.error.call_args_list]
        assert len(errors) == 1 and "CUSTOM_CONFIGS_DRIFT=refuse" in errors[0]

    def test_without_drift_the_push_materializes_as_usual(self, push_configs, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")

        push_configs._materialize_custom_configs(_db([_config("fresh", b"# fresh")]))

        assert push_configs.CUSTOM_CONFIGS_PATH.joinpath("http", "fresh.conf").read_bytes() == b"# fresh"
        push_configs.LOGGER.error.assert_not_called()


class TestEnvOnlyInstallIsUnchanged:
    """AC 6, on the path that runs before EVERY push: a line per file per push would be the
    regression the drift log is supposed to prevent, not the feature."""

    CONFIGS = [
        _config("first", b"# CREATED BY ENV\n# one\n"),
        _config("second", b"# CREATED BY ENV\n# two\n", _type="server_http", service_id="app1.example.com"),
    ]

    def test_a_second_push_over_its_own_output_is_silent(self, push_configs, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        db = _db(self.CONFIGS)

        push_configs._materialize_custom_configs(db)
        root = push_configs.CUSTOM_CONFIGS_PATH
        before = {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*.conf"))}
        push_configs.LOGGER.reset_mock()

        push_configs._materialize_custom_configs(db)
        after = {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*.conf"))}

        assert (
            before
            == after
            == {
                "http/first.conf": b"# CREATED BY ENV\n# one\n",
                "server-http/app1.example.com/second.conf": b"# CREATED BY ENV\n# two\n",
            }
        )
        assert _drift_warnings(push_configs) == []
        push_configs.LOGGER.error.assert_not_called()


class TestRefusalIsNotAcknowledged:
    """A refusal materializes NOTHING, so the change it was dispatched for is still owed.

    `_materialize_custom_configs` returns before the write loop, not just past the drifted file, so
    a custom config added in the UI is neither written nor pushed. `acknowledge_changes` clears
    `custom_configs_changed` (`push-configs.py`, `db.clear_applied_changes`) and nothing else
    re-raises it — the flag would go quiet with the change never delivered, which is the failure
    `may_acknowledge_without_pushing` exists to describe, reached here through a setting instead of
    a down instance. Its own docstring: "Clearing it wrongly would cost a lost configuration."

    The trigger is ordinary, not exotic: an operator edits a file whose row is owned by a
    `CUSTOM_CONF_*` variable or by an orchestrator label. `check_configs_changes` re-submits it as
    `manual`, the method arbitration drops the submission (`db_methods/custom_configs.py`, the
    branch this lane made log), and the row therefore never comes to match the file — so the
    `modified` drift survives every reload, and under `refuse` so does the refusal, until the
    operator deletes the file or changes it at its source.

    (An earlier revision of this docstring claimed a removed `CUSTOM_CONF_*` leaves a permanent
    orphan behind. It does not: that file was written by the projection, so it matches the
    manifest and is not drift at all, and the wipe removes it on the same pass — which is also
    what `7c7c50e66` does.)
    """

    def test_a_refusal_reports_false_so_the_caller_can_withhold_the_ack(self, push_configs, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        _project(push_configs.CUSTOM_CONFIGS_PATH, "http/envcfg.conf", b"# from env")
        _edit(push_configs.CUSTOM_CONFIGS_PATH, "http/envcfg.conf", b"# OPERATOR EDIT\n")

        assert push_configs._materialize_custom_configs(_db([_config("envcfg", b"# from env")])) is False

    def test_an_ordinary_run_reports_true(self, push_configs, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)

        assert push_configs._materialize_custom_configs(_db([_config("fresh", b"# fresh")])) is True

    def test_an_empty_database_still_reports_true(self, push_configs, monkeypatch):
        """Nothing to write is not a refusal: the wipe ran and the folder now matches the database."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)

        assert push_configs._materialize_custom_configs(_db([])) is True

    def test_the_job_acknowledges_only_when_the_custom_configs_were_materialized(self):
        """The guard has to be in the ack branch, not merely in the return value.

        Read the real source of the main block rather than restating it: a copy here would keep
        passing while the shipped branch rotted. The main block is a ``try`` that pushes and
        exits, so it cannot be executed -- but it CAN be parsed, and the branch is checked as a
        tree rather than as a substring: a text search for the `elif` line before the ack call
        also passes when the two bodies are swapped, which is the one mutation that matters here.

        The assertion is on literal source shape: rewriting the branch as
        ``if custom_configs_materialized:`` with the bodies exchanged is semantically identical and
        would fail here. That is a false negative by design -- fix the test, not the code.
        """
        tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))

        def _walk(nodes):
            for node in nodes:
                yield node
                yield from _walk(list(ast.iter_child_nodes(node)))

        assert any(
            isinstance(node, ast.Assign)
            and ast.unparse(node.targets[0]) == "custom_configs_materialized"
            and ast.unparse(node.value) == "_materialize_custom_configs(db)"
            for node in _walk(tree.body)
        ), "the return value of the projection is not captured"

        branches = [node for node in _walk(tree.body) if isinstance(node, ast.If) and ast.unparse(node.test) == "not custom_configs_materialized"]
        assert len(branches) == 1, "the ack is not gated on the refusal"
        branch = branches[0]

        held_back = ast.unparse(ast.Module(body=branch.body, type_ignores=[]))
        assert "acknowledge_changes" not in held_back, "a refused projection still acknowledges the change"
        # and the operator is told why the change is still pending, the same way a deferred push is
        assert "note_deferral(" in held_back

        # The other side of the same `if` is where the acknowledgement actually lives.
        acknowledged = ast.unparse(ast.Module(body=branch.orelse, type_ignores=[]))
        assert "acknowledge_changes(db, metadata_snapshot, 'pushed and reloaded')" in acknowledged

        # Inspecting one branch is not enough on its own: an acknowledgement added ANYWHERE else
        # would leave this branch clean and defeat the guard. There are exactly two CALLS in the
        # job -- this one and the no-instances path (`report-CC-1.md` §3c explains why that one
        # stays) -- and a third has to be argued for, not slipped in.
        calls = [node for node in _walk(tree.body) if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "acknowledge_changes"]
        assert len(calls) == 2, "an acknowledgement was added outside the two known paths"


class TestDriftPolicyValue:
    """The worker reads the setting from the database as well as the environment.

    `worker/tasks.py` clears the job environment and overlays `db.get_config()` (defaults
    included) before every job, so under Celery `getenv` already carries the stored value. A push
    run outside that overlay — bwcli, a diagnostic run — has an empty environment, and falling back
    to the compiled default there would make the worker and the scheduler apply different policies
    to the same folder on all-in-one and Linux.
    """

    def test_the_environment_wins_when_it_is_set(self, push_configs, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        db = Mock()
        db.get_config.return_value = {"CUSTOM_CONFIGS_DRIFT": "overwrite"}

        assert push_configs._drift_policy_value(db) == "refuse"
        db.get_config.assert_not_called()

    def test_an_empty_environment_falls_back_to_the_database(self, push_configs, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        db = Mock()
        db.get_config.return_value = {"CUSTOM_CONFIGS_DRIFT": "refuse"}

        assert push_configs._drift_policy_value(db) == "refuse"

    def test_an_unreachable_database_is_not_fatal(self, push_configs, monkeypatch):
        """The policy must never be the reason a push crashes."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        db = Mock()
        db.get_config.side_effect = RuntimeError("no database")

        assert push_configs._drift_policy_value(db) == ""


class TestAnOrdinaryDatabaseChangeIsNotDrift:
    """Criticos round 2: comparing the folder against the *current* rows makes every legitimate
    change look like an operator edit, which under `refuse` deadlocks the very change it protects.

    This is the push side of that, and it is the one that hurts: the flag never clears, so the
    scheduler re-dispatches every APPLY_RETRY_INTERVAL and each run re-pushes and reloads the whole
    fleet, for ever, on a config somebody saved in the web UI.
    """

    def test_a_row_edited_in_the_ui_materializes_normally_under_refuse(self, push_configs, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        target = _project(push_configs.CUSTOM_CONFIGS_PATH, "http/foo.conf", b"# v1\n")

        # nobody touched the disk; the row now holds v2
        assert push_configs._materialize_custom_configs(_db([_config("foo", b"# v2\n", method="ui")])) is True
        assert target.read_bytes() == b"# v2\n"
        assert _drift_warnings(push_configs) == []
        push_configs.LOGGER.error.assert_not_called()

    def test_a_deleted_row_takes_its_own_projection_with_it_under_refuse(self, push_configs, monkeypatch):
        """A deletion leaves the file until the next wipe. That file is the projection's own
        output, so removing it is not a refusal — `orphan` is for files the projection never wrote."""
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        target = _project(push_configs.CUSTOM_CONFIGS_PATH, "http/gone.conf", b"# once in the database\n")

        assert push_configs._materialize_custom_configs(_db([])) is True
        assert not target.exists()
        assert _drift_warnings(push_configs) == []

    def test_the_manifest_follows_the_projection_so_a_push_is_not_drift_for_the_next_one(self, push_configs, monkeypatch):
        """Two writers share this folder on all-in-one and Linux; whichever wrote last owns the
        manifest, so the other must not report that output as drift."""
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        db = _db([_config("foo", b"# v2\n", method="ui")])

        push_configs._materialize_custom_configs(db)
        push_configs.LOGGER.reset_mock()

        assert push_configs._materialize_custom_configs(db) is True
        assert _drift_warnings(push_configs) == []

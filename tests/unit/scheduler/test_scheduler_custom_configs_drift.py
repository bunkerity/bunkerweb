"""``/etc/bunkerweb/configs`` is a projection, and it used to be rewritten in silence.

``generate_custom_configs`` unlinks every file under ``configs/*/*`` and re-materializes the tree
from the database on boot, on SIGHUP and on every pass that raised ``CONFIGS_NEED_GENERATION``.
A file the operator edited or dropped by hand therefore disappeared with nothing in the logs --
issue #173's last open complaint, and acceptance criterion 1 of the custom-configs design.

Two things are asserted here, in this order of importance:

1. a drifted file produces exactly one WARNING naming the path, the method that owns the database
   row and both short checksums -- under the default ``CUSTOM_CONFIGS_DRIFT=overwrite`` the file
   is still overwritten, so the only new thing is the line;
2. ``CUSTOM_CONFIGS_DRIFT=refuse`` keeps the whole folder as it is and logs an ERROR saying how to
   resolve it.

And the one that guards the rest of the fleet: an install that only uses ``CUSTOM_CONF_*``
variables must be byte-identical to before, WARNING included -- i.e. no WARNING at all. Its files
hash equal to their rows, so the detector has nothing to say.

``src/scheduler/main.py`` mkdir()s at import, so it is loaded through the same sandboxed importer
``test_scheduler_env_and_config_rescan.py`` uses.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"
_REAL_MKDIR = Path.mkdir


def _sandboxed_mkdir(sandbox):
    def _mkdir(self, *args, **kwargs):
        target = self if self.is_relative_to(sandbox) else (sandbox.joinpath(*self.parts[1:]) if self.is_absolute() else self)
        if target.is_absolute() and not target.is_relative_to(sandbox):
            raise PermissionError(13, "Permission denied", str(target))
        return _REAL_MKDIR(target, *args, **kwargs)

    return _mkdir


@pytest.fixture(scope="module")
def scheduler_main(tmp_path_factory):
    sandbox = tmp_path_factory.mktemp("drift-import-sandbox")
    spec = importlib.util.spec_from_file_location("bw_scheduler_main_drift", _MAIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bw_scheduler_main_drift"] = module
    with patch.object(Path, "mkdir", _sandboxed_mkdir(sandbox)):
        spec.loader.exec_module(module)
    yield module
    sys.modules.pop("bw_scheduler_main_drift", None)


def _config(name, data, *, method="scheduler", service_id=None, _type="http", is_draft=False):
    return {"service_id": service_id, "type": _type, "name": name, "data": data, "method": method, "is_draft": is_draft, "checksum": "unused"}


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A configs folder, plus the manifest the projection would have left behind.

    ``write`` seeds a file as the projection wrote it; ``edit`` then changes it behind the
    projection's back, which is what "drift" means. Seeding with ``write`` alone leaves a file the
    projection never wrote — an orphan — which is the other half.
    """
    import custom_configs_drift  # type: ignore

    root = tmp_path.joinpath("configs")
    state = tmp_path.joinpath("projection.json")
    monkeypatch.setattr(custom_configs_drift, "PROJECTION_STATE_PATH", state)

    def _write(relative, content):
        target = root.joinpath(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def _project(relative, content):
        """Seed a file AND record it as this projection's own output."""
        target = _write(relative, content)
        custom_configs_drift.write_projection(root)
        return target

    def _edit(relative, content):
        """Change a projected file behind the projection's back."""
        target = root.joinpath(relative)
        target.write_bytes(content)
        return target

    def _orphan(relative, content):
        """Drop a file the projection never wrote: record the manifest first, then add it."""
        root.mkdir(parents=True, exist_ok=True)
        custom_configs_drift.write_projection(root)
        return _write(relative, content)

    return type(
        "Tree",
        (),
        {
            "root": root,
            "state": state,
            "write": staticmethod(_write),
            "project": staticmethod(_project),
            "edit": staticmethod(_edit),
            "orphan": staticmethod(_orphan),
        },
    )


@pytest.fixture
def logger(scheduler_main, monkeypatch):
    fake = Mock()
    monkeypatch.setattr(scheduler_main, "LOGGER", fake)
    return fake


def _warnings(logger):
    return [call.args[0] for call in logger.warning.call_args_list]


def _drift_warnings(logger):
    return [message for message in _warnings(logger) if "Custom config drift" in message]


class TestOverwriteLogsTheDriftAndStillOverwrites:
    """The default policy. Behaviour is unchanged; the line is the deliverable."""

    def test_an_edited_file_is_named_with_its_method_and_both_checksums(self, scheduler_main, tree, logger, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        tree.project("http/envcfg.conf", b"# CREATED BY ENV\n# from env")
        edited = tree.edit("http/envcfg.conf", b"# CREATED BY ENV\n# OPERATOR EDIT\n")

        scheduler_main.generate_custom_configs([_config("envcfg", b"# CREATED BY ENV\n# from env")], original_path=tree.root)

        drift = _drift_warnings(logger)
        assert len(drift) == 1, f"expected exactly one drift warning, got {drift}"
        assert edited.as_posix() in drift[0]
        assert "database method=scheduler" in drift[0]
        assert "disk sha256=" in drift[0] and "database sha256=" in drift[0]
        assert "CUSTOM_CONFIGS_DRIFT=overwrite" in drift[0]
        assert edited.read_bytes() == b"# CREATED BY ENV\n# from env", "overwrite must still overwrite"

    def test_a_file_with_no_row_is_named_before_it_is_deleted(self, scheduler_main, tree, logger, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        stray = tree.orphan("http/stray.conf", b"# dropped by hand\n")

        scheduler_main.generate_custom_configs([], original_path=tree.root)

        drift = _drift_warnings(logger)
        assert len(drift) == 1, f"expected exactly one drift warning, got {drift}"
        assert stray.as_posix() in drift[0]
        assert "was not written by the projection" in drift[0]
        assert not stray.exists(), "overwrite must still delete the orphan"

    def test_a_per_service_file_is_matched_at_its_own_depth(self, scheduler_main, tree, logger, monkeypatch):
        """``<type>/<service>/<name>.conf`` is the second layout the generator writes; matching it
        at the wrong depth would report every per-service config as an orphan on every reload."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        tree.project("server-http/app1.example.com/svc.conf", b"# same\n")

        scheduler_main.generate_custom_configs(
            [_config("svc", b"# same\n", _type="server_http", service_id="app1.example.com", method="ui")], original_path=tree.root
        )

        assert _drift_warnings(logger) == []


class TestRefuseKeepsTheFolder:
    def test_the_edit_survives_and_the_error_says_how_to_resolve_it(self, scheduler_main, tree, logger, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        tree.project("http/envcfg.conf", b"# from env")
        edited = tree.edit("http/envcfg.conf", b"# OPERATOR EDIT\n")

        scheduler_main.generate_custom_configs([_config("envcfg", b"# from env")], original_path=tree.root)

        assert edited.read_bytes() == b"# OPERATOR EDIT\n"
        errors = [call.args[0] for call in logger.error.call_args_list]
        assert len(errors) == 1, f"expected exactly one refusal error, got {errors}"
        assert "CUSTOM_CONFIGS_DRIFT=refuse" in errors[0]
        assert edited.as_posix() in errors[0]
        assert "deleting the file" in errors[0] and "adopt" in errors[0]

    def test_the_whole_projection_is_held_back_not_just_the_drifted_file(self, scheduler_main, tree, logger, monkeypatch):
        """A partial rewrite would leave the tree in a state neither the database nor the operator
        asked for, so `refuse` writes nothing at all -- including the configs that did not drift."""
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        tree.project("http/envcfg.conf", b"# from env")
        tree.edit("http/envcfg.conf", b"# OPERATOR EDIT\n")

        scheduler_main.generate_custom_configs([_config("envcfg", b"# from env"), _config("other", b"# other", method="ui")], original_path=tree.root)

        assert not tree.root.joinpath("http", "other.conf").exists()

    def test_no_drift_means_refuse_changes_nothing(self, scheduler_main, tree, logger, monkeypatch):
        """``refuse`` is not "stop projecting": with nothing drifted the pass runs as usual."""
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")

        scheduler_main.generate_custom_configs([_config("fresh", b"# fresh")], original_path=tree.root)

        assert tree.root.joinpath("http", "fresh.conf").read_bytes() == b"# fresh"
        logger.error.assert_not_called()

    def test_an_unknown_policy_value_falls_back_to_overwrite(self, scheduler_main, tree, logger, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "adopt")
        tree.project("http/envcfg.conf", b"# from env")
        edited = tree.edit("http/envcfg.conf", b"# OPERATOR EDIT\n")

        scheduler_main.generate_custom_configs([_config("envcfg", b"# from env")], original_path=tree.root)

        assert edited.read_bytes() == b"# from env"


class TestEnvOnlyInstallIsUnchanged:
    """AC 6. An install whose configs all come from ``CUSTOM_CONF_*`` writes the database bytes to
    disk and reads them back equal, so nothing is drifted and nothing is logged -- on every
    reload, which is the one that matters: a line per file per reload would be the real
    regression."""

    CONFIGS = [
        _config("first", b"# CREATED BY ENV\n# one\n"),
        _config("second", b"# CREATED BY ENV\n# two\n", _type="server_http", service_id="app1.example.com"),
    ]

    def test_a_second_pass_over_its_own_output_is_silent(self, scheduler_main, tree, logger, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)

        scheduler_main.generate_custom_configs(self.CONFIGS, original_path=tree.root)
        before = {path.relative_to(tree.root).as_posix(): path.read_bytes() for path in sorted(tree.root.rglob("*.conf"))}
        logger.reset_mock()

        scheduler_main.generate_custom_configs(self.CONFIGS, original_path=tree.root)
        after = {path.relative_to(tree.root).as_posix(): path.read_bytes() for path in sorted(tree.root.rglob("*.conf"))}

        assert (
            before
            == after
            == {
                "http/first.conf": b"# CREATED BY ENV\n# one\n",
                "server-http/app1.example.com/second.conf": b"# CREATED BY ENV\n# two\n",
            }
        )
        assert _drift_warnings(logger) == []
        logger.error.assert_not_called()

    def test_refuse_does_not_change_it_either(self, scheduler_main, tree, logger, monkeypatch):
        """An env-only install that opts into ``refuse`` must keep projecting, not freeze."""
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")

        scheduler_main.generate_custom_configs(self.CONFIGS, original_path=tree.root)
        logger.reset_mock()
        scheduler_main.generate_custom_configs(self.CONFIGS, original_path=tree.root)

        assert tree.root.joinpath("http", "first.conf").read_bytes() == b"# CREATED BY ENV\n# one\n"
        assert _drift_warnings(logger) == []
        logger.error.assert_not_called()


class TestDrafts:
    def test_a_draft_row_projects_nothing_so_its_file_reads_as_an_orphan(self, scheduler_main, tree, logger, monkeypatch):
        """A draft is deliberately not written, so a file at its path is about to be deleted --
        naming it is the point, and it happens once because the deletion then makes it stop."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        drafted = tree.orphan("http/drafted.conf", b"# left behind\n")

        scheduler_main.generate_custom_configs([_config("drafted", b"# drafted", is_draft=True)], original_path=tree.root)

        drift = _drift_warnings(logger)
        assert len(drift) == 1 and drafted.as_posix() in drift[0]
        assert not drafted.exists()

        logger.reset_mock()
        scheduler_main.generate_custom_configs([_config("drafted", b"# drafted", is_draft=True)], original_path=tree.root)
        assert _drift_warnings(logger) == []


class TestDriftPolicyValue:
    """The scheduler must read the setting the same way the worker does, or the two writers of one
    folder follow different policies.

    ``worker/tasks.py`` clears the job environment and overlays ``db.get_config()`` — defaults
    included — before every job, so the worker reads ``CUSTOM_CONFIGS_DRIFT`` from the **database**.
    Reading only ``getenv`` here would mean a value set in the web UI applies in the worker and is
    ignored in the scheduler, which on all-in-one and Linux is the same directory.
    """

    def test_the_environment_wins_when_it_is_set(self, scheduler_main, monkeypatch):
        monkeypatch.setenv("CUSTOM_CONFIGS_DRIFT", "refuse")
        client = Mock()
        client.get_config.return_value = {"CUSTOM_CONFIGS_DRIFT": "overwrite"}
        monkeypatch.setattr(scheduler_main, "API_CLIENT", client)

        assert scheduler_main._drift_policy_value() == "refuse"
        client.get_config.assert_not_called()

    def test_an_empty_environment_falls_back_to_the_database(self, scheduler_main, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        client = Mock()
        client.get_config.return_value = {"CUSTOM_CONFIGS_DRIFT": "refuse"}
        monkeypatch.setattr(scheduler_main, "API_CLIENT", client)

        assert scheduler_main._drift_policy_value() == "refuse"

    def test_a_ui_set_policy_actually_reaches_the_projection(self, scheduler_main, tree, logger, monkeypatch):
        """The end this exists for: `refuse` chosen in the web UI, never exported to this process."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        client = Mock()
        client.get_config.return_value = {"CUSTOM_CONFIGS_DRIFT": "refuse"}
        monkeypatch.setattr(scheduler_main, "API_CLIENT", client)
        tree.project("http/envcfg.conf", b"# from env")
        edited = tree.edit("http/envcfg.conf", b"# OPERATOR EDIT\n")

        scheduler_main.generate_custom_configs([_config("envcfg", b"# from env")], original_path=tree.root)

        assert edited.read_bytes() == b"# OPERATOR EDIT\n"

    def test_an_unreachable_api_is_not_fatal(self, scheduler_main, monkeypatch):
        """The policy must never be the reason a reload crashes; no API means the default."""
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        client = Mock()
        client.get_config.side_effect = RuntimeError("API unreachable")
        monkeypatch.setattr(scheduler_main, "API_CLIENT", client)

        assert scheduler_main._drift_policy_value() == ""

    def test_no_api_client_at_all_is_not_fatal(self, scheduler_main, monkeypatch):
        monkeypatch.delenv("CUSTOM_CONFIGS_DRIFT", raising=False)
        monkeypatch.setattr(scheduler_main, "API_CLIENT", None)

        assert scheduler_main._drift_policy_value() == ""

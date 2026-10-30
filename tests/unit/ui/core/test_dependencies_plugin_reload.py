"""app/dependencies.py: plugin validation, the DB-to-disk plugin reload and the reload latch.

``UIDatabase`` is a mock (see ``conftest.import_dependencies``); the plugin trees are real
directories under ``tmp_path``, built and unpacked with the same tar helpers production uses.
"""

import json
import os
import stat
from pathlib import Path

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore

REPO_COMMON = Path(__file__).resolve().parents[4] / "src" / "common"

VALID_PLUGIN = {
    "id": "demo",
    "name": "Demo",
    "description": "A demo plugin",
    "version": "1.0",
    "stream": "no",
    "settings": {},
}


def make_plugin_dir(base: Path, plugin_id="demo", plugin_json=None, extra=None):
    root = base / plugin_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(json.dumps(plugin_json if plugin_json is not None else {**VALID_PLUGIN, "id": plugin_id}))
    for name, body in (extra or {}).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    return root


def archive_of(directory: Path) -> bytes:
    return create_plugin_tar_gz(directory, arc_root=directory.name).read()


def db_row(directory: Path, *, plugin_type="external", method="ui", data=True, checksum=True):
    blob = archive_of(directory)
    return {
        "id": directory.name,
        "name": directory.name,
        "type": plugin_type,
        "method": method,
        "data": blob if data else b"",
        "checksum": bytes_hash(blob, algorithm="sha256") if checksum else None,
    }


@pytest.fixture
def deps(import_dependencies, tmp_path, monkeypatch):
    module, db = import_dependencies
    tree = tmp_path / "bw"
    tree.mkdir()
    (tree / "settings.json").symlink_to(REPO_COMMON / "settings.json")
    (tree / "core").symlink_to(REPO_COMMON / "core")
    monkeypatch.setattr(module, "BUNKERWEB_PATH", tree)
    db.checked_changes.return_value = ""
    db.get_plugins.return_value = []
    module.plugin_validator = None
    return module, db


def test_module_wires_its_collaborators(deps, tmp_path):
    module, db = deps
    assert module.DB is db
    assert module.DATA.file_path == tmp_path / "ui_data.json"
    assert module.BW_CONFIG.args == (db, module.DATA)
    assert module.CONFIG_TASKS_EXECUTOR is not module.PAGE_TASKS_EXECUTOR


class TestInvalidPluginJson:
    def test_symlinked_plugin_is_never_flagged(self, deps, tmp_path):
        module, db = deps
        real = make_plugin_dir(tmp_path / "src")
        link = tmp_path / "link"
        link.symlink_to(real)
        assert module.invalid_plugin_json(link) is False

    def test_directory_without_manifest_is_not_flagged(self, deps, tmp_path):
        (tmp_path / "empty").mkdir()
        assert deps[0].invalid_plugin_json(tmp_path / "empty") is False

    def test_unparsable_manifest_is_flagged_and_logged(self, deps, tmp_path):
        module, db = deps
        bad = make_plugin_dir(tmp_path, "badjson")
        (bad / "plugin.json").write_text("{nope")
        assert module.invalid_plugin_json(bad) is True
        assert "Keeping invalid manual plugin badjson" in db.logger.error.call_args.args[0]

    def test_valid_manifest_passes_the_real_validator(self, deps, tmp_path):
        module, db = deps
        assert module.invalid_plugin_json(make_plugin_dir(tmp_path, "goodone")) is False
        assert module.plugin_validator is not None  # built once and kept
        db.logger.error.assert_not_called()

    def test_manifest_failing_validation_is_flagged_with_the_reason(self, deps, tmp_path):
        module, db = deps
        broken = make_plugin_dir(tmp_path, "nosettings", plugin_json={"id": "nosettings", "name": "x"})
        assert module.invalid_plugin_json(broken) is True
        assert "Keeping invalid manual plugin nosettings" in db.logger.error.call_args.args[0]

    def test_validator_crash_is_flagged(self, deps, tmp_path):
        module, db = deps

        class Boom:
            def _Configurator__validate_plugin(self, plugin):
                raise KeyError("settings")

        module.plugin_validator = Boom()
        assert module.invalid_plugin_json(make_plugin_dir(tmp_path, "crashy")) is True
        assert "Keeping invalid manual plugin crashy" in db.logger.error.call_args.args[0]


class TestReloadPlugins:
    def test_database_error_on_the_flag_is_logged_and_returned(self, deps):
        module, db = deps
        db.checked_changes.return_value = "locked"
        assert module.reload_plugins() == "locked"
        assert "An error occurred when setting the changes to checked" in db.logger.error.call_args.args[0]

    def test_external_and_pro_plugins_land_in_their_own_trees(self, deps, tmp_path):
        module, db = deps
        ext = make_plugin_dir(tmp_path / "stage", "extplug", extra={"jobs/run.py": "print(1)", "ui/actions.py": "x = 1", "bwcli/tool.sh": "#!/bin/sh"})
        pro = make_plugin_dir(tmp_path / "stage", "proplug")
        core = make_plugin_dir(tmp_path / "stage", "coreplug")
        db.get_plugins.return_value = [db_row(ext), db_row(pro, plugin_type="pro"), db_row(core, plugin_type="core")]

        assert module.reload_plugins() == ""

        assert (module.EXTERNAL_PLUGINS_PATH / "extplug" / "plugin.json").is_file()
        assert (module.PRO_PLUGINS_PATH / "proplug" / "plugin.json").is_file()
        assert not (module.EXTERNAL_PLUGINS_PATH / "coreplug").exists()
        for relative in ("jobs/run.py", "ui/actions.py", "bwcli/tool.sh"):
            mode = stat.S_IMODE((module.EXTERNAL_PLUGINS_PATH / "extplug" / relative).stat().st_mode)
            assert mode == 0o750, relative
        db.checked_changes.assert_called_once_with(["ui_plugins"])

    def test_matching_checksum_leaves_the_tree_untouched(self, deps, tmp_path):
        module, db = deps
        ext = make_plugin_dir(module.EXTERNAL_PLUGINS_PATH, "same", extra={"marker.txt": "keep"})
        row = db_row(ext)
        os.utime(ext / "marker.txt", (1, 1))
        db.get_plugins.return_value = [row]
        module.reload_plugins()
        assert (ext / "marker.txt").stat().st_mtime == 1

    def test_changed_checksum_replaces_the_tree_from_the_database(self, deps, tmp_path):
        module, db = deps
        staged = make_plugin_dir(tmp_path / "stage", "chg", extra={"new.txt": "from-db"})
        row = db_row(staged)
        live = make_plugin_dir(module.EXTERNAL_PLUGINS_PATH, "chg", extra={"old.txt": "local"})
        db.get_plugins.return_value = [row]
        module.reload_plugins()
        assert (live / "new.txt").read_text() == "from-db"
        assert not (live / "old.txt").exists()

    def test_unreadable_stored_data_keeps_files_and_rearms_the_flag(self, deps, tmp_path):
        module, db = deps
        staged = make_plugin_dir(tmp_path / "stage", "partial")
        live = make_plugin_dir(module.EXTERNAL_PLUGINS_PATH, "partial", extra={"keep.txt": "x"})
        db.get_plugins.return_value = [db_row(staged, data=False)]
        assert module.reload_plugins() == "some plugin data could not be loaded"
        assert (live / "keep.txt").is_file()
        db.checked_changes.assert_called_with(["ui_plugins"], value=True)
        assert 'Data of external plugin "partial" cannot be loaded' in db.logger.error.call_args.args[0]

    def test_orphans_are_removed_but_invalid_manual_ones_are_kept(self, deps, tmp_path):
        module, db = deps
        ext = module.EXTERNAL_PLUGINS_PATH
        make_plugin_dir(ext, "orphan")
        (ext / "stray.txt").write_text("x")
        (ext / "dangling").symlink_to(tmp_path / "nowhere")
        broken = make_plugin_dir(ext, "handmade")
        (broken / "plugin.json").write_text("{broken")
        pro_orphan = make_plugin_dir(module.PRO_PLUGINS_PATH, "proorphan")
        db.get_plugins.return_value = []

        module.reload_plugins()

        assert not (ext / "orphan").exists() and not (ext / "stray.txt").exists() and not (ext / "dangling").is_symlink()
        assert (ext / "handmade").is_dir()
        assert not pro_orphan.exists()

    def test_manual_plugin_with_an_invalid_local_manifest_is_not_overwritten(self, deps, tmp_path):
        module, db = deps
        staged = make_plugin_dir(tmp_path / "stage", "man")
        row = db_row(staged, method="manual")
        live = make_plugin_dir(module.EXTERNAL_PLUGINS_PATH, "man")
        (live / "plugin.json").write_text("{broken")
        db.get_plugins.return_value = [row]
        module.reload_plugins()
        assert (live / "plugin.json").read_text() == "{broken"

    def test_extraction_failure_is_logged_for_managed_plugins_only(self, deps, tmp_path, monkeypatch):
        module, db = deps
        staged = make_plugin_dir(tmp_path / "stage", "oserr")
        monkeypatch.setattr(module, "safe_tar_extractall", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        db.get_plugins.return_value = [db_row(staged)]
        module.reload_plugins()
        assert 'Error while generating external plugins "oserr": disk full' in db.logger.error.call_args.args[0]

        db.logger.error.reset_mock()
        db.get_plugins.return_value = [db_row(staged, method="manual")]
        module.reload_plugins()
        db.logger.error.assert_not_called()

    def test_unexpected_extraction_error_is_always_logged(self, deps, tmp_path, monkeypatch):
        module, db = deps
        staged = make_plugin_dir(tmp_path / "stage", "weird")
        monkeypatch.setattr(module, "safe_tar_extractall", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad tar")))
        db.get_plugins.return_value = [db_row(staged, method="manual")]
        module.reload_plugins()
        assert "bad tar" in db.logger.error.call_args.args[0]

    def test_replaced_symlink_root_is_unlinked_before_extraction(self, deps, tmp_path):
        module, db = deps
        staged = make_plugin_dir(tmp_path / "stage", "linked", extra={"f.txt": "real"})
        row = db_row(staged)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (module.EXTERNAL_PLUGINS_PATH / "linked").symlink_to(elsewhere)
        db.get_plugins.return_value = [row]
        module.reload_plugins()
        target = module.EXTERNAL_PLUGINS_PATH / "linked"
        assert not target.is_symlink() and (target / "f.txt").read_text() == "real"
        assert list(elsewhere.iterdir()) == []


class TestSafeReloadPlugins:
    def test_free_latch_is_taken_and_the_reload_runs(self, deps, monkeypatch):
        module, db = deps
        monkeypatch.setattr(module, "reload_plugins", lambda: "done")
        assert module.safe_reload_plugins() == "done"
        assert module.DATA["IS_RELOADING_PLUGINS"] is True
        assert module.DATA["RELOADING_PLUGINS_SINCE"] > 0

    def test_a_fresh_latch_defers_to_the_holder(self, deps, monkeypatch):
        module, db = deps
        monkeypatch.setattr(module, "reload_plugins", lambda: pytest.fail("must not reload"))
        module.DATA.update({"IS_RELOADING_PLUGINS": True, "RELOADING_PLUGINS_SINCE": module.time()})
        assert module.safe_reload_plugins() is None

    def test_a_stale_latch_is_treated_as_free(self, deps, monkeypatch):
        module, db = deps
        monkeypatch.setattr(module, "reload_plugins", lambda: "done")
        module.DATA.update({"IS_RELOADING_PLUGINS": True, "RELOADING_PLUGINS_SINCE": module.time() - module.RELOAD_LATCH_TIMEOUT - 1})
        assert module.safe_reload_plugins() == "done"

    @pytest.mark.parametrize("flag", ["force", "data"])
    def test_force_overrides_a_fresh_latch(self, deps, monkeypatch, flag):
        module, db = deps
        monkeypatch.setattr(module, "reload_plugins", lambda: "forced")
        module.DATA.update({"IS_RELOADING_PLUGINS": True, "RELOADING_PLUGINS_SINCE": module.time()})
        if flag == "data":
            module.DATA["FORCE_RELOAD_PLUGIN"] = True
            assert module.safe_reload_plugins() == "forced"
        else:
            assert module.safe_reload_plugins(force=True) == "forced"

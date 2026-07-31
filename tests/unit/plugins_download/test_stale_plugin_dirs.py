"""`_cleanup_stale_plugin_dirs` must never delete the last copy of a plugin.

`_install_plugin_atomically` renames the live directory to `.<id>.bak-<uuid>`, then renames the
freshly copied one into its place. Between those two renames there is NO live directory and the
previous version exists only as that backup. The sweep at the start of the next run used to
rmtree every `.bak-*` unconditionally, so a kill in that window destroyed the only local copy
while the database row still claimed the plugin was installed.

Both `misc/jobs/download-plugins.py` and `pro/jobs/download-pro-plugins.py` carry the same
install pattern, so both are exercised here against the same rules.

These are scripts, not modules: importing one runs it and ends in `sys_exit`. Only their
definitions are loaded.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]

JOBS = {
    "external": (ROOT / "src" / "common" / "core" / "misc" / "jobs" / "download-plugins.py", "EXTERNAL_PLUGINS_DIR"),
    "pro": (ROOT / "src" / "common" / "core" / "pro" / "jobs" / "download-pro-plugins.py", "PRO_PLUGINS_DIR"),
}


def _load_definitions(path):
    """Load module-level imports/assignments/defs only, skipping the executable script body."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    # `magic` (libmagic bindings) ships in the runtime images, not in the unit venv, and these
    # jobs import it at module level for content-type sniffing. Stub it rather than adding a
    # binary dependency to the test environment for a function that never calls it.
    stubs = {name: ModuleType(name) for name in ("jobs", "logger", "Database", "common_utils", "API", "ApiCaller", "magic")}
    stubs["magic"].Magic = Mock()
    stubs["jobs"].Job = Mock()
    stubs["logger"].getLogger = Mock(return_value=Mock())
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["Database"].Database = Mock()
    for attribute in ("bytes_hash", "get_os_info", "get_integration", "get_version", "create_plugin_tar_gz", "safe_zip_extractall", "safe_tar_extractall"):
        setattr(stubs["common_utils"], attribute, Mock())

    module = ModuleType(f"bw_{path.stem.replace('-', '_')}")
    module.__dict__["__file__"] = str(path)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(path), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


MODULES = {key: _load_definitions(path) for key, (path, _) in JOBS.items()}


@pytest.fixture(params=sorted(JOBS))
def job(request, tmp_path, monkeypatch):
    """Point one of the two jobs at a scratch plugin directory."""
    module = MODULES[request.param]
    _, dir_attribute = JOBS[request.param]
    monkeypatch.setattr(module, dir_attribute, tmp_path)
    return module, tmp_path


def _make_dir(root, name, marker="plugin.json"):
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / marker).write_text("{}")
    return directory


class TestBackupPromotion:
    def test_a_backup_is_restored_when_its_plugin_is_missing(self, job):
        """The kill window: live directory gone, backup holding the only copy."""
        module, root = job
        _make_dir(root, ".myplugin.bak-abc123")

        module._cleanup_stale_plugin_dirs()

        assert (root / "myplugin" / "plugin.json").is_file()
        assert list(root.glob(".*.bak-*")) == []

    def test_a_backup_is_deleted_once_its_plugin_is_back(self, job):
        """The normal case -- the install completed, so the backup is genuinely stale."""
        module, root = job
        _make_dir(root, "myplugin")
        _make_dir(root, ".myplugin.bak-abc123")

        module._cleanup_stale_plugin_dirs()

        assert (root / "myplugin").is_dir()
        assert list(root.glob(".*.bak-*")) == []

    def test_restoring_one_plugin_does_not_disturb_another(self, job):
        module, root = job
        _make_dir(root, "kept")
        _make_dir(root, ".kept.bak-111")
        _make_dir(root, ".lost.bak-222")

        module._cleanup_stale_plugin_dirs()

        assert (root / "kept" / "plugin.json").is_file()
        assert (root / "lost" / "plugin.json").is_file()
        assert list(root.glob(".*.bak-*")) == []

    def test_a_plugin_id_containing_dots_is_restored_under_its_full_name(self, job):
        """The id is everything between the leading dot and `.bak-`, so it must not be split on
        the first dot it happens to contain."""
        module, root = job
        _make_dir(root, ".my.plugin.v2.bak-abc123")

        module._cleanup_stale_plugin_dirs()

        assert (root / "my.plugin.v2" / "plugin.json").is_file()


class TestTemporaryDirs:
    def test_a_temporary_dir_is_always_removed(self, job):
        """`.tmp-` holds a half-finished copy of the NEW version. It is never worth keeping, and
        must never be promoted -- that would install a partial plugin."""
        module, root = job
        _make_dir(root, ".myplugin.tmp-abc123")

        module._cleanup_stale_plugin_dirs()

        assert not (root / "myplugin").exists()
        assert list(root.glob(".*.tmp-*")) == []

    def test_a_temporary_dir_is_removed_even_with_no_live_plugin(self, job):
        module, root = job
        _make_dir(root, ".gone.tmp-abc123")

        module._cleanup_stale_plugin_dirs()

        assert not (root / "gone").exists()
        assert list(root.glob("*")) == []


class TestFailureToRestore:
    def test_an_unrestorable_backup_is_left_on_disk_rather_than_deleted(self, job, monkeypatch):
        """If the promotion fails, the backup is still the only copy. Keeping an unremovable
        directory is a far better outcome than deleting the plugin."""
        module, root = job
        backup = _make_dir(root, ".myplugin.bak-abc123")

        def refuse(self, target):
            raise OSError("cross-device link")

        monkeypatch.setattr(Path, "rename", refuse)
        module._cleanup_stale_plugin_dirs()

        assert (backup / "plugin.json").is_file()

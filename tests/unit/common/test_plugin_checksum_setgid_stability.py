"""A plugin archive hashes the same before and after the database round trip, whatever the staging directory mode.

On Linux the packaging scripts set `/var/tmp/bunkerweb` to `2770`, so the directories the plugin
downloaders stage under it inherit setgid (`2750` under `UMask=027`). `create_plugin_tar_gz()` kept
that mode in its directory entries, while `safe_tar_extractall()` restores directories with
`member.mode & 0o755`. The installed tree then hashed differently from the checksum stored with it,
the integrity check reinstalled the plugin on every run, and each reinstall flagged the plugins as
changed again (#4024).

`plugin_tar_filter()` now forces directory entries to `0o755` and drops group/other write. The cycle
below mirrors the downloaders: stage under a `2770` parent with `umask 0o027`, strip the write bits,
archive, hash, restore, hash again.
"""

import os
import tarfile
from io import BytesIO
from shutil import copytree

import pytest

import common_utils  # type: ignore
from common_utils import bytes_hash, create_plugin_tar_gz, safe_tar_extractall, strip_plugin_write_bits  # type: ignore

PLUGIN = "sample"


@pytest.fixture(autouse=True)
def umask_027():
    previous = os.umask(0o027)
    yield
    os.umask(previous)


@pytest.fixture(params=["native", "fallback"])
def extract_branch(request, monkeypatch):
    """Run the restore through each `safe_tar_extractall()` branch (the 3.11 runtimes have no `data_filter`)."""
    if request.param == "native":
        if not hasattr(tarfile, "data_filter") or not common_utils._supports_tar_filter(tarfile.TarFile):
            pytest.skip("this runtime has no tarfile.data_filter")
    else:
        monkeypatch.setattr(common_utils, "_supports_tar_filter", lambda tar: False)
        # 3.14 filters a bare extract() with data_filter on its own; the runtimes this branch serves apply the raw mode.
        if hasattr(tarfile, "fully_trusted_filter"):
            monkeypatch.setattr(tarfile.TarFile, "extraction_filter", staticmethod(tarfile.fully_trusted_filter), raising=False)
    return request.param


def _setgid_dir(tmp_path, name):
    directory = tmp_path / name
    directory.mkdir()
    directory.chmod(0o2770)
    if not directory.stat().st_mode & 0o2000:
        pytest.skip("this file system does not keep the setgid bit on a directory")
    return directory


def _write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)


def _plugin_tree(parent):
    """A plugin as a downloader leaves it after `_set_plugin_permissions()`, built under a setgid parent."""
    root = parent / PLUGIN
    root.mkdir()
    _write(root / "plugin.json", '{"id": "sample"}', 0o640)
    _write(root / "jobs" / "job.py", "print('job')\n", 0o750)
    _write(root / "ui" / "actions.py", "def pre_render(**kwargs): pass\n", 0o750)
    _write(root / "ui" / "templates" / "page.html", "<p>page</p>\n", 0o640)
    _write(root / "docs" / "readme.md", "readme\n", 0o640)
    return root


def _modes(root):
    return {path.relative_to(root.parent).as_posix(): path.stat().st_mode & 0o7777 for path in (root, *sorted(root.rglob("*")))}


def _stage(source, parent, name=PLUGIN):
    """What an install does to a downloaded tree: copy it under the staging directory, then strip the write bits."""
    staged = parent / name
    copytree(source, staged)
    strip_plugin_write_bits(staged)
    return staged


def _archive(root):
    return create_plugin_tar_gz(root, arc_root=root.name).getvalue()


def _checksum(data):
    return bytes_hash(BytesIO(data), algorithm="sha256")


def _restore(data, parent):
    """What `generate_external_plugins()` does with the stored archive."""
    parent.mkdir(exist_ok=True)
    with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tar:
        safe_tar_extractall(tar, parent)
    return parent / PLUGIN


def _tarinfo_1616(tarinfo):
    """`plugin_tar_filter()` as 1.6.16 shipped it: directory and file modes left as they are."""
    tarinfo.mtime = 0
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = "root"
    tarinfo.gname = "root"
    return tarinfo


def _archive_modes(data):
    with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tar:
        return {member.name: member.mode & 0o7777 for member in tar.getmembers()}


def test_the_fixture_reproduces_the_setgid_staging_tree(tmp_path):
    staging = _setgid_dir(tmp_path, "staging")
    staged = _stage(_plugin_tree(_setgid_dir(tmp_path, "download")), staging)

    assert staged.stat().st_mode & 0o7777 == 0o2750
    assert (staged / "jobs").stat().st_mode & 0o7777 == 0o2750


def test_the_checksum_holds_across_three_restore_cycles(tmp_path, extract_branch):
    staging = _setgid_dir(tmp_path, "staging")
    restored_parent = _setgid_dir(tmp_path, "restored")
    stored = _archive(_stage(_plugin_tree(_setgid_dir(tmp_path, "download")), staging))
    checksum = _checksum(stored)

    for cycle in range(3):
        installed = _restore(stored, restored_parent / f"cycle{cycle}")
        assert _checksum(_archive(installed)) == checksum, f"cycle {cycle} hashed differently after the restore"
        stored = _archive(installed)


def test_a_content_change_still_changes_the_checksum(tmp_path, extract_branch):
    staging = _setgid_dir(tmp_path, "staging")
    stored = _archive(_stage(_plugin_tree(_setgid_dir(tmp_path, "download")), staging))
    installed = _restore(stored, tmp_path / "restored")

    (installed / "jobs" / "job.py").write_text("print('changed')\n")
    assert _checksum(_archive(installed)) != _checksum(stored)

    (installed / "jobs" / "job.py").write_text("print('job')\n")
    assert _checksum(_archive(installed)) == _checksum(stored)

    _write(installed / "docs" / "extra.md", "extra\n", 0o640)
    assert _checksum(_archive(installed)) != _checksum(stored)


def test_file_modes_survive_the_restore_and_directories_lose_the_special_bits(tmp_path, extract_branch):
    staging = _setgid_dir(tmp_path, "staging")
    stored = _archive(_stage(_plugin_tree(_setgid_dir(tmp_path, "download")), staging))
    installed = _restore(stored, tmp_path / "restored")

    modes = _modes(installed)
    assert modes[f"{PLUGIN}/plugin.json"] == 0o640
    assert modes[f"{PLUGIN}/ui/templates/page.html"] == 0o640
    assert modes[f"{PLUGIN}/jobs/job.py"] == 0o750
    assert modes[f"{PLUGIN}/ui/actions.py"] == 0o750
    assert {mode for name, mode in modes.items() if (installed.parent / name).is_dir()} == {0o755}


def test_an_archive_in_the_1616_format_mismatches_once_then_the_refreshed_one_is_stable(tmp_path, monkeypatch, extract_branch):
    staging = _setgid_dir(tmp_path, "staging")
    download = _plugin_tree(_setgid_dir(tmp_path, "download"))

    # The archive a 1.6.16 downloader stored: directory entries keep the setgid bit.
    with monkeypatch.context() as old:
        old.setattr(common_utils, "plugin_tar_filter", _tarinfo_1616)
        old_archive = _archive(_stage(download, staging / "old"))
    assert _archive_modes(old_archive)[PLUGIN] == 0o2750
    assert _archive_modes(old_archive)[f"{PLUGIN}/jobs"] == 0o2750

    # The tree installed from it hashes differently: the integrity check sees one mismatch ...
    installed = _restore(old_archive, tmp_path / "from-old")
    assert _checksum(_archive(installed)) != _checksum(old_archive)

    # ... the reinstall stores the canonical archive ...
    new_archive = _archive(_stage(download, staging / "new"))
    assert _archive_modes(new_archive)[PLUGIN] == 0o755
    assert _checksum(new_archive) != _checksum(old_archive)

    # ... and every later check agrees with it.
    stored = new_archive
    for cycle in range(3):
        installed = _restore(stored, tmp_path / f"from-new{cycle}")
        stored_again = _archive(installed)
        assert _checksum(stored_again) == _checksum(new_archive), f"cycle {cycle} hashed differently after the restore"
        stored = stored_again


@pytest.mark.parametrize(("plugin_type", "flag"), [("external", "external_plugins_changed"), ("pro", "pro_plugins_changed")])
def test_reingesting_an_identical_checksum_raises_no_change_flag(db, tmp_path, monkeypatch, plugin_type, flag):
    """A reinstall that stores the checksum the database already holds must not ask for a reconfiguration.

    This is what keeps an integrity mismatch that reinstalls identical content from feeding itself.
    """
    import Database as database_module
    from fixtures.seed import make_external_plugin, seed_minimal

    seed_minimal(db)
    monkeypatch.setattr(database_module, "sep", str(tmp_path))

    def ingest(checksum):
        plugin = make_external_plugin(method="scheduler", checksum=checksum, data=checksum.encode())
        return db.update_external_plugins([plugin], _type=plugin_type, per_plugin_commit=False)

    assert ingest("first") == ""
    assert db.get_metadata()[flag] is True
    # The first re-ingest still rewrites the stored `separator` of a setting that declares none (the column
    # defaults to " " on insert), so it settles the rows before the flag is checked.
    assert ingest("first") == ""
    assert db.checked_changes() == ""
    assert db.get_metadata()[flag] is False

    assert ingest("first") == ""
    assert db.get_metadata()[flag] is False

    assert ingest("second") == ""
    assert db.get_metadata()[flag] is True

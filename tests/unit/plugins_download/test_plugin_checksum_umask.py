"""A plugin tree hashes the same before and after the restore, whatever umask wrote it (#4024).

A plugin's checksum is the sha256 of `create_plugin_tar_gz(dir)`, and the tar records each entry's
mode. `safe_tar_extractall` restores a plugin from its stored tarball with the tarfile `data`
filter, which drops group/other write from files and ignores the mode of directories (they come
out as `0777 & ~umask`). A tree written under a group-writable umask (zip extraction, plain file
writes) therefore hashed differently from its own restore: PRO plugins were reinstalled on every
check.
"""

import os
import tarfile
from io import BytesIO

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz, safe_tar_extractall  # type: ignore


def _checksum(directory):
    return bytes_hash(create_plugin_tar_gz(directory, arc_root="myplugin"), algorithm="sha256")


def _build(root, umask):
    """Write a small plugin the way a job does: files and directories created under `umask`."""
    previous = os.umask(umask)
    try:
        plugin = root / "myplugin"
        (plugin / "jobs" / "sub").mkdir(parents=True)
        (plugin / "plugin.json").write_text('{"id": "myplugin"}')
        (plugin / "jobs" / "run.py").write_text("print('x')")
        (plugin / "jobs" / "sub" / "helper.py").write_text("x = 1")
        (plugin / "jobs" / "run.py").chmod(0o770 & ~umask)
    finally:
        os.umask(previous)
    return plugin


def _restore(plugin, dest, umask):
    blob = create_plugin_tar_gz(plugin, arc_root="myplugin").getvalue()
    previous = os.umask(umask)
    try:
        with tarfile.open(fileobj=BytesIO(blob), mode="r:gz") as tar:
            safe_tar_extractall(tar, dest)
    finally:
        os.umask(previous)
    return dest / "myplugin"


@pytest.mark.parametrize("restore_umask", [0o002, 0o022])
def test_checksum_survives_restore_under_group_writable_umask(tmp_path, restore_umask):
    plugin = _build(tmp_path / "src", 0o002)
    restored = _restore(plugin, tmp_path / "out", restore_umask)

    assert _checksum(plugin) == _checksum(restored)


@pytest.mark.parametrize("restore_umask", [0o002, 0o022])
def test_checksum_does_not_depend_on_the_umask_that_wrote_the_tree(tmp_path, restore_umask):
    group_writable = _build(tmp_path / "a", 0o002)
    private = _build(tmp_path / "b", 0o022)

    assert _checksum(group_writable) == _checksum(private)
    assert _checksum(_restore(group_writable, tmp_path / "out", restore_umask)) == _checksum(private)


def test_the_executable_bit_still_counts(tmp_path):
    plugin = _build(tmp_path / "src", 0o022)
    before = _checksum(plugin)
    (plugin / "jobs" / "run.py").chmod(0o640)

    assert _checksum(plugin) != before

"""PRO plugins were downloaded again on every restart because their archive bytes never repeated.

A plugin's checksum is the hash of its tar.gz. The archive carried each file's modification time, listed
entries in directory order and stamped the gzip header with the current time, so the same plugin hashed
differently each time it was packed and the scheduler saw a new version on every start. The tests pack the
same content under different file times, creation orders and clocks and require identical bytes.

Refs: #3258.
"""

import gzip
import os
import tarfile
from io import BytesIO

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore

FILES = {
    "plugin.json": '{"id": "myplugin"}',
    "jobs/run.py": "print('run')",
    "jobs/sub/helper.py": "x = 1",
    "ui/page.html": "<p>page</p>",
    "README.md": "# plugin",
}


def _build(root, order, *, mtime):
    plugin = root / "myplugin"
    plugin.mkdir(parents=True)
    for name in order:
        path = plugin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FILES[name])
    for path in (*plugin.rglob("*"), plugin):
        os.utime(path, (mtime, mtime))
    return plugin


def _pack(plugin):
    return create_plugin_tar_gz(plugin, arc_root="myplugin").getvalue()


def test_file_modification_times_do_not_change_the_archive(tmp_path):
    first = _pack(_build(tmp_path / "a", list(FILES), mtime=1_700_000_000))
    second = _pack(_build(tmp_path / "b", list(FILES), mtime=1_800_000_000))

    assert bytes_hash(first, algorithm="sha256") == bytes_hash(second, algorithm="sha256")
    assert first == second


def test_creation_order_does_not_change_the_archive(tmp_path):
    first = _pack(_build(tmp_path / "a", list(FILES), mtime=1_700_000_000))
    second = _pack(_build(tmp_path / "b", list(reversed(FILES)), mtime=1_700_000_000))

    assert first == second
    with tarfile.open(fileobj=BytesIO(first), mode="r:gz") as tar:
        names = tar.getnames()
    assert names == sorted(names)


def test_the_clock_at_packing_time_does_not_change_the_archive(tmp_path, monkeypatch):
    plugin = _build(tmp_path / "a", list(FILES), mtime=1_700_000_000)
    monkeypatch.setattr(gzip.time, "time", lambda: 1_700_000_000.0)
    first = _pack(plugin)
    monkeypatch.setattr(gzip.time, "time", lambda: 1_900_000_000.0)
    second = _pack(plugin)

    assert first == second
    assert first[4:8] == b"\x00\x00\x00\x00"

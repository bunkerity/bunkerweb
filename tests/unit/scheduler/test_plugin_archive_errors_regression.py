"""Unusable plugin archives must compare unequal instead of aborting generation.

Corrupt gzip/tar data and read failures must follow the comparison's False fallback.
"""

from io import BytesIO
from tarfile import ExFileObject, TarError

import pytest


@pytest.mark.parametrize("corrupt", ["installed", "stored", "read-error"])
def test_unreadable_archive_returns_false(sched_main, tmp_path, monkeypatch, corrupt):
    plugin_dir = tmp_path / "demo"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"id":"demo"}')
    valid = sched_main.create_plugin_tar_gz(plugin_dir).getvalue()
    data = b"invalid gzip/tar bytes" if corrupt == "stored" else valid
    plugin = {"data": data, "checksum": sched_main.bytes_hash(data, algorithm="sha256")}

    if corrupt == "read-error":

        def fail_read(*args):
            raise OSError("injected archive read failure")

        monkeypatch.setattr(ExFileObject, "read", fail_read)

    installed = BytesIO(b"invalid gzip/tar bytes" if corrupt == "installed" else valid)
    try:
        result = sched_main.installed_plugin_matches_archive(installed, plugin)
    except (OSError, TarError, ValueError) as error:
        result = error
    assert result is False, f"unreadable archives must return False, got {result!r}"

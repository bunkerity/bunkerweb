"""Scheduler permission changes must not reinstall an unchanged plugin (#4024)."""

import ast
import logging
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from tarfile import open as tar_open
from traceback import format_exc
from types import SimpleNamespace
from typing import Union

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz, plugin_tar_exclude

ROOT = Path(__file__).resolve().parents[3]


def generate(plugins_dir, plugin, removed):
    tree = ast.parse((ROOT / "src/scheduler/main.py").read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "generate_external_plugins")
    namespace = {
        "Path": Path,
        "Union": Union,
        "BytesIO": BytesIO,
        "suppress": suppress,
        "tar_open": tar_open,
        "format_exc": format_exc,
        "S_IRGRP": S_IRGRP,
        "S_IRUSR": S_IRUSR,
        "S_IWUSR": S_IWUSR,
        "S_IXGRP": S_IXGRP,
        "S_IXUSR": S_IXUSR,
        "bytes_hash": bytes_hash,
        "create_plugin_tar_gz": create_plugin_tar_gz,
        "plugin_tar_exclude": plugin_tar_exclude,
        "EXTERNAL_PLUGINS_PATH": plugins_dir,
        "API_CLIENT": SimpleNamespace(get_plugins=lambda **kwargs: [plugin]),
        "LOGGER": logging.getLogger("plugin-permissions"),
        "read_manual_plugin": lambda *args: ({"id": "sample"}, None),
        "get_plugin_validator": lambda: None,
        "rmtree": lambda path, **kwargs: (removed.append(path), rmtree(path, **kwargs)),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "scheduler/main.py", "exec"), namespace)
    namespace["generate_external_plugins"](plugins_dir)


@pytest.mark.parametrize("change", [None, "content", "extra", "missing", "mode", "checksum", "symlink"])
def test_scheduler_normalizes_executables_once(tmp_path, change):
    root = tmp_path / "download/sample"
    root.mkdir(parents=True)
    (root / "plugin.json").write_text('{"id":"sample"}')
    for name in ("jobs/run.py", "jobs/sub/run.py", "bwcli/tool", "ui/actions.py", "ui/page.html", "ui/other.html"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n")
        path.chmod(0o640)
    (root / "ui/resource").symlink_to("page.html")
    data = create_plugin_tar_gz(root, arc_root="sample").getvalue()
    plugin = {"id": "sample", "name": "sample", "method": "scheduler", "data": data, "checksum": bytes_hash(data, algorithm="sha256")}
    installed_dir = tmp_path / "plugins"
    removed = []
    generate(installed_dir, plugin, removed)
    job = installed_dir / "sample/jobs/run.py"
    assert job.stat().st_mode & 0o777 == 0o750
    installed_archive = create_plugin_tar_gz(installed_dir / "sample", arc_root="sample")
    assert bytes_hash(installed_archive, algorithm="sha256") != plugin["checksum"]
    if change == "content":
        job.write_text("modified\n")
    elif change == "extra":
        (installed_dir / "sample/extra").write_text("extra")
    elif change == "missing":
        job.unlink()
    elif change == "mode":
        (installed_dir / "sample/ui/page.html").chmod(0o600)
    elif change == "checksum":
        plugin["checksum"] = "invalid"
    elif change == "symlink":
        link = installed_dir / "sample/ui/resource"
        link.unlink()
        link.symlink_to("other.html")
    for _ in range(3):
        generate(installed_dir, plugin, removed)
        if change:
            break
    assert bool(removed) is bool(change)

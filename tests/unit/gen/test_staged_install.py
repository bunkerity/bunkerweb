"""Failed rendering or installation must not publish a partial generation."""

from pathlib import Path
import runpy
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_failed_render_keeps_existing_output(tmp_path, monkeypatch):
    import Templator
    import Configurator

    output = tmp_path / "output"
    output.mkdir()
    (output / "policy.conf").write_text("deny all;\n")
    (output / "variables.env").write_text("IS_LOADING=no\n")
    settings, variables = tmp_path / "settings.json", tmp_path / "variables.env"
    settings.write_text("{}")
    variables.write_text("SERVER_NAME=\n")
    for name in ("templates", "core", "plugins", "pro-plugins"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(Configurator, "Configurator", Mock(return_value=Mock(get_config=Mock(return_value={}))))

    reached = []

    def render(instance):
        reached.append(True)
        (instance._output / "partial.conf").write_text("partial")
        raise ValueError("broken template")

    monkeypatch.setattr(Templator.Templator, "render", render)
    monkeypatch.setattr(Templator, "sep", str(tmp_path))
    argv = [
        str(ROOT / "src/common/gen/main.py"),
        "--settings",
        str(settings),
        "--variables",
        str(variables),
        "--output",
        str(output),
        "--target",
        str(tmp_path / "target"),
    ]
    for name in ("templates", "core", "plugins", "pro-plugins"):
        argv.extend([f"--{name}", str(tmp_path / name)])
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as failure:
        runpy.run_path(argv[0], run_name="__main__")
    assert failure.value.code != 0
    assert reached == [True], "fixture did not reach template rendering"
    assert {p.name: p.read_text() for p in output.iterdir()} == {"policy.conf": "deny all;\n", "variables.env": "IS_LOADING=no\n"}


def test_install_failure_keeps_sentinel(tmp_path, monkeypatch):
    from sync_tree import INSTALL_SENTINEL, sync_tree
    import sync_tree as module

    source, destination = tmp_path / "stage", tmp_path / "dest"
    source.mkdir()
    destination.mkdir()
    (source / "policy.conf").write_text("new")
    (destination / "policy.conf").write_text("old")

    def fail(*args):
        assert (destination / INSTALL_SENTINEL).is_file()
        raise OSError("disk full")

    monkeypatch.setattr(module, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        sync_tree(source, destination)
    assert (destination / INSTALL_SENTINEL).is_file()
    assert (destination / "policy.conf").read_text() == "old"


def test_complete_install_removes_stale_entries_and_sentinel(tmp_path):
    from sync_tree import INSTALL_SENTINEL, sync_tree

    source, destination = tmp_path / "stage", tmp_path / "dest"
    source.mkdir()
    destination.mkdir()
    (destination / INSTALL_SENTINEL).touch()
    (destination / ".stale").write_text("stale")
    (destination / ".bw-rescue.1").mkdir()
    (destination / "nested").mkdir()
    (destination / "nested/old").touch()
    (source / "nested").mkdir()
    (source / "nested/new").write_text("policy")
    sync_tree(source, destination)
    assert (destination / "nested/new").read_text() == "policy"
    assert not (destination / "nested/old").exists()
    assert not (destination / ".stale").exists()
    assert not (destination / INSTALL_SENTINEL).exists()
    assert (destination / ".bw-rescue.1").is_dir()


def test_output_directory_may_be_a_symlink(tmp_path):
    from sync_tree import sync_tree

    real = tmp_path / "real"
    real.mkdir()
    destination = tmp_path / "output"
    destination.symlink_to(real, target_is_directory=True)
    stage = destination / ".bw-stage"
    stage.mkdir()
    (stage / "policy.conf").write_text("deny all;")
    sync_tree(stage, destination)
    assert destination.is_symlink()
    assert (real / "policy.conf").read_text() == "deny all;"

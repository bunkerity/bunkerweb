"""The config saver must keep registered plugins ahead of new setting-id claimants."""

import json
import logging
import runpy
import sys
from pathlib import Path

import pytest

import common_utils
import logger
from fixtures.seed import make_external_plugin, make_general_settings

ROOT = Path(__file__).resolve().parents[3]
GEN = ROOT / "src" / "common" / "gen"


def _mount(directory, plugin_id, key):
    plugin = make_external_plugin(plugin_id)
    manifest = {name: plugin[name] for name in ("id", "name", "description", "version", "stream")}
    manifest["settings"] = {key: {"id": "shared-id", "context": "global", "default": "x", "help": "h", "label": "L", "regex": "^.*$", "type": "text"}}
    folder = directory / plugin_id
    folder.mkdir()
    (folder / "plugin.json").write_text(json.dumps(manifest))


@pytest.fixture
def saver(db, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(GEN))
    monkeypatch.setattr(common_utils, "get_version", lambda: (ROOT / "src" / "VERSION").read_text().strip())
    monkeypatch.setattr(logger, "getLogger", logging.getLogger)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(make_general_settings()))
    core, external, pro = (tmp_path / name for name in ("core", "external", "pro"))
    for directory in (core, external, pro):
        directory.mkdir()
    variables = tmp_path / "variables.env"
    variables.write_text(f"DATABASE_URI={db.database_uri}\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(GEN / "save_config.py"),
            "--settings",
            str(settings),
            "--core",
            str(core),
            "--plugins",
            str(external),
            "--pro-plugins",
            str(pro),
            "--variables",
            str(variables),
            "--init",
        ],
    )

    def run():
        with pytest.raises(SystemExit) as stopped:
            runpy.run_path(str(GEN / "save_config.py"), run_name="__main__")
        assert stopped.value.code == 0

    return run, {"external": external, "pro": pro}


@pytest.mark.parametrize("registered_type", ["external", "pro"])
@pytest.mark.parametrize("new_type", ["external", "pro"])
def test_save_config_keeps_a_registered_plugins_settings(db, saver, caplog, registered_type, new_type):
    run, directories = saver
    _mount(directories[registered_type], "z_registered", "REGISTERED_ONE")
    run()
    assert db.get_metadata()["is_initialized"]
    assert not isinstance(db.save_config({"REGISTERED_ONE": "kept"}, "scheduler"), str)
    before = next(plugin for plugin in db.get_plugins(_type=registered_type) if plugin["id"] == "z_registered")
    _mount(directories[new_type], "a_new", "NEW_ONE")

    with caplog.at_level(logging.ERROR):
        run()

    plugins = {plugin["id"]: plugin for plugin in db.get_plugins()}
    assert plugins["z_registered"]["settings"] == before["settings"]
    assert db.get_config()["REGISTERED_ONE"] == "kept"
    assert "a_new" not in plugins
    assert f"Refusing {new_type} plugin a_new" in caplog.text
    assert "shared-id" in caplog.text and "z_registered" in caplog.text
    assert "IntegrityError" not in caplog.text


def test_save_config_does_not_read_plugins_before_initialization(db, saver, monkeypatch):
    run, _ = saver
    assert not db.get_metadata()["is_initialized"]

    def unexpected_read(*args, **kwargs):
        pytest.fail("save_config read plugins from an uninitialized database")

    monkeypatch.setattr(type(db), "get_plugins", unexpected_read)
    run()
    assert db.get_metadata()["is_initialized"]

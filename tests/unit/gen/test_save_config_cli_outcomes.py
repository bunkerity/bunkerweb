"""Saver CLI propagates failures and passes computed state to its database boundary."""

import os
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import common_utils
import Configurator
import Database
import logger
import save_config


@pytest.fixture
def saver(tmp_path, monkeypatch):
    paths = {name: tmp_path / name for name in ("settings", "core", "plugins", "pro-plugins")}
    paths["settings"].write_text("{}")
    for name in ("core", "plugins", "pro-plugins"):
        paths[name].mkdir()
    variables = tmp_path / "variables.env"
    variables.write_text("DATABASE_URI=sqlite:///from-file.sqlite\n")
    monkeypatch.setattr(common_utils, "get_integration", lambda: "Docker")
    monkeypatch.setattr(common_utils, "get_version", lambda: "9.9.9")
    log = Mock()
    monkeypatch.setattr(logger, "getLogger", lambda *args: log)
    settings = {"BUNKERWEB_INSTANCES": "", "API_HTTP_PORT": "5000", "API_HTTPS_PORT": "5443", "API_SERVER_NAME": "bwapi"}
    config = Mock()
    config.get_config.side_effect = lambda *args, **kwargs: settings.copy()
    config.get_settings.return_value = {"settings": "general"}
    config.get_plugins.side_effect = lambda kind: {"plugins": kind}
    config.explicit_keys = {"BUNKERWEB_INSTANCES"}
    factory = Mock(return_value=config)
    monkeypatch.setattr(Configurator, "Configurator", factory)
    db = Mock()
    db.database_uri = "sqlite:///unused.sqlite"
    db.get_metadata.return_value = {"is_initialized": True, "version": "9.9.9"}
    db.init_tables.return_value = (False, "")
    db.initialize_db.return_value = ""
    db.save_config.return_value = {"general"}
    db.save_custom_configs.return_value = ""
    db.update_instances.return_value = ""
    db.add_instance.return_value = ""
    db.checked_changes.return_value = ""
    db_factory = Mock(return_value=db)
    monkeypatch.setattr(Database, "Database", db_factory)
    for key in tuple(os.environ):
        if "CUSTOM_CONF_" in key:
            monkeypatch.delenv(key)

    def run(*args):
        argv = [save_config.__file__]
        for name, path in paths.items():
            argv.extend(["--" + name, str(path)])
        monkeypatch.setattr("sys.argv", argv + list(args))
        try:
            runpy.run_path(save_config.__file__, run_name="__main__")
        except SystemExit as error:
            return error.code
        return 0

    return SimpleNamespace(run=run, db=db, config=config, settings=settings, paths=paths, variables=variables, log=log, db_factory=db_factory)


def test_save_success_marks_changes_and_uses_dotenv_database(saver, monkeypatch):
    monkeypatch.setenv("CUSTOM_CONF_HTTP_global.conf", "set $global safe;")
    monkeypatch.setenv("app.example.com_CUSTOM_CONF_SERVER_HTTP_route.conf", "set $route safe;")
    assert saver.run("--variables", str(saver.variables), "--method", "autoconf", "--first-run") == 0
    saver.db_factory.assert_called_once_with(saver.log, sqlalchemy_string="sqlite:///from-file.sqlite")
    saver.config.get_config.assert_called_once_with(saver.db, first_run=True)
    saver.db.save_config.assert_called_once_with(saver.settings, "autoconf", changed=False, explicit_keys={"BUNKERWEB_INSTANCES"})
    configs, method = saver.db.save_custom_configs.call_args.args
    assert method == "autoconf"
    assert {conf["exploded"]: conf["value"] for conf in configs} == {
        ("", "HTTP", "global"): "# CREATED BY ENV\nset $global safe;",
        ("app.example.com", "SERVER_HTTP", "route"): "# CREATED BY ENV\nset $route safe;",
    }
    assert all(conf["is_draft"] is False for conf in configs)
    saver.db.checked_changes.assert_called_once_with(["config", "custom_configs", "instances"], plugins_changes={"general"}, value=True)


def test_instances_deduplicate_hostname_and_keep_transport_ports(saver):
    saver.settings["BUNKERWEB_INSTANCES"] = "http://one.example:6000 https://one.example:7443 https://two.example:6443 http://[broken"
    assert saver.run() == 0
    assert [call.args for call in saver.db.add_instance.call_args_list] == [("one.example", 6000, "bwapi"), ("two.example", "5000", "bwapi")]
    assert saver.db.add_instance.call_args_list[0].kwargs == {"method": "manual", "changed": False, "listen_https": False, "https_port": "5443"}
    assert saver.db.add_instance.call_args_list[1].kwargs == {"method": "manual", "changed": False, "listen_https": True, "https_port": 6443}
    warnings = " ".join(str(call.args[0]) for call in saver.log.warning.call_args_list)
    assert "Duplicate BunkerWeb instance hostname one.example" in warnings
    assert "Invalid BunkerWeb instance http://[broken" in warnings


def test_save_error_exits_nonzero_even_if_custom_configs_succeed(saver):
    saver.db.save_config.return_value = "injected save failure"
    assert saver.run() == 1
    assert "injected save failure" in str(saver.log.error.call_args_list)
    saver.db.checked_changes.assert_called_once_with(["custom_configs", "instances"], plugins_changes=set(), value=True)


def test_init_only_initializes_fresh_database(saver):
    saver.db.get_metadata.return_value = "not initialized"
    saver.db.init_tables.return_value = (True, "")
    assert saver.run("--init") == 0
    saver.db.initialize_db.assert_called_once_with(version="9.9.9", integration="Docker")
    assert saver.db.init_tables.call_args.args[0] == [{"settings": "general"}, {"plugins": "core"}, {"plugins": "external"}, {"plugins": "pro"}]
    saver.db.save_config.assert_not_called()


@pytest.mark.parametrize("initialized", [True, False])
def test_table_initialization_error_stops_before_config_save(saver, initialized):
    saver.db.get_metadata.return_value = {"is_initialized": initialized, "version": "9.9.9"}
    saver.db.init_tables.return_value = (False, "bad schema")
    assert saver.run() == 1
    saver.db.initialize_db.assert_not_called()
    saver.db.save_config.assert_not_called()
    assert "bad schema" in str(saver.log.error.call_args_list)


def test_metadata_error_stops_before_config_save(saver):
    saver.db.initialize_db.return_value = "metadata write failed"
    assert saver.run() == 1
    saver.db.save_config.assert_not_called()
    assert "metadata write failed" in str(saver.log.error.call_args_list)


def test_warning_failures_leave_successful_settings_saved(saver):
    saver.db.save_custom_configs.return_value = "bad custom config"
    saver.db.update_instances.return_value = "clear instances failed"
    saver.db.add_instance.return_value = "add instance failed"
    saver.settings["BUNKERWEB_INSTANCES"] = "one.example"
    assert saver.run("--no-check-changes") == 0
    saver.db.checked_changes.assert_not_called()
    warnings = " ".join(str(call.args[0]) for call in saver.log.warning.call_args_list)
    assert "bad custom config" in warnings and "clear instances failed" in warnings and "add instance failed" in warnings


@pytest.mark.parametrize("missing", ["settings", "core", "plugins", "pro-plugins"])
def test_missing_input_stops_before_database_access(saver, missing):
    path = saver.paths[missing]
    path.unlink() if path.is_file() else path.rmdir()
    assert saver.run() == 1
    saver.db_factory.assert_not_called()
    assert str(path) in str(saver.log.error.call_args_list)


def test_unexpected_database_error_has_failure_exit(saver):
    saver.db.get_metadata.side_effect = RuntimeError("unavailable")
    assert saver.run() == 1
    saver.db.save_config.assert_not_called()
    assert "unavailable" in str(saver.log.error.call_args_list)


@pytest.mark.parametrize(
    "stored,installed,engine,expected",
    [
        ("1.6.17", "1.6.17", "sqlite", False),
        ("1.6.17", "1.6.18~rc2", "sqlite", True),
        ("1.6.17", "1.6.18~rc2", "postgresql", False),
        ("1.6.17", "1.6.18-rc2", "sqlite", True),
    ],
)
def test_migration_lookup_matches_normalized_version_and_engine(tmp_path, monkeypatch, stored, installed, engine, expected):
    monkeypatch.setattr(save_config, "ALEMBIC_PATH", tmp_path)
    (tmp_path / "sqlite_versions").mkdir()
    (tmp_path / "sqlite_versions/abc_upgrade_to_version_1_6_18_rc2.py").touch()
    assert save_config.migration_pending(stored, installed, engine) is expected

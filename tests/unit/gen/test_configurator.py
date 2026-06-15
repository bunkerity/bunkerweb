"""Configurator — settings/plugin loading + variable validation in get_config().

Built from tmp fixtures (a settings.json + one core plugin dir). No DB, runs once.
"""

import json
import logging

import pytest

from Configurator import Configurator  # type: ignore  (src/common/gen on path)

LOGGER = logging.getLogger("cfg-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)

SETTINGS = {
    "SERVER_NAME": {"context": "multisite", "default": "www.example.com", "help": "h", "id": "server-name", "label": "x", "regex": "^.*$", "type": "text"},
    "MULTISITE": {"context": "global", "default": "no", "help": "h", "id": "multisite", "label": "x", "regex": "^(yes|no)$", "type": "check"},
}

CORE_PLUGIN = {
    "id": "test",
    "name": "Test",
    "description": "Test plugin",
    "version": "1.0",
    "stream": "no",
    "settings": {
        "TEST_GLOBAL": {"context": "global", "default": "def", "help": "h", "id": "tg", "label": "x", "regex": "^[a-z]+$", "type": "text"},
        "TEST_MS": {"context": "multisite", "default": "ms", "help": "h", "id": "tm", "label": "x", "regex": "^[a-z]+$", "type": "text"},
        "TEST_MULTI": {"context": "multisite", "default": "", "help": "h", "id": "tmu", "label": "x", "regex": "^[a-z]+$", "type": "text", "multiple": "grp"},
    },
}


@pytest.fixture
def cfg_paths(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(SETTINGS))
    plugin_dir = tmp_path / "core" / "test"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(CORE_PLUGIN))
    return str(settings_file), str(tmp_path / "core")


def _cfg(cfg_paths, variables):
    settings_file, core = cfg_paths
    return Configurator(settings_file, core, [], [], variables, LOGGER)


class TestLoading:
    def test_settings_and_plugins_loaded(self, cfg_paths):
        c = _cfg(cfg_paths, {})
        assert "SERVER_NAME" in c.get_settings()
        core = c.get_plugins("core")
        assert len(core) == 1 and core[0]["id"] == "test"
        assert "TEST_GLOBAL" in c.get_plugins_settings("core")
        assert c.get_plugins("external") == []


class TestRedactValue:
    def test_empty(self):
        assert Configurator._redact_value("") == "''"

    def test_nonempty_reports_length_only(self):
        assert Configurator._redact_value("secret") == "'<redacted, length=6>'"


class TestGetConfig:
    def test_defaults(self, cfg_paths):
        config = _cfg(cfg_paths, {}).get_config()
        assert config["TEST_GLOBAL"] == "def"
        assert config["MULTISITE"] == "no"

    def test_valid_override_applied(self, cfg_paths):
        assert _cfg(cfg_paths, {"TEST_GLOBAL": "abc"}).get_config()["TEST_GLOBAL"] == "abc"

    def test_regex_mismatch_keeps_default(self, cfg_paths):
        # "ABC123" fails ^[a-z]+$ -> variable skipped -> default retained
        assert _cfg(cfg_paths, {"TEST_GLOBAL": "ABC123"}).get_config()["TEST_GLOBAL"] == "def"

    def test_excluded_vars_dropped(self, cfg_paths):
        config = _cfg(cfg_paths, {"PATH": "/usr/bin", "_PRIVATE": "x", "CUSTOM_CONF_HTTP_x": "y"}).get_config()
        assert "PATH" not in config
        assert "_PRIVATE" not in config
        assert "CUSTOM_CONF_HTTP_x" not in config

    def test_unknown_var_dropped(self, cfg_paths):
        assert "TOTALLY_UNKNOWN" not in _cfg(cfg_paths, {"TOTALLY_UNKNOWN": "x"}).get_config()

    def test_multisite_expansion(self, cfg_paths):
        config = _cfg(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app1"}).get_config()
        assert config["app1_TEST_MS"] == "ms"  # multisite setting expanded per server
        assert "app1_TEST_GLOBAL" not in config  # global-context setting not expanded

    def test_multiple_suffix_accepted(self, cfg_paths):
        assert _cfg(cfg_paths, {"TEST_MULTI_1": "abc"}).get_config()["TEST_MULTI_1"] == "abc"

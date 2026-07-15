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
        "TEST_FLAG": {"context": "multisite", "default": "no", "help": "h", "id": "tf", "label": "x", "regex": "^(yes|no)$", "type": "check"},
        "TEST_SIZE": {"context": "global", "default": "64m", "help": "h", "id": "ts", "label": "x", "regex": "^\\d+([kKmMgG])?$", "type": "size"},
        "TEST_DUR": {
            "context": "global",
            "default": "30s",
            "help": "h",
            "id": "td",
            "label": "x",
            "regex": "^(\\d+(ms|s|m|h|d|w|M|y))+$|^\\d+$",
            "type": "duration",
        },
        "TEST_LIST": {
            "context": "global",
            "default": "",
            "help": "h",
            "id": "tl",
            "label": "x",
            "regex": "^( *([a-z0-9.]+) *)*$",
            "type": "multivalue",
            "separator": " ",
        },
        "TEST_NUM": {"context": "global", "default": "0", "help": "h", "id": "tn", "label": "x", "regex": "^\\d+$", "type": "number"},
        "TEST_NUM_MS": {"context": "multisite", "default": "0", "help": "h", "id": "tnm", "label": "x", "regex": "^\\d+$", "type": "number"},
        "TEST_SELECT": {
            "context": "global",
            "default": "opt1",
            "help": "h",
            "id": "tse",
            "label": "x",
            "regex": "^(opt1|opt2)$",
            "type": "select",
            "select": ["opt1", "opt2"],
        },
        "TEST_CISELECT": {
            "context": "global",
            "default": "modern",
            "help": "h",
            "id": "tcse",
            "label": "x",
            "regex": "^(modern|intermediate|old)$",
            "type": "select",
            "select": ["modern", "intermediate", "old"],
            "case_insensitive": True,
        },
        "TEST_CIMULTI": {
            "context": "global",
            "default": "",
            "help": "h",
            "id": "tcmu",
            "label": "x",
            "regex": "^( *(alpha|beta) *)*$",
            "type": "multiselect",
            "separator": " ",
            "multiselect": [{"id": "alpha", "label": "Alpha", "value": "alpha"}, {"id": "beta", "label": "Beta", "value": "beta"}],
            "case_insensitive": True,
        },
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


class TestNormalization:
    def test_supported_types_are_canonicalized_together(self, cfg_paths):
        config = _cfg(
            cfg_paths,
            {
                "TEST_GLOBAL": "on",
                "TEST_SIZE": "64 M",
                "TEST_DUR": "30 sec",
                "TEST_LIST": "  a   b  c ",
                "TEST_NUM": "8080 ",
                "TEST_SELECT": " opt1 ",
                "TEST_CISELECT": "Modern",
                "TEST_CIMULTI": "ALPHA Beta",
            },
        ).get_config()

        assert config["TEST_GLOBAL"] == "on"
        assert config["TEST_SIZE"] == "64m"
        assert config["TEST_DUR"] == "30s"
        assert config["TEST_LIST"] == "a b c"
        assert config["TEST_NUM"] == "8080"
        assert config["TEST_SELECT"] == "opt1"
        assert config["TEST_CISELECT"] == "modern"
        assert config["TEST_CIMULTI"] == "alpha beta"

    def test_invalid_values_keep_defaults(self, cfg_paths):
        config = _cfg(
            cfg_paths, {"MULTISITE": "maybe", "TEST_GLOBAL": " abc ", "TEST_DUR": "30m1h", "TEST_NUM": "   ", "TEST_CISELECT": "moderns"}
        ).get_config()

        assert config["MULTISITE"] == "no"
        assert config["TEST_GLOBAL"] == "def"
        assert config["TEST_DUR"] == "30s"
        assert config["TEST_NUM"] == "0"
        assert config["TEST_CISELECT"] == "modern"

    def test_multisite_values_are_normalized(self, cfg_paths):
        config = _cfg(
            cfg_paths,
            {"MULTISITE": "true", "SERVER_NAME": "app1", "app1_TEST_FLAG": "on", "app1_TEST_MS": "on", "app1_TEST_NUM_MS": "8080 "},
        ).get_config()

        assert config["MULTISITE"] == "yes"
        assert config["app1_TEST_FLAG"] == "yes"
        assert config["app1_TEST_MS"] == "on"
        assert config["app1_TEST_NUM_MS"] == "8080"

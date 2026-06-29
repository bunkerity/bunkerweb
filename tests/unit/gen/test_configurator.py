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


class TestCheckNormalization:
    """A1: 'check' values are canonicalized to yes/no at the env/file boundary."""

    def test_truthy_alias_canonicalized(self, cfg_paths):
        assert _cfg(cfg_paths, {"MULTISITE": "true"}).get_config()["MULTISITE"] == "yes"

    @pytest.mark.parametrize("raw,expected", [("on", "yes"), ("1", "yes"), ("YES", "yes"), ("off", "no"), ("0", "no"), ("disabled", "no")])
    def test_alias_forms(self, cfg_paths, raw, expected):
        assert _cfg(cfg_paths, {"MULTISITE": raw}).get_config()["MULTISITE"] == expected

    def test_invalid_check_falls_back_to_default(self, cfg_paths):
        # "maybe" is not a boolean alias -> regex ^(yes|no)$ rejects -> default "no" retained.
        assert _cfg(cfg_paths, {"MULTISITE": "maybe"}).get_config()["MULTISITE"] == "no"

    def test_text_setting_not_coerced(self, cfg_paths):
        # TEST_GLOBAL is text (^[a-z]+$): "on" is valid text and must be stored verbatim,
        # never coerced to "yes".
        assert _cfg(cfg_paths, {"TEST_GLOBAL": "on"}).get_config()["TEST_GLOBAL"] == "on"

    def test_truthy_multisite_flag_enables_multisite_mode(self, cfg_paths):
        # MULTISITE=true must enable multisite mode so prefixed per-service check settings
        # are validated/normalized, not silently dropped to their default.
        cfg = _cfg(cfg_paths, {"MULTISITE": "true", "SERVER_NAME": "app1", "app1_TEST_FLAG": "on"}).get_config()
        assert cfg["MULTISITE"] == "yes"
        assert cfg["app1_TEST_FLAG"] == "yes"

    def test_multisite_prefixed_check_canonicalized(self, cfg_paths):
        cfg = _cfg(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app1", "app1_TEST_FLAG": "1"}).get_config()
        assert cfg["app1_TEST_FLAG"] == "yes"

    def test_multisite_text_not_coerced(self, cfg_paths):
        # TEST_MS is text (^[a-z]+$): a boolean-looking value stays verbatim per service.
        cfg = _cfg(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app1", "app1_TEST_MS": "on"}).get_config()
        assert cfg["app1_TEST_MS"] == "on"


class TestUnitNormalization:
    """B2: size/duration values are canonicalized to NGINX form at the boundary, and the
    parser accepts compound durations the old single-group regex rejected."""

    @pytest.mark.parametrize(
        "raw,expected",
        [("64M", "64m"), ("64 m", "64m"), ("1KB", "1k"), ("131072", "131072"), ("2g", "2g")],
    )
    def test_size_canonicalized(self, cfg_paths, raw, expected):
        assert _cfg(cfg_paths, {"TEST_SIZE": raw}).get_config()["TEST_SIZE"] == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [("30sec", "30s"), ("5min", "5m"), ("2hr", "2h"), ("6month", "6M"), ("30 s", "30s"), ("1h30m", "1h30m"), ("1d12h", "1d12h")],
    )
    def test_duration_canonicalized(self, cfg_paths, raw, expected):
        assert _cfg(cfg_paths, {"TEST_DUR": raw}).get_config()["TEST_DUR"] == expected

    def test_compound_duration_accepted(self, cfg_paths):
        # The old per-plugin regex ^\d+(ms?|[shdwMy])$ rejected compound times; now accepted.
        assert _cfg(cfg_paths, {"TEST_DUR": "1h30m15s"}).get_config()["TEST_DUR"] == "1h30m15s"

    def test_invalid_unit_falls_back_to_default(self, cfg_paths):
        # Not a valid duration -> parser returns None -> regex rejects -> default retained.
        assert _cfg(cfg_paths, {"TEST_DUR": "30x"}).get_config()["TEST_DUR"] == "30s"
        assert _cfg(cfg_paths, {"TEST_SIZE": "1.5g"}).get_config()["TEST_SIZE"] == "64m"

    @pytest.mark.parametrize("bad", ["30m1h", "1h1h", "1h1d", "1m1m1m"])
    def test_order_invalid_compound_rejected_at_boundary(self, cfg_paths, bad):
        # The permissive regex would match these, but NGINX rejects them. The parser is
        # authoritative at the seam: order-invalid -> rejected -> default retained (NOT stored).
        assert _cfg(cfg_paths, {"TEST_DUR": bad}).get_config()["TEST_DUR"] == "30s"


class TestListNormalization:
    """B1: multivalue/multiselect items are trimmed, empties dropped, separator canonical."""

    def test_trim_and_collapse(self, cfg_paths):
        cfg = _cfg(cfg_paths, {"TEST_LIST": " 10.0.0.1  10.0.0.2 "}).get_config()
        assert cfg["TEST_LIST"] == "10.0.0.1 10.0.0.2"

    def test_already_canonical_unchanged(self, cfg_paths):
        cfg = _cfg(cfg_paths, {"TEST_LIST": "a b c"}).get_config()
        assert cfg["TEST_LIST"] == "a b c"


class TestScalarTrim:
    """A2: surrounding whitespace stripped for number/select at the env boundary; excluded
    types (text) keep whitespace and stay gated by their own regex."""

    def test_number_trimmed(self, cfg_paths):
        assert _cfg(cfg_paths, {"TEST_NUM": "8080 "}).get_config()["TEST_NUM"] == "8080"

    def test_select_trimmed(self, cfg_paths):
        assert _cfg(cfg_paths, {"TEST_SELECT": " opt1 "}).get_config()["TEST_SELECT"] == "opt1"

    def test_all_whitespace_number_falls_back_to_default(self, cfg_paths):
        # "   " -> "" after trim -> fails ^\d+$ -> default retained (same as today).
        assert _cfg(cfg_paths, {"TEST_NUM": "   "}).get_config()["TEST_NUM"] == "0"

    def test_text_not_trimmed_into_validity(self, cfg_paths):
        # TEST_GLOBAL is text (^[a-z]+$): " abc " keeps its spaces -> fails regex -> default.
        # Proves text is excluded from trim (not silently trimmed to "abc").
        assert _cfg(cfg_paths, {"TEST_GLOBAL": " abc "}).get_config()["TEST_GLOBAL"] == "def"

    def test_multisite_prefixed_number_trimmed(self, cfg_paths):
        cfg = _cfg(cfg_paths, {"MULTISITE": "yes", "SERVER_NAME": "app1", "app1_TEST_NUM_MS": "8080 "}).get_config()
        assert cfg["app1_TEST_NUM_MS"] == "8080"


class TestSelectCaseInsensitive:
    """A3: opt-in select/multiselect canonicalize a value to the declared option casing; the
    case-sensitive regex then passes on the canonical form. Opt-out selects stay case-sensitive."""

    @pytest.mark.parametrize("raw,expected", [("Modern", "modern"), ("INTERMEDIATE", "intermediate"), ("old", "old")])
    def test_opt_in_select_canonicalized(self, cfg_paths, raw, expected):
        assert _cfg(cfg_paths, {"TEST_CISELECT": raw}).get_config()["TEST_CISELECT"] == expected

    def test_opt_in_select_no_match_falls_back(self, cfg_paths):
        # "moderns" maps to no option -> verbatim -> regex rejects -> default retained.
        assert _cfg(cfg_paths, {"TEST_CISELECT": "moderns"}).get_config()["TEST_CISELECT"] == "modern"

    def test_opt_out_select_case_sensitive(self, cfg_paths):
        # TEST_SELECT has no case_insensitive flag: "OPT1" != "opt1" -> regex rejects -> default.
        assert _cfg(cfg_paths, {"TEST_SELECT": "OPT1"}).get_config()["TEST_SELECT"] == "opt1"

    def test_opt_in_multiselect_per_item_canonicalized(self, cfg_paths):
        assert _cfg(cfg_paths, {"TEST_CIMULTI": "ALPHA Beta"}).get_config()["TEST_CIMULTI"] == "alpha beta"

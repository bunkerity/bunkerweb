"""Configurator.__validate_plugin -- the manifest caps shared with helpers.load_plugin (Lua).

PX-A §2.2 : an over-long ``help`` string (or a bad id/name/description/version/stream/setting)
made ``__load_plugin`` drop the *whole* plugin with a single WARNING, while ``helpers.load_plugin``
kept loading, ordering and running it -- split-brain, silent. This wave: same verdict on both
sides (a refused manifest is refused everywhere), refusal logged as ERROR naming the plugin id,
the file, the failing field and the cap.
"""

import json
import logging
from pathlib import Path

import pytest

from Configurator import MANIFEST_CAPS, Configurator  # type: ignore

_CORE_PLUGIN_FILES = sorted((Path(__file__).resolve().parents[3] / "src" / "common" / "core").glob("*/plugin.json"))

LOGGER = logging.getLogger("cfg-manifest-test")

SETTING = {"context": "multisite", "default": "x", "help": "h", "id": "MY_SETTING", "label": "l", "regex": "^.*$", "type": "text"}

BASE = {
    "id": "myplug",
    "name": "My",
    "description": "d",
    "version": "1.0",
    "stream": "no",
    "settings": {"MY_SETTING": dict(SETTING)},
}


def _configurator(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({}))
    core = tmp_path / "core"
    core.mkdir()
    return Configurator(str(settings_file), str(core), [], [], {}, LOGGER)


def _validate(tmp_path, plugin):
    configurator = _configurator(tmp_path)
    return configurator._Configurator__validate_plugin(plugin)


class TestValidManifestPasses:
    def test_base_plugin_is_valid(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE))
        assert ok, msg


class TestPluginLevelCaps:
    def test_invalid_id_characters(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, id="bad id!"))
        assert not ok
        assert "id of plugin" in msg

    def test_id_too_long(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, id="a" * 65))
        assert not ok
        assert "id of plugin" in msg

    def test_name_too_long(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, name="a" * 129))
        assert not ok
        assert f"name of plugin myplug is 129 bytes, max {MANIFEST_CAPS['name_max']}" == msg

    def test_description_too_long(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, description="a" * 257))
        assert not ok
        assert f"description of plugin myplug is 257 bytes, max {MANIFEST_CAPS['description_max']}" == msg

    def test_invalid_version(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, version="not-a-version"))
        assert not ok
        assert "version of plugin myplug is 'not-a-version'" in msg

    def test_invalid_stream(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, stream="maybe"))
        assert not ok
        assert "stream of plugin myplug is 'maybe'" in msg
        assert "no, partial, yes" in msg

    def test_id_with_trailing_newline_is_refused(self, tmp_path):
        """C2 : plain ``$`` lets a trailing newline slip through ``re.match`` -- Lua's anchored
        pattern never would. Same verdict on both sides means Python must refuse it too."""
        ok, msg = _validate(tmp_path, dict(BASE, id="myplug\n"))
        assert not ok
        assert "id of plugin" in msg

    def test_id_with_non_ascii_is_refused(self, tmp_path):
        """C2 : Python's ``\\w`` is Unicode-aware by default ; Lua's ``%w`` is ASCII-only."""
        ok, msg = _validate(tmp_path, dict(BASE, id="pluginé"))
        assert not ok
        assert "id of plugin" in msg

    def test_version_with_non_ascii_digits_is_refused(self, tmp_path):
        """C2 : Python's ``\\d`` matches Unicode digits (e.g. Arabic-Indic) by default."""
        ok, msg = _validate(tmp_path, dict(BASE, version="١.٢"))
        assert not ok
        assert "version of plugin myplug" in msg

    def test_name_length_is_measured_in_utf8_bytes(self, tmp_path):
        """C3 : Lua's ``#`` counts bytes, not characters. 300 "e"-with-acute characters are 300
        chars (under the 128 cap by char count is irrelevant here) but 600 UTF-8 bytes -- Python
        must refuse using the same unit Lua does, or a byte-boundary manifest gets different
        verdicts on each side."""
        ok, msg = _validate(tmp_path, dict(BASE, name="é" * 65))  # 65 chars, 130 bytes
        assert not ok
        assert "130 bytes, max 128" in msg


class TestPerSettingCaps:
    def _with_setting(self, **overrides):
        plugin = json.loads(json.dumps(BASE))  # deep copy
        plugin["settings"]["MY_SETTING"].update(overrides)
        return plugin

    def test_missing_key(self, tmp_path):
        plugin = self._with_setting()
        del plugin["settings"]["MY_SETTING"]["help"]
        ok, msg = _validate(tmp_path, plugin)
        assert not ok
        assert "setting MY_SETTING of plugin myplug is missing key(s) help" in msg

    def test_invalid_setting_id(self, tmp_path):
        plugin = self._with_setting()
        plugin["settings"]["not valid"] = plugin["settings"].pop("MY_SETTING")
        ok, msg = _validate(tmp_path, plugin)
        assert not ok
        assert "id of setting not valid of plugin myplug is invalid" in msg

    def test_setting_id_with_trailing_newline_is_refused(self, tmp_path):
        """C2, setting-id side of the same regex-dialect gap as the plugin id."""
        plugin = self._with_setting()
        plugin["settings"]["MY_SETTING\n"] = plugin["settings"].pop("MY_SETTING")
        ok, msg = _validate(tmp_path, plugin)
        assert not ok
        assert "id of setting" in msg

    def test_invalid_context(self, tmp_path):
        ok, msg = _validate(tmp_path, self._with_setting(context="nowhere"))
        assert not ok
        assert "context of setting MY_SETTING of plugin myplug is 'nowhere'" in msg

    def test_default_too_long(self, tmp_path):
        ok, msg = _validate(tmp_path, self._with_setting(default="a" * 4097))
        assert not ok
        assert f"default of setting MY_SETTING of plugin myplug is 4097 bytes, max {MANIFEST_CAPS['setting_default_max']}" == msg

    def test_help_too_long(self, tmp_path):
        """The exact regression from PX-A §2.2 : an over-long ``help`` string."""
        ok, msg = _validate(tmp_path, self._with_setting(help="a" * 640))
        assert not ok
        assert f"help of setting MY_SETTING of plugin myplug is 640 bytes, max {MANIFEST_CAPS['setting_help_max']}" == msg

    def test_help_length_is_measured_in_utf8_bytes(self, tmp_path):
        """C3 : same non-ASCII byte-vs-char gap as the plugin name, on the setting side -- this is
        the field closest to a real cap today (core `crowdsec` help is 510/512 bytes)."""
        ok, msg = _validate(tmp_path, self._with_setting(help="é" * 300))  # 300 chars, 600 bytes
        assert not ok
        assert "600 bytes, max 512" in msg

    def test_label_too_long(self, tmp_path):
        ok, msg = _validate(tmp_path, self._with_setting(label="a" * 257))
        assert not ok
        assert f"label of setting MY_SETTING of plugin myplug is 257 bytes, max {MANIFEST_CAPS['setting_label_max']}" == msg

    def test_regex_too_long(self, tmp_path):
        ok, msg = _validate(tmp_path, self._with_setting(regex="a" * 1025))
        assert not ok
        assert f"regex of setting MY_SETTING of plugin myplug is 1025 bytes, max {MANIFEST_CAPS['setting_regex_max']}" == msg

    def test_invalid_type(self, tmp_path):
        ok, msg = _validate(tmp_path, self._with_setting(type="not-a-type"))
        assert not ok
        assert "type of setting MY_SETTING of plugin myplug is 'not-a-type'" in msg


class TestNonStringFieldsAreRefusedWithFieldNamed:
    """Criticos round 2, N3 : without these guards Python still refuses a non-string field (the
    exception raised by e.g. ``len(129)`` propagates out of ``__validate_plugin``, and
    ``__load_plugin``'s ``except BaseException`` catches it and drops the plugin -- same verdict as
    Lua) but the message names no field and no cap, unlike Lua's ``... must be a string``. These
    guards close that gap so both sides report the SAME field, not just the same refusal."""

    def test_numeric_id(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, id=12345))
        assert not ok
        assert "id of plugin 12345 must be a string" == msg

    def test_numeric_name(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, name=129))
        assert not ok
        assert "name of plugin myplug must be a string" == msg

    def test_numeric_version(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, version=1.0))
        assert not ok
        assert "version of plugin myplug must be a string" == msg

    def test_settings_as_a_list(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, settings=["not", "an", "object"]))
        assert not ok
        assert "settings of plugin myplug must be an object" == msg

    def test_setting_value_not_an_object(self, tmp_path):
        ok, msg = _validate(tmp_path, dict(BASE, settings={"MY_SETTING": "not-an-object"}))
        assert not ok
        assert "setting MY_SETTING of plugin myplug must be an object" == msg

    def test_numeric_setting_default(self, tmp_path):
        plugin = json.loads(json.dumps(BASE))
        plugin["settings"]["MY_SETTING"]["default"] = 0
        ok, msg = _validate(tmp_path, plugin)
        assert not ok
        assert "default of setting MY_SETTING of plugin myplug must be a string" == msg


class TestLoadPluginRefusalIsAnErrorNotAWarning:
    """PX-A §2.2 : ``__load_plugin`` used to WARN and silently drop the whole plugin."""

    def _write_plugin(self, tmp_path, **overrides):
        core = tmp_path / "core"
        core.mkdir()
        plugin_dir = core / "myplug"
        plugin_dir.mkdir()
        manifest = dict(BASE, **overrides)
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
        return core, plugin_dir / "plugin.json"

    def test_invalid_manifest_logs_error_naming_id_file_and_cap(self, tmp_path, caplog):
        core, plugin_file = self._write_plugin(tmp_path, name="a" * 129)
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({}))
        configurator = Configurator(str(settings_file), str(core), [], [], {}, LOGGER)
        # WARNING, not ERROR : caplog.at_level also RAISES the logger's effective level, so
        # capturing at ERROR would silently swallow any .warning() call and make the assertion
        # below vacuously true. Capturing at WARNING still keeps every ERROR record too.
        with caplog.at_level(logging.WARNING, logger="cfg-manifest-test"):
            configurator._Configurator__load_plugin(plugin_file, "core")
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "an invalid manifest must log at ERROR, not WARNING"
        message = error_records[0].message
        assert "myplug" in message  # plugin id
        assert str(plugin_file) in message  # file
        assert "name of plugin" in message  # failing field
        assert "max 128" in message  # the cap
        # Scoped to THIS refusal, not "no WARNING anywhere" : an unrelated WARNING from another
        # optional-field check (e.g. PLUG-ORDER's "order" block, warn-and-drop by design) must not
        # make this assertion flaky just because it shares a caplog capture.
        assert not any(r.levelno == logging.WARNING and "myplug" in r.message for r in caplog.records)

    def test_valid_manifest_loads_without_error(self, tmp_path, caplog):
        core, plugin_file = self._write_plugin(tmp_path)
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({}))
        configurator = Configurator(str(settings_file), str(core), [], [], {}, LOGGER)
        with caplog.at_level(logging.ERROR, logger="cfg-manifest-test"):
            configurator._Configurator__load_plugin(plugin_file, "core")
        assert not any(r.levelno == logging.ERROR for r in caplog.records)


class TestCoreManifestsAllPass:
    """Brief PX-MANIFEST §Change 3 : the shared checks must not refuse a shipped core manifest."""

    @pytest.fixture(scope="class")
    def configurator(self, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("core-manifests")
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({}))
        core = tmp_path / "core"
        core.mkdir()
        return Configurator(str(settings_file), str(core), [], [], {}, LOGGER)

    @pytest.mark.parametrize("plugin_file", _CORE_PLUGIN_FILES, ids=lambda p: p.parent.name)
    def test_core_manifest_passes_the_shared_checks(self, configurator, plugin_file):
        plugin = json.loads(plugin_file.read_text())
        ok, msg = configurator._Configurator__validate_plugin(plugin)
        assert ok, f"{plugin_file} : {msg}"


class TestLuaCapsAgreeWithPython:
    """C4 : both suites can stay green while the two hand-mirrored cap sets quietly drift apart --
    change one side's number and the *other* language's tests never notice. This test is the one
    thing that would catch that : it reads the literal cap numbers out of ``helpers.lua`` itself
    (not out of a Python re-implementation of it) and compares them to ``MANIFEST_CAPS``.
    """

    _HELPERS_LUA = Path(__file__).resolve().parents[3] / "src" / "bw" / "lua" / "bunkerweb" / "helpers.lua"

    # (Lua source needle, MANIFEST_CAPS key)
    _PAIRS = [
        (r"#plugin\.id > (\d+)", "plugin_id_max"),
        (r"#plugin\.name > (\d+)", "name_max"),
        (r"#plugin\.description > (\d+)", "description_max"),
        (r"#setting > (\d+)", "setting_id_max"),
        (r"#data\.default > (\d+)", "setting_default_max"),
        (r"#data\.help > (\d+)", "setting_help_max"),
        (r"#data\.label > (\d+)", "setting_label_max"),
        (r"#data\.regex > (\d+)", "setting_regex_max"),
    ]

    def test_every_lua_cap_literal_matches_manifest_caps(self):
        import re

        lua_source = self._HELPERS_LUA.read_text()
        for needle, cap_key in self._PAIRS:
            match = re.search(needle, lua_source)
            assert match, f"could not find {needle!r} in helpers.lua -- did load_plugin's shape change?"
            lua_cap = int(match.group(1))
            assert lua_cap == MANIFEST_CAPS[cap_key], (
                f"helpers.lua enforces {cap_key.replace('_max', '')} <= {lua_cap} bytes, "
                f"but MANIFEST_CAPS['{cap_key}'] = {MANIFEST_CAPS[cap_key]} -- the two sides have drifted"
            )

"""Configurator.__validate_plugin — the optional ``extensions`` block (1.7).

Plugin-shipped API/DB code is a trust boundary, so the manifest is validated strictly:
module paths are .py files inside the plugin (no traversal), the API prefix is locked
to ``/<id>``, and table prefixes are bw_-namespaced and tied to the plugin id.
"""

import json
import logging

from Configurator import Configurator  # type: ignore

LOGGER = logging.getLogger("cfg-ext-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)

SETTINGS = {
    "SERVER_NAME": {"context": "multisite", "default": "www.example.com", "help": "h", "id": "server-name", "label": "x", "regex": "^.*$", "type": "text"},
}

BASE = {"id": "myplug", "name": "My", "description": "d", "version": "1.0", "stream": "no", "settings": {}}


def _configurator(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(SETTINGS))
    core = tmp_path / "core"
    core.mkdir()
    return Configurator(str(settings_file), str(core), [], [], {}, LOGGER)


def _validate(tmp_path, extensions):
    c = _configurator(tmp_path)
    plugin = dict(BASE, extensions=extensions)
    # name-mangled private validator — the focused unit under test
    return c._Configurator__validate_plugin(plugin)


class TestValidExtensions:
    def test_full_block(self, tmp_path):
        ok, _ = _validate(
            tmp_path,
            {
                "api": {"module": "api/router.py", "prefix": "/myplug"},
                "db": {"models": "db/models.py", "methods": "db/methods.py", "table_prefix": "bw_myplug_"},
            },
        )
        assert ok

    def test_api_only(self, tmp_path):
        ok, _ = _validate(tmp_path, {"api": {"module": "api/router.py"}})
        assert ok

    def test_db_only_models(self, tmp_path):
        ok, _ = _validate(tmp_path, {"db": {"models": "db/models.py"}})
        assert ok

    def test_no_extensions_key_is_valid(self, tmp_path):
        c = _configurator(tmp_path)
        ok, _ = c._Configurator__validate_plugin(dict(BASE))
        assert ok


def _validate_setting(tmp_path, setting):
    c = _configurator(tmp_path)
    plugin = dict(BASE, settings={"MYSETTING": setting})
    return c._Configurator__validate_plugin(plugin)


def _select_setting(**over):
    base = {
        "context": "global",
        "default": "modern",
        "help": "h",
        "id": "ms",
        "label": "x",
        "regex": "^(modern|old)$",
        "type": "select",
        "select": ["modern", "old"],
    }
    base.update(over)
    return base


def _multiselect_setting(**over):
    base = {
        "context": "global",
        "default": "",
        "help": "h",
        "id": "mm",
        "label": "x",
        "regex": "^.*$",
        "type": "multiselect",
        "separator": "",
        "multiselect": [{"id": "b", "label": "B", "value": "b"}],
    }
    base.update(over)
    return base


class TestCaseInsensitiveValidation:
    """A3: the per-setting ``case_insensitive`` flag is validated by __validate_plugin."""

    def test_true_on_select_is_valid(self, tmp_path):
        ok, _ = _validate_setting(tmp_path, _select_setting(case_insensitive=True))
        assert ok

    def test_false_on_non_select_is_valid(self, tmp_path):
        # A disabled flag on a non-select type is a harmless no-op.
        ok, _ = _validate_setting(
            tmp_path,
            {"context": "global", "default": "0", "help": "h", "id": "n", "label": "x", "regex": r"^\d+$", "type": "number", "case_insensitive": False},
        )
        assert ok

    def test_non_boolean_rejected(self, tmp_path):
        ok, msg = _validate_setting(tmp_path, _select_setting(case_insensitive="yes"))
        assert not ok and "boolean" in msg

    def test_true_on_non_select_rejected(self, tmp_path):
        ok, msg = _validate_setting(
            tmp_path, {"context": "global", "default": "0", "help": "h", "id": "n", "label": "x", "regex": r"^\d+$", "type": "number", "case_insensitive": True}
        )
        assert not ok and "Only select/multiselect" in msg

    def test_true_on_empty_separator_multiselect_rejected(self, tmp_path):
        ok, msg = _validate_setting(tmp_path, _multiselect_setting(case_insensitive=True))
        assert not ok and "Empty separator" in msg

    def test_true_on_casefold_colliding_options_rejected(self, tmp_path):
        ok, msg = _validate_setting(tmp_path, _select_setting(select=["A", "a"], regex="^(A|a)$", case_insensitive=True))
        assert not ok and "collide" in msg


class TestRejectedExtensions:
    def test_empty_block(self, tmp_path):
        ok, _ = _validate(tmp_path, {})
        assert not ok

    def test_traversal_module(self, tmp_path):
        ok, _ = _validate(tmp_path, {"api": {"module": "../../../etc/passwd.py"}})
        assert not ok

    def test_non_py_module(self, tmp_path):
        ok, _ = _validate(tmp_path, {"db": {"models": "db/models.txt"}})
        assert not ok

    def test_absolute_module(self, tmp_path):
        ok, _ = _validate(tmp_path, {"api": {"module": "/etc/evil.py"}})
        assert not ok

    def test_prefix_not_locked_to_id(self, tmp_path):
        ok, _ = _validate(tmp_path, {"api": {"module": "api/router.py", "prefix": "/instances"}})
        assert not ok

    def test_db_without_models_or_methods(self, tmp_path):
        ok, _ = _validate(tmp_path, {"db": {"table_prefix": "bw_myplug_"}})
        assert not ok

    def test_table_prefix_not_tied_to_id(self, tmp_path):
        ok, _ = _validate(tmp_path, {"db": {"models": "db/models.py", "table_prefix": "bw_settings_"}})
        assert not ok

    def test_table_prefix_not_bw_namespaced(self, tmp_path):
        ok, _ = _validate(tmp_path, {"db": {"models": "db/models.py", "table_prefix": "myplug_"}})
        assert not ok

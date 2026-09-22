"""Configurator.__validate_plugin — the optional ``order`` block (1.7).

Unlike ``extensions``, ``order`` is not a trust boundary: it only reshuffles a list the Lua
runtime rebuilds on every configuration load. A malformed block must therefore never sink the
plugin — the whole point of PX-A §2.2 is that a manifest defect currently makes the plugin
vanish from the generated configuration while its Lua half keeps running. So: warn, drop the
key, keep the plugin.
"""

import json
import logging

import pytest

from Configurator import Configurator  # type: ignore

LOGGER = logging.getLogger("cfg-order-test")

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


def _validate(tmp_path, order):
    """Returns ``(ok, msg, plugin)`` — the plugin dict is returned because the validator
    mutates it in place (an invalid ``order`` is dropped, the plugin survives)."""
    configurator = _configurator(tmp_path)
    plugin = dict(BASE, order=order)
    ok, msg = configurator._Configurator__validate_plugin(plugin)
    return ok, msg, plugin


class TestValidOrder:
    def test_before_and_after(self, tmp_path):
        order = {"ssl_certificate": {"before": ["certificates"], "after": ["letsencrypt"]}}
        ok, msg, plugin = _validate(tmp_path, order)
        assert ok, msg
        assert plugin["order"] == order

    def test_before_only(self, tmp_path):
        ok, msg, plugin = _validate(tmp_path, {"access": {"before": ["antibot"]}})
        assert ok, msg
        assert plugin["order"] == {"access": {"before": ["antibot"]}}

    def test_headers_alias_is_accepted(self, tmp_path):
        ok, msg, plugin = _validate(tmp_path, {"headers": {"after": ["cors"]}})
        assert ok, msg
        assert "order" in plugin

    def test_several_phases(self, tmp_path):
        order = {"init": {"before": ["a"]}, "log": {"after": ["b"]}, "preread": {"before": ["c"], "after": ["d"]}}
        ok, msg, plugin = _validate(tmp_path, order)
        assert ok, msg
        assert plugin["order"] == order

    def test_empty_block(self, tmp_path):
        ok, msg, plugin = _validate(tmp_path, {})
        assert ok, msg
        assert plugin["order"] == {}

    def test_wildcard_before(self, tmp_path):
        """Lane PLUG-ORDER-b : ``"*"`` is a valid id token, not a regex-matchable plugin id."""
        order = {"access": {"before": ["*"]}}
        ok, msg, plugin = _validate(tmp_path, order)
        assert ok, msg
        assert plugin["order"] == order

    def test_wildcard_after(self, tmp_path):
        order = {"init": {"after": ["*"]}}
        ok, msg, plugin = _validate(tmp_path, order)
        assert ok, msg
        assert plugin["order"] == order

    def test_wildcard_alongside_explicit_ids(self, tmp_path):
        order = {"access": {"before": ["*", "antibot"]}}
        ok, msg, plugin = _validate(tmp_path, order)
        assert ok, msg
        assert plugin["order"] == order

    def test_no_order_key_is_valid(self, tmp_path):
        configurator = _configurator(tmp_path)
        plugin = dict(BASE)
        ok, msg = configurator._Configurator__validate_plugin(plugin)
        assert ok, msg
        assert "order" not in plugin


class TestInvalidOrderIsDroppedNotRefused:
    def _dropped(self, tmp_path, order, caplog):
        with caplog.at_level(logging.WARNING, logger="cfg-order-test"):
            ok, msg, plugin = _validate(tmp_path, order)
        assert ok, msg
        assert "order" not in plugin, "an invalid order block must be dropped, not kept"
        assert any("order" in record.message for record in caplog.records), "the drop must be warned about"
        assert any("myplug" in record.message for record in caplog.records), "the warning must name the plugin"

    def test_not_a_dict(self, tmp_path, caplog):
        self._dropped(tmp_path, ["access"], caplog)

    def test_unknown_phase(self, tmp_path, caplog):
        self._dropped(tmp_path, {"not_a_phase": {"before": ["a"]}}, caplog)

    def test_phase_value_not_a_dict(self, tmp_path, caplog):
        self._dropped(tmp_path, {"access": ["antibot"]}, caplog)

    def test_unknown_constraint_key(self, tmp_path, caplog):
        self._dropped(tmp_path, {"access": {"beside": ["antibot"]}}, caplog)

    def test_constraint_not_a_list(self, tmp_path, caplog):
        self._dropped(tmp_path, {"access": {"before": "antibot"}}, caplog)

    def test_constraint_item_not_a_string(self, tmp_path, caplog):
        self._dropped(tmp_path, {"access": {"before": ["antibot", 3]}}, caplog)

    def test_constraint_item_is_not_a_plugin_id(self, tmp_path, caplog):
        self._dropped(tmp_path, {"access": {"before": ["not a plugin id!"]}}, caplog)

    def test_a_huge_offending_entry_is_truncated_in_the_message(self, tmp_path):
        """A refused entry is unbounded (the 64-char cap is what it failed), so it must not be
        echoed whole into the log. Same bound on the Lua side."""
        configurator = _configurator(tmp_path)
        ok, msg = configurator._Configurator__validate_plugin_order("myplug", {"access": {"before": ["a" * 100000]}})
        assert not ok
        assert len(msg) < 400, len(msg)
        assert "(truncated)" in msg

    def test_a_huge_phase_name_is_truncated_in_the_message(self, tmp_path):
        configurator = _configurator(tmp_path)
        ok, msg = configurator._Configurator__validate_plugin_order("myplug", {"z" * 5000: {"before": ["*"]}})
        assert not ok
        assert len(msg) < 400, len(msg)

    def test_a_flood_of_unknown_constraint_keys_is_capped_in_the_message(self, tmp_path):
        configurator = _configurator(tmp_path)
        order = {"access": {"k%d" % i: 1 for i in range(5000)}}
        ok, msg = configurator._Configurator__validate_plugin_order("myplug", order)
        assert not ok
        assert len(msg) < 400, len(msg)

    def test_a_control_byte_cannot_forge_a_second_log_line(self, tmp_path):
        """Same as the Lua half: the message goes to a log handler unescaped."""
        configurator = _configurator(tmp_path)
        forged = "x\n2026/09/21 10:00:00 [error] 1#1: *1 [ALL] client 1.2.3.4 banned by an admin"
        for order in ({forged: {"before": ["*"]}}, {"access": {forged: 1}}, {"access": {"before": [forged]}}):
            ok, msg = configurator._Configurator__validate_plugin_order("myplug", order)
            assert not ok
            assert "\n" not in msg, msg

    def test_double_asterisk_is_not_the_wildcard(self, tmp_path, caplog):
        """Only the literal ``"*"`` is special-cased ; a near-miss stays a rejected plugin id."""
        self._dropped(tmp_path, {"access": {"before": ["**"]}}, caplog)


class TestPluginStillLoads:
    def test_invalid_order_does_not_drop_the_plugin(self, tmp_path):
        """The regression PX-A §2.2 describes: a manifest defect that makes a plugin vanish."""
        ok, msg, plugin = _validate(tmp_path, "nonsense")
        assert ok, msg
        assert plugin["id"] == "myplug"


# --- the other half of the verdict (SEC F-09) ---------------------------------------
# Python pops an invalid ``order`` from the plugin dict, but the Lua runtime re-reads the same
# plugin.json from disk (init-lua.conf) and never sees that pop -- so "ignoring the order
# declaration" was only true on the Python side. The shared table below is walked by both suites:
# here against ``__validate_plugin_order``, and in tests/unit/common/test_order_plugins.py against
# the real helpers.lua. A shape that leaves this file's REJECTED list must leave the Lua one too.

import importlib.util  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

_HARNESS_PATH = Path(__file__).resolve().parents[1] / "common" / "test_order_plugins.py"
# Loaded by path, under a name of its own: the same file is also collected by pytest as
# ``test_order_plugins``, and reusing that name would hand one of the two a half-built module.
_spec = importlib.util.spec_from_file_location("_order_lua_harness", _HARNESS_PATH)
assert _spec is not None and _spec.loader is not None, f"the Lua order harness moved: {_HARNESS_PATH}"
_harness = importlib.util.module_from_spec(_spec)
# Registered before it is executed, as the importlib docs prescribe: a module that looks itself up
# in sys.modules (dataclasses, pickle, ...) must find itself there.
sys.modules[_spec.name] = _harness
try:
    _spec.loader.exec_module(_harness)
except BaseException:
    del sys.modules[_spec.name]
    raise


def _verdict(tmp_path, order):
    configurator = _configurator(tmp_path)
    return configurator._Configurator__validate_plugin_order("myplug", order)[0]


class TestPythonLuaParity:
    """One manifest, one verdict. Red before SEC-ORDER-PARITY: the Lua half salvaged the valid
    entries of a block Python had refused whole."""

    @pytest.mark.parametrize("label", sorted(_harness.REJECTED_ORDERS))
    def test_both_halves_refuse(self, tmp_path, label):
        order = _harness.REJECTED_ORDERS[label]
        assert not _verdict(tmp_path, order), f"{label}: the Python validator must refuse it"
        result = _lua_verdict(order)
        assert result is False, f"{label}: the Lua parser must refuse it too"

    @pytest.mark.parametrize("label", sorted(_harness.ALLOWED_ORDERS))
    def test_both_halves_accept(self, tmp_path, label):
        order = _harness.ALLOWED_ORDERS[label]
        assert _verdict(tmp_path, order), f"{label}: the Python validator must accept it"
        assert _lua_verdict(order) is True, f"{label}: the Lua parser must accept it too"

    def test_an_empty_container_cannot_smuggle_a_sibling_phase(self, tmp_path):
        """Criticos round 1 — the divergence that survived the first fix. cjson cannot tell JSON
        ``[]`` from JSON ``{}``, so the Lua half reads every empty container as "no constraint".
        While Python refused those three shapes, a manifest pairing one of them with a perfectly
        valid *sibling* phase had the sibling applied by the runtime and reported as ignored by the
        generator -- F-09 again, with ``[]`` in the place of ``123`` and much easier to hit by
        accident."""
        smuggled = ({"access": [], "log": {"before": ["*"]}}, {"access": {"before": {}}, "log": {"before": ["*"]}}, [])
        for index, order in enumerate(smuggled):
            # One Configurator per case: _configurator() mkdir()s its own core directory.
            case = tmp_path / f"case{index}"
            case.mkdir()
            assert _verdict(case, order), f"{order}: Python must accept what Lua cannot refuse"
            assert _lua_verdict(order) is True, f"{order}: Lua accepts it"

    def test_the_finding_manifest(self, tmp_path):
        """``{"access": {"before": ["whitelist", 123]}}`` — Python said "ignoring the order
        declaration" while Lua applied ``whitelist`` and reordered the access phase."""
        order = {"access": {"before": ["whitelist", 123]}}
        assert not _verdict(tmp_path, order)
        assert _lua_verdict(order) is False


def _lua_verdict(order):
    """``True`` if the real helpers.lua kept the declaration, ``False`` if it refused it."""
    if _harness.LUA is None:
        pytest.skip("no stand-alone lua/luajit on PATH")
    plugins = [_harness._plugin(pid, ["access", "header"], order=order if pid == "authbasic" else None) for pid in _harness.CORE_ACCESS]
    result = _harness._capture_order({"access": _harness.CORE_ACCESS}, plugins, {})
    return not [w for w in result["warnings"] if _harness.IGNORED in w]

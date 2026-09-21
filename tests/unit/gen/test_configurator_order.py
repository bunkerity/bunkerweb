"""Configurator.__validate_plugin — the optional ``order`` block (1.7).

Unlike ``extensions``, ``order`` is not a trust boundary: it only reshuffles a list the Lua
runtime rebuilds on every configuration load. A malformed block must therefore never sink the
plugin — the whole point of PX-A §2.2 is that a manifest defect currently makes the plugin
vanish from the generated configuration while its Lua half keeps running. So: warn, drop the
key, keep the plugin.
"""

import json
import logging

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

    def test_double_asterisk_is_not_the_wildcard(self, tmp_path, caplog):
        """Only the literal ``"*"`` is special-cased ; a near-miss stays a rejected plugin id."""
        self._dropped(tmp_path, {"access": {"before": ["**"]}}, caplog)


class TestPluginStillLoads:
    def test_invalid_order_does_not_drop_the_plugin(self, tmp_path):
        """The regression PX-A §2.2 describes: a manifest defect that makes a plugin vanish."""
        ok, msg, plugin = _validate(tmp_path, "nonsense")
        assert ok, msg
        assert plugin["id"] == "myplug"

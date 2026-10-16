"""``Configurator.validate_manual_plugin``: the manifest rules plus the setting-id uniqueness the database enforces.

``bw_settings`` stores a setting under its key (primary key) and its ``id`` field (unique ``name``). A
manifest that repeats either, inside itself or against core or another plugin, passes ``__validate_plugin``
and then fails the whole save with ``1062 Duplicate entry``.
"""

import json
import logging
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from manual_plugins import read_manual_plugin  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src" / "common" / "gen") not in sys.path:
    sys.path.append(str(ROOT / "src" / "common" / "gen"))

from Configurator import Configurator  # type: ignore  # noqa: E402

CORE = ROOT / "src" / "common" / "core"


@pytest.fixture(scope="module")
def validator():
    return Configurator(str(ROOT / "src" / "common" / "settings.json"), str(CORE), [], [], {}, logging.getLogger("vmp"))


def _setting(setting_id):
    return {"id": setting_id, "context": "global", "default": "x", "help": "h", "label": "L", "regex": "^.*$", "type": "text"}


def _plugin(plugin_id="mine", **settings):
    return {"id": plugin_id, "name": "N", "description": "d", "version": "1.0", "stream": "no", "settings": settings or {"MINE_ONE": _setting("mine-one")}}


def test_a_plain_manifest_is_valid(validator):
    assert validator.validate_manual_plugin(_plugin()) == (True, "ok")


def test_a_manifest_the_manifest_rules_refuse_keeps_their_message(validator):
    plugin = _plugin()
    plugin["version"] = "one"

    valid, message = validator.validate_manual_plugin(plugin)

    assert not valid and "version" in message


def test_the_manifest_is_not_modified(validator):
    plugin = _plugin()
    plugin["order"] = {"access": {"before": ["*"]}}
    before = deepcopy(plugin)

    validator.validate_manual_plugin(plugin)

    assert plugin == before


def test_a_repeated_id_inside_the_plugin_names_both_settings(validator):
    valid, message = validator.validate_manual_plugin(_plugin(MINE_A=_setting("same"), MINE_B=_setting("same")))

    assert not valid
    assert "'same'" in message and "MINE_A" in message and "MINE_B" in message


@pytest.mark.parametrize("bad", [None, 7, ["x"], {"a": 1}])
def test_a_setting_id_that_is_not_a_string_is_refused(validator, bad):
    valid, message = validator.validate_manual_plugin(_plugin(MINE_A=_setting(bad)))

    assert not valid and "MINE_A" in message


def test_a_key_core_owns_is_refused(validator):
    valid, message = validator.validate_manual_plugin(_plugin(USE_ANTIBOT=_setting("own-id")))

    assert not valid and "USE_ANTIBOT" in message and "antibot" in message


def test_an_id_core_owns_is_refused(validator):
    valid, message = validator.validate_manual_plugin(_plugin(MINE_A=_setting("use-antibot")))

    assert not valid and "use-antibot" in message and "USE_ANTIBOT" in message and "antibot" in message


def test_a_global_setting_is_owned_by_general(validator):
    valid, message = validator.validate_manual_plugin(_plugin(SERVER_NAME=_setting("own-id")))

    assert not valid and "SERVER_NAME" in message and "general" in message


def test_another_plugins_key_and_id_are_refused(validator):
    other = _plugin("other", OTHER_ONE=_setting("other-one"))

    key = validator.validate_manual_plugin(_plugin(OTHER_ONE=_setting("different")), [other])
    name = validator.validate_manual_plugin(_plugin(MINE_A=_setting("other-one")), [other])

    assert not key[0] and "OTHER_ONE" in key[1] and "other" in key[1]
    assert not name[0] and "other-one" in name[1] and "other" in name[1]


def test_a_plugin_does_not_conflict_with_its_own_stored_copy(validator):
    stored = _plugin("mine", MINE_ONE=_setting("mine-one"))

    assert validator.validate_manual_plugin(_plugin("mine", MINE_ONE=_setting("mine-one")), [stored]) == (True, "ok")


def test_a_stored_plugin_with_odd_settings_does_not_break_the_check(validator):
    odd = [{"id": "odd"}, {"id": "odd2", "settings": None}, {"id": "odd3", "settings": {"X": "str", "Y": {"id": 3}}}, {"settings": {}}]

    assert validator.validate_manual_plugin(_plugin(), odd) == (True, "ok")


@pytest.mark.parametrize("manifest", sorted(CORE.glob("*/plugin.json")), ids=lambda path: path.parent.name)
def test_no_shipped_core_plugin_collides_with_the_others(validator, manifest):
    """The rule must not refuse what BunkerWeb ships: each core plugin against all the rest of them."""
    plugin = json.loads(manifest.read_text())
    others = [json.loads(other.read_text()) for other in CORE.glob("*/plugin.json") if other != manifest]

    valid, message = validator.validate_manual_plugin(plugin, others)

    assert valid, message


class TestReadManualPlugin:
    def test_returns_the_manifest_and_no_problem(self, validator, tmp_path):
        tmp_path.joinpath("plugin.json").write_text(json.dumps(_plugin()))

        manifest, problem = read_manual_plugin(tmp_path, validator)

        assert problem is None and manifest["id"] == "mine"

    def test_unreadable_returns_no_manifest(self, validator, tmp_path):
        manifest, problem = read_manual_plugin(tmp_path, validator)

        assert manifest is None and "plugin.json" in problem

    def test_invalid_returns_the_manifest_with_the_reason(self, validator, tmp_path):
        tmp_path.joinpath("plugin.json").write_text(json.dumps({"id": "half"}))

        manifest, problem = read_manual_plugin(tmp_path, validator)

        assert manifest == {"id": "half"} and "Missing mandatory keys" in problem

    def test_a_validator_that_raises_is_a_problem_not_a_crash(self, tmp_path):
        class Exploding:
            def validate_manual_plugin(self, manifest, others):
                raise RuntimeError("boom")

        tmp_path.joinpath("plugin.json").write_text(json.dumps(_plugin()))

        manifest, problem = read_manual_plugin(tmp_path, Exploding())

        assert manifest["id"] == "mine" and "boom" in problem


class TestLoadedPluginsAreDeduplicated:
    """``save_config`` hands ``init_tables`` every external and pro plugin the Configurator loaded."""

    @staticmethod
    def _mount(root, name, settings):
        folder = root / name
        folder.mkdir(parents=True)
        folder.joinpath("plugin.json").write_text(json.dumps(_plugin(name, **settings)))

    @staticmethod
    def _load(external, pro, caplog):
        with caplog.at_level(logging.ERROR, logger="dedupe"):
            configurator = Configurator(str(ROOT / "src" / "common" / "settings.json"), str(CORE), str(external), str(pro), {}, logging.getLogger("dedupe"))
        ids = lambda kind: sorted(plugin["id"] for plugin in configurator.get_plugins(kind))  # noqa: E731
        return ids("external"), ids("pro")

    def test_the_lower_plugin_id_keeps_a_shared_setting_id(self, tmp_path, caplog):
        external, pro = tmp_path / "external", tmp_path / "pro"
        pro.mkdir()
        self._mount(external, "beta", {"BETA_ONE": _setting("shared")})
        self._mount(external, "alpha", {"ALPHA_ONE": _setting("shared")})

        assert self._load(external, pro, caplog) == (["alpha"], [])
        assert "beta" in caplog.text and "shared" in caplog.text and "alpha" in caplog.text

    def test_core_and_external_win_over_the_rest(self, tmp_path, caplog):
        external, pro = tmp_path / "external", tmp_path / "pro"
        self._mount(external, "bykey", {"USE_ANTIBOT": _setting("bykey-id")})
        self._mount(external, "fine", {"FINE_ONE": _setting("fine-one")})
        self._mount(pro, "propl", {"PROPL_ONE": _setting("fine-one")})

        assert self._load(external, pro, caplog) == (["fine"], [])
        assert "bykey" in caplog.text and "propl" in caplog.text

    def test_plugins_that_do_not_collide_are_all_kept(self, tmp_path, caplog):
        external, pro = tmp_path / "external", tmp_path / "pro"
        self._mount(external, "one", {"ONE_A": _setting("one-a")})
        self._mount(external, "two", {"TWO_A": _setting("two-a")})
        self._mount(pro, "three", {"THREE_A": _setting("three-a")})

        assert self._load(external, pro, caplog) == (["one", "two"], ["three"])
        assert caplog.text == ""

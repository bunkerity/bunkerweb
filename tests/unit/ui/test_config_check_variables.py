"""UI Config.check_variables — boolean ("check") normalization seam (A1).

check_variables is not pure (it reads plugins settings via the API client and flashes
errors), but its boolean-normalization branch is isolatable: we build a Config without
running __init__ (which would read /usr/share/bunkerweb/settings.json), stub the two
collaborators it touches (UIData.load_from_file + get_plugins_settings), and run it in
``threaded=True`` mode so errors append to a list instead of calling Flask's flash().
"""

import pytest

from app.models.config import Config  # type: ignore  (src/ui on path via ui conftest)


class _FakeData(dict):
    def load_from_file(self):  # check_variables calls this first
        return None


def _config(plugins_settings, *, ignore_regex=False):
    cfg = Config.__new__(Config)  # skip __init__ (avoids the hardcoded settings.json read)
    cfg._Config__data = _FakeData(TO_FLASH=[])
    cfg._Config__ignore_regex_check = ignore_regex
    cfg.get_plugins_settings = lambda: plugins_settings  # type: ignore[method-assign]
    return cfg


_CHECK = {"USE_X": {"type": "check", "regex": "^(yes|no)$", "context": "global"}}
_TEXT = {"TXT": {"type": "text", "regex": "^.*$", "context": "global"}}
_SIZE = {"SZ": {"type": "size", "regex": r"^\d+([kKmMgG])?$", "context": "global"}}
_DUR = {"DUR": {"type": "duration", "regex": r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", "context": "global"}}
_LIST = {"LST": {"type": "multivalue", "regex": r"^( *([a-z0-9.]+) *)*$", "context": "global", "separator": " "}}


@pytest.fixture(autouse=True)
def _no_blacklist(monkeypatch):
    # Neutralize the blacklist so our synthetic settings are never filtered out.
    monkeypatch.setattr("app.models.config.get_blacklisted_settings", lambda global_config: set())


class TestCheckVariablesNormalization:
    @pytest.mark.parametrize("raw", ["true", "on", "1", "YES", "enabled"])
    def test_truthy_alias_canonicalized_and_written_back(self, raw):
        cfg = _config(_CHECK)
        variables = {"USE_X": raw}
        out = cfg.check_variables(variables, config={}, to_check={"USE_X": raw}, global_config=True, new=True, threaded=True)
        assert out["USE_X"] == "yes"
        assert variables["USE_X"] == "yes"  # written back in place for the API payload

    @pytest.mark.parametrize("raw", ["false", "off", "0", "disabled"])
    def test_falsy_alias_canonicalized(self, raw):
        cfg = _config(_CHECK)
        out = cfg.check_variables({"USE_X": raw}, config={}, to_check={"USE_X": raw}, global_config=True, new=True, threaded=True)
        assert out["USE_X"] == "no"

    def test_invalid_check_removed(self):
        cfg = _config(_CHECK)
        variables = {"USE_X": "maybe"}
        out = cfg.check_variables(variables, config={}, to_check={"USE_X": "maybe"}, global_config=True, new=True, threaded=True)
        assert "USE_X" not in out  # not a boolean alias -> regex rejects -> dropped

    def test_text_setting_not_coerced(self):
        cfg = _config(_TEXT)
        out = cfg.check_variables({"TXT": "on"}, config={}, to_check={"TXT": "on"}, global_config=True, new=True, threaded=True)
        assert out["TXT"] == "on"


class TestUnitAndListNormalization:
    @pytest.mark.parametrize("raw,canon", [("64M", "64m"), ("64 m", "64m"), ("1mb", "1m")])
    def test_size_canonicalized_and_written_back(self, raw, canon):
        cfg = _config(_SIZE)
        variables = {"SZ": raw}
        out = cfg.check_variables(variables, config={}, to_check={"SZ": raw}, global_config=True, new=True, threaded=True)
        assert out["SZ"] == canon
        assert variables["SZ"] == canon  # written back for the API payload

    @pytest.mark.parametrize("raw,canon", [("30sec", "30s"), ("5min", "5m"), ("1h 30m", "1h30m"), ("6month", "6M")])
    def test_duration_canonicalized(self, raw, canon):
        cfg = _config(_DUR)
        out = cfg.check_variables({"DUR": raw}, config={}, to_check={"DUR": raw}, global_config=True, new=True, threaded=True)
        assert out["DUR"] == canon

    def test_invalid_unit_removed(self):
        cfg = _config(_DUR)
        out = cfg.check_variables({"DUR": "30x"}, config={}, to_check={"DUR": "30x"}, global_config=True, new=True, threaded=True)
        assert "DUR" not in out  # parser rejects -> dropped

    @pytest.mark.parametrize("bad", ["30m1h", "1h1h", "1h1d"])
    def test_order_invalid_compound_removed(self, bad):
        # Permissive regex would match; the authoritative parser rejects order-invalid units.
        cfg = _config(_DUR)
        out = cfg.check_variables({"DUR": bad}, config={}, to_check={"DUR": bad}, global_config=True, new=True, threaded=True)
        assert "DUR" not in out

    def test_list_items_trimmed(self):
        cfg = _config(_LIST)
        variables = {"LST": " 10.0.0.1  10.0.0.2 "}
        out = cfg.check_variables(variables, config={}, to_check={"LST": " 10.0.0.1  10.0.0.2 "}, global_config=True, new=True, threaded=True)
        assert out["LST"] == "10.0.0.1 10.0.0.2"
        assert variables["LST"] == "10.0.0.1 10.0.0.2"

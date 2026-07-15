"""UI Config.check_variables normalization and payload write-back."""

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


SETTINGS = {
    "USE_X": {"type": "check", "regex": "^(yes|no)$", "context": "global"},
    "TXT": {"type": "text", "regex": "^.*$", "context": "global"},
    "SZ": {"type": "size", "regex": r"^\d+([kKmMgG])?$", "context": "global"},
    "DUR": {"type": "duration", "regex": r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", "context": "global"},
    "LST": {"type": "multivalue", "regex": r"^( *([a-z0-9.]+) *)*$", "context": "global", "separator": " "},
    "NUM": {"type": "number", "regex": r"^\d+$", "context": "global"},
    "PLAIN_SELECT": {"type": "select", "regex": r"^(opt1|opt2)$", "context": "global", "select": ["opt1", "opt2"]},
    "CI_SELECT": {
        "type": "select",
        "regex": r"^(modern|old)$",
        "context": "global",
        "select": ["modern", "old"],
        "case_insensitive": True,
    },
    "MS": {
        "type": "multiselect",
        "regex": r"^( *(alpha|beta) *)*$",
        "context": "global",
        "separator": " ",
        "multiselect": [{"id": "alpha", "label": "A", "value": "alpha"}, {"id": "beta", "label": "B", "value": "beta"}],
        "case_insensitive": True,
    },
}


@pytest.fixture(autouse=True)
def _no_blacklist(monkeypatch):
    # Neutralize the blacklist so our synthetic settings are never filtered out.
    monkeypatch.setattr("app.models.config.get_blacklisted_settings", lambda global_config: set())


def test_normalized_values_are_written_back_for_api_payload():
    variables = {
        "USE_X": "true",
        "TXT": "  on  ",
        "SZ": "64 M",
        "DUR": "30 sec",
        "LST": " 10.0.0.1  10.0.0.2 ",
        "NUM": "8080 ",
        "PLAIN_SELECT": " opt1 ",
        "CI_SELECT": "Modern",
        "MS": "ALPHA Beta",
    }
    expected = {
        "USE_X": "yes",
        "TXT": "  on  ",
        "SZ": "64m",
        "DUR": "30s",
        "LST": "10.0.0.1 10.0.0.2",
        "NUM": "8080",
        "PLAIN_SELECT": "opt1",
        "CI_SELECT": "modern",
        "MS": "alpha beta",
    }

    out = _config(SETTINGS).check_variables(variables, config={}, to_check=variables.copy(), global_config=True, new=True, threaded=True)

    assert out == expected
    assert variables == expected


def test_invalid_normalized_values_are_removed():
    variables = {"USE_X": "maybe", "DUR": "30m1h", "NUM": "   ", "PLAIN_SELECT": "OPT1", "CI_SELECT": "moderns"}

    out = _config(SETTINGS).check_variables(variables, config={}, to_check=variables.copy(), global_config=True, new=True, threaded=True)

    assert not out

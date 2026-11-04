"""UI Config.check_variables validation contracts shared with dev."""

import pytest

from app.models.config import Config  # type: ignore  (src/ui on path via ui conftest)


class _FakeData(dict):
    def load_from_file(self):
        return None


def _config(plugins_settings, *, ignore_regex=False):
    cfg = Config.__new__(Config)
    cfg._Config__data = _FakeData(TO_FLASH=[])
    cfg._Config__ignore_regex_check = ignore_regex
    cfg.get_plugins_settings = lambda: plugins_settings  # type: ignore[method-assign]
    return cfg


SETTINGS = {
    "USE_X": {"type": "check", "regex": "^(yes|no)$", "context": "global"},
    "USE_TEMPLATE": {"type": "multivalue", "regex": "^.*$", "context": "multisite", "separator": " "},
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
    "SSL_PROTOCOLS": {
        "type": "multiselect",
        "regex": r"^(?! )( ?(?:SSLv[23]|TLSv1(?:\.[1-3])?))+$",
        "context": "multisite",
        "separator": " ",
        "multiselect": [{"id": v, "label": v, "value": v} for v in ("SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3")],
    },
}


def _real_resource_settings():
    from json import loads
    from pathlib import Path as _Path

    core = _Path(__file__).resolve().parents[3] / "src" / "common" / "core"
    settings = {}
    for manifest in sorted(core.glob("*/plugin.json")):
        settings.update(loads(manifest.read_text(encoding="utf-8")).get("settings", {}))
    settings.update(loads((core.parent / "settings.json").read_text(encoding="utf-8")))
    return settings


@pytest.fixture(autouse=True)
def _no_blacklist(monkeypatch):
    monkeypatch.setattr("app.models.config.get_blacklisted_settings", lambda global_config: set())


_STORED = {
    "SSL_PROTOCOLS": {"value": "TLSv1.3", "method": "ui", "global": False},
    "DUR": {"value": "10s", "method": "ui", "global": False},
}


def _flashed(cfg):
    return [entry["content"] for entry in cfg._Config__data["TO_FLASH"]]


def test_invalid_edit_on_a_new_service_does_not_invent_a_value():
    variables = {"SSL_PROTOCOLS": ""}
    cfg = _config(SETTINGS)

    out = cfg.check_variables(variables, config=_STORED, to_check=variables.copy(), new=True, threaded=True)

    assert out == {}
    assert _flashed(cfg) == ["Variable SSL_PROTOCOLS is not valid."]


def test_valid_edit_still_applies():
    variables = {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}
    cfg = _config(SETTINGS)

    out = cfg.check_variables(variables, config=_STORED, to_check=variables.copy(), threaded=True)

    assert out == {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}
    assert _flashed(cfg) == []


def _template_config(known, *, raises=None, ignore_regex=False):
    cfg = _config(SETTINGS, ignore_regex=ignore_regex)

    class _Client:
        calls = 0

        def get_templates(self):
            type(self).calls += 1
            if raises is not None:
                raise raises
            return {tid: {"name": tid} for tid in known}

    client = _Client()
    cfg._Config__api_client = client
    return cfg, client


def test_an_empty_value_needs_no_catalog():
    """Detaching every template is a legal edit, not an unknown layer."""
    cfg, client = _template_config({"low"})
    variables = {"USE_TEMPLATE": ""}

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    assert out["USE_TEMPLATE"] == ""
    assert client.calls == 0


_REAL = _real_resource_settings()


def test_a_literal_value_is_still_validated():
    """Stripping @tokens must not turn the gate off: garbage still fails."""
    cfg = _config(_REAL)

    out = cfg.check_variables({"BLACKLIST_IP": "@office not-an-ip"}, config={}, to_check={"BLACKLIST_IP": "@office not-an-ip"}, new=True, threaded=True)

    assert out == {}
    assert _flashed(cfg) == ["Variable BLACKLIST_IP is not valid."]


def test_a_non_resource_setting_keeps_its_at_sign_verbatim():
    """value_for_validation only strips for keys in RESOURCE_LIST_SETTINGS."""
    cfg = _config(SETTINGS)

    out = cfg.check_variables({"LST": "@office"}, config={}, to_check={"LST": "@office"}, new=True, threaded=True)

    assert out == {}, "LST is not a resource-list setting, @office must still be rejected"
    assert _flashed(cfg) == ["Variable LST is not valid."]


_GREYLIST = {k: v for k, v in _REAL.items() if k == "USE_GREYLIST" or k.startswith("GREYLIST_")}


@pytest.mark.parametrize("entry_key", ["GREYLIST_IP", "GREYLIST_RDNS", "GREYLIST_ASN", "GREYLIST_USER_AGENT", "GREYLIST_URI", "GREYLIST_IP_URLS"])
def test_enabling_alongside_an_entry_is_allowed(entry_key):
    """Adding an entry and enabling in the SAME save must work -- the check reads the save's
    complete desired state, not the stored config."""
    entry = {"GREYLIST_IP": "1.2.3.4", "GREYLIST_ASN": "AS64500", "GREYLIST_IP_URLS": "https://example.com/list.txt"}.get(entry_key, "x.example.com")
    variables = {"USE_GREYLIST": "yes", entry_key: entry}
    cfg = _config(_GREYLIST)

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    assert out["USE_GREYLIST"] == "yes"
    assert _flashed(cfg) == []


def test_an_entry_already_stored_on_the_scope_counts():
    """The save posts only the switch; the entry lives in the stored config."""
    stored = {"USE_GREYLIST": {"value": "no", "method": "ui", "global": False}, "GREYLIST_IP": {"value": "1.2.3.4", "method": "ui", "global": False}}
    cfg = _config(_GREYLIST)

    out = cfg.check_variables({"USE_GREYLIST": "yes"}, config=stored, to_check={"USE_GREYLIST": "yes"}, threaded=True)

    assert out["USE_GREYLIST"] == "yes"
    assert _flashed(cfg) == []


def test_an_already_enabled_greylist_never_blocks_an_unrelated_save():
    """Both save paths strip unchanged keys from `to_check`, so USE_GREYLIST is absent there.
    Re-checking a scope that is already misconfigured would make every later edit unsaveable."""
    stored = {"USE_GREYLIST": {"value": "yes", "method": "ui", "global": False}}
    cfg = _config(_GREYLIST | {"USE_X": SETTINGS["USE_X"]})

    out = cfg.check_variables({"USE_GREYLIST": "yes", "USE_X": "yes"}, config=stored, to_check={"USE_X": "yes"}, threaded=True)

    assert out["USE_GREYLIST"] == "yes"
    assert _flashed(cfg) == []


def test_disabling_an_empty_greylist_is_never_refused():
    cfg = _config(_GREYLIST)

    out = cfg.check_variables(
        {"USE_GREYLIST": "no"}, config={"USE_GREYLIST": {"value": "yes", "method": "ui", "global": False}}, to_check={"USE_GREYLIST": "no"}, threaded=True
    )

    assert out["USE_GREYLIST"] == "no"
    assert _flashed(cfg) == []

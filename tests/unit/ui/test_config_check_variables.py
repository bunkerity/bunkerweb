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
    # Verbatim shape of the real USE_TEMPLATE: an ORDERED LIST whose regex cannot express
    # "these ids exist", because template ids are user-created.
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
    # Verbatim shape of core/ssl SSL_PROTOCOLS: unlike MS above, its regex REJECTS the empty
    # string an emptied multiselect posts -- the exact value that used to delete the row.
    "SSL_PROTOCOLS": {
        "type": "multiselect",
        "regex": r"^(?! )( ?(?:SSLv[23]|TLSv1(?:\.[1-3])?))+$",
        "context": "multisite",
        "separator": " ",
        "multiselect": [{"id": v, "label": v, "value": v} for v in ("SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3")],
    },
}


def _real_resource_settings():
    """The shipped plugin.json schemas, so the @group tests run against the REAL regexes.

    The point of the fix is that no regex had to change: reproducing a hand-written
    approximation here would prove nothing about `@office-eu` on the actual country
    regex (`^( *([A-Z]{2}|@[A-Z0-9_]+) *)*$`, uppercase-only) or on the IP one (no `@`
    branch at all).
    """
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


# --- a rejected value must revert the field, never delete the row ---------------------------
# check_variables' return value is the complete desired state of the save: a key missing from it
# has its row DELETED (src/common/db/db_methods/config_save.py:592). Dropping an invalid value
# therefore reverted the service to the *global* value instead of to its own stored one.

_STORED = {
    "SSL_PROTOCOLS": {"value": "TLSv1.3", "method": "ui", "global": False},
    "DUR": {"value": "10s", "method": "ui", "global": False},
}


def _flashed(cfg):
    return [entry["content"] for entry in cfg._Config__data["TO_FLASH"]]


def test_invalid_edit_keeps_the_stored_value_and_reports_the_error():
    # What an emptied multiselect posts: no pattern on the hidden input, so no client gate.
    variables = {"SSL_PROTOCOLS": ""}
    cfg = _config(SETTINGS)

    out = cfg.check_variables(variables, config=_STORED, to_check=variables.copy(), threaded=True)

    assert out == {"SSL_PROTOCOLS": "TLSv1.3"}, "the row must survive at its stored value, not be deleted"
    assert _flashed(cfg) == ["Variable SSL_PROTOCOLS is not valid."], "reverting must not swallow the error"


def test_invalid_unit_keeps_the_stored_value():
    # Passes the client-side pattern, fails NGINX's unit-order rule in normalize_unit.
    variables = {"DUR": "30m1h"}
    cfg = _config(SETTINGS)

    out = cfg.check_variables(variables, config=_STORED, to_check=variables.copy(), threaded=True)

    assert out == {"DUR": "10s"}
    assert _flashed(cfg) == ["Variable DUR is not valid."]


def test_invalid_edit_on_a_new_service_does_not_invent_a_value():
    # On `new`, the caller passes the GLOBAL config as `config` (routes/services.py:576-579),
    # so falling back to it would seed the new service with a value nobody asked for.
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


# --- USE_TEMPLATE: the referential gate the regex cannot provide -------------------


def _template_config(known, *, raises=None, ignore_regex=False):
    """A Config whose API client reports `known` template ids (or fails with `raises`)."""
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


def test_an_unknown_layer_is_reported_with_its_position():
    cfg, _ = _template_config({"low", "high"})
    variables = {"USE_TEMPLATE": "low typo"}

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    flashed = " ".join(entry["content"] for entry in cfg._Config__data["TO_FLASH"])
    assert "typo" in flashed
    assert "position 2" in flashed
    assert "USE_TEMPLATE" not in out, "on `new` there is nothing stored to fall back on"


def test_a_rejected_layer_list_reverts_to_the_stored_value_instead_of_being_dropped():
    """`reject_value`, never `pop`: USE_TEMPLATE is in the service restore_skip, so a missing
    key DELETES the row and detaches EVERY template from the service -- far worse than the
    typo. Reverting is what a refused edit should do."""
    cfg, _ = _template_config({"low", "high"})
    variables = {"USE_TEMPLATE": "low typo"}
    stored = {"USE_TEMPLATE": {"value": "low high", "method": "ui"}}

    out = cfg.check_variables(variables, config=stored, to_check=variables.copy(), new=False, threaded=True)

    assert out["USE_TEMPLATE"] == "low high"


def test_a_fully_known_layer_list_passes_and_is_canonicalised():
    cfg, _ = _template_config({"low", "high"})
    variables = {"USE_TEMPLATE": "  low   high "}

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    assert out["USE_TEMPLATE"] == "low high"
    assert not cfg._Config__data["TO_FLASH"]


def test_every_unknown_layer_is_named_not_just_the_first():
    cfg, _ = _template_config({"low"})
    variables = {"USE_TEMPLATE": "a low b"}

    cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    flashed = " ".join(entry["content"] for entry in cfg._Config__data["TO_FLASH"])
    assert "position 1" in flashed and "position 3" in flashed


def test_the_catalog_is_fetched_once_and_only_for_a_use_template_edit():
    cfg, client = _template_config({"low"})
    variables = {"USE_X": "yes", "TXT": "hello"}

    cfg.check_variables(variables, config={}, to_check=variables.copy(), global_config=True, new=True, threaded=True)
    assert client.calls == 0, "an ordinary save must not pay for a template lookup"

    variables = {"USE_TEMPLATE": "low"}
    cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)
    assert client.calls == 1


def test_an_unreachable_api_does_not_reject_the_edit():
    """Cannot prove a layer is unknown -> do not reject. A false rejection reverts a legitimate
    edit; a missed one is still reported per position at generation time."""
    from app.api_client import ApiUnavailableError  # type: ignore

    cfg, _ = _template_config({"low"}, raises=ApiUnavailableError("down"))
    variables = {"USE_TEMPLATE": "low whatever"}

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    assert out["USE_TEMPLATE"] == "low whatever"
    assert not cfg._Config__data["TO_FLASH"]


def test_an_empty_value_needs_no_catalog():
    """Detaching every template is a legal edit, not an unknown layer."""
    cfg, client = _template_config({"low"})
    variables = {"USE_TEMPLATE": ""}

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    assert out["USE_TEMPLATE"] == ""
    assert client.calls == 0


# --- @group tokens must survive the regex gate ----------------------------------------------
# The UI's own resource-group picker inserts `@alias` tokens into resource-list settings, but
# check_variables validated the RAW value while Configurator.__check_var and db
# config_read.check_setting both strip the tokens first (value_for_validation). So the UI
# rejected the value its own picker had just produced -- and, being an unknown key on a new
# service, dropped it entirely.

_REAL = _real_resource_settings()


@pytest.mark.parametrize("alias", ["@office", "@office-eu", "@a_b-9"])
@pytest.mark.parametrize("key", ["BLACKLIST_IP", "BLACKLIST_COUNTRY"])
def test_group_tokens_pass_the_regex_gate(key, alias):
    """Lowercase and hyphenated aliases, on the two shapes that used to fail differently:
    BLACKLIST_IP's regex has no `@` branch at all, BLACKLIST_COUNTRY's has an UPPERCASE-only
    one (`@[A-Z0-9_]+`). Neither regex is touched by the fix -- the tokens are stripped."""
    value = f"{alias} 1.2.3.4" if key == "BLACKLIST_IP" else f"{alias} FR"
    cfg = _config(_REAL)

    out = cfg.check_variables({key: value}, config={}, to_check={key: value}, new=True, threaded=True)

    assert out == {key: value}, "the stored value must keep its @tokens verbatim"
    assert _flashed(cfg) == []


def test_every_resource_list_setting_accepts_a_lowercase_hyphenated_alias():
    """All 30 RESOURCE_LIST_SETTINGS keys, against their real shipped regexes."""
    from resource_group_resolver import RESOURCE_LIST_SETTINGS  # type: ignore

    rejected = []
    for key in RESOURCE_LIST_SETTINGS:
        cfg = _config(_REAL)
        out = cfg.check_variables({key: "@office-eu"}, config={}, to_check={key: "@office-eu"}, new=True, threaded=True)
        if out.get(key) != "@office-eu" or _flashed(cfg):
            rejected.append(key)

    assert not rejected, f"rejected by their own regex: {rejected}"


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


# --- USE_GREYLIST cannot be flipped on with nothing in the greylist -------------------------
# greylist.lua:209 denies EVERY request once nothing matched, and greylist:preread (:212) runs
# the same access() for streams. So enabling an empty greylist -- one click on the compose shelf
# -- takes the whole scope offline, HTTP and L4, with nothing in the UI saying so.

_GREYLIST = {k: v for k, v in _REAL.items() if k == "USE_GREYLIST" or k.startswith("GREYLIST_")}


def test_enabling_an_empty_greylist_is_refused():
    variables = {"USE_GREYLIST": "yes"}
    cfg = _config(_GREYLIST)

    out = cfg.check_variables(
        variables, config={"USE_GREYLIST": {"value": "no", "method": "ui", "global": False}}, to_check={"USE_GREYLIST": "yes"}, threaded=True
    )

    assert out == {"USE_GREYLIST": "no"}, "the flip must be reverted, not stored"
    assert "denies every request" in _flashed(cfg)[0]
    assert "GREYLIST_IP" in _flashed(cfg)[0], "the flash must say how to proceed"


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


def test_clearing_the_last_entry_in_the_same_save_is_refused():
    """Enabling while emptying the only entry is the same lockout, one save later."""
    stored = {"USE_GREYLIST": {"value": "no", "method": "ui", "global": False}, "GREYLIST_IP": {"value": "1.2.3.4", "method": "ui", "global": False}}
    variables = {"USE_GREYLIST": "yes", "GREYLIST_IP": ""}
    cfg = _config(_GREYLIST)

    out = cfg.check_variables(variables, config=stored, to_check=variables.copy(), threaded=True)

    assert out["USE_GREYLIST"] == "no"


def test_a_group_alias_counts_as_an_entry():
    variables = {"USE_GREYLIST": "yes", "GREYLIST_IP": "@office-eu"}
    cfg = _config(_GREYLIST)

    out = cfg.check_variables(variables, config={}, to_check=variables.copy(), new=True, threaded=True)

    assert out == variables
    assert _flashed(cfg) == []


def test_an_already_enabled_greylist_never_blocks_an_unrelated_save():
    """Both save paths strip unchanged keys from `to_check`, so USE_GREYLIST is absent there.
    Re-checking a scope that is already (mis)configured would make every later edit unsaveable."""
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


def test_greylist_rdns_global_is_not_mistaken_for_an_entry():
    """GREYLIST_RDNS_GLOBAL is a `check` defaulting to "yes" -- it feeds no entry, so counting it
    would make the guard permanently inert."""
    stored = {"USE_GREYLIST": {"value": "no", "method": "ui", "global": False}, "GREYLIST_RDNS_GLOBAL": {"value": "yes", "method": "default", "global": True}}
    cfg = _config(_GREYLIST)

    out = cfg.check_variables({"USE_GREYLIST": "yes"}, config=stored, to_check={"USE_GREYLIST": "yes"}, threaded=True)

    assert out["USE_GREYLIST"] == "no"
    assert "denies every request" in _flashed(cfg)[0]

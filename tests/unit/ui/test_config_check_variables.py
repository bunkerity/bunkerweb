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

"""Easy mode: an emptied field takes the setting's default instead of failing validation (BW-2371).

On a service built from a template the stored value is the template's. Emptying a field whose setting
rejects an empty value used to post ``""``: ``check_variables`` refused it and the whole save was
dropped, so the template value stayed and the only way back to the default was typing it. The fix gives
the emptied field the setting's default, as if the user had typed it. A setting that accepts an empty
value keeps it. With regex checks disabled, easy mode also keeps the empty value.
"""

from json import loads
from pathlib import Path

import pytest


def real_settings(*names):
    """The shipped definitions (default, regex, type) of the named core settings."""
    core = Path(__file__).resolve().parents[4] / "src" / "common" / "core"
    catalog = {}
    for manifest in sorted(core.glob("*/plugin.json")):
        catalog.update(loads(manifest.read_text(encoding="utf-8")).get("settings", {}))
    catalog.update(loads((core.parent / "settings.json").read_text(encoding="utf-8")))
    return {name: catalog[name] for name in names}


SETTINGS = real_settings(
    "REVERSE_PROXY_URL",
    "REVERSE_PROXY_HOST",
    "MAX_CLIENT_SIZE",
    "CONTENT_SECURITY_POLICY",
    "LIMIT_REQ_URL",
    "SERVER_NAME",
) | {"A_FILE": {"default": "default-content", "regex": r"^[\s\S]+$", "type": "file", "context": "multisite"}}

SERVICE = "ui.example.com"


@pytest.fixture
def editing(h, monkeypatch):
    h.db.get_services.return_value = [{"id": SERVICE, "method": "ui", "is_draft": False}]
    h.db.get_custom_configs.return_value = {}
    h.db.save_custom_configs.return_value = ""
    h.db.get_templates.return_value = {}
    h.config.get_config.return_value = {"SERVER_NAME": SERVICE}
    state = {
        "service": {
            "SERVER_NAME": {"value": SERVICE, "method": "ui", "global": False},
            "IS_DRAFT": {"value": "no", "method": "ui", "global": False},
            "USE_TEMPLATE": {"value": "authentik", "method": "ui", "global": False},
            "MAX_CLIENT_SIZE": {"value": "64m", "method": "default", "template": "authentik", "global": False},
            "REVERSE_PROXY_URL_1": {"value": "/ws/", "method": "default", "template": "authentik", "global": False},
        },
        "global": {"SERVER_NAME": {"value": "", "method": "default", "global": True}},
    }

    def get_config(**kwargs):
        if kwargs.get("with_setting_drafts"):
            return {}
        return state["service"] if kwargs.get("service") else state["global"]

    h.db.get_config.side_effect = get_config
    h.config.check_variables.side_effect = lambda variables, *a, **kw: dict(variables)
    h.config.edit_service.return_value = ("", False)
    h.config.new_service.return_value = ("", False)
    h.config.get_plugins_settings.return_value = SETTINGS
    monkeypatch.setattr(h.config, "_Config__ignore_regex_check", False)
    return h


def _save(h, mode="easy", service=SERVICE, **form):
    data = {"csrf_token": "t", "SERVER_NAME": SERVICE, "OLD_SERVER_NAME": SERVICE if service != "new" else ""} | form
    return h.client().post(f"/services/{service}?mode={mode}", data=data)


def _edited(h):
    _, variables = h.config.edit_service.call_args.args
    return variables


def test_a_cleared_field_with_a_non_empty_default_takes_the_default(editing):
    _save(editing, MAX_CLIENT_SIZE="")

    assert _edited(editing)["MAX_CLIENT_SIZE"] == "10m"


def test_a_cleared_numbered_field_is_left_for_validation_to_reject(editing):
    """The base default of REVERSE_PROXY_URL is `/`: giving it to `_1` would add a second `location /` and break the reload."""
    _save(editing, REVERSE_PROXY_URL_1="")

    assert _edited(editing)["REVERSE_PROXY_URL_1"] == ""


def test_a_cleared_field_on_a_new_service_takes_the_default(editing):
    h = editing
    _save(h, service="new", USE_TEMPLATE="authentik", MAX_CLIENT_SIZE="")

    variables = h.config.new_service.call_args.args[0]
    assert variables["MAX_CLIENT_SIZE"] == "10m"


@pytest.mark.parametrize("service", [SERVICE, "new"])
def test_a_cleared_field_stays_empty_when_regex_checks_are_disabled(editing, service):
    editing.config._Config__ignore_regex_check = True

    _save(editing, service=service, USE_TEMPLATE="authentik", MAX_CLIENT_SIZE="")

    variables = editing.config.new_service.call_args.args[0] if service == "new" else _edited(editing)
    assert variables["MAX_CLIENT_SIZE"] == ""


def test_a_field_that_accepts_an_empty_value_keeps_it_empty(editing):
    """An empty CSP is a legal, deliberate value: it must stay reachable in easy mode."""
    _save(editing, CONTENT_SECURITY_POLICY="")

    assert _edited(editing)["CONTENT_SECURITY_POLICY"] == ""


def test_a_cleared_field_whose_default_is_empty_stays_empty(editing):
    _save(editing, REVERSE_PROXY_HOST="")

    assert _edited(editing)["REVERSE_PROXY_HOST"] == ""


def test_a_value_the_user_typed_is_never_replaced(editing):
    _save(editing, MAX_CLIENT_SIZE="20m")

    assert _edited(editing)["MAX_CLIENT_SIZE"] == "20m"


@pytest.mark.parametrize("mode", ["advanced", "raw"])
def test_advanced_and_raw_modes_keep_posting_the_empty_value(editing, mode):
    """Only easy mode substitutes: the other modes show the field as the user left it."""
    extra = {"RAW_PRESENT_SETTINGS": '["MAX_CLIENT_SIZE"]', "RAW_DRAFT_SETTINGS": "[]"} if mode == "raw" else {}
    _save(editing, mode=mode, MAX_CLIENT_SIZE="", **extra)

    assert _edited(editing)["MAX_CLIENT_SIZE"] == ""


def test_reset_cleared_settings_skips_file_settings_and_unknown_keys(h):
    variables = {"A_FILE": "", "NOT_A_SETTING": "", "NOT_A_SETTING_1": "", "SERVER_NAME": "", "LIMIT_REQ_URL_3": ""}

    reset = h.utils.reset_cleared_settings(variables, SETTINGS)

    assert reset == []
    assert variables == {"A_FILE": "", "NOT_A_SETTING": "", "NOT_A_SETTING_1": "", "SERVER_NAME": "", "LIMIT_REQ_URL_3": ""}


def test_reset_cleared_settings_resets_an_unsuffixed_field_and_reports_it(h):
    variables = {"LIMIT_REQ_URL": "", "MAX_CLIENT_SIZE": "20m"}

    assert h.utils.reset_cleared_settings(variables, SETTINGS) == ["LIMIT_REQ_URL"]
    assert variables == {"LIMIT_REQ_URL": "/", "MAX_CLIENT_SIZE": "20m"}

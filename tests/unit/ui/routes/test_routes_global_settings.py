"""The global settings page and the save task behind it."""

import pytest


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


def _entry(value, **extra):
    return {"value": value, "global": True, "method": "ui"} | extra


@pytest.fixture
def gs(h):
    state = {
        "global": {"X": _entry("1")},
        "config": {"SERVER_NAME": _entry("a.example.com"), "X": _entry("1"), "a.example.com_X": _entry("1")},
        "draft": {"SERVER_NAME": _entry("a.example.com"), "X": _entry("1")},
    }

    def get_config(**kwargs):
        if kwargs.get("with_setting_drafts"):
            return state["draft"]
        if kwargs.get("global_only") and "with_drafts" not in kwargs:
            return state["global"]
        return state["config"]

    h.db.get_config.side_effect = get_config
    h.config.check_variables.side_effect = lambda variables, *a, **kw: dict(variables)
    h.config.edit_global_conf.return_value = ("", "")
    h.config.get_plugins_settings.return_value = {}
    h.state = state
    return h


def _post(h, data, query=""):
    return h.client().post(f"/global-settings{query}", data={"csrf_token": "t"} | data)


def test_page_renders_with_the_requested_mode_and_type(h, gs):
    h.client().get("/global-settings?mode=raw&type=core")

    template, context = h.renders[-1]
    assert template == "global_settings.html" and (context["mode"], context["type"]) == ("raw", "core")


def test_the_legacy_global_config_path_serves_the_same_page(h, gs):
    assert h.client().get("/global-config").status_code == 200
    assert h.renders[-1][0] == "global_settings.html"


def test_as_json_returns_the_global_config(h, gs):
    response = h.client().get("/global-settings?as_json=true")

    assert response.get_json() == {"X": _entry("1")}


def test_a_changed_value_is_saved_and_copied_to_services_that_follow_the_global_value(h, gs):
    response = _post(h, {"X": "2"})

    saved = h.config.edit_global_conf.call_args.args[0]
    assert saved == {"X": "2", "a.example.com_X": "2"}
    assert h.config.edit_global_conf.call_args.kwargs["check_changes"] is True
    assert {"content": "Global settings successfully saved.", "type": "success"} in h.data["TO_FLASH"]
    assert "message=Saving+global+settings" in response.headers["Location"]
    assert h.data["RELOADING"] is False


def test_a_service_with_its_own_value_is_left_alone_unless_overridden(h, gs):
    h.state["config"]["a.example.com_X"] = _entry("custom", **{"global": False})

    _post(h, {"X": "2"})
    assert "a.example.com_X" not in h.config.edit_global_conf.call_args.args[0]

    _post(h, {"X": "2", "OVERRIDE_NON_GLOBAL_SERVICES": "yes"})
    assert h.config.edit_global_conf.call_args.args[0]["a.example.com_X"] == "2"


def test_saving_the_same_values_reports_nothing_changed_and_saves_nothing(h, gs):
    _post(h, {"X": "1"})

    h.config.edit_global_conf.assert_not_called()
    assert any(item["type"] == "warning" and "no values were changed" in item["content"] for item in h.data["TO_FLASH"])
    assert h.data["RELOADING"] is False and h.data["CONFIG_CHANGED"] is False


def test_values_rejected_by_validation_are_never_saved(h, gs):
    h.config.check_variables.side_effect = lambda *a, **kw: {}

    _post(h, {"X": "bad"})

    h.config.edit_global_conf.assert_not_called()
    assert h.data["RELOADING"] is False


def test_a_save_error_from_the_config_layer_is_queued_as_an_error(h, gs):
    h.config.edit_global_conf.return_value = ("Can't save: boom", True)

    _post(h, {"X": "2"})

    assert {"content": "Can't save: boom", "type": "error"} in h.data["TO_FLASH"]


def test_a_license_key_change_raises_the_pro_loading_flag(h, gs):
    h.state["config"]["PRO_LICENSE_KEY"] = _entry("old")

    _post(h, {"PRO_LICENSE_KEY": "new"})

    assert h.data["PRO_LOADING"] is True
    assert {"content": "Checking license key to upgrade.", "type": "success", "save": False} in h.data["TO_FLASH"]


def test_file_name_changes_alone_count_as_a_change(h, gs):
    _post(h, {"X": "1", "X__FILE_NAME": "cert.pem"})

    assert h.config.edit_global_conf.call_args.kwargs["file_name_map"] == {"X": "cert.pem"}


def test_the_redirect_keeps_a_non_default_mode_and_type(h, gs):
    response = _post(h, {"X": "2"}, "?mode=easy&type=core")

    assert "global-settings?mode=easy&type=core" in response.headers["Location"].replace("%3F", "?").replace("%26", "&").replace("%3D", "=")


def test_draft_metadata_is_refused_outside_raw_mode(h, gs):
    client = h.client()

    client.post("/global-settings", data={"csrf_token": "t", "RAW_DRAFT_SETTINGS": "{}", "X": "2"})

    h.config.edit_global_conf.assert_not_called()
    assert "Setting draft metadata is only accepted in raw mode." in _flashed(h, client)


def test_raw_mode_requires_the_present_settings_metadata(h, gs):
    client = h.client()

    client.post("/global-settings?mode=raw", data={"csrf_token": "t", "X": "2"})

    h.config.edit_global_conf.assert_not_called()
    assert "Missing RAW_PRESENT_SETTINGS metadata." in _flashed(h, client)


def test_raw_mode_saves_with_the_parsed_draft_state(h, gs):
    gs.routes.global_settings.parse_raw_draft_settings = lambda *a, **kw: {"X": True}

    _post(h, {"X": "2", "RAW_DRAFT_SETTINGS": "{}", "RAW_PRESENT_SETTINGS": "[]"}, "?mode=raw")

    assert h.config.edit_global_conf.call_args.kwargs["draft_settings"] == {"X": True}


def test_raw_mode_surfaces_a_metadata_error(h, gs):
    def refuse(*a, **kw):
        raise h.routes.global_settings.RawDraftSettingsError("bad metadata")

    h.routes.global_settings.parse_raw_draft_settings = refuse
    client = h.client()

    client.post("/global-settings?mode=raw", data={"csrf_token": "t", "RAW_PRESENT_SETTINGS": "[]"})

    assert "bad metadata" in _flashed(h, client)
    h.config.edit_global_conf.assert_not_called()


def test_a_post_is_refused_in_read_only_mode(h, gs):
    h.db.readonly = True
    client = h.client()

    client.post("/global-settings", data={"csrf_token": "t", "X": "2"})

    h.config.edit_global_conf.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)

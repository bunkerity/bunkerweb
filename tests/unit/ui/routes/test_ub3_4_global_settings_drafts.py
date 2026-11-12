"""Global saves retain drafts and enforce ownership of draft-state changes."""

import json

import pytest


def _entry(value, **extra):
    return {"value": value, "global": True, "method": "ui"} | extra


@pytest.fixture
def drafts(h):
    active = {"SERVER_NAME": _entry("app.example"), "X": _entry("live", file_name="live.pem"), "Y": _entry("old")}
    saved = active | {"X": _entry("staged", is_draft=True, file_name="staged.pem")}
    active["app.example_X"] = _entry("live")
    active["app.example_Y"] = _entry("old")

    def get_config(**kwargs):
        settings = saved if kwargs.get("with_setting_drafts") else active
        return {key: value.copy() for key, value in settings.items() if not kwargs.get("global_only") or not key.startswith("app.example_")}

    h.db.get_config.side_effect = get_config
    h.config.get_plugins_settings.return_value = {"X": {"context": "multisite"}, "Y": {"context": "multisite"}}
    h.config.check_variables.side_effect = lambda variables, *args, **kwargs: dict(variables)
    h.config.edit_global_conf.return_value = ("", "")
    return saved


@pytest.mark.parametrize("mode", ["easy", "advanced"])
@pytest.mark.parametrize("posted", [{"X": "live", "X__FILE_NAME": "live.pem"}, {"X": "edited", "X__FILE_NAME": "edited.pem"}, {}])
def test_saving_another_global_value_retains_draft_and_its_filename(h, drafts, mode, posted):
    response = h.client().post(f"/global-settings?mode={mode}", data={"csrf_token": "t", "Y": "new"} | posted)

    assert response.status_code == 302
    call = h.config.edit_global_conf.call_args
    assert call.args[0] == {"X": "staged", "Y": "new", "app.example_Y": "new"}
    assert call.kwargs == {"check_changes": True, "file_name_map": {"X": "staged.pem"} if posted else {}, "draft_settings": None}
    assert h.config.check_variables.call_args.args[2] == {"Y": "new"}
    if posted.get("X") == "edited":
        assert {"content": "Draft settings remain unchanged; activate or edit them in Raw mode.", "type": "warning"} in h.data["TO_FLASH"]
    assert h.data["RELOADING"] is False


@pytest.mark.parametrize("mode", ["easy", "advanced"])
def test_editing_only_a_saved_draft_in_form_modes_does_not_save(h, drafts, mode):
    response = h.client().post(f"/global-settings?mode={mode}", data={"csrf_token": "t", "X": "edited", "X__FILE_NAME": "edited.pem", "Y": "old"})

    assert response.status_code == 302
    h.config.edit_global_conf.assert_not_called()
    assert h.data["TO_FLASH"] == [
        {
            "content": "The global settings were not edited because no values were changed. Draft settings remain unchanged; activate or edit them in Raw mode.",
            "type": "warning",
        }
    ]
    assert h.data["RELOADING"] is False and h.data["CONFIG_CHANGED"] is False


@pytest.mark.parametrize("method", ["autoconf", "scheduler"])
@pytest.mark.parametrize("action", ["draft", "activate", "delete"])
def test_raw_cannot_change_draft_state_of_a_setting_owned_by_another_method(h, drafts, method, action):
    drafts["X"].update(method=method, is_draft=action != "draft")
    data = {"csrf_token": "t", "Y": "old", "RAW_DRAFT_SETTINGS": "[]", "RAW_PRESENT_SETTINGS": '["Y"]'}
    if action != "delete":
        data.update(X="staged", RAW_PRESENT_SETTINGS='["X", "Y"]')
    if action == "draft":
        data["RAW_DRAFT_SETTINGS"] = '["X"]'

    response = h.client().post("/global-settings?mode=raw", data=data)

    assert response.status_code == 302
    h.config.edit_global_conf.assert_not_called()
    assert h.data["TO_FLASH"] == [{"content": f"Setting X cannot change draft state because it is managed by the {method} method.", "type": "error"}]
    assert h.data["RELOADING"] is False and h.data["CONFIG_CHANGED"] is False


@pytest.mark.parametrize("action, desired", [("draft", True), ("activate", False), ("delete", None)])
@pytest.mark.parametrize("method", ["ui", "api"])
def test_raw_can_change_draft_state_of_an_editable_setting(h, drafts, action, desired, method):
    drafts["X"].update(method=method, is_draft=action != "draft")
    data = {"csrf_token": "t", "Y": "old", "RAW_DRAFT_SETTINGS": "[]", "RAW_PRESENT_SETTINGS": '["Y"]'}
    if action != "delete":
        data.update(X="staged", RAW_PRESENT_SETTINGS='["X", "Y"]')
    if action == "draft":
        data["RAW_DRAFT_SETTINGS"] = json.dumps(["X"])

    response = h.client().post("/global-settings?mode=raw", data=data)

    assert response.status_code == 302
    assert h.config.edit_global_conf.call_args.kwargs["draft_settings"] == {"X": desired, "Y": False}
    assert {"content": "Global settings successfully saved.", "type": "success"} in h.data["TO_FLASH"]

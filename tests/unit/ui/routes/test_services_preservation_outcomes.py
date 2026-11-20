"""Service saves preserve draft data and move custom configs through the atomic rename boundary."""

from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.fixture
def service_edit(h):
    effective = {"SERVER_NAME": {"value": "ui.example.com", "method": "ui"}, "USE_X": {"value": "no", "method": "ui"}}
    drafts = {}
    h.db.get_config.side_effect = lambda **kw: (
        drafts if kw.get("with_setting_drafts") else effective if kw.get("service") else {"SERVER_NAME": {"value": "", "method": "default"}}
    )
    h.db.get_custom_configs.return_value = {}
    h.db.get_services.return_value = [{"id": "ui.example.com", "method": "ui", "is_draft": False}]
    h.db.save_custom_configs.return_value = ""
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com"}
    h.config.get_plugins_settings.return_value = {}
    h.config.check_variables.side_effect = lambda variables, *args, **kw: dict(variables)
    h.config.edit_service.return_value = ("", False)
    h.config.new_service.return_value = ("", False)
    return h, effective, drafts


def _save(h, mode="easy", service="ui.example.com", query="", **fields):
    form = {"csrf_token": "unit", "SERVER_NAME": "ui.example.com", "OLD_SERVER_NAME": "ui.example.com", "USE_X": "yes"} | fields
    response = h.client().post(f"/services/{service}?mode={mode}{query}", data=form)
    assert response.status_code == 302
    location = urlsplit(response.headers["Location"])
    assert location.path == "/loading"
    return parse_qs(location.query)


def _messages(h):
    return [(item["content"], item["type"]) for item in h.data["TO_FLASH"]]


@pytest.mark.parametrize("mode", ["easy", "advanced"])
def test_non_raw_edits_keep_draft_file_contents_and_filename(service_edit, mode):
    h, effective, drafts = service_edit
    effective["BLOB"] = {"value": "live certificate", "method": "ui", "file_name": "live.pem"}
    drafts["BLOB"] = {"value": "draft certificate", "method": "ui", "file_name": "draft.pem", "is_draft": True}
    target = _save(h, mode=mode, BLOB="attempted overwrite", BLOB__FILE_NAME="live.pem")
    assert target["next"] == [f"/services/ui.example.com?{'mode=advanced' if mode == 'advanced' else ''}"]
    call = h.config.edit_service.call_args
    assert call.args[1]["BLOB"] == "draft certificate"
    assert call.kwargs["file_name_map"] == {"BLOB": "draft.pem"}
    assert call.kwargs["draft_settings"] is None
    assert ("Draft settings remain unchanged; activate or edit them in Raw mode.", "warning") in _messages(h)


def test_clone_preserves_draft_file_and_rekeys_its_draft_state(service_edit):
    h, effective, drafts = service_edit
    effective["BLOB"] = {"value": "effective file", "method": "ui", "file_name": "live.pem"}
    drafts["BLOB"] = {"value": "saved draft", "method": "ui", "file_name": "draft.pem", "is_draft": True}
    _save(h, service="new", query="&clone=ui.example.com", SERVER_NAME="copy.example.com", OLD_SERVER_NAME="")
    call = h.config.new_service.call_args
    assert call.args[0]["BLOB"] == "saved draft"
    assert call.kwargs["file_name_map"] == {"BLOB": "draft.pem"}
    assert call.kwargs["draft_settings"] == {"copy.example.com_BLOB": True}
    assert ("Configuration successfully created for service copy.example.com.", "success") in _messages(h)


def test_rename_rekeys_preserved_draft_state_and_filename(service_edit):
    h, effective, drafts = service_edit
    effective["BLOB"] = {"value": "effective file", "method": "ui", "file_name": "live.pem"}
    drafts["BLOB"] = {"value": "saved draft", "method": "ui", "file_name": "draft.pem", "is_draft": True}
    target = _save(h, mode="advanced", SERVER_NAME="new.example.com")
    call = h.config.edit_service.call_args
    assert call.args[0] == "ui.example.com" and call.args[1]["BLOB"] == "saved draft"
    assert call.kwargs["draft_settings"] == {"new.example.com_BLOB": True}
    assert call.kwargs["file_name_map"] == {"BLOB": "draft.pem"}
    assert target["next"] == ["/services"]


@pytest.mark.parametrize("posted,changes", [("old", False), ("new", True)])
def test_rename_carries_only_changed_custom_config_into_atomic_edit(service_edit, posted, changes):
    h, _, _ = service_edit
    h.db.get_custom_configs.return_value = {
        "ui.example.com_server_http_mine": {
            "service_id": "ui.example.com",
            "type": "server_http",
            "name": "mine",
            "data": b"old",
            "method": "ui",
            "template": None,
            "is_draft": False,
        }
    }
    _save(h, SERVER_NAME="new.example.com", CUSTOM_CONF_SERVER_HTTP_mine=posted)
    payload = h.config.edit_service.call_args.kwargs["custom_config_changes"]
    assert payload == (
        [
            {
                "type": "server_http",
                "name": "mine",
                "config": {"service_id": "new.example.com", "type": "server_http", "name": "mine", "data": b"new", "method": "ui", "is_draft": False},
            }
        ]
        if changes
        else []
    )
    h.db.save_custom_configs.assert_not_called()
    assert ("Configuration successfully saved for service new.example.com.", "success") in _messages(h)


def test_inconsistent_database_server_name_refuses_rename(service_edit):
    h, effective, _ = service_edit
    effective["SERVER_NAME"]["value"] = "other.example.com"
    _save(h, SERVER_NAME="new.example.com")
    h.config.edit_service.assert_not_called()
    h.db.save_custom_configs.assert_not_called()
    assert ("Service ui.example.com has an inconsistent SERVER_NAME (other.example.com) and cannot be renamed from the Web UI.", "error") in _messages(h)
    assert h.data["CONFIG_CHANGED"] is False and h.data["RELOADING"] is False


@pytest.mark.parametrize("template,keep_default", [("old", True), ("new", False)])
def test_advanced_save_restores_managed_values_but_drops_switched_template_defaults(service_edit, template, keep_default):
    h, effective, _ = service_edit
    effective.update(
        KEPT={"value": "managed value", "method": "env"},
        TEMPLATE_VALUE={"value": "old default", "method": "default", "template": "old"},
        USE_TEMPLATE={"value": "old", "method": "ui"},
    )
    _save(h, mode="advanced", USE_TEMPLATE=template)
    saved = h.config.edit_service.call_args.args[1]
    assert saved["KEPT"] == "managed value"
    assert ("TEMPLATE_VALUE" in saved) is keep_default
    if keep_default:
        assert saved["TEMPLATE_VALUE"] == "old default"
    assert saved["USE_TEMPLATE"] == template


def test_filename_change_alone_saves_file_metadata(service_edit):
    h, effective, _ = service_edit
    effective["BLOB"] = {"value": "same content", "method": "ui", "file_name": "old.pem"}
    _save(h, USE_X="no", BLOB="same content", BLOB__FILE_NAME="new.pem")
    assert h.config.edit_service.call_args.kwargs["file_name_map"] == {"BLOB": "new.pem"}
    assert ("Configuration successfully saved for service ui.example.com.", "success") in _messages(h)


def test_removing_template_custom_config_keeps_unrelated_configs_and_checksums(service_edit):
    h, _, _ = service_edit
    h.db.get_custom_configs.return_value = {
        "ui.example.com_server_http_old": {
            "service_id": "ui.example.com",
            "type": "server_http",
            "name": "old",
            "data": b"old",
            "method": "ui",
            "template": "old",
        },
        "other.example.com_server_http_keep": {
            "service_id": "other.example.com",
            "type": "server_http",
            "name": "keep",
            "data": b"keep",
            "method": "ui",
            "template": None,
            "checksum": "unchanged",
        },
    }
    _save(h)
    configs = list(h.db.save_custom_configs.call_args.args[0])
    assert configs == [
        {"service_id": "other.example.com", "type": "server_http", "name": "keep", "data": b"keep", "method": "ui", "is_draft": False, "checksum": "unchanged"}
    ]


def test_raw_save_strips_service_prefix_from_posted_setting_names(service_edit):
    h, _, _ = service_edit
    h.config.get_plugins_settings.return_value = {"USE_X": {"context": "multisite"}}
    _save(
        h,
        mode="raw",
        RAW_DRAFT_SETTINGS="[]",
        RAW_PRESENT_SETTINGS='["ui.example.com_USE_X"]',
        **{"ui.example.com_SERVER_NAME": "ui.example.com", "ui.example.com_USE_X": "yes"},
    )
    saved = h.config.edit_service.call_args.args[1]
    assert saved["SERVER_NAME"] == "ui.example.com" and saved["USE_X"] == "yes"
    assert "ui.example.com_USE_X" not in saved and "ui.example.com_SERVER_NAME" not in saved

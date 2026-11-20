"""The /services blueprint: listing, convert, delete, certificate pre-check, export/import and the settings page."""

import io
import json
import zipfile
from unittest.mock import MagicMock

import pytest


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


def _queued(h):
    return [(item["content"], item["type"]) for item in h.data["TO_FLASH"]]


@pytest.fixture
def services(h):
    h.db.get_services.return_value = [
        {"id": "ui.example.com", "method": "ui", "is_draft": False},
        {"id": "draft.example.com", "method": "ui", "is_draft": True},
        {"id": "auto.example.com", "method": "autoconf", "is_draft": False},
        {"id": "autodraft.example.com", "method": "autoconf", "is_draft": True},
    ]
    h.db.get_custom_configs.return_value = [{"service_id": "ui.example.com"}, {"service_id": None}, {"service_id": "ui.example.com"}]
    h.db.get_templates.return_value = {}
    h.db.save_config.return_value = None
    h.db.delete_services.return_value = ""
    h.db.get_config.return_value = {}
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com draft.example.com"}
    h.config.gen_conf.return_value = None
    return h.routes.services


def test_services_page_lists_services_and_the_ones_that_own_configs(h, services):
    h.client().get("/services")

    template, context = h.renders[-1]
    assert template == "services.html" and len(context["services"]) == 4
    assert context["services_with_configs"] == ["ui.example.com"]


def test_services_with_a_trailing_slash_redirects(h, services):
    response = h.client().get("/services/")

    assert response.status_code == 302 and response.headers["Location"].endswith("/services")


# --------------------------------------------------------------------------------------
# convert
# --------------------------------------------------------------------------------------
def test_convert_to_draft_changes_only_online_ui_services(h, services):
    h.db.get_config.return_value = {"SERVER_NAME": "x"}
    h.client().post("/services/convert", data={"services": "ui.example.com,draft.example.com,auto.example.com,ghost", "convert_to": "draft"})

    saved = h.db.save_config.call_args.args
    assert saved[0] == {"SERVER_NAME": "x", "ui.example.com_IS_DRAFT": "yes"} and saved[1] == "ui"
    queued = _queued(h)
    assert ("Service auto.example.com is not a UI/API service and will not be converted.", "error") in queued
    assert ("Service draft.example.com is already a draft service and will not be converted.", "error") in queued
    assert any(item[1] == "success" and 'Converted to "Draft" services: ui.example.com' in item[0] for item in queued)


def test_convert_to_online_sets_the_flag_back(h, services):
    h.client().post("/services/convert", data={"services": "draft.example.com", "convert_to": "online"})

    assert h.db.save_config.call_args.args[0] == {"draft.example.com_IS_DRAFT": "no"}


def test_convert_with_nothing_convertible_changes_nothing(h, services):
    h.client().post("/services/convert", data={"services": "auto.example.com", "convert_to": "online"})

    h.db.save_config.assert_not_called()
    assert ("All selected services could not be found, are not UI/API services or are already converted.", "error") in _queued(h)
    assert h.data["RELOADING"] is False and h.data["CONFIG_CHANGED"] is False


def test_convert_save_error_is_queued(h, services):
    h.db.save_config.return_value = "locked"

    h.client().post("/services/convert", data={"services": "ui.example.com", "convert_to": "draft"})

    assert ("locked", "error") in _queued(h)


@pytest.mark.parametrize("form", [{"services": "a"}, {"convert_to": "draft"}, {"services": "a", "convert_to": "weird"}])
def test_convert_rejects_incomplete_or_invalid_requests(h, services, form):
    h.client().post("/services/convert", data=form)

    h.db.save_config.assert_not_called()


# --------------------------------------------------------------------------------------
# delete
# --------------------------------------------------------------------------------------
def test_delete_removes_ui_services_and_explains_why_others_stay(h, services):
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com", "ui.example.com_X": "1", "other_X": "2"}

    h.client().post("/services/delete", data={"services": "ui.example.com,auto.example.com"})

    new_env = h.config.gen_conf.call_args.args[0]
    assert "ui.example.com_X" not in new_env and new_env["other_X"] == "2"
    assert new_env["SERVER_NAME"] == "draft.example.com auto.example.com autodraft.example.com"
    queued = _queued(h)
    assert ("Service auto.example.com is online autoconf service (convert it to draft first) and will not be deleted.", "error") in queued
    assert ("Deleted service: ui.example.com", "success") in queued


def test_deleting_a_drafted_autoconf_service_goes_straight_to_the_database(h, services):
    h.client().post("/services/delete", data={"services": "autodraft.example.com"})

    h.db.delete_services.assert_called_once_with(["autodraft.example.com"])
    assert h.config.gen_conf.call_args.kwargs["check_changes"] is False, "only drafts are going away, nothing needs applying"


def test_deleting_an_online_service_asks_the_scheduler_to_apply(h, services):
    h.client().post("/services/delete", data={"services": "ui.example.com"})

    assert h.config.gen_conf.call_args.kwargs["check_changes"] is True


def test_delete_stops_when_the_autoconf_draft_removal_fails(h, services):
    h.db.delete_services.return_value = "locked"

    h.client().post("/services/delete", data={"services": "autodraft.example.com"})

    h.config.gen_conf.assert_not_called()
    assert ("Failed to delete drafted autoconf services: locked", "error") in _queued(h)


def test_delete_with_nothing_deletable(h, services):
    h.client().post("/services/delete", data={"services": "auto.example.com,ghost"})

    h.config.gen_conf.assert_not_called()
    assert ("All selected services could not be found or are not UI/API services.", "error") in _queued(h)


def test_delete_reports_a_generation_error(h, services):
    h.config.gen_conf.return_value = "template failed"

    h.client().post("/services/delete", data={"services": "ui.example.com"})

    assert ("template failed", "error") in _queued(h) and h.data["CONFIG_CHANGED"] is False


@pytest.mark.parametrize(
    "path, form",
    [
        ("/services/delete", {"services": "ui.example.com"}),
        ("/services/convert", {"services": "ui.example.com", "convert_to": "draft"}),
        ("/services/import", {}),
        ("/services/new", {"csrf_token": "t"}),
    ],
)
def test_service_writes_are_refused_in_read_only_mode(h, services, path, form):
    h.db.readonly = True
    client = h.client()

    client.post(path, data=form)

    h.db.save_config.assert_not_called()
    h.db.delete_services.assert_not_called()
    h.config.gen_conf.assert_not_called()
    h.config.new_service.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)


# --------------------------------------------------------------------------------------
# certificate pre-check
# --------------------------------------------------------------------------------------
def test_validate_certificate_needs_both_halves(h, services):
    response = h.client().post("/services/validate-certificate", data={"cert": "x"})

    assert response.status_code == 400 and response.get_json()["ok"] is False


def test_validate_certificate_reports_a_malformed_pem(h, services):
    services.normalize_pem = lambda data, kind: (None, f"bad {kind}")

    assert h.client().post("/services/validate-certificate", data={"cert": "c", "key": "k"}).get_json() == {"ok": False, "error": "bad cert", "warnings": []}


def test_validate_certificate_reports_a_malformed_key(h, services):
    services.normalize_pem = lambda data, kind: (data, "") if kind == "cert" else (None, "bad key")

    assert h.client().post("/services/validate-certificate", data={"cert": "c", "key": "k"}).get_json()["error"] == "bad key"


def test_validate_certificate_warns_about_uncovered_server_names(h, services):
    services.normalize_pem = lambda data, kind: (data, "")
    services.validate_certificate_pair = lambda cert, key: {"ok": True, "warnings": [], "names": ["a.example.com"]}
    services.uncovered_server_names = lambda result, names: [name for name in names if name not in result["names"]]

    body = h.client().post("/services/validate-certificate", data={"cert": "c", "key": "k", "server_name": "a.example.com b.example.com"}).get_json()

    assert body["ok"] is True and body["warnings"] == ["Certificate does not cover b.example.com."]


def test_validate_certificate_with_a_failing_pair_skips_the_name_check(h, services):
    services.normalize_pem = lambda data, kind: (data, "")
    services.validate_certificate_pair = lambda cert, key: {"ok": False, "error": "mismatch", "warnings": []}
    services.uncovered_server_names = MagicMock()

    assert h.client().post("/services/validate-certificate", data={"cert": "c", "key": "k", "server_name": "a"}).get_json()["error"] == "mismatch"
    services.uncovered_server_names.assert_not_called()


# --------------------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------------------
def test_parse_services_export(services):
    content = "# comment\n\nsite_SERVER_NAME=site\nsite_USE_X = yes \nbroken line\nnoprefix=1\n_=2\nother_A=b=c\n"

    parsed, errors = services.parse_services_export(content)

    assert parsed == {"site": {"SERVER_NAME": "site", "USE_X": "yes"}, "other": {"A": "b=c"}}
    assert errors == ["Line 5 is not a valid key/value pair.", "Line 6 is missing a service prefix.", "Line 7 has an invalid key: _."]


def test_export_writes_one_env_block_per_service(h, services):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com b.example.com", "a.example.com_X": "1", "b.example.com_Y": "2", "plain": "z"}

    response = h.client().get("/services/export?services=a.example.com,ghost")

    text = response.get_data(as_text=True)
    assert "# Configuration for a.example.com\na.example.com_X=1\n" in text
    assert "# Configuration for ghost not found" in text and "b.example.com_Y" not in text
    assert response.headers["Content-Disposition"].endswith("services_export.env")


def test_export_with_configs_is_a_zip_of_env_and_json(h, services):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com", "a.example.com_X": "1"}
    h.db.get_custom_configs.return_value = [
        {"service_id": "a.example.com", "type": "SERVER-HTTP", "name": "mine", "data": b"location / {}", "is_draft": True},
        {"service_id": "other", "type": "http", "name": "skip", "data": b"x"},
        {"service_id": None, "type": "http", "name": "global", "data": b"x"},
    ]

    response = h.client().get("/services/export?services=a.example.com&include_configs=yes")

    archive = zipfile.ZipFile(io.BytesIO(response.get_data()))
    assert sorted(archive.namelist()) == ["configs_export.json", "services_export.env"]
    configs = json.loads(archive.read("configs_export.json"))["configs"]
    assert configs == [{"service_id": "a.example.com", "type": "server_http", "name": "mine", "data": "location / {}", "is_draft": True}]


# --------------------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------------------
def _import(h, name, content, **form):
    client = h.client()
    return client, client.post("/services/import", data={"services_file": (io.BytesIO(content), name)} | form, content_type="multipart/form-data")


@pytest.fixture
def importing(h, services):
    h.config.check_variables.side_effect = lambda variables, *a, **kw: dict(variables)
    h.config.new_service.return_value = ("", False)
    services.apply_imported_configs = MagicMock(return_value={"created": 1, "overwritten": 0})
    services.flash_import_results = MagicMock()
    return services


def test_import_creates_new_services_and_skips_existing_ones(h, importing):
    env = b"new.example.com_SERVER_NAME=new.example.com\nnew.example.com_IS_DRAFT=yes\nui.example.com_SERVER_NAME=ui.example.com\nnoname.example.com_X=1\n"

    _import(h, "services.env", env)

    call = h.config.new_service.call_args
    assert call.args[0] == {"SERVER_NAME": "new.example.com"} and call.kwargs == {"is_draft": True, "override_method": "ui", "check_changes": False}
    assert h.config.new_service.call_count == 1
    queued = _queued(h)
    assert ("Imported service: new.example.com", "success") in queued
    assert ("Skipped existing service: ui.example.com", "warning") in queued
    assert ("Failed to import service: noname.example.com (missing SERVER_NAME)", "error") in queued
    assert h.data["CONFIG_CHANGED"] is True and h.data["RELOADING"] is False


def test_import_reports_a_creation_error(h, importing):
    h.config.new_service.return_value = ("Can't create", True)

    _import(h, "services.env", b"a.example.com_SERVER_NAME=a.example.com\n")

    assert ("Can't create", "error") in _queued(h) and ("Failed to import service: a.example.com", "error") in _queued(h)


def test_import_rejects_an_invalid_server_name_after_validation(h, importing):
    h.config.check_variables.side_effect = lambda *a, **kw: {}

    _import(h, "services.env", b"a.example.com_SERVER_NAME=bad name!\n")

    h.config.new_service.assert_not_called()
    assert ("Failed to import service: a.example.com (invalid SERVER_NAME)", "error") in _queued(h)


@pytest.mark.parametrize(
    "name, content, message",
    [
        ("x.env", b"\xff\xfe", "Invalid file encoding. Please upload a UTF-8 file."),
        ("x.env", b"# only a comment\n", "No services or custom configurations found in the import file."),
        ("x.zip", b"not a zip", "Uploaded file is not a valid zip archive."),
    ],
)
def test_import_refuses_unusable_files(h, importing, name, content, message):
    client, _ = _import(h, name, content)

    h.config.new_service.assert_not_called()
    assert message in _flashed(h, client)


def test_import_requires_a_file(h, importing):
    client = h.client()

    client.post("/services/import", data={})

    assert "No services file uploaded." in _flashed(h, client)


def _zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_import_reads_only_the_two_known_members_of_an_archive(h, importing):
    importing.parse_configs_export = lambda raw: ([{"name": "mine"}], [])
    archive = _zip({"services_export.env": "a.example.com_SERVER_NAME=a.example.com\n", "configs_export.json": "{}", "../evil.txt": "x"})

    _import(h, "export.zip", archive, overwrite_configs="yes")

    importing.apply_imported_configs.assert_called_once_with([{"name": "mine"}], True, [])
    importing.flash_import_results.assert_called_once()
    assert h.config.new_service.call_count == 1


@pytest.mark.parametrize(
    "files, message",
    [
        ({"other.txt": "x"}, "The uploaded archive must contain services_export.env and/or configs_export.json."),
        ({"services_export.env": b"\xff\xfe"}, "Invalid encoding for services_export.env inside the archive."),
        ({"configs_export.json": b"\xff\xfe"}, "Invalid encoding for configs_export.json inside the archive."),
    ],
)
def test_import_refuses_a_bad_archive(h, importing, files, message):
    client, _ = _import(h, "export.zip", _zip({name: content for name, content in files.items()}))

    h.config.new_service.assert_not_called()
    assert message in _flashed(h, client)


def test_import_refuses_an_archive_that_expands_too_much(h, importing, monkeypatch):
    monkeypatch.setattr(importing, "ZIP_MAX_UNCOMPRESSED_BYTES", 10)
    client, _ = _import(h, "export.zip", _zip({"services_export.env": "a" * 100}))

    h.config.new_service.assert_not_called()
    assert "Refusing to extract the archive: uncompressed size exceeds the safety limit." in _flashed(h, client)


# --------------------------------------------------------------------------------------
# settings page
# --------------------------------------------------------------------------------------
def test_an_unknown_service_goes_back_to_the_list(h, services):
    response = h.client().get("/services/ghost.example.com")

    assert response.status_code == 302 and response.headers["Location"].endswith("/services")


def test_the_service_page_renders_the_configuration(h, services):
    h.db.get_templates.return_value = {"my tpl!": {}, "my-tpl": {}}
    h.db.get_config.return_value = {"SERVER_NAME": {"value": "ui.example.com"}}

    h.client().get("/services/ui.example.com?mode=raw&type=core&template=high")

    template, context = h.renders[-1]
    assert template == "service_settings.html"
    assert (context["mode"], context["type"], context["current_template"], context["clone"]) == ("raw", "core", "high", None)
    assert sorted(item["dom_id"] for item in context["templates"].values()) == ["my-tpl", "my-tpl-2"]


def test_a_new_service_can_be_cloned_from_an_existing_one(h, services):
    def get_config(**kwargs):
        if kwargs.get("service") == "ui.example.com":
            return {"X": {"value": "clone"}, "SERVER_NAME": {"value": "ui.example.com"}}
        return {"X": {"value": "global"}, "SERVER_NAME": {"value": ""}, "USE_UI": {"value": "yes"}}

    h.db.get_config.side_effect = get_config
    h.db.get_custom_configs.side_effect = lambda **kwargs: {"ui.example.com_conf": "data"}
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com"}

    h.client().get("/services/new?clone=ui.example.com")

    context = h.renders[-1][1]
    assert context["clone"] == "ui.example.com"
    assert context["config"]["X"] == {"value": "clone", "clone": True}
    assert context["config"]["SERVER_NAME"]["value"] == "" and context["config"]["USE_UI"]["value"] == "no"
    assert context["configs"]["new_conf"] == "data"


def test_a_new_service_without_a_clone_starts_from_the_global_values(h, services):
    h.db.get_config.return_value = {"SERVER_NAME": {"value": ""}}

    h.client().get("/services/new")

    assert h.renders[-1][1]["clone"] == "" and h.renders[-1][1]["config"] == {"SERVER_NAME": {"value": ""}}


def test_saving_a_new_service_without_a_server_name_just_returns_to_the_list(h, services):
    response = h.client().post("/services/new", data={"csrf_token": "t", "USE_X": "yes"})

    assert response.status_code == 302 and "/loading?next=/services" in response.headers["Location"]


def test_metadata_for_drafts_is_only_accepted_in_raw_mode(h, services):
    client = h.client()

    client.post("/services/new", data={"csrf_token": "t", "RAW_DRAFT_SETTINGS": "{}", "SERVER_NAME": "a"})

    h.config.new_service.assert_not_called()
    assert "Setting draft metadata is only accepted in raw mode." in _flashed(h, client)


def test_raw_mode_requires_the_present_settings_metadata(h, services):
    client = h.client()

    client.post("/services/new?mode=raw", data={"csrf_token": "t", "SERVER_NAME": "a"})

    assert "Missing RAW_PRESENT_SETTINGS metadata." in _flashed(h, client)


# --------------------------------------------------------------------------------------
# saving a service (easy mode)
# --------------------------------------------------------------------------------------
@pytest.fixture
def editing(h, services):
    state = {
        "service": {
            "SERVER_NAME": {"value": "ui.example.com", "method": "ui", "global": False},
            "USE_X": {"value": "no", "method": "ui", "global": False},
            "IS_DRAFT": {"value": "no", "method": "ui", "global": False},
        },
        "global": {"SERVER_NAME": {"value": "", "method": "default", "global": True}, "USE_X": {"value": "no", "method": "default", "global": True}},
    }

    def get_config(**kwargs):
        if kwargs.get("with_setting_drafts"):
            return {}
        if kwargs.get("service"):
            return state["service"]
        return state["global"]

    h.db.get_config.side_effect = get_config
    h.db.get_custom_configs.return_value = {}
    h.db.save_custom_configs.return_value = ""
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com"}
    h.config.check_variables.side_effect = lambda variables, *a, **kw: dict(variables)
    h.config.edit_service.return_value = ("", False)
    h.config.new_service.return_value = ("", False)
    h.config.get_plugins_settings.return_value = {}
    h.state = state
    return h


def _save(h, service="ui.example.com", query="", **form):
    data = {"csrf_token": "t", "SERVER_NAME": "ui.example.com", "OLD_SERVER_NAME": "ui.example.com", "USE_X": "no"} | form
    return h.client().post(f"/services/{service}{query}", data=data)


def test_a_changed_setting_is_saved_on_the_service(editing):
    h = editing

    response = _save(h, USE_X="yes")

    name, variables = h.config.edit_service.call_args.args
    assert name == "ui.example.com" and variables["USE_X"] == "yes" and variables["SERVER_NAME"] == "ui.example.com"
    assert h.config.edit_service.call_args.kwargs["is_draft"] is False and h.config.edit_service.call_args.kwargs["check_changes"] is True
    assert ("Configuration successfully saved for service ui.example.com.", "success") in _queued(h)
    assert "message=Saving+configuration+for+service+ui.example.com" in response.headers["Location"]


def test_saving_the_same_values_reports_that_nothing_changed(editing):
    h = editing

    _save(h)

    h.config.edit_service.assert_not_called()
    assert ("The service ui.example.com was not edited because no values or custom configs were changed.", "warning") in _queued(h)
    assert h.data["CONFIG_CHANGED"] is False


def test_a_value_rejected_by_validation_is_never_saved(editing):
    h = editing
    h.config.check_variables.side_effect = lambda *a, **kw: {}

    _save(h, USE_X="invalid")

    h.config.edit_service.assert_not_called()
    assert h.data["RELOADING"] is False


def test_turning_a_service_into_a_draft(editing):
    h = editing

    _save(h, IS_DRAFT="yes")

    kwargs = h.config.edit_service.call_args.kwargs
    assert kwargs["is_draft"] is True and kwargs["check_changes"] is True


def test_saving_an_unchanged_draft_does_not_ask_the_scheduler_to_apply(editing):
    h = editing
    h.state["service"]["IS_DRAFT"]["value"] = "yes"

    _save(h, IS_DRAFT="yes", USE_X="yes")

    assert h.config.edit_service.call_args.kwargs["check_changes"] is False


def test_an_error_from_the_config_layer_is_queued(editing):
    h = editing
    h.config.edit_service.return_value = ("Can't edit: boom", True)

    _save(h, USE_X="yes")

    assert ("Can't edit: boom", "error") in _queued(h) and h.data["CONFIG_CHANGED"] is False


def test_an_already_exists_error_is_only_a_warning(editing):
    h = editing
    h.config.edit_service.return_value = ("Service x already exists.", True)

    _save(h, USE_X="yes")

    assert ("Service x already exists.", "warning") in _queued(h)


def test_a_custom_config_in_the_form_is_saved_with_the_service(editing):
    h = editing

    _save(h, CUSTOM_CONF_SERVER_HTTP_mine="location /x {}\r\n")

    configs = list(h.db.save_custom_configs.call_args.args[0])
    assert [(c["type"], c["name"], c["data"], c["method"]) for c in configs] == [("server_http", "mine", b"location /x {}", "ui")]
    assert "CUSTOM_CONF_SERVER_HTTP_mine" not in h.config.edit_service.call_args.args[1]


def test_a_custom_config_save_error_is_queued(editing):
    h = editing
    h.db.save_custom_configs.return_value = "locked"

    _save(h, CUSTOM_CONF_SERVER_HTTP_mine="x")

    assert ("An error occurred while saving the custom configs: locked", "error") in _queued(h)


def test_a_template_managed_custom_config_cannot_be_overridden(editing):
    h = editing
    h.db.get_custom_configs.return_value = {
        "ui.example.com_server_http_mine": {
            "data": b"old",
            "method": "default",
            "template": "tpl",
            "is_draft": False,
            "service_id": "ui.example.com",
            "type": "server_http",
            "name": "mine",
        }
    }

    _save(h, CUSTOM_CONF_SERVER_HTTP_mine="new", USE_TEMPLATE="other")

    assert any("cannot be edited because it has been created via the default method" in item[0] for item in _queued(h))


def test_renaming_a_service_passes_the_old_name(editing):
    h = editing

    response = _save(h, SERVER_NAME="new.example.com", OLD_SERVER_NAME="ui.example.com")

    assert h.config.edit_service.call_args.args[0] == "ui.example.com"
    assert h.config.edit_service.call_args.args[1]["SERVER_NAME"] == "new.example.com"
    assert "next=/services&" in response.headers["Location"], "a renamed service returns to the list, not to its old page"


def test_a_forged_old_server_name_cannot_redirect_the_edit_to_another_service(editing):
    h = editing

    _save(h, SERVER_NAME="ui.example.com", OLD_SERVER_NAME="other.example.com", USE_X="yes")

    assert h.config.edit_service.call_args.args[0] == "ui.example.com"


def test_a_service_owned_by_another_method_cannot_be_renamed(editing):
    h = editing
    h.db.get_services.return_value = [{"id": "ui.example.com", "method": "autoconf", "is_draft": False}]

    _save(h, SERVER_NAME="new.example.com")

    h.config.edit_service.assert_not_called()
    assert any("cannot be renamed from the Web UI" in item[0] for item in _queued(h))


def test_a_new_service_is_created_with_the_ui_method(editing):
    h = editing

    response = _save(h, service="new", SERVER_NAME="fresh.example.com", OLD_SERVER_NAME="")

    kwargs = h.config.new_service.call_args.kwargs
    assert h.config.new_service.call_args.args[0]["SERVER_NAME"] == "fresh.example.com"
    assert kwargs["override_method"] == "ui" and kwargs["is_draft"] is False
    assert ("Configuration successfully created for service fresh.example.com.", "success") in _queued(h)
    assert "message=Creating+configuration+for+service+fresh.example.com" in response.headers["Location"]


def test_a_new_service_that_validation_empties_is_not_created(editing):
    h = editing
    h.config.check_variables.side_effect = lambda variables, *a, **kw: {**variables, "SERVER_NAME": ""}

    _save(h, service="new", SERVER_NAME="x", OLD_SERVER_NAME="")

    h.config.new_service.assert_not_called()
    assert ("The service was not created because the server name was not provided.", "error") in _queued(h)


def test_a_clone_inherits_the_source_settings_it_did_not_post(editing):
    h = editing
    h.state["service"]["USE_Y"] = {"value": "yes", "method": "ui", "global": False}

    _save(h, service="new", query="?clone=ui.example.com", SERVER_NAME="copy.example.com", OLD_SERVER_NAME="")

    variables = h.config.new_service.call_args.args[0]
    assert variables["USE_Y"] == "yes" and variables["SERVER_NAME"] == "copy.example.com"


def test_raw_mode_passes_the_parsed_draft_state_to_the_save(editing):
    h = editing
    h.routes.services.parse_raw_draft_settings = lambda *a, **kw: {"USE_X": True}

    _save(h, query="?mode=raw", USE_X="yes", RAW_DRAFT_SETTINGS="{}", RAW_PRESENT_SETTINGS="[]")

    assert h.config.edit_service.call_args.kwargs["draft_settings"] == {"USE_X": True}


def test_raw_mode_metadata_errors_are_flashed(editing):
    h = editing

    def refuse(*a, **kw):
        raise h.routes.services.RawDraftSettingsError("bad metadata")

    h.routes.services.parse_raw_draft_settings = refuse
    client = h.client()

    client.post("/services/ui.example.com?mode=raw", data={"csrf_token": "t", "SERVER_NAME": "ui.example.com", "RAW_PRESENT_SETTINGS": "[]"})

    h.config.edit_service.assert_not_called()
    assert "bad metadata" in _flashed(h, client)

"""The /configs blueprint: custom config selection, create/edit/convert/delete, export and import."""

import json

import pytest

from common_utils import bytes_hash  # type: ignore


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


def _queued(h):
    return [(item["content"], item["type"]) for item in h.data["TO_FLASH"]]


@pytest.fixture
def cfg(h):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com b.example.com"}
    h.db.get_custom_configs.return_value = []
    h.db.upsert_custom_config.return_value = ""
    h.db.get_templates.return_value = {"ui": {}, "tpl1": {}, "tpl2": {}}
    return h.routes.configs


def _row(**extra):
    return {"service_id": None, "type": "http", "name": "mine", "data": b"x", "method": "ui", "is_draft": False, "template": None} | extra


# --------------------------------------------------------------------------------------
# selection validation and export parsing
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "selection, ok",
    [
        ([{"name": "a", "type": "http"}], True),
        ([{"name": "a.b", "type": "SERVER-HTTP", "service": "s"}], True),
        ([{"name": "a", "type": "http", "service": None}], True),
        ([], False),
        ("x", False),
        ([{"name": "", "type": "http"}], False),
        ([{"name": "a\nb", "type": "http"}], False),
        ([{"name": "n" * 256, "type": "http"}], False),
        ([{"name": "a", "type": "nope"}], False),
        ([{"name": "a", "type": 5}], False),
        ([{"name": "a", "type": "http", "service": 5}], False),
        (["str"], False),
    ],
)
def test_valid_config_selection(cfg, selection, ok):
    assert cfg._valid_config_selection(selection) is ok


def test_parse_configs_export_keeps_valid_entries_and_reports_the_rest(cfg):
    payload = {
        "configs": [
            {"name": "good", "type": "SERVER-HTTP", "service_id": "global", "data": "d", "is_draft": True},
            {"name": "svc", "type": "http", "service_id": "a.example.com"},
            "string",
            {"name": "bad name!", "type": "http"},
            {"name": "x", "type": 5},
            {"name": "x", "type": "unknown"},
            {"name": "x", "type": "http", "service_id": 5},
            {"name": "x", "type": "http", "data": 5},
            {"name": "x", "type": "http", "is_draft": "yes"},
        ]
    }

    valid, errors = cfg.parse_configs_export(json.dumps(payload))

    assert valid == [
        {"service_id": None, "type": "server_http", "name": "good", "data": "d", "is_draft": True},
        {"service_id": "a.example.com", "type": "http", "name": "svc", "data": "", "is_draft": False},
    ]
    assert errors == [
        "entry #3 is not a JSON object.",
        "entry #4 has an invalid name.",
        "entry #5 (x) has a missing or invalid type.",
        "entry #6 (x) has an unknown type 'unknown'.",
        "entry #7 (x) has an invalid service_id.",
        "entry #8 (x) has non-string data.",
        "entry #9 (x) has a non-boolean is_draft value.",
    ]


@pytest.mark.parametrize("content, message", [("{nope", "File is not valid JSON"), ("[]", "must be a JSON object"), ("{}", "missing a 'configs' array")])
def test_parse_configs_export_rejects_malformed_documents(cfg, content, message):
    valid, errors = cfg.parse_configs_export(content)

    assert valid == [] and message in errors[0]


def test_a_config_name_with_a_trailing_newline_is_not_a_valid_name(cfg):
    valid, errors = cfg.parse_configs_export(json.dumps({"configs": [{"name": "name\n", "type": "http"}]}))

    assert valid == [] and errors == ["entry #1 has an invalid name."]


# --------------------------------------------------------------------------------------
# apply_imported_configs
# --------------------------------------------------------------------------------------
def _entry(**extra):
    return {"service_id": None, "type": "http", "name": "mine", "data": "new", "is_draft": False} | extra


def test_import_creates_a_missing_config(h, cfg):
    results = cfg.apply_imported_configs([_entry()], False, ["warn"])

    assert results["created"] == ["http/mine"] and results["parse_errors"] == ["warn"]
    args, kwargs = h.db.upsert_custom_config.call_args
    assert args[:2] == ("http", "mine") and args[2]["method"] == "ui" and kwargs == {"service_id": None, "new": True}


def test_import_fails_for_an_unknown_service(h, cfg):
    results = cfg.apply_imported_configs([_entry(service_id="ghost.example.com")], True)

    assert results["failed"] == ["http/mine for service ghost.example.com (service 'ghost.example.com' does not exist)"]
    h.db.upsert_custom_config.assert_not_called()


@pytest.mark.parametrize(
    "existing, overwrite, bucket, fragment",
    [
        (_row(), False, "skipped", "already exists; enable 'Overwrite existing' to replace"),
        (_row(), True, "overwritten", ""),
        (_row(method="scheduler"), True, "skipped", "non-editable method: scheduler"),
        (_row(template="t", checksum=bytes_hash("new", algorithm="sha256")), True, "skipped", "unchanged from template"),
        (_row(template="t", checksum="other"), False, "created", ""),
    ],
)
def test_import_over_an_existing_config(h, cfg, existing, overwrite, bucket, fragment):
    h.db.get_custom_configs.return_value = [existing | {"type": "HTTP"}]

    results = cfg.apply_imported_configs([_entry()], overwrite)

    assert len(results[bucket]) == 1 and fragment in results[bucket][0]
    assert (h.db.upsert_custom_config.call_count == 1) is (bucket in ("created", "overwritten"))


def test_import_reports_a_database_error(h, cfg):
    h.db.upsert_custom_config.return_value = "locked"

    assert cfg.apply_imported_configs([_entry()], False)["failed"] == ["http/mine (locked)"]


def test_flash_import_results_summarizes_each_bucket(h, cfg):
    cfg.flash_import_results({"parse_errors": ["p"], "created": ["a", "b"], "overwritten": ["c"], "skipped": ["d"], "failed": ["e"]})

    assert _queued(h) == [
        ("Import warning: p", "error"),
        ("Imported custom configurations: a, b", "success"),
        ("Overwrote custom configuration: c", "success"),
        ("Skipped custom configuration: d", "warning"),
        ("Failed to import custom configuration: e", "error"),
    ]


# --------------------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------------------
def test_configs_page_hides_the_ui_template_from_the_template_list(h, cfg):
    h.config.get_config.return_value = {"SERVER_NAME": "a b"}

    h.client().get("/configs?service=a&type=http")

    context = h.renders[-1][1]
    assert h.renders[-1][0] == "configs.html"
    assert context["db_templates"] == "tpl1 tpl2" and (context["config_service"], context["config_type"]) == ("a", "http")


def test_new_config_form_can_clone_an_existing_config(h, cfg):
    h.db.get_custom_config.return_value = {"data": b"cloned", "is_draft": True}
    h.config.get_config.return_value = {"SERVER_NAME": "a b", "USE_MODSECURITY_GLOBAL_CRS": "YES"}

    h.client().get("/configs/new?clone=global/http/mine")

    template, context = h.renders[-1]
    assert template == "config_edit.html" and context["config_value"] == "cloned" and context["is_draft"] == "yes"
    assert (context["config_service"], context["type"], context["name"]) == ("global", "HTTP", "mine")
    assert context["use_modsecurity_global_crs"] is True and context["services"] == ["a", "b"]
    assert h.db.get_custom_config.call_args.kwargs["service_id"] is None


def test_edit_page_shows_the_stored_config(h, cfg):
    h.db.get_custom_config.return_value = _row(service_id="a.example.com", data=b"conf", is_draft=True, template="tpl")

    h.client().get("/configs/a.example.com/http/mine")

    context = h.renders[-1][1]
    assert context["config_value"] == "conf" and context["is_draft"] == "yes" and context["config_template"] == "tpl" and context["type"] == "HTTP"


def test_editing_a_missing_config_goes_back_to_the_list(h, cfg):
    h.db.get_custom_config.return_value = None
    client = h.client()

    response = client.get("/configs/global/http/ghost")

    assert "/loading?next=/configs" in response.headers["Location"]
    assert "Config http/ghost does not exist." in _flashed(h, client)


# --------------------------------------------------------------------------------------
# create
# --------------------------------------------------------------------------------------
NEW = {"service": "global", "type": "HTTP", "name": "mine", "value": "line1\r\nline2  ", "is_draft": "yes"}


def test_create_a_global_config(h, cfg):
    response = h.client().post("/configs/new", data=NEW)

    args, kwargs = h.db.upsert_custom_config.call_args
    assert args == ("http", "mine", {"type": "http", "name": "mine", "data": "line1\nline2", "method": "ui", "is_draft": True, "service_id": None})
    assert kwargs == {"service_id": None, "new": True}
    assert ("Created custom configuration http/mine", "success") in _queued(h)
    assert "/configs/global/http/mine" in response.headers["Location"].replace("%2F", "/")


def test_create_a_service_config(h, cfg):
    h.client().post("/configs/new", data=NEW | {"service": "a.example.com", "is_draft": "no"})

    assert h.db.upsert_custom_config.call_args.args[2]["service_id"] == "a.example.com"


@pytest.mark.parametrize(
    "change, message",
    [
        ({"service": "ghost"}, "Service ghost does not exist."),
        ({"type": "NOPE"}, "Invalid type parameter on /configs/new."),
        ({"name": "bad name"}, "Invalid name parameter on /configs/new."),
        ({"name": "name\n"}, "Invalid name parameter on /configs/new."),
    ],
)
def test_create_rejects_invalid_fields(h, cfg, change, message):
    client = h.client()

    client.post("/configs/new", data=NEW | change)

    h.db.upsert_custom_config.assert_not_called()
    assert message in _flashed(h, client)


def test_create_reports_a_duplicate_and_other_errors(h, cfg):
    client = h.client()
    h.db.upsert_custom_config.return_value = "The custom config already exists"
    client.post("/configs/new", data=NEW)
    assert ("Config http/mine already exists", "error") in _queued(h) and h.data["CONFIG_CHANGED"] is False

    h.db.upsert_custom_config.return_value = "locked"
    client.post("/configs/new", data=NEW)
    assert ("An error occurred while saving the custom configs: locked", "error") in _queued(h)


# --------------------------------------------------------------------------------------
# edit
# --------------------------------------------------------------------------------------
EDIT = {"service": "a.example.com", "type": "SERVER_HTTP", "name": "renamed", "value": "new data", "is_draft": "no"}


def test_edit_saves_with_the_new_identity(h, cfg):
    h.db.get_custom_config.return_value = _row()

    response = h.client().post("/configs/global/http/mine", data=EDIT)

    args, kwargs = h.db.upsert_custom_config.call_args
    assert args[:2] == ("http", "mine") and args[2] == {
        "service_id": "a.example.com",
        "type": "server_http",
        "name": "renamed",
        "data": "new data",
        "method": "ui",
        "is_draft": False,
    }
    assert kwargs == {"service_id": None}
    assert "/configs/a.example.com/server_http/renamed" in response.headers["Location"]


def test_edit_reports_a_save_error_and_a_save_success(h, cfg):
    h.db.get_custom_config.return_value = _row()
    client = h.client()

    h.db.upsert_custom_config.return_value = "locked"
    client.post("/configs/global/http/mine", data=EDIT)
    h.db.upsert_custom_config.return_value = ""
    client.post("/configs/global/http/mine", data=EDIT)

    flashed = _flashed(h, client)
    assert "An error occurred while saving the custom configs: locked" in flashed
    assert "Saved custom configuration server_http/renamed for service a.example.com" in flashed


def test_edit_with_identical_values_is_refused(h, cfg):
    h.db.get_custom_config.return_value = _row(data=b"same")
    client = h.client()

    client.post("/configs/global/http/mine", data={"service": "global", "type": "HTTP", "name": "mine", "value": "same", "is_draft": "no"})

    h.db.upsert_custom_config.assert_not_called()
    assert "No values were changed." in _flashed(h, client)


def test_a_config_owned_by_another_method_cannot_be_edited(h, cfg):
    h.db.get_custom_config.return_value = _row(method="scheduler")
    client = h.client()

    client.post("/configs/global/http/mine", data=EDIT)

    h.db.upsert_custom_config.assert_not_called()
    assert any("cannot be edited" in message for message in _flashed(h, client))


def test_a_template_config_keeps_its_name_but_can_change_content(h, cfg):
    h.db.get_custom_config.return_value = _row(template="t", method="default")
    client = h.client()

    client.post("/configs/global/http/mine", data=EDIT)
    h.db.upsert_custom_config.assert_not_called()
    assert "Renaming a template-based custom config is not allowed." in _flashed(h, client)

    client.post("/configs/global/http/mine", data=EDIT | {"name": "mine"})
    assert h.db.upsert_custom_config.call_args.args[2]["method"] == "ui"


@pytest.mark.parametrize(
    "change, message",
    [
        ({"service": "ghost"}, "Service ghost does not exist."),
        ({"type": "NOPE"}, "Invalid type parameter on /configs/new."),
        ({"name": "bad name"}, "Invalid name parameter on /configs/new."),
    ],
)
def test_edit_rejects_invalid_fields(h, cfg, change, message):
    h.db.get_custom_config.return_value = _row()
    client = h.client()

    client.post("/configs/global/http/mine", data=EDIT | change)

    h.db.upsert_custom_config.assert_not_called()
    assert message in _flashed(h, client)


@pytest.mark.parametrize(
    "path, form",
    [
        ("/configs/new", NEW),
        ("/configs/global/http/mine", EDIT),
        ("/configs/delete", {"configs": "[]"}),
        ("/configs/convert", {"configs": "[]", "convert_to": "draft"}),
        ("/configs/import", {}),
    ],
)
def test_config_writes_are_refused_in_read_only_mode(h, cfg, path, form):
    h.db.get_custom_config.return_value = _row()
    h.db.readonly = True
    client = h.client()

    client.post(path, data=form)

    h.db.upsert_custom_config.assert_not_called()
    h.db.delete_custom_configs.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)


# --------------------------------------------------------------------------------------
# convert and delete
# --------------------------------------------------------------------------------------
def _convert(h, selection, to="draft"):
    return h.client().post("/configs/convert", data={"configs": json.dumps(selection), "convert_to": to})


def test_convert_changes_the_draft_flag_of_ui_configs_only(h, cfg):
    h.db.get_custom_configs.return_value = [
        _row(name="ui"),
        _row(name="svc", service_id="a.example.com"),
        _row(name="locked", method="scheduler"),
        _row(name="already", is_draft=True),
        _row(name="tpl", template="t"),
    ]
    selection = [
        {"name": n, "type": "http", "service": s}
        for n, s in (("ui", "global"), ("svc", "a.example.com"), ("locked", "global"), ("already", ""), ("tpl", ""), ("ghost", ""))
    ]

    _convert(h, selection)

    assert sorted((call.args[1], call.args[2]["is_draft"]) for call in h.db.upsert_custom_config.call_args_list) == [("svc", True), ("ui", True)]
    queued = _queued(h)
    assert ("Custom config http/locked is not a UI/API custom config and will not be converted.", "error") in queued
    assert ("Custom config http/already is already a draft config and will not be converted.", "error") in queued
    assert ("Custom config http/ghost could not be found.", "error") in queued
    assert any(item[1] == "success" and item[0].startswith('Converted to "Draft" configs:') for item in queued)


def test_convert_with_nothing_convertible(h, cfg):
    _convert(h, [{"name": "ghost", "type": "http"}], "online")

    h.db.upsert_custom_config.assert_not_called()
    assert ("All selected custom configs could not be found, are not UI/API custom configs or are already converted.", "error") in _queued(h)


def test_convert_stops_at_the_first_save_error(h, cfg):
    h.db.get_custom_configs.return_value = [_row(name="a"), _row(name="b")]
    h.db.upsert_custom_config.return_value = "locked"

    _convert(h, [{"name": "a", "type": "http"}, {"name": "b", "type": "http"}])

    assert h.db.upsert_custom_config.call_count == 1
    assert ("An error occurred while saving the custom configs: locked", "error") in _queued(h)


@pytest.mark.parametrize(
    "form",
    [
        {"configs": ""},
        {"configs": "{"},
        {"configs": "[]", "convert_to": "draft"},
        {"configs": '[{"name": "a", "type": "http"}]', "convert_to": "weird"},
        {"configs": '[{"name": "a", "type": "http"}]'},
    ],
)
def test_convert_rejects_bad_requests(h, cfg, form):
    h.client().post("/configs/convert", data=form)

    h.db.upsert_custom_config.assert_not_called()


def test_delete_reports_deleted_and_protected_configs(h, cfg):
    h.db.delete_custom_configs.return_value = ("", {("a.example.com", "http", "x"), (None, "http", "y")}, {(None, "http", "locked")})

    h.client().post(
        "/configs/delete",
        data={
            "configs": json.dumps(
                [{"name": "x", "type": "http", "service": "a.example.com"}, {"name": "y", "type": "http"}, {"name": "locked", "type": "http"}]
            )
        },
    )

    queued = _queued(h)
    assert ("Custom config http/locked is not a UI/API custom config and will not be deleted.", "error") in queued
    assert ("Deleted configs: a.example.com/http/x, http/y", "success") in queued


def test_delete_error_and_nothing_deleted(h, cfg):
    h.db.delete_custom_configs.return_value = ("locked", set(), set())
    h.client().post("/configs/delete", data={"configs": json.dumps([{"name": "x", "type": "http"}])})
    assert ("An error occurred while deleting the custom configs: locked", "error") in _queued(h)

    h.db.delete_custom_configs.return_value = ("", set(), set())
    h.client().post("/configs/delete", data={"configs": json.dumps([{"name": "x", "type": "http"}])})
    assert ("All selected custom configs could not be found or are not UI/API custom configs.", "error") in _queued(h)


@pytest.mark.parametrize("form", [{"configs": ""}, {"configs": "{"}, {"configs": "[]"}])
def test_delete_rejects_bad_requests(h, cfg, form):
    h.client().post("/configs/delete", data=form)

    h.db.delete_custom_configs.assert_not_called()


# --------------------------------------------------------------------------------------
# export and import
# --------------------------------------------------------------------------------------
def test_export_all_normalizes_types_and_decodes_data(h, cfg):
    h.db.get_custom_configs.return_value = [
        _row(type="SERVER-HTTP", service_id="a", data=b"d", is_draft=True),
        _row(name="bin", data=b"\xff"),
        _row(name="str", data="text"),
    ]

    response = h.client().get("/configs/export")

    payload = json.loads(response.get_data())
    assert payload["version"] == 1 and response.headers["Content-Disposition"].endswith("configs_export.json")
    assert payload["configs"][0] == {"service_id": "a", "type": "server_http", "name": "mine", "data": "d", "is_draft": True}
    assert payload["configs"][1]["data"] == "�" and payload["configs"][2]["data"] == "text"


def test_export_a_selection(h, cfg):
    h.db.get_custom_configs.return_value = [_row(name="keep"), _row(name="drop"), _row(name="svc", service_id="a")]

    response = h.client().get(
        "/configs/export",
        query_string={"configs": json.dumps([{"name": "keep", "type": "HTTP", "service": "global"}, {"name": "svc", "type": "http", "service": "a"}])},
    )

    assert [item["name"] for item in json.loads(response.get_data())["configs"]] == ["keep", "svc"]


@pytest.mark.parametrize(
    "selection",
    ["{", "[]", "{}", '["x"]', '[{"type": "http"}]', '[{"name": "a", "type": 5}]', '[{"name": "a", "type": "http", "service": 5}]'],
)
def test_export_rejects_a_malformed_selection(h, cfg, selection):
    client = h.client()

    client.get("/configs/export", query_string={"configs": selection})

    assert "Invalid configs parameter on /configs/export." in _flashed(h, client)
    h.db.get_custom_configs.assert_not_called()


def test_export_with_nothing_to_export(h, cfg):
    client = h.client()

    client.get("/configs/export")

    assert "No custom configurations to export." in _flashed(h, client)


def _import(h, content, name="configs.json", **form):
    import io

    client = h.client()
    return client, client.post("/configs/import", data={"configs_file": (io.BytesIO(content), name)} | form, content_type="multipart/form-data")


def test_import_applies_the_parsed_configs(h, cfg):
    payload = json.dumps({"configs": [{"name": "mine", "type": "http", "data": "d"}]}).encode()

    _import(h, payload, overwrite="yes")

    assert h.db.upsert_custom_config.call_count == 1
    assert ("Imported custom configuration: http/mine", "success") in _queued(h)
    assert h.data["CONFIG_CHANGED"] is True and h.data["RELOADING"] is False


@pytest.mark.parametrize(
    "content, message",
    [
        (b"\xff\xfe", "Invalid file encoding. Please upload a UTF-8 JSON file."),
        (b"{nope", "Import error: File is not valid JSON"),
        (json.dumps({"configs": []}).encode(), "No custom configurations found in the import file."),
    ],
)
def test_import_refuses_unusable_files(h, cfg, content, message):
    client, _ = _import(h, content)

    h.db.upsert_custom_config.assert_not_called()
    assert any(message in flashed for flashed in _flashed(h, client))


def test_import_requires_a_file(h, cfg):
    client = h.client()

    client.post("/configs/import", data={})

    assert "No custom configurations file uploaded." in _flashed(h, client)

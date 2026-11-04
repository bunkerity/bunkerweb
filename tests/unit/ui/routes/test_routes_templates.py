"""The /templates blueprint: the editor context, the settings catalog and the write permissions."""

import json
from datetime import datetime, timezone

import pytest

CORS = {"Sec-Fetch-Mode": "cors"}


@pytest.fixture
def tpl(h):
    h.db.get_templates.return_value = {"mine": {"method": "ui", "name": "Mine"}, "core": {"method": "default"}}
    h.db.get_template_details.return_value = None
    h.db.get_plugins.return_value = []
    h.config.get_settings.return_value = {}
    h.config.get_plugins.return_value = {}
    for method in ("create_template", "update_template", "delete_template"):
        getattr(h.db, method).return_value = ""
    return h.routes.templates


def _flashed(h, client):
    return [(message, category) for message, category in h.flashes(client)]


def test_templates_page_lists_the_templates(h, tpl):
    h.client().get("/templates")

    assert h.renders[-1][0] == "templates.html" and set(h.renders[-1][1]["templates"]) == {"mine", "core"}


# --------------------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [("RAW", "raw"), (" easy ", "easy"), ("weird", "easy"), (None, "easy"), (5, "easy")])
def test_view_mode_defaults_to_easy(tpl, raw, expected):
    assert tpl._normalize_view_mode(raw) == expected


@pytest.mark.parametrize("raw, expected", [(["a", 1, None, {"x": 1}, True], ["a", "1", "True"]), ("one", ["one"]), (3, ["3"]), (None, []), ({"k": 1}, [])])
def test_tags_are_flattened_to_strings(tpl, raw, expected):
    assert tpl._normalise_tags(raw) == expected


def test_convert_template_details_accepts_both_settings_shapes(tpl):
    as_dict = tpl._convert_template_details(
        {"id": "t", "settings": {"A": "1", 2: "x"}, "steps": [{"title": "s", "settings": ["A"]}], "configs": [{"type": "http", "name": "n", "data": "d"}]}
    )
    as_list = tpl._convert_template_details({"id": "t", "name": "T", "settings": [{"key": "A", "default": "1"}, {"key": "", "default": "x"}, {"key": "B"}]})

    assert as_dict["settings"] == {"A": "1", "2": "x"} and as_dict["name"] == "t"
    assert as_dict["steps"] == [{"title": "s", "subtitle": None, "settings": ["A"], "configs": []}]
    assert as_dict["configs"] == [{"type": "http", "name": "n", "data": "d", "order": None}]
    assert as_list["settings"] == {"A": "1", "B": ""} and as_list["name"] == "T"


def test_template_meta_datetimes_are_serialized(tpl):
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    assert tpl._serialize_template_meta({"created": moment, "name": "x"}) == {"created": moment.astimezone().isoformat(), "name": "x"}


def test_the_multisite_catalog_merges_core_and_plugin_settings_in_plugin_order(h, tpl):
    h.config.get_settings.return_value = {
        "SERVER_NAME": {"context": "multisite", "label": "Server name", "type": "text", "help": "names", "default": "", "regex": "^x$", "multiple": "srv"},
        "WORKERS": {"context": "global"},
        "BROKEN": "not a dict",
    }
    h.db.get_plugins.return_value = [{"id": "second"}, {"id": "first"}]
    h.config.get_plugins.return_value = {
        "first": {
            "name": "First",
            "type": "external",
            "category": "security",
            "settings": {
                "A": {
                    "context": "multisite",
                    "select": ["x", {"id": "y"}, None],
                    "multiselect": [{"id": "m"}, {"nope": 1}],
                    "separator": " ",
                    "accept": "image/*",
                    "category": "other",
                    "tags": ["t"],
                    "advanced": 1,
                },
                "SERVER_NAME": {"context": "multisite"},
            },
        },
        "second": {"settings": {"B": {"context": "multisite", "docs": "http://d"}}},
        "orphan": {"settings": {"C": {"context": "multisite"}}},
        "bad": "x",
        "nosettings": {"settings": None},
    }

    catalog = tpl._build_multisite_settings_catalog()

    assert [entry["key"] for entry in catalog] == ["SERVER_NAME", "B", "A", "C"]
    server = catalog[0]
    assert (server["label"], server["description"], server["regex"], server["multiple"], server["default"]) == ("Server name", "names", "^x$", "srv", "")
    a = catalog[2]
    assert a["options"] == ["x", {"id": "y"}] and a["multiselect"] == [{"id": "m"}] and a["separator"] == " " and a["accept"] == "image/*"
    assert a["category"] == "other" and a["tags"] == ["t"] and a["advanced"] is True and a["plugin"]["category"] == "security"
    assert catalog[1]["docs"] == "http://d" and catalog[1]["plugin"]["name"] == "second"
    assert all(entry["key"] != "WORKERS" for entry in catalog)


def test_the_catalog_survives_failing_sources(h, tpl):
    h.config.get_settings.side_effect = RuntimeError("x")
    h.db.get_plugins.side_effect = RuntimeError("x")
    h.config.get_plugins.side_effect = RuntimeError("x")

    assert tpl._build_multisite_settings_catalog() == []


def test_the_catalog_accepts_a_list_of_plugins(h, tpl):
    h.config.get_plugins.return_value = [{"id": "p", "settings": {"S": {"context": "multisite"}}}]

    assert [entry["key"] for entry in tpl._build_multisite_settings_catalog()] == ["S"]


# --------------------------------------------------------------------------------------
# editor pages
# --------------------------------------------------------------------------------------
def test_the_new_template_page_starts_empty(h, tpl):
    h.client().get("/templates/new?view=raw")

    template, context = h.renders[-1]
    assert template == "template_edit.html"
    assert context["editor_mode"] == "create" and context["view_mode"] == "raw" and context["template_id"] is None
    assert context["template_data"] == {"id": "", "name": "", "settings": {}, "steps": [], "configs": []}
    assert context["can_edit_template"] is True and context["edit_restrictions"] == [] and set(context["routes"]) == {"list", "create"}


def test_cloning_copies_the_source_without_its_id(h, tpl):
    h.db.get_template_details.return_value = {"name": "Src", "settings": {"A": "1"}}

    h.client().get("/templates/new?clone=src")

    context = h.renders[-1][1]
    assert context["template_data"]["id"] == "" and context["template_data"]["settings"] == {"A": "1"}
    assert context["clone_meta"] == {"source_id": "src", "source_name": "Src"}


def test_cloning_an_unknown_template_flashes_and_opens_an_empty_editor(h, tpl):
    client = h.client()

    client.get("/templates/new?clone=ghost")

    assert ("Template ghost not found.", "error") in _flashed(h, client)
    assert h.renders[-1][1]["clone_meta"] is None


def test_the_edit_page_marks_a_non_ui_template_read_only(h, tpl):
    h.db.get_template_details.return_value = {"name": "Core"}

    h.client().get("/templates/core")

    context = h.renders[-1][1]
    assert context["can_edit_template"] is False and context["edit_restrictions"] == ["method"]
    assert context["routes"]["update"].endswith("/templates/core/update")


def test_the_edit_page_for_a_ui_template_is_editable_with_write_permission(h, tpl):
    h.db.get_template_details.return_value = {"name": "Mine"}

    h.client("writer", permissions=("read", "write")).get("/templates/mine")
    assert h.renders[-1][1]["can_edit_template"] is True

    h.client("viewer", admin=False, permissions=("read",)).get("/templates/mine")
    assert h.renders[-1][1]["can_edit_template"] is False and h.renders[-1][1]["edit_restrictions"] == ["user"]


def test_the_edit_page_of_an_unknown_template_redirects_with_a_message(h, tpl):
    client = h.client()

    response = client.get("/templates/ghost")

    assert response.headers["Location"].endswith("/templates") and ("Template not found.", "error") in _flashed(h, client)


def test_the_editor_reports_a_read_only_database(h, tpl):
    h.db.readonly = True

    h.client().get("/templates/new")

    assert h.renders[-1][1]["edit_restrictions"] == ["database"] and h.renders[-1][1]["can_edit_template"] is False


def test_template_detail_json(h, tpl):
    h.db.get_template_details.return_value = {"name": "Mine", "settings": {"A": "1"}}
    client = h.client()

    body = client.get("/templates/mine/json", headers=CORS).get_json()

    assert body["status"] == "success" and body["template"]["id"] == "mine" and body["template"]["settings"] == {"A": "1"}
    h.db.get_template_details.return_value = None
    assert client.get("/templates/mine/json", headers=CORS).status_code == 404
    assert client.get("/templates/mine/json").status_code == 403


# --------------------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------------------
def _template(**extra):
    return {"template": json.dumps({"id": " new-tpl ", "name": "New", "settings": {"A": "1"}} | extra)}


def test_create_stores_the_template_and_flashes(h, tpl):
    client = h.client()

    response = client.post("/templates/create", headers=CORS, data=_template())

    h.db.create_template.assert_called_once_with("new-tpl", name="New", settings={"A": "1"}, steps=[], configs=[])
    assert response.get_json() == {"status": "success"} and ("Template new-tpl created successfully.", "message") in _flashed(h, client)


@pytest.mark.parametrize(
    "form, message",
    [
        ({}, "Missing template payload"),
        ({"template": "{nope"}, "Invalid JSON payload"),
        ({"template": "[1]"}, "Template payload must be a JSON object"),
        ({"template": json.dumps({"id": "  "})}, "Template id is required"),
    ],
)
def test_create_validates_the_payload(h, tpl, form, message):
    response = h.client().post("/templates/create", headers=CORS, data=form)

    assert response.status_code == 400 and message in response.get_json()["message"]
    h.db.create_template.assert_not_called()


def test_create_reports_a_database_error(h, tpl):
    h.db.create_template.return_value = "already exists"

    response = h.client().post("/templates/create", headers=CORS, data=_template())

    assert response.status_code == 400 and response.get_json()["message"] == "already exists"


@pytest.mark.parametrize("path", ["/templates/create", "/templates/mine/update", "/templates/mine/delete"])
def test_writes_are_refused_to_a_read_only_user(h, tpl, path):
    response = h.client("viewer", admin=False, permissions=("read",)).post(path, headers=CORS, data=_template())

    assert response.status_code == 403 and response.get_json()["message"] == "User is read-only"
    h.db.create_template.assert_not_called()
    h.db.update_template.assert_not_called()
    h.db.delete_template.assert_not_called()


@pytest.mark.parametrize("path", ["/templates/create", "/templates/mine/update", "/templates/mine/delete"])
def test_writes_are_a_409_on_a_read_only_database(h, tpl, path):
    h.db.readonly = True

    response = h.client().post(path, headers=CORS, data=_template())

    assert response.status_code == 409
    h.db.create_template.assert_not_called()


def test_update_keeps_the_current_parts_the_payload_omits(h, tpl):
    h.db.get_template_details.return_value = {"name": "Old", "settings": {"A": "old"}, "steps": [{"title": "s"}], "configs": [{"type": "http", "name": "n"}]}

    response = h.client().post("/templates/mine/update", headers=CORS, data={"template": json.dumps({"settings": {"A": "new"}})})

    kwargs = h.db.update_template.call_args.kwargs
    assert response.get_json() == {"status": "success"}
    assert kwargs["name"] == "Old" and kwargs["settings"] == {"A": "new"}
    assert kwargs["steps"] == [{"title": "s", "subtitle": None, "settings": [], "configs": []}] and kwargs["configs"][0]["name"] == "n"


def test_update_of_an_unknown_template_is_a_404(h, tpl):
    assert h.client().post("/templates/ghost/update", headers=CORS, data=_template()).status_code == 404
    h.db.update_template.assert_not_called()


def test_update_validates_the_payload_and_reports_database_errors(h, tpl):
    h.db.get_template_details.return_value = {"name": "Old"}
    client = h.client()

    assert client.post("/templates/mine/update", headers=CORS, data={}).status_code == 400
    h.db.update_template.return_value = "locked"
    assert client.post("/templates/mine/update", headers=CORS, data=_template()).get_json()["message"] == "locked"


def test_delete_one_maps_in_use_conflicts_to_409(h, tpl):
    client = h.client()
    assert client.post("/templates/mine/delete", headers=CORS).get_json() == {"status": "success"}

    h.db.delete_template.return_value = "Template is currently used by a service"
    assert client.post("/templates/mine/delete", headers=CORS).status_code == 409
    h.db.delete_template.return_value = "other"
    assert client.post("/templates/mine/delete", headers=CORS).status_code == 400


def test_bulk_delete_reports_successes_and_failures(h, tpl):
    h.db.delete_template.side_effect = ["", "in use", ""]
    client = h.client()

    client.post("/templates/delete", data={"templates": "a, b ,,c"})

    assert [call.args[0] for call in h.db.delete_template.call_args_list] == ["a", "b", "c"]
    flashed = _flashed(h, client)
    assert ("Successfully deleted 2 template(s).", "message") in flashed and ("Error deleting template b: in use", "error") in flashed


def test_bulk_delete_with_nothing_selected_warns(h, tpl):
    client = h.client()

    client.post("/templates/delete", data={})

    h.db.delete_template.assert_not_called()
    assert ("No templates selected for deletion.", "warning") in _flashed(h, client)


def test_bulk_delete_is_refused_to_a_read_only_user(h, tpl):
    client = h.client("viewer", admin=False, permissions=("read",))

    client.post("/templates/delete", data={"templates": "a"})

    h.db.delete_template.assert_not_called()
    assert ("User is read-only", "error") in _flashed(h, client)

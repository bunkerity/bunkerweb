"""Resource-group UI client and Flask route contracts."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call, patch

import pytest
from flask import Flask
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.api_client import ApiClient


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


@pytest.fixture(scope="module")
def resource_groups_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    route_utils = ModuleType("app.routes.utils")
    route_utils.cors_required = lambda function: function
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    module_name = "app.routes._resource_groups_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "resource_groups.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "app.dependencies": dependencies,
            "app.routes.utils": route_utils,
            "app.utils": app_utils,
            module_name: module,
        },
    ):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def route_app(resource_groups_route):
    module, client = resource_groups_route
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.resource_groups)
    return module, client, app


def test_api_client_paths_and_payloads(api_client, monkeypatch):
    get = Mock(
        side_effect=[
            {"resource_groups": {"office": {"name": "office"}}},
            {"resource_group": {"id": "office"}},
            {"references": [{"scope": "global"}]},
        ]
    )
    post = Mock(return_value={"status": "success"})
    patch_request = Mock(return_value={"status": "success"})
    delete = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_get", get)
    monkeypatch.setattr(api_client, "_post", post)
    monkeypatch.setattr(api_client, "_patch", patch_request)
    monkeypatch.setattr(api_client, "_delete", delete)

    assert "office" in api_client.get_resource_groups(include_usage=True)
    assert api_client.get_resource_group("office") == {"id": "office"}
    assert api_client.get_resource_group_references("office") == [{"scope": "global"}]
    api_client.create_resource_group("office", "office", entries=[{"kind": "ip", "value": "1.2.3.4"}])
    api_client.update_resource_group("office", description="HQ")
    api_client.clone_resource_group("office", "office-copy", "office-copy")
    api_client.delete_resource_group("office")

    assert get.call_args_list == [
        call("/resource_groups", params={"include_usage": "true"}),
        call("/resource_groups/office"),
        call("/resource_groups/office/references"),
    ]
    assert post.call_args_list == [
        call(
            "/resource_groups",
            json={
                "id": "office",
                "name": "office",
                "description": "",
                "entries": [{"kind": "ip", "value": "1.2.3.4"}],
            },
        ),
        call(
            "/resource_groups/office/clone",
            json={"id": "office-copy", "name": "office-copy"},
        ),
    ]
    patch_request.assert_called_once_with("/resource_groups/office", json={"description": "HQ"})
    delete.assert_called_once_with("/resource_groups/office")


def test_page_requests_usage_and_renders_rows(route_app, monkeypatch):
    module, client, app = route_app
    client.get_resource_groups.return_value = {"office": {"name": "office", "entries": [], "method": "ui"}}
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/groups"):
        assert module.resource_groups_page.__wrapped__() == "rendered"

    client.get_resource_groups.assert_called_once_with(include_usage=True)
    assert render.call_args.kwargs["resource_groups"][0]["id"] == "office"


def test_create_group_parses_ordered_entries(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())
    entries = '[{"kind":"country","value":"fr","comment":"HQ"},{"kind":"asn","value":"AS42"}]'

    with app.test_request_context(
        "/groups/save",
        method="POST",
        data={"alias": "office", "description": "Trusted", "entries": entries},
    ):
        response = module.resource_groups_save.__wrapped__()

    assert response.status_code == 302
    client.create_resource_group.assert_called_once_with(
        "office",
        "office",
        description="Trusted",
        entries=[
            {"kind": "country", "value": "fr", "comment": "HQ", "order": 1},
            {"kind": "asn", "value": "AS42", "comment": "", "order": 2},
        ],
    )


def test_update_keeps_alias_stable(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())

    with app.test_request_context(
        "/groups/save",
        method="POST",
        data={
            "group_id": "office",
            "alias": "renamed",
            "description": "New",
            "entries": "[]",
        },
    ):
        module.resource_groups_save.__wrapped__()

    client.update_resource_group.assert_called_once_with("office", description="New", entries=[])


def test_invalid_alias_never_reaches_api(route_app, monkeypatch):
    module, client, app = route_app
    flash = Mock()
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context(
        "/groups/save",
        method="POST",
        data={"alias": "not valid", "description": "", "entries": "[]"},
    ):
        module.resource_groups_save.__wrapped__()

    client.create_resource_group.assert_not_called()
    flash.assert_called_once_with(
        "The alias must contain 1 to 64 letters, digits, underscores, or dashes",
        "error",
    )


def test_builtin_alias_never_reaches_api(route_app, monkeypatch):
    module, client, app = route_app
    flash = Mock()
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context(
        "/groups/save",
        method="POST",
        data={"alias": "EU", "description": "", "entries": "[]"},
    ):
        module.resource_groups_save.__wrapped__()

    client.create_resource_group.assert_not_called()
    flash.assert_called_once_with("This alias is reserved by BunkerWeb", "error")


def test_readonly_blocks_delete(route_app, monkeypatch):
    module, client, app = route_app
    client.readonly = True
    monkeypatch.setattr(module, "flash", Mock())

    with app.test_request_context("/groups/delete", method="POST", data={"group_id": "office"}):
        response = module.resource_groups_delete.__wrapped__()

    assert response.status_code == 302
    client.delete_resource_group.assert_not_called()


def test_resource_group_picker_only_lists_matching_kind():
    templates = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
    environment = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    picker = environment.get_template("components/resource-group-picker.html").module.resource_group_picker
    groups = {
        "office": {
            "name": "office",
            "entries": [
                {"kind": "ip", "value": "192.0.2.1"},
                {"kind": "ip", "value": "192.0.2.2"},
            ],
        },
        "countries": {
            "name": "countries",
            "entries": [{"kind": "country", "value": "FR"}],
        },
    }

    rendered = str(picker("setting-whitelist-ip", groups, "ip"))

    assert 'value="@office"' in rendered
    assert "@office (2)" in rendered
    assert "@countries" not in rendered
    assert 'data-target="#setting-whitelist-ip"' in rendered


def test_resource_group_interactions_translate_dynamic_copy_and_restore_focus():
    ui_root = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
    script = (ui_root / "static" / "js" / "pages" / "groups.js").read_text(encoding="utf-8")
    locale = json.loads((ui_root / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
    keys = {
        "clone_copy",
        "collapse_all",
        "delete_confirm",
        "editor_edit",
        "editor_new",
        "global_configuration",
        "import_extension",
        "import_size",
        "max_entries",
        "references_error",
        "showing_count",
        "template_configuration",
    }

    for key in keys:
        assert f'"resource_groups.{key}"' in script
        assert isinstance(locale["resource_groups"][key], str)
    assert '"hidden.bs.modal"' in script
    assert "modal.show(trigger)" in script


def test_resource_group_data_controls_are_not_hidden_focus_targets():
    template = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "groups.html").read_text(encoding="utf-8")

    for control_id in (
        "resource-groups-data",
        "resource-group-entries",
        "resource-group-import-file",
    ):
        attributes = template.split(f'id="{control_id}"', 1)[1].split(">", 1)[0]
        assert " hidden" in attributes
        assert "visually-hidden" not in attributes

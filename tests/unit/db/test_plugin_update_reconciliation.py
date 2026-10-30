"""Plugin updates reconcile owned rows and preserve user-created templates."""

from copy import deepcopy
import json

import pytest

import Database as database_module
from fixtures.seed import make_external_plugin, seed_minimal

pytestmark = pytest.mark.multiengine


@pytest.fixture
def plugin_assets(db, tmp_path, monkeypatch):
    seed_minimal(db)
    monkeypatch.setattr(database_module, "sep", str(tmp_path))
    path = tmp_path / "etc/bunkerweb/plugins/extplugin/templates"
    for config_type in ("server-http", "modsec"):
        folder = path / "profile/configs" / config_type
        folder.mkdir(parents=True)
        (folder / "route.conf").write_text("# plugin config\n")
    return path


def _template():
    return {
        "name": "Profile",
        "settings": {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_URL_1": "/keep", "REVERSE_PROXY_URL_2": "/remove"},
        "configs": ["server-http/route.conf", "modsec/route.conf"],
        "steps": [
            {"title": "Routing", "subtitle": "Upstream", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"], "configs": ["server-http/route.conf"]},
            {"title": "Extra", "subtitle": "Details", "settings": ["REVERSE_PROXY_URL_2"], "configs": ["modsec/route.conf"]},
        ],
    }


def _create_user_template(db):
    assert (
        db.create_template(
            "user-profile",
            name="User profile",
            settings={"USE_REVERSE_PROXY": "no", "REVERSE_PROXY_URL_2": "/user"},
            steps=[
                {"title": "User routing", "settings": ["USE_REVERSE_PROXY"]},
                {"title": "User extra", "settings": ["REVERSE_PROXY_URL_2"], "configs": ["modsec/route.conf"]},
            ],
            configs=[{"type": "modsec", "name": "route", "data": "# user config\n"}],
        )
        == ""
    )
    return db.get_template_details("user-profile")


@pytest.mark.parametrize("options", [["one", "two", "three"], ["one"], [], ["two", "one"]], ids=["append", "truncate", "clear", "reorder"])
@pytest.mark.parametrize("kind", ["select", "multiselect"])
def test_plugin_choice_updates_compare_complete_ordered_lists(db, plugin_assets, kind, options):
    def manifest(choices):
        plugin = make_external_plugin()
        rows = choices if kind == "select" else [{"id": value, "label": value.title(), "value": value} for value in choices]
        plugin["settings"]["EXTPLUGIN_MS"].update(type=kind, **{kind: rows})
        return plugin, rows

    initial, _ = manifest(["one", "two"])
    assert db.update_external_plugins([initial]) == ""
    incoming, expected = manifest(options)
    assert db.update_external_plugins([incoming]) == ""
    assert db.get_plugins(_type="external")[0]["settings"]["EXTPLUGIN_MS"][kind] == expected


@pytest.mark.parametrize("operation", ["append", "remove"])
def test_plugin_step_changes_preserve_other_templates_and_remove_owned_rows(db, plugin_assets, operation):
    template = _template()
    initial = deepcopy(template)
    if operation == "append":
        initial["steps"] = initial["steps"][:1]
        initial["settings"].pop("REVERSE_PROXY_URL_2")
        initial["configs"].remove("modsec/route.conf")
    path = plugin_assets / "profile.json"
    path.write_text(json.dumps(initial))
    assert db.update_external_plugins([make_external_plugin()]) == ""
    user_before = _create_user_template(db)
    if operation == "remove":
        template["steps"] = template["steps"][:1]
        # Step deletion must clean its children even if stale manifest references remain.
    path.write_text(json.dumps(template))
    assert db.update_external_plugins([make_external_plugin()]) == ""
    assert db.get_template_details("user-profile") == user_before
    saved = db.get_templates()["profile"]
    assert len(saved["steps"]) == (2 if operation == "append" else 1)
    if operation == "remove":
        assert saved["settings"] == {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_URL_1": "/keep"}
        assert saved["configs"] == {"server_http/route.conf": "# plugin config\n"}


def test_first_plugin_update_repairs_stale_rows_without_changing_user_templates(db, plugin_assets):
    template = _template()
    path = plugin_assets / "profile.json"
    path.write_text(json.dumps(template))
    assert db.update_external_plugins([make_external_plugin()]) == ""
    user_before = _create_user_template(db)
    template["settings"].pop("REVERSE_PROXY_URL_2")
    template["configs"].remove("modsec/route.conf")
    template["steps"][1].update(title="Revised", settings=[], configs=[])
    path.write_text(json.dumps(template))
    incoming = make_external_plugin()
    incoming["settings"]["EXTPLUGIN_MS"].update(type="select", select=["new", "other"])
    assert db.update_external_plugins([incoming]) == ""
    assert db.get_template_details("user-profile") == user_before
    saved = db.get_templates()["profile"]
    assert saved["settings"] == {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_URL_1": "/keep"}
    assert saved["configs"] == {"server_http/route.conf": "# plugin config\n"}
    assert db.get_plugins(_type="external")[0]["settings"]["EXTPLUGIN_MS"]["select"] == ["new", "other"]

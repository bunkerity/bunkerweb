"""`GET /templates/{id}/export`, `POST /templates/import` and the ownership guards (CAT-C2).

The real router module, with the real FastAPI ``APIRouter`` and ``JSONResponse`` and a real
``Database`` behind ``get_db``: only the auth guard and the ``app.utils`` accessor are stubbed.
So these tests exercise ``template_package`` validation, ``create_template`` /
``update_template`` / ``delete_template`` and their ownership guards end to end, not a mock of
them. (There is no ``httpx`` in the unit venv, so no ``TestClient``: the endpoint functions are
called directly and the route table is asserted separately.)

The guards close design gaps G6 and G7. What they prevent was measured on the unguarded code
(``.cache/wave23-2026-09-23/proofs/cat-c2/sync-effect-probe.txt``): an edit or a delete of a
plugin-owned template was accepted, then silently undone at the next scheduler boot (core) or
plugin sync (external) -- and an edited external template kept its new name and ``method="ui"``
while its content reverted, a hybrid nobody asked for.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from fixtures.seed import make_core_plugin, make_general_settings

ROOT = Path(__file__).resolve().parents[3]
PACKAGE_FORMAT = "bunkerweb-template/1"


def _load_router():
    names = {
        "bw_tpl_io": ModuleType("bw_tpl_io"),
        "bw_tpl_io.routers": ModuleType("bw_tpl_io.routers"),
        "bw_tpl_io.auth": ModuleType("bw_tpl_io.auth"),
        "bw_tpl_io.auth.guard": ModuleType("bw_tpl_io.auth.guard"),
        "bw_tpl_io.utils": ModuleType("bw_tpl_io.utils"),
    }
    for package in ("bw_tpl_io", "bw_tpl_io.routers", "bw_tpl_io.auth"):
        names[package].__path__ = []
    names["bw_tpl_io.auth.guard"].guard = lambda: None
    names["bw_tpl_io.utils"].get_db = lambda: None
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "templates.py"
        spec = importlib.util.spec_from_file_location("bw_tpl_io.routers.templates", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _body(response):
    return json.loads(response.body)


@pytest.fixture
def api(db, monkeypatch):
    db.init_tables([make_general_settings(), make_core_plugin("tplplug")])
    db.initialize_db("1.7.0", "Docker")
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    return db


def _package(template_id="web", *, name="Web template", value="one", config="# one\n", **over):
    package = {
        "format": PACKAGE_FORMAT,
        "id": template_id,
        "name": name,
        "settings": {"TPLPLUG_MS": value},
        "steps": [{"title": "Step 1", "subtitle": "", "settings": ["TPLPLUG_MS"], "configs": ["modsec/extra.conf"]}],
        "configs": [{"type": "modsec", "name": "extra", "data": config}],
    }
    package.update(over)
    return package


def _create_plugin_owned(db, template_id="owned"):
    assert (
        db.create_template(
            template_id,
            plugin_id="tplplug",
            name="Owned by a plugin",
            settings={"TPLPLUG_MS": "plugin"},
            steps=[{"title": "S", "settings": ["TPLPLUG_MS"]}],
            method="manual",
        )
        == ""
    )


def _snapshot(db, template_id):
    details = db.get_template_details(template_id)
    if details is None:
        return None
    return {
        "name": details["name"],
        "method": details["method"],
        "plugin_id": details["plugin_id"],
        "settings": {s["key"]: s["default"] for s in details["settings"]},
        "configs": {c["key"]: c["data"] for c in details["configs"]},
        "steps": [(s["title"], s["subtitle"], s["settings"], s["configs"]) for s in details["steps"]],
    }


# ── the route table ─────────────────────────────────────────────────────────────


def test_both_routes_are_registered_and_guarded():
    routes = {(route.path, method): route for route in ROUTER.router.routes for method in route.methods}
    assert ("/templates/{template_id}/export", "GET") in routes
    assert ("/templates/import", "POST") in routes
    for key in (("/templates/{template_id}/export", "GET"), ("/templates/import", "POST")):
        assert [dependency.dependency for dependency in routes[key].dependencies] == [ROUTER.guard]


# ── export ──────────────────────────────────────────────────────────────────────


def test_export_answers_the_package_as_an_attachment(api):
    assert ROUTER.import_template(_package()).status_code == 201
    response = ROUTER.export_template("web")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="web.bwtemplate.json"'
    assert _body(response) == {
        "format": PACKAGE_FORMAT,
        "id": "web",
        "name": "Web template",
        "settings": {"TPLPLUG_MS": "one"},
        "steps": [{"title": "Step 1", "subtitle": "", "settings": ["TPLPLUG_MS"], "configs": ["modsec/extra.conf"]}],
        "configs": [{"type": "modsec", "name": "extra", "data": "# one\n"}],
    }


def test_export_of_an_unknown_template_is_a_404(api):
    response = ROUTER.export_template("nope")
    assert response.status_code == 404
    assert _body(response)["message"] == "Template not found"


def test_a_plugin_owned_template_exports_too(api):
    """Export is a read: it is how an operator copies a core template before editing the copy."""
    _create_plugin_owned(api)
    body = _body(ROUTER.export_template("owned"))
    assert body["id"] == "owned" and body["settings"] == {"TPLPLUG_MS": "plugin"}
    assert "plugin_id" not in body and "method" not in body


def test_export_then_import_round_trips(api):
    assert ROUTER.import_template(_package()).status_code == 201
    before = _snapshot(api, "web")
    exported = _body(ROUTER.export_template("web"))
    assert api.delete_template("web") == ""
    assert ROUTER.import_template(exported).status_code == 201
    assert _snapshot(api, "web") == before


# ── import ──────────────────────────────────────────────────────────────────────


def test_import_creates_a_ui_template(api):
    response = ROUTER.import_template(_package())
    assert response.status_code == 201
    assert _body(response) == {"status": "success", "id": "web", "replaced": False}
    snap = _snapshot(api, "web")
    assert snap["method"] == "ui" and snap["plugin_id"] is None
    assert snap["configs"] == {"modsec/extra.conf": "# one\n"}


def test_import_drops_unknown_keys_and_never_takes_ownership(api):
    """`plugin_id` and `method` are not package fields: an imported template is always the UI's."""
    response = ROUTER.import_template(_package(plugin_id="tplplug", method="manual", locales={"fr": {"name": "x"}}))
    assert response.status_code == 201
    snap = _snapshot(api, "web")
    assert snap["method"] == "ui" and snap["plugin_id"] is None


@pytest.mark.parametrize(
    ("package", "fragment"),
    [
        ({"format": "bunkerweb-template/2", "id": "web"}, "unsupported package format"),
        (_package("../etc"), "invalid template id"),
        (_package("bad id"), "invalid template id"),
        (_package(name=""), "name must be a non-empty string"),
        (_package(configs=[{"type": "modsec", "name": "../x", "data": ""}]), "config 1 must be an object"),
        (_package(configs=[{"type": "modsec", "name": f"c{i}", "data": ""} for i in range(33)]), "at most 32"),
        ("not an object", "not a JSON object"),
    ],
)
def test_a_malformed_package_is_a_400_and_creates_nothing(api, package, fragment):
    response = ROUTER.import_template(package)
    assert response.status_code == 400
    assert fragment in _body(response)["message"]
    assert api.get_templates() == {}


def test_an_unknown_setting_refuses_the_whole_template(api):
    package = _package(settings={"TPLPLUG_MS": "one", "NOT_A_SETTING": "x"})
    package["steps"][0]["settings"].append("NOT_A_SETTING")
    response = ROUTER.import_template(package)
    assert response.status_code == 400
    assert "Unknown settings: NOT_A_SETTING" in _body(response)["message"]
    assert api.get_templates() == {}


def test_an_existing_id_is_a_409_without_replace_and_nothing_changes(api):
    assert ROUTER.import_template(_package()).status_code == 201
    before = _snapshot(api, "web")
    response = ROUTER.import_template(_package(value="two"))
    assert response.status_code == 409
    assert _body(response)["message"] == "Template web already exists"
    assert _snapshot(api, "web") == before


def test_replace_updates_a_ui_template_in_place(api):
    assert ROUTER.import_template(_package()).status_code == 201
    response = ROUTER.import_template(_package(name="Web v2", value="two", config="# two\n"), replace=True)
    assert response.status_code == 200
    assert _body(response) == {"status": "success", "id": "web", "replaced": True}
    snap = _snapshot(api, "web")
    assert snap["name"] == "Web v2" and snap["settings"] == {"TPLPLUG_MS": "two"}
    assert snap["configs"] == {"modsec/extra.conf": "# two\n"}
    assert snap["method"] == "ui"


def test_replace_of_a_missing_id_creates_it(api):
    response = ROUTER.import_template(_package(), replace=True)
    assert response.status_code == 201
    assert _body(response)["replaced"] is False


def test_replace_never_touches_a_plugin_owned_template(api):
    _create_plugin_owned(api, "web")
    before = _snapshot(api, "web")
    response = ROUTER.import_template(_package(), replace=True)
    assert response.status_code == 409
    assert "managed by plugin tplplug" in _body(response)["message"]
    assert _snapshot(api, "web") == before


def test_a_name_collision_is_a_409_naming_the_other_template(api):
    assert ROUTER.import_template(_package("first", name="Shared name")).status_code == 201
    response = ROUTER.import_template(_package("second", name="Shared name"))
    assert response.status_code == 409
    assert "first" in _body(response)["message"]
    assert "second" not in api.get_templates()


# ── the ownership guards (G6 update, G7 delete) ─────────────────────────────────


def test_patch_refuses_a_plugin_owned_template(api):
    _create_plugin_owned(api)
    before = _snapshot(api, "owned")
    response = ROUTER.update_template("owned", ROUTER.TemplateUpdateRequest(name="Hijacked", settings={"TPLPLUG_MS": "x"}))
    assert response.status_code == 409
    assert _body(response)["message"] == "Template owned is managed by plugin tplplug and cannot be changed"
    assert _snapshot(api, "owned") == before


def test_patch_refuses_a_template_managed_by_another_method(api):
    assert (
        api.create_template("sched", name="From a URL", settings={"TPLPLUG_MS": "a"}, steps=[{"title": "S", "settings": ["TPLPLUG_MS"]}], method="scheduler")
        == ""
    )
    response = ROUTER.update_template("sched", ROUTER.TemplateUpdateRequest(name="Edited"))
    assert response.status_code == 409
    assert _body(response)["message"] == "Template sched is managed by scheduler and cannot be changed"
    assert _snapshot(api, "sched")["name"] == "From a URL"


def test_patch_still_updates_a_ui_template(api):
    assert ROUTER.import_template(_package()).status_code == 201
    response = ROUTER.update_template("web", ROUTER.TemplateUpdateRequest(name="Renamed"))
    assert response.status_code == 200
    assert _snapshot(api, "web")["name"] == "Renamed"


def test_delete_refuses_a_plugin_owned_template(api):
    _create_plugin_owned(api)
    response = ROUTER.delete_template("owned")
    assert response.status_code == 409
    assert _body(response)["message"] == "Template owned is managed by plugin tplplug and cannot be deleted"
    assert _snapshot(api, "owned") is not None


def test_delete_still_removes_a_ui_template(api):
    assert ROUTER.import_template(_package()).status_code == 201
    assert ROUTER.delete_template("web").status_code == 200
    assert _snapshot(api, "web") is None

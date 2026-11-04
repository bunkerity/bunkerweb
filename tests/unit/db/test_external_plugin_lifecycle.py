"""External manifests persist their assets without losing unrelated user settings."""

from copy import deepcopy
from io import BytesIO
import json
import tarfile

import pytest

import Database as database_module
from fixtures.seed import FIXED_DT, add_global_value, add_service_setting, make_external_plugin, seed_minimal, session
from model import Bw_cli_commands, Global_values, Jobs, Jobs_cache, Jobs_runs, Plugins, Services_settings, Settings

pytestmark = pytest.mark.multiengine


@pytest.fixture
def plugin_tree(db, tmp_path, monkeypatch):
    seed_minimal(db)
    monkeypatch.setattr(database_module, "sep", str(tmp_path))
    path = tmp_path / "etc/bunkerweb/plugins/extplugin"
    path.mkdir(parents=True)
    return path


def _manifest():
    plugin = make_external_plugin()
    plugin["settings"].update(
        {
            "EXT_CHOICE": {
                "id": "ext-choice",
                "context": "multisite",
                "default": "one",
                "help": "choice",
                "label": "Choice",
                "regex": "^.*$",
                "type": "select",
                "select": ["one", "two"],
            },
            "EXT_FLAGS": {
                "id": "ext-flags",
                "context": "multisite",
                "default": "a",
                "help": "flags",
                "label": "Flags",
                "regex": "^.*$",
                "type": "multiselect",
                "separator": ",",
                "multiselect": [{"id": "alpha", "label": "Alpha", "value": "a"}],
            },
            "EXT_FILE": {
                "id": "ext-file",
                "context": "multisite",
                "default": "",
                "help": "file",
                "label": "File",
                "regex": "^.*$",
                "type": "file",
                "accept": ".pem",
            },
        }
    )
    plugin["jobs"] = [{"name": "ext-job", "file": "refresh.py", "every": "hour", "reload": False, "async": False}]
    return plugin


def _write_assets(path):
    (path / "ui").mkdir()
    (path / "ui/template.html").write_text("<p>plugin page</p>")
    (path / "bwcli").mkdir()
    (path / "bwcli/show.py").write_text("print('status')\n")
    (path / "templates/profile/configs/server-http").mkdir(parents=True)
    (path / "templates/profile/configs/server-http/route.conf").write_text("set $profile safe;\n")
    (path / "templates/profile.json").write_text(
        json.dumps(
            {
                "name": "Profile",
                "settings": {"USE_REVERSE_PROXY": "yes"},
                "steps": [{"title": "Routing", "subtitle": "Upstream", "settings": ["USE_REVERSE_PROXY"], "configs": ["server-http/route.conf"]}],
                "configs": ["server-http/route.conf"],
            }
        )
    )


@pytest.mark.parametrize("per_plugin_commit", [True, False])
def test_manifest_roundtrips_settings_jobs_page_command_and_template(db, plugin_tree, per_plugin_commit):
    _write_assets(plugin_tree)
    plugin = _manifest() | {"page": True, "bwcli": {"show": "show.py", "missing": "absent.py"}}
    assert db.update_external_plugins([plugin], per_plugin_commit=per_plugin_commit) == ""

    saved = db.get_plugins(_type="external", with_data=True)
    assert len(saved) == 1
    saved = saved[0]
    assert (saved["id"], saved["data"], saved["checksum"]) == ("extplugin", b"fake-tar", "extsum")
    assert saved["settings"]["EXT_CHOICE"]["select"] == ["one", "two"]
    assert saved["settings"]["EXT_FLAGS"]["multiselect"] == [{"id": "alpha", "label": "Alpha", "value": "a"}]
    assert saved["settings"]["EXT_FLAGS"]["separator"] == ","
    assert saved["settings"]["EXT_FILE"]["accept"] == ".pem"
    assert saved["bwcli"] == {"show": "show.py"}
    assert saved["page"] is True
    with tarfile.open(fileobj=BytesIO(db.get_plugin_page("extplugin")), mode="r:gz") as archive:
        member = next(member for member in archive.getmembers() if member.name.endswith("template.html"))
        assert archive.extractfile(member).read() == b"<p>plugin page</p>"
    assert db.get_templates()["profile"]["configs"] == {"server_http/route.conf": "set $profile safe;\n"}
    assert db.get_template_settings("profile") == {"USE_REVERSE_PROXY": "yes"}
    with session(db) as s:
        job = s.query(Jobs).filter_by(name="ext-job").one()
        assert (job.file_name, job.every, job.reload, job.run_async) == ("refresh.py", "hour", False, False)
    metadata = db.get_metadata()
    assert metadata["external_plugins_changed"] is True
    assert metadata["reload_ui_plugins"] is True


def test_changed_manifest_updates_fields_settings_jobs_and_command(db, plugin_tree):
    _write_assets(plugin_tree)
    old = _manifest() | {"page": True, "bwcli": {"show": "show.py"}}
    assert db.update_external_plugins([deepcopy(old)]) == ""
    assert db.add_job_run("ext-job", False, FIXED_DT) == ""
    assert db.upsert_job_cache(None, "old.txt", b"old", job_name="ext-job") == ""

    new = deepcopy(old)
    new.update(name="New name", description="New description", stream="partial", version="2.0", checksum="newsum", data=b"new-tar", method="autoconf")
    new["settings"]["EXTPLUGIN_GLOBAL"].update(
        context="multisite", default="new", help="new help", label="New label", regex="^new$", type="multivalue", separator=";", multiple="items"
    )
    new["settings"]["EXT_FLAGS"]["multiselect"] = [{"id": "beta", "label": "Beta", "value": "b"}]
    new["jobs"][0].update(file="new.py", every="day", reload=True, **{"async": True})
    (plugin_tree / "bwcli/new.py").write_text("print('new')\n")
    new["bwcli"]["show"] = "new.py"
    (plugin_tree / "ui/template.html").write_text("<p>new page</p>")
    assert db.update_external_plugins([new]) == ""

    saved = db.get_plugins(_type="external", with_data=True)[0]
    assert (saved["name"], saved["description"], saved["stream"], saved["version"], saved["method"], saved["data"]) == (
        "New name",
        "New description",
        "partial",
        "2.0",
        "autoconf",
        b"new-tar",
    )
    setting = saved["settings"]["EXTPLUGIN_GLOBAL"]
    assert (
        setting["context"],
        setting["default"],
        setting["help"],
        setting["label"],
        setting["regex"],
        setting["type"],
        setting["separator"],
        setting["multiple"],
    ) == ("multisite", "new", "new help", "New label", "^new$", "multivalue", ";", "items")
    assert saved["settings"]["EXT_FLAGS"]["multiselect"] == [{"id": "beta", "label": "Beta", "value": "b"}]
    assert saved["bwcli"] == {"show": "new.py"}
    with session(db) as s:
        job = s.query(Jobs).filter_by(name="ext-job").one()
        assert (job.file_name, job.every, job.reload, job.run_async) == ("new.py", "day", True, True)
        assert s.query(Jobs_runs).filter_by(job_name="ext-job").count() == 0
        assert s.query(Jobs_cache).filter_by(job_name="ext-job").count() == 0


@pytest.mark.parametrize("checksum,kept", [("extsum", True), ("different", False)])
def test_missing_settings_preserve_user_values_only_for_identical_archive(db, plugin_tree, checksum, kept):
    assert db.update_external_plugins([make_external_plugin()]) == ""
    add_global_value(db, setting_id="EXTPLUGIN_GLOBAL", value="user-global")
    add_service_setting(db, service_id="app1.example.com", setting_id="EXTPLUGIN_MS", value="user-service")
    incoming = make_external_plugin(checksum=checksum)
    incoming["settings"] = {}
    assert db.update_external_plugins([incoming]) == ""
    with session(db) as s:
        assert bool(s.query(Settings).filter_by(id="EXTPLUGIN_GLOBAL").count()) is kept
        assert bool(s.query(Global_values).filter_by(setting_id="EXTPLUGIN_GLOBAL").count()) is kept
        assert bool(s.query(Services_settings).filter_by(setting_id="EXTPLUGIN_MS").count()) is kept


@pytest.mark.parametrize("plugin_type", ["external", "pro"])
def test_empty_inventory_preserves_plugin_settings_and_user_values(db, plugin_tree, plugin_type):
    assert db.update_external_plugins([make_external_plugin()], _type=plugin_type) == ""
    add_global_value(db, setting_id="EXTPLUGIN_GLOBAL", value="owned-by-user")
    assert db.update_external_plugins([], _type=plugin_type) == ""
    assert db.get_plugins(_type=plugin_type, with_data=True)[0]["data"] == b"fake-tar"
    with session(db) as s:
        assert s.query(Global_values).filter_by(setting_id="EXTPLUGIN_GLOBAL").one().value == "owned-by-user"


def test_explicit_metadata_clear_removes_code_but_keeps_settings(db, plugin_tree):
    _write_assets(plugin_tree)
    assert db.update_external_plugins([make_external_plugin() | {"page": True}]) == ""
    add_global_value(db, setting_id="EXTPLUGIN_GLOBAL", value="saved")
    assert db.update_external_plugins([], only_clear_metadata=True) == ""
    saved = db.get_plugins(_type="external", with_data=True)[0]
    assert saved["data"] is None and saved["checksum"] is None and saved["page"] is False
    assert "EXTPLUGIN_GLOBAL" in saved["settings"]
    with session(db) as s:
        assert s.query(Global_values).filter_by(setting_id="EXTPLUGIN_GLOBAL").one().value == "saved"


def test_nonempty_inventory_prunes_only_missing_unpreserved_plugins(db, plugin_tree):
    for name in ("retained", "preserved", "removed"):
        assert db.update_external_plugins([make_external_plugin(name)], delete_missing=False) == ""
    assert db.update_external_plugins([make_external_plugin("retained")], preserve_ids={"preserved"}) == ""
    assert {p["id"] for p in db.get_plugins(_type="external")} == {"retained", "preserved"}
    with session(db) as s:
        assert s.query(Settings).filter_by(plugin_id="removed").count() == 0


def test_method_mismatch_and_core_replacement_are_rejected(db, plugin_tree):
    assert db.update_external_plugins([make_external_plugin()]) == ""
    assert db.update_external_plugins([make_external_plugin(method="ui", version="2.0")]) == ""
    assert db.get_plugins(_type="external")[0]["version"] == "1.0"
    incoming = make_external_plugin("general", method="autoconf", version="9.0")
    assert db.update_external_plugins([incoming], delete_missing=False) == ""
    with session(db) as s:
        core = s.query(Plugins).filter_by(id="general").one()
        assert (core.type, core.version) == ("core", "1.0")


def test_removed_assets_and_jobs_disappear_on_update(db, plugin_tree):
    _write_assets(plugin_tree)
    assert db.update_external_plugins([_manifest() | {"page": True, "bwcli": {"show": "show.py"}}]) == ""
    for path in (plugin_tree / "ui").iterdir():
        path.unlink()
    (plugin_tree / "ui").rmdir()
    (plugin_tree / "templates/profile.json").unlink()
    incoming = _manifest()
    incoming["jobs"] = []
    assert db.update_external_plugins([incoming]) == ""
    assert db.get_plugin_page("extplugin") is None
    assert "profile" not in db.get_templates()
    assert "bwcli" not in db.get_plugins(_type="external")[0]
    with session(db) as s:
        assert s.query(Jobs).filter_by(name="ext-job").count() == 0
        assert s.query(Bw_cli_commands).filter_by(plugin_id="extplugin").count() == 0


def test_readonly_inventory_update_does_not_write(db, plugin_tree):
    db.readonly = True
    assert db.update_external_plugins([make_external_plugin()]) == "The database is read-only, the changes will not be saved"
    assert db.get_plugins(_type="external") == []


def test_changing_text_setting_to_select_persists_new_choices(db, plugin_tree):
    assert db.update_external_plugins([make_external_plugin()]) == ""
    incoming = make_external_plugin(checksum="new-archive")
    incoming["settings"]["EXTPLUGIN_MS"].update(type="select", default="new", select=["new", "other"])
    assert db.update_external_plugins([incoming]) == ""
    assert db.get_plugins(_type="external")[0]["settings"]["EXTPLUGIN_MS"]["select"] == ["new", "other"]


@pytest.mark.parametrize("removed", ["settings", "configs"])
def test_template_update_drops_removed_manifest_entries(db, plugin_tree, removed):
    _write_assets(plugin_tree)
    assert db.update_external_plugins([_manifest()]) == ""
    path = plugin_tree / "templates/profile.json"
    template = json.loads(path.read_text())
    template[removed] = {} if removed == "settings" else []
    template["steps"][0][removed] = []
    path.write_text(json.dumps(template))
    assert db.update_external_plugins([_manifest()]) == ""
    if removed == "settings":
        assert db.get_template_settings("profile") == {}
    else:
        assert db.get_templates()["profile"]["configs"] == {}


def test_updating_one_template_step_leaves_other_templates_unchanged(db, plugin_tree):
    _write_assets(plugin_tree)
    assert db.update_external_plugins([_manifest()]) == ""
    assert (
        db.create_template("other", name="Other", settings={"USE_REVERSE_PROXY": "no"}, steps=[{"title": "Other step", "settings": ["USE_REVERSE_PROXY"]}])
        == ""
    )
    path = plugin_tree / "templates/profile.json"
    template = json.loads(path.read_text())
    template["steps"][0]["title"] = "Renamed routing"
    path.write_text(json.dumps(template))
    assert db.update_external_plugins([_manifest()]) == ""
    assert db.get_template_details("profile")["steps"][0]["title"] == "Renamed routing"
    assert db.get_template_details("other")["steps"][0]["title"] == "Other step"

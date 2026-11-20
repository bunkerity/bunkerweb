"""``update_external_plugins`` and ``delete_plugin``: the refusals that protect user data, and the cascades.

A guard test proves the refusal (rows and user values still there after the call, warning logged), next to the
control that shows the same call deleting when the guard does not apply.
"""

import json
import logging
from copy import deepcopy

import pytest
from sqlalchemy import func, select

import Database as database_module
from fixtures.seed import (
    FIXED_DT,
    add_global_value,
    add_service_setting,
    make_external_plugin,
    seed_minimal,
    session,
)
from model import (
    Bw_cli_commands,
    Global_values,
    Jobs,
    Jobs_cache,
    Jobs_runs,
    Multiselects,
    Plugin_pages,
    Plugins,
    Selects,
    Services_settings,
    Settings,
    Template_custom_configs,
    Template_settings,
    Template_steps,
    Templates,
)

pytestmark = pytest.mark.multiengine

READONLY = "The database is read-only, the changes will not be saved"


def _count(db, model, **filters):
    with session(db) as s:
        return s.scalar(select(func.count()).select_from(model).filter_by(**filters))


def _plugin_ids(db, kind):
    with session(db) as s:
        return sorted(row.id for row in s.query(Plugins).filter_by(type=kind))


@pytest.fixture
def tree(db, tmp_path, monkeypatch):
    seed_minimal(db)
    monkeypatch.setattr(database_module, "sep", str(tmp_path))
    return tmp_path


@pytest.fixture
def logs(db, caplog):
    db.logger.propagate = True
    caplog.set_level(logging.DEBUG, logger=db.logger.name)
    return caplog


def _messages(logs, level=None):
    return [r.getMessage() for r in logs.records if level is None or r.levelno == level]


def _plugin(plugin_id="extplugin", **kwargs):
    return make_external_plugin(plugin_id, **kwargs)


def _dir(tree, plugin_id="extplugin", kind="external"):
    path = tree / "etc/bunkerweb" / ("plugins" if kind == "external" else "pro/plugins") / plugin_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clear_flags(db):
    assert db.checked_changes(["config", "custom_configs", "external_plugins", "pro_plugins", "instances", "ui_plugins"], value=False) == ""


def _user_values(db, plugin_id):
    add_global_value(db, setting_id=f"{plugin_id.upper()}_GLOBAL", value="user-set", method="ui")


class TestCascadeOnMissingPlugins:
    def test_a_plugin_dropped_from_a_non_empty_list_is_deleted_with_everything_it_owns(self, db, tree):
        path = _dir(tree, "gone")
        (path / "templates/profile/configs/server-http").mkdir(parents=True)
        (path / "templates/profile/configs/server-http/route.conf").write_text("set $x 1;\n")
        (path / "templates/profile.json").write_text(
            json.dumps(
                {
                    "name": "P",
                    "settings": {"USE_REVERSE_PROXY": "yes"},
                    "steps": [{"title": "t", "subtitle": "s", "settings": ["USE_REVERSE_PROXY"], "configs": ["server-http/route.conf"]}],
                    "configs": ["server-http/route.conf"],
                }
            )
        )
        (path / "bwcli").mkdir()
        (path / "bwcli/show.py").write_text("print(1)\n")
        (path / "ui").mkdir()
        (path / "ui/template.html").write_text("<p>x</p>")
        gone = _plugin("gone") | {"page": True, "bwcli": {"show": "show.py"}}
        gone["jobs"] = [{"name": "gone-job", "file": "g.py", "every": "hour"}]
        assert db.update_external_plugins([gone, _plugin("kept")]) == ""
        _user_values(db, "gone")
        add_service_setting(db, service_id="app1.example.com", setting_id="GONE_GLOBAL", value="svc", method="ui")
        assert db.add_job_run("gone-job", True, FIXED_DT) == ""
        assert db.upsert_job_cache(None, "c.txt", b"c", job_name="gone-job") == ""
        assert _count(db, Templates, plugin_id="gone") == 1

        assert db.update_external_plugins([_plugin("kept")]) == ""

        assert _plugin_ids(db, "external") == ["kept"]
        for model, filters in (
            (Jobs, {"plugin_id": "gone"}),
            (Jobs_runs, {"job_name": "gone-job"}),
            (Jobs_cache, {"job_name": "gone-job"}),
            (Plugin_pages, {"plugin_id": "gone"}),
            (Bw_cli_commands, {"plugin_id": "gone"}),
            (Templates, {"plugin_id": "gone"}),
            (Template_steps, {"template_id": "profile"}),
            (Template_settings, {"template_id": "profile"}),
            (Template_custom_configs, {"template_id": "profile"}),
            (Settings, {"plugin_id": "gone"}),
            (Global_values, {"setting_id": "GONE_GLOBAL"}),
            (Services_settings, {"setting_id": "GONE_GLOBAL"}),
        ):
            assert _count(db, model, **filters) == 0, model.__name__
        assert _count(db, Settings, plugin_id="kept") == 2

    def test_an_empty_incoming_list_is_refused_and_the_plugins_and_values_stay(self, db, tree, logs):
        assert db.update_external_plugins([_plugin("a"), _plugin("b")]) == ""
        _user_values(db, "a")
        assert db.update_external_plugins([]) == ""
        assert _plugin_ids(db, "external") == ["a", "b"]
        assert _count(db, Global_values, setting_id="A_GLOBAL", value="user-set") == 1
        assert any("Refusing to cascade-delete 2 external plugin(s)" in m and "incoming plugins list is empty" in m for m in _messages(logs))

    def test_the_explicit_wipe_path_keeps_rows_but_drops_payload_and_page(self, db, tree):
        _dir(tree, "a", "pro")
        (_dir(tree, "a", "pro") / "ui").mkdir()
        (_dir(tree, "a", "pro") / "ui/template.html").write_text("<p>x</p>")
        assert db.update_external_plugins([_plugin("a") | {"page": True}], _type="pro") == ""
        _user_values(db, "a")
        assert _count(db, Plugin_pages, plugin_id="a") == 1
        assert db.update_external_plugins([], _type="pro", only_clear_metadata=True) == ""
        with session(db) as s:
            row = s.get(Plugins, "a")
            assert row.data is None and row.checksum is None
        assert _count(db, Plugin_pages, plugin_id="a") == 0
        assert _count(db, Settings, plugin_id="a") == 2 and _count(db, Global_values, setting_id="A_GLOBAL") == 1

    def test_the_explicit_wipe_path_on_external_plugins_deletes_nothing_it_was_not_asked_to(self, db, tree):
        assert db.update_external_plugins([_plugin("a"), _plugin("b")]) == ""
        assert db.update_external_plugins([_plugin("a")], only_clear_metadata=True) == ""
        assert _plugin_ids(db, "external") == ["a", "b"]
        with session(db) as s:
            assert s.get(Plugins, "b").checksum is None and s.get(Plugins, "a").checksum == "extsum"

    def test_pro_plugins_absent_from_the_incoming_list_are_never_cascade_deleted(self, db, tree, logs):
        assert db.update_external_plugins([_plugin("a"), _plugin("b")], _type="pro") == ""
        _user_values(db, "b")
        assert db.update_external_plugins([_plugin("a")], _type="pro") == ""
        assert _plugin_ids(db, "pro") == ["a", "b"]
        assert _count(db, Global_values, setting_id="B_GLOBAL", value="user-set") == 1
        assert any("Refusing to cascade-delete 1 pro plugin(s)" in m and "missing=['b']" in m for m in _messages(logs))

    def test_preserved_ids_and_delete_missing_false_both_keep_a_missing_plugin(self, db, tree):
        assert db.update_external_plugins([_plugin("a"), _plugin("b"), _plugin("c")]) == ""
        assert db.update_external_plugins([_plugin("a")], preserve_ids={"b", "c"}) == ""
        assert _plugin_ids(db, "external") == ["a", "b", "c"]
        assert db.update_external_plugins([_plugin("a")], delete_missing=False) == ""
        assert _plugin_ids(db, "external") == ["a", "b", "c"]
        assert db.update_external_plugins([_plugin("a")], preserve_ids={"b"}) == ""
        assert _plugin_ids(db, "external") == ["a", "b"]

    def test_plugins_of_another_type_are_outside_the_cascade(self, db, tree):
        assert db.update_external_plugins([_plugin("ext")]) == ""
        assert db.update_external_plugins([_plugin("pro1")], _type="pro") == ""
        assert db.update_external_plugins([_plugin("ext2")]) == ""
        assert _plugin_ids(db, "external") == ["ext2"] and _plugin_ids(db, "pro") == ["pro1"]
        assert _count(db, Plugins, id="general") == 1

    def test_read_only_mode_refuses_before_any_write(self, db, tree):
        assert db.update_external_plugins([_plugin("a")]) == ""
        db.readonly = True
        assert db.update_external_plugins([_plugin("b")]) == READONLY
        assert _plugin_ids(db, "external") == ["a"]

    def test_a_commit_failure_is_returned_and_rolled_back(self, db, tree, monkeypatch):
        assert db.update_external_plugins([_plugin("a"), _plugin("b")]) == ""
        original = db._db_session

        class FailingCommit:
            def __init__(self):
                self.ctx = original()

            def __enter__(self):
                session_ = self.ctx.__enter__()
                monkeypatch.setattr(session_, "commit", lambda: (_ for _ in ()).throw(RuntimeError("disk full")))
                return session_

            def __exit__(self, *exc):
                return self.ctx.__exit__(*exc)

        monkeypatch.setattr(db, "_db_session", FailingCommit)
        assert db.update_external_plugins([_plugin("a")]) == "disk full"
        monkeypatch.undo()
        monkeypatch.setattr(database_module, "sep", str(tree))
        assert _plugin_ids(db, "external") == ["a", "b"]


class TestExistingPluginGuards:
    def test_a_plugin_owned_by_another_method_is_left_alone(self, db, tree, logs):
        assert db.update_external_plugins([_plugin("a", method="ui")]) == ""
        assert db.update_external_plugins([_plugin("a", method="manual", version="9.9")]) == ""
        with session(db) as s:
            assert s.get(Plugins, "a").version == "1.0" and s.get(Plugins, "a").method == "ui"
        assert any('Plugin "a" already exists, but the method is different, skipping update' in m for m in _messages(logs))

    def test_an_external_manifest_can_not_overwrite_a_core_plugin(self, db, tree, logs):
        manifest = _plugin("general", method="manual", version="66.6") | {"name": "Hijacked"}
        assert db.update_external_plugins([manifest, _plugin("ok")]) == ""
        with session(db) as s:
            general = s.get(Plugins, "general")
            assert (general.name, general.version, general.type) == ("General", "1.0", "core")
        assert any("is not external, skipping update" in m for m in _messages(logs))

    def test_an_identical_checksum_with_fewer_settings_preserves_the_stored_settings_and_values(self, db, tree, logs):
        assert db.update_external_plugins([_plugin("a")]) == ""
        _user_values(db, "a")
        shrunk = _plugin("a")
        shrunk["settings"].pop("A_GLOBAL")
        assert db.update_external_plugins([shrunk, _plugin("b")]) == ""
        assert _count(db, Settings, plugin_id="a") == 2 and _count(db, Global_values, setting_id="A_GLOBAL") == 1
        assert any("re-ingested with an identical checksum" in m for m in _messages(logs, logging.INFO))

    def test_a_new_checksum_with_fewer_settings_really_removes_them_and_their_values(self, db, tree):
        assert db.update_external_plugins([_plugin("a")]) == ""
        _user_values(db, "a")
        shrunk = _plugin("a", checksum="other-sum", data=b"other")
        shrunk["settings"].pop("A_GLOBAL")
        assert db.update_external_plugins([shrunk, _plugin("b")]) == ""
        assert _count(db, Settings, plugin_id="a") == 1 and _count(db, Global_values, setting_id="A_GLOBAL") == 0
        assert db.get_plugins(_type="external", with_data=True)[0]["data"] == b"other"

    def test_the_stored_payload_follows_the_checksum_only(self, db, tree):
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert db.update_external_plugins([_plugin("a", data=b"changed-bytes")]) == ""
        assert db.get_plugins(_type="external", with_data=True)[0]["data"] == b"fake-tar"
        assert db.update_external_plugins([_plugin("a", data=b"changed-bytes", checksum="new")]) == ""
        assert db.get_plugins(_type="external", with_data=True)[0]["data"] == b"changed-bytes"


class TestSettingChangesOnAnInstalledPlugin:
    def _installed(self, db):
        assert db.update_external_plugins([_plugin("a")]) == ""

    def test_a_new_setting_with_select_and_multiselect_options_is_added(self, db, tree):
        self._installed(db)
        update = _plugin("a")
        update["settings"]["A_CHOICE"] = {
            "id": "a-choice",
            "context": "multisite",
            "default": "one",
            "help": "h",
            "label": "L",
            "regex": "^.*$",
            "type": "select",
            "select": ["one", "two"],
        }
        update["settings"]["A_FLAGS"] = {
            "id": "a-flags",
            "context": "multisite",
            "default": "x",
            "help": "h",
            "label": "L",
            "regex": "^.*$",
            "type": "multiselect",
            "multiselect": [{"id": "x", "label": "X", "value": "x"}, "not-a-dict"],
        }
        assert db.update_external_plugins([update]) == ""
        saved = db.get_plugins(_type="external")[0]["settings"]
        assert saved["A_CHOICE"]["select"] == ["one", "two"]
        assert saved["A_FLAGS"]["multiselect"] == [{"id": "x", "label": "X", "value": "x"}]
        assert _count(db, Selects, setting_id="A_CHOICE") == 2 and _count(db, Multiselects, setting_id="A_FLAGS") == 1

    def test_name_accept_and_order_changes_are_stored(self, db, tree):
        self._installed(db)
        update = _plugin("a")
        update["settings"]["A_GLOBAL"]["id"] = "renamed-global"
        update["settings"]["A_GLOBAL"]["accept"] = ".pem"
        update["settings"] = {"A_MS": update["settings"]["A_MS"], "A_GLOBAL": update["settings"]["A_GLOBAL"]}
        assert db.update_external_plugins([update]) == ""
        with session(db) as s:
            row = s.get(Settings, "A_GLOBAL")
            assert (row.name, row.accept, row.order) == ("renamed-global", ".pem", 1)
            assert s.get(Settings, "A_MS").order == 0

    def test_a_job_added_later_is_created_and_a_removed_one_goes_with_its_runs_and_cache(self, db, tree):
        self._installed(db)
        with_job = _plugin("a")
        with_job["jobs"] = [{"name": "a-job", "file": "a.py", "every": "hour"}]
        assert db.update_external_plugins([with_job]) == ""
        assert _count(db, Jobs, name="a-job") == 1
        assert db.add_job_run("a-job", True, FIXED_DT) == ""
        assert db.upsert_job_cache(None, "c.txt", b"c", job_name="a-job") == ""
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert (_count(db, Jobs, name="a-job"), _count(db, Jobs_runs, job_name="a-job"), _count(db, Jobs_cache, job_name="a-job")) == (0, 0, 0)

    def test_a_changed_job_definition_resets_its_runs_and_cache(self, db, tree):
        with_job = _plugin("a")
        with_job["jobs"] = [{"name": "a-job", "file": "a.py", "every": "hour"}]
        assert db.update_external_plugins([with_job]) == ""
        assert db.add_job_run("a-job", True, FIXED_DT) == ""
        changed = _plugin("a")
        changed["jobs"] = [{"name": "a-job", "file": "a.py", "every": "day"}]
        assert db.update_external_plugins([changed]) == ""
        assert _count(db, Jobs_runs, job_name="a-job") == 0
        with session(db) as s:
            assert s.get(Jobs, "a-job").every == "day"


class TestPluginDirectoryAssets:
    def test_an_unreadable_ui_directory_skips_the_rest_of_the_plugin_with_a_warning(self, db, tree, logs, monkeypatch):
        (_dir(tree, "a") / "ui").mkdir()
        (_dir(tree, "a") / "ui/template.html").write_text("x")

        def broken(_path):
            raise OSError("unreadable")

        monkeypatch.setattr(database_module, "create_plugin_tar_gz", broken)
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert db.update_external_plugins([_plugin("a", checksum="v2")]) == ""
        assert _count(db, Plugin_pages, plugin_id="a") == 0
        assert any("could not be archived: unreadable" in m for m in _messages(logs, logging.WARNING))

    def test_the_page_follows_the_ui_directory_and_disappears_with_it(self, db, tree):
        ui = _dir(tree, "a") / "ui"
        ui.mkdir()
        (ui / "template.html").write_text("v1")
        assert db.update_external_plugins([_plugin("a") | {"page": True}]) == ""
        first = db.get_plugin_page("a")
        (ui / "template.html").write_text("v2 changed")
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert db.get_plugin_page("a") != first
        (ui / "template.html").unlink()
        ui.rmdir()
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Plugin_pages, plugin_id="a") == 0

    def test_a_command_whose_file_is_missing_is_skipped_and_one_added_later_is_stored(self, db, tree, logs):
        path = _dir(tree, "a")
        (path / "bwcli").mkdir()
        (path / "bwcli/ok.py").write_text("print(1)\n")
        assert db.update_external_plugins([_plugin("a") | {"bwcli": {"ok": "ok.py", "ghost": "ghost.py"}}]) == ""
        assert sorted(r for r in db.get_plugins(_type="external")[0]["bwcli"]) == ["ok"]
        (path / "bwcli/second.py").write_text("print(2)\n")
        assert db.update_external_plugins([_plugin("a") | {"bwcli": {"ok": "ok.py", "second": "second.py", "ghost2": "g.py"}}]) == ""
        assert sorted(db.get_plugins(_type="external")[0]["bwcli"]) == ["ok", "second"]
        assert any('Command "ghost"' in m for m in _messages(logs, logging.WARNING))

    def test_a_command_repointed_to_a_missing_file_is_removed(self, db, tree):
        path = _dir(tree, "a")
        (path / "bwcli").mkdir()
        (path / "bwcli/ok.py").write_text("print(1)\n")
        assert db.update_external_plugins([_plugin("a") | {"bwcli": {"ok": "ok.py"}}]) == ""
        assert db.update_external_plugins([_plugin("a") | {"bwcli": {"ok": "gone.py"}}]) == ""
        assert _count(db, Bw_cli_commands, plugin_id="a") == 0

    def test_a_non_mapping_command_list_is_ignored(self, db, tree):
        assert db.update_external_plugins([_plugin("a") | {"bwcli": ["not", "a", "dict"]}]) == ""
        assert _count(db, Bw_cli_commands, plugin_id="a") == 0


def _write_template(tree, plugin_id, name, body, configs=None):
    path = _dir(tree, plugin_id)
    (path / "templates").mkdir(exist_ok=True)
    (path / "templates" / f"{name}.json").write_text(body if isinstance(body, str) else json.dumps(body))
    for rel, content in (configs or {}).items():
        target = path / "templates" / name / "configs" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return path


GOOD = {
    "name": "Good",
    "settings": {"USE_REVERSE_PROXY": "yes"},
    "steps": [{"title": "one", "subtitle": "first", "settings": ["USE_REVERSE_PROXY"], "configs": ["server-http/a.conf"]}],
    "configs": ["server-http/a.conf"],
}


def _bad_template():
    return {
        "name": "Bad",
        "settings": {"USE_TEMPLATE": "x", "NOT_A_SETTING": "x", "USE_REVERSE_PROXY": "maybe", "SECURITY_MODE": "block", "SERVER_NAME": "x"},
        "steps": [
            {"title": "one", "subtitle": "s", "settings": ["USE_TEMPLATE", "NOT_A_SETTING", "USE_REVERSE_PROXY"], "configs": ["server-http/in-step.conf"]}
        ],
        "configs": ["nonsense", "http/a.conf", "server-http/missing.conf", "server-http/orphan.conf", "server-http/in-step.conf"],
    }


BAD_CONFIGS = {"server-http/orphan.conf": "x", "server-http/in-step.conf": "ok;"}


class TestTemplatesFromTheManifestDirectory:
    def test_a_fresh_install_keeps_only_the_valid_parts_of_a_bad_template(self, db, tree, logs):
        _write_template(tree, "a", "bad", _bad_template(), BAD_CONFIGS)
        _write_template(tree, "a", "broken", "{ not json")
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Templates, plugin_id="a") == 1
        assert db.get_template_settings("bad") == {}
        assert list(db.get_templates()["bad"]["configs"]) == ["server_http/in-step.conf"]
        text = "\n".join(_messages(logs, logging.ERROR))
        assert "is not a valid JSON file" in text
        for needle in (
            "restricted",
            "does not exist",
            "not a valid template setting",
            "doesn't belong to a step",
            "is invalid",
            "not a valid type",
            "does not exist, skipping",
        ):
            assert needle in text or needle == "restricted" and "restricted" in text, needle

    def test_an_update_drops_template_entries_that_became_invalid_and_keeps_the_valid_ones(self, db, tree, logs):
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert db.get_template_settings("t") == {"USE_REVERSE_PROXY": "yes"}
        bad = _bad_template()
        bad["settings"]["USE_REVERSE_PROXY"] = "yes"
        _write_template(tree, "a", "t", bad, BAD_CONFIGS)
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert db.get_template_settings("t") == {"USE_REVERSE_PROXY": "yes"}
        assert list(db.get_templates()["t"]["configs"]) == ["server_http/in-step.conf"]
        text = "\n".join(_messages(logs, logging.ERROR))
        for needle in (
            "is restricted, skipping it",
            "does not exist, skipping it",
            "is invalid, skipping it",
            "is not a valid type",
            "doesn't belong to a step",
        ):
            assert needle in text, needle

    def test_an_invalid_value_is_removed_from_an_already_stored_template(self, db, tree):
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        _write_template(tree, "a", "t", GOOD | {"settings": {"USE_REVERSE_PROXY": "maybe"}}, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert db.get_template_settings("t") == {}

    def test_changed_step_text_setting_default_and_config_content_are_stored(self, db, tree):
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        changed = deepcopy(GOOD)
        changed["steps"][0].update(title="two", subtitle="second")
        changed["settings"]["USE_REVERSE_PROXY"] = "no"
        _write_template(tree, "a", "t", changed, {"server-http/a.conf": "v2;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        details = db.get_template_details("t")
        assert (details["steps"][0]["title"], details["steps"][0]["subtitle"]) == ("two", "second")
        assert db.get_template_settings("t") == {"USE_REVERSE_PROXY": "no"}
        assert db.get_templates()["t"]["configs"] == {"server_http/a.conf": "v2;"}

    def test_a_removed_step_takes_its_settings_and_configs_along(self, db, tree):
        two_steps = deepcopy(GOOD)
        two_steps["steps"].append({"title": "extra", "subtitle": "s", "settings": ["SECURITY_MODE"], "configs": []})
        two_steps["settings"]["SECURITY_MODE"] = "detect"
        _write_template(tree, "a", "t", two_steps, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Template_steps, template_id="t") == 2 and _count(db, Template_settings, template_id="t") == 2
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Template_steps, template_id="t") == 1 and _count(db, Template_settings, template_id="t") == 1

    def test_a_template_added_later_is_stored_and_a_removed_file_removes_the_template(self, db, tree):
        _write_template(tree, "a", "t1", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        _write_template(tree, "a", "t2", GOOD | {"name": "Good two"}, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Templates, plugin_id="a") == 2
        (tree / "etc/bunkerweb/plugins/a/templates/t1.json").unlink()
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Templates, plugin_id="a", id="t2") == 1 and _count(db, Templates, plugin_id="a", id="t1") == 0
        assert _count(db, Template_custom_configs, template_id="t1") == 0

    def test_a_vanished_templates_directory_removes_every_stored_template(self, db, tree, logs):
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        import shutil

        shutil.rmtree(tree / "etc/bunkerweb/plugins/a/templates")
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Templates, plugin_id="a") == 0 and _count(db, Template_steps, template_id="t") == 0
        assert any("templates directory does not exist, removing all templates" in m for m in _messages(logs, logging.WARNING))

    def test_a_template_config_removed_from_the_manifest_is_dropped(self, db, tree):
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        _write_template(tree, "a", "t", GOOD | {"configs": []}, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([_plugin("a")]) == ""
        assert _count(db, Template_custom_configs, template_id="t") == 0


class TestDuplicateInstalls:
    def test_a_setting_that_already_exists_under_another_plugin_is_not_added_twice(self, db, tree, logs):
        assert db.update_external_plugins([_plugin("a")]) == ""
        clash = _plugin("b")
        clash["settings"] = {"A_GLOBAL": clash["settings"]["B_GLOBAL"]}
        assert db.update_external_plugins([_plugin("a"), clash]) == ""
        assert _count(db, Settings, plugin_id="b") == 0 and _count(db, Settings, id="A_GLOBAL") == 1
        assert "A setting with id A_GLOBAL already exists" in "\n".join(_messages(logs, logging.WARNING))


class TestDeletePlugin:
    def test_deleting_a_ui_plugin_removes_everything_it_owns_and_flags_the_external_change(self, db, tree):
        with_everything = _plugin("a", method="ui")
        with_everything["jobs"] = [{"name": "a-job", "file": "a.py", "every": "hour"}]
        _write_template(tree, "a", "t", GOOD, {"server-http/a.conf": "v1;"})
        assert db.update_external_plugins([with_everything]) == ""
        _clear_flags(db)
        assert db.add_job_run("a-job", True, FIXED_DT) == ""
        assert db.upsert_job_cache(None, "c.txt", b"c", job_name="a-job") == ""
        _user_values(db, "a")

        assert db.delete_plugin("a", "ui") == ""

        for model, filters in (
            (Plugins, {"id": "a"}),
            (Settings, {"plugin_id": "a"}),
            (Global_values, {"setting_id": "A_GLOBAL"}),
            (Jobs, {"plugin_id": "a"}),
            (Jobs_runs, {"job_name": "a-job"}),
            (Jobs_cache, {"job_name": "a-job"}),
            (Templates, {"plugin_id": "a"}),
            (Template_steps, {"template_id": "t"}),
        ):
            assert _count(db, model, **filters) == 0, model.__name__
        meta = db.get_metadata()
        assert meta["external_plugins_changed"] is True and meta["reload_ui_plugins"] is True and meta["last_external_plugins_change"] is not None
        assert meta["pro_plugins_changed"] is False

    # methods_enum has no "pro" value: a pro plugin is stored with method "manual", so the flag follows the plugin's type.
    def test_deleting_a_pro_plugin_flags_the_pro_change(self, db, tree):
        assert db.update_external_plugins([_plugin("p")], _type="pro") == ""
        _clear_flags(db)
        assert db.delete_plugin("p", "manual") == ""
        assert db.get_metadata()["pro_plugins_changed"] is True

    def test_a_manual_plugin_deletion_raises_no_change_flag(self, db, tree):
        assert db.update_external_plugins([_plugin("a")]) == ""
        _clear_flags(db)
        assert db.delete_plugin("a", "manual") == ""
        meta = db.get_metadata()
        assert (meta["external_plugins_changed"], meta["pro_plugins_changed"], meta["reload_ui_plugins"]) == (False, False, False)

    def test_changes_false_leaves_the_flags_down(self, db, tree):
        assert db.update_external_plugins([_plugin("a", method="ui")]) == ""
        _clear_flags(db)
        assert db.delete_plugin("a", "ui", changes=False) == ""
        assert db.get_metadata()["external_plugins_changed"] is False

    def test_a_wrong_method_is_refused_and_nothing_is_deleted(self, db, tree):
        assert db.update_external_plugins([_plugin("a")]) == ""
        _user_values(db, "a")
        assert db.delete_plugin("a", "ui") == "Plugin with id a and method ui not found"
        assert _count(db, Plugins, id="a") == 1 and _count(db, Global_values, setting_id="A_GLOBAL") == 1

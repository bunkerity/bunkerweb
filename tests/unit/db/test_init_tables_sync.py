"""``init_tables`` syncing the core plugins' settings, jobs, pages, commands and templates into the database.

The shipped plugin tree is read from absolute paths (``/usr/share/bunkerweb/core/<id>``), so these tests redirect
every ``Path("/", ...)`` the module builds into a temporary root. Rows are asserted before and after each run; the
boolean ``init_tables`` returns means "changes were applied".
"""

import json
import logging
import shutil
from copy import deepcopy
from pathlib import Path as RealPath

import pytest
from sqlalchemy import func, select

import Database as database_module
from fixtures.seed import FIXED_DT, add_global_value, add_service, add_service_setting, make_core_plugin, session
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

pytestmark = [pytest.mark.multiengine, pytest.mark.slow]


def _count(db, model, **filters):
    with session(db) as s:
        return s.scalar(select(func.count()).select_from(model).filter_by(**filters))


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A temporary filesystem root standing in for ``/``."""

    def redirect(*parts):
        if parts and str(parts[0]) == "/":
            return RealPath(tmp_path, *parts[1:])
        return RealPath(*parts)

    monkeypatch.setattr(database_module, "Path", redirect)
    return tmp_path


@pytest.fixture
def logs(db, caplog):
    db.logger.propagate = True
    caplog.set_level(logging.DEBUG, logger=db.logger.name)
    return caplog


def _messages(logs, level=None):
    return [r.getMessage() for r in logs.records if level is None or r.levelno == level]


def _core(root, plugin_id):
    path = root / "usr/share/bunkerweb/core" / plugin_id
    path.mkdir(parents=True, exist_ok=True)
    return path


_GENERAL_SOURCE = {
    "MULTISITE": {"id": "multisite", "context": "global", "default": "no", "help": "h", "label": "M", "regex": "^(yes|no)$", "type": "check"},
    "USE_REVERSE_PROXY": {
        "id": "use-reverse-proxy",
        "context": "multisite",
        "default": "no",
        "help": "h",
        "label": "R",
        "regex": "^(yes|no)$",
        "type": "check",
    },
    "SERVER_NAME": {"id": "server-name", "context": "multisite", "default": "", "help": "h", "label": "S", "regex": "^.*$", "type": "text"},
}


def _general():
    # init_tables rewrites the nested setting dicts it is given, so every call gets a fresh copy
    return deepcopy(_GENERAL_SOURCE)


def _alpha(**kwargs):
    return make_core_plugin("alpha", **kwargs)


def _write_template(root, plugin_id, name, body, configs=None):
    path = _core(root, plugin_id)
    (path / "templates").mkdir(exist_ok=True)
    (path / "templates" / f"{name}.json").write_text(body if isinstance(body, str) else json.dumps(body))
    for rel, content in (configs or {}).items():
        target = path / "templates" / name / "configs" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


TEMPLATE = {
    "name": "Alpha template",
    "settings": {"USE_REVERSE_PROXY": "yes", "ALPHA_MS": "tuned"},
    "steps": [{"title": "One", "subtitle": "first", "settings": ["USE_REVERSE_PROXY", "ALPHA_MS"], "configs": ["server-http/a.conf"]}],
    "configs": ["server-http/a.conf"],
}


class TestPagesCommandsAndTemplates:
    def _install(self, db, root):
        ui = _core(root, "alpha") / "ui"
        ui.mkdir()
        (ui / "template.html").write_text("<p>alpha</p>")
        _write_template(root, "alpha", "tpl", TEMPLATE, {"server-http/a.conf": "set $a 1;\n"})
        assert db.init_tables([_general(), _alpha()]) == (True, "")

    def test_a_plugin_directory_yields_its_page_and_its_templates(self, db, root):
        self._install(db, root)
        assert db.get_plugin_page("alpha") is not None
        assert next(p for p in db.get_plugins() if p["id"] == "alpha")["page"] is True
        details = db.get_template_details("tpl")
        assert (details["name"], details["plugin_id"], details["method"]) == ("Alpha template", "alpha", "manual")
        assert [(s["title"], s["subtitle"]) for s in details["steps"]] == [("One", "first")]
        assert [(s["key"], s["default"]) for s in details["settings"]] == [("USE_REVERSE_PROXY", "yes"), ("ALPHA_MS", "tuned")]
        assert [(c["key"], c["data"]) for c in details["configs"]] == [("server_http/a.conf", "set $a 1;\n")]

    def test_a_second_run_with_nothing_changed_applies_nothing(self, db, root):
        self._install(db, root)
        assert db.init_tables([_general(), _alpha()]) == (False, "")

    def test_changed_files_are_applied_in_place(self, db, root):
        self._install(db, root)
        page_before = db.get_plugin_page("alpha")
        (root / "usr/share/bunkerweb/core/alpha/ui/template.html").write_text("<p>alpha two</p>")
        changed = json.loads(json.dumps(TEMPLATE))
        changed["name"] = "Alpha template"
        changed["steps"][0].update(title="Two", subtitle="second")
        changed["settings"]["ALPHA_MS"] = "adjusted"
        _write_template(root, "alpha", "tpl", changed, {"server-http/a.conf": "set $a 2;\n"})
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        assert db.get_plugin_page("alpha") != page_before
        details = db.get_template_details("tpl")
        assert (details["steps"][0]["title"], details["steps"][0]["subtitle"]) == ("Two", "second")
        assert dict((s["key"], s["default"]) for s in details["settings"])["ALPHA_MS"] == "adjusted"
        assert details["configs"][0]["data"] == "set $a 2;\n"

    def test_removed_files_remove_the_page_and_the_templates(self, db, root):
        self._install(db, root)
        shutil.rmtree(root / "usr/share/bunkerweb/core/alpha/ui")
        shutil.rmtree(root / "usr/share/bunkerweb/core/alpha/templates")
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        assert _count(db, Plugin_pages, plugin_id="alpha") == 0
        assert _count(db, Templates, plugin_id="alpha") == 0 and _count(db, Template_steps) == 0
        assert _count(db, Template_settings) == 0 and _count(db, Template_custom_configs) == 0

    def test_a_template_file_that_is_invalid_json_or_a_directory_is_ignored(self, db, root, logs):
        _write_template(root, "alpha", "broken", "{ nope")
        (root / "usr/share/bunkerweb/core/alpha/templates/subdir").mkdir()
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        assert _count(db, Templates) == 0
        assert any("is not valid JSON" in m for m in _messages(logs, logging.ERROR))

    def test_invalid_template_entries_are_skipped_one_by_one(self, db, root, logs):
        bad = {
            "name": "Bad",
            "settings": {"USE_TEMPLATE": "x", "NOT_A_SETTING": "y", "SERVER_NAME": "orphan", "USE_REVERSE_PROXY": "yes"},
            "steps": [
                {"title": "One", "subtitle": "s", "settings": ["USE_TEMPLATE", "NOT_A_SETTING", "USE_REVERSE_PROXY"], "configs": ["server-http/ok.conf"]}
            ],
            "configs": ["nonsense", "http/x.conf", "server-http/missing.conf", "server-http/orphan.conf", "server-http/ok.conf"],
        }
        _write_template(root, "alpha", "bad", bad, {"server-http/orphan.conf": "x", "server-http/ok.conf": "ok;"})
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        details = db.get_template_details("bad")
        assert [s["key"] for s in details["settings"]] == ["USE_REVERSE_PROXY"]
        assert [c["key"] for c in details["configs"]] == ["server_http/ok.conf"]
        text = "\n".join(_messages(logs, logging.ERROR))
        for needle in ("restricted setting", "invalid setting", "doesn't belong to a step", "invalid config", "invalid config type", "missing config"):
            assert needle in text, needle

    def test_the_unsupported_letsencrypt_dns_plugin_is_never_stored(self, db, root, logs):
        unsupported = _alpha()
        unsupported["id"] = "letsencrypt_dns"
        assert db.init_tables([_general(), unsupported]) == (True, "")
        assert _count(db, Plugins, id="letsencrypt_dns") == 0
        assert any("is no longer supported" in m for m in _messages(logs, logging.WARNING))

    def test_commands_are_synchronised_with_the_manifest(self, db, root):
        plugin = _alpha()
        plugin["bwcli"] = {"show": "show.py", "second": "second.py"}
        assert db.init_tables([_general(), plugin]) == (True, "")
        assert _count(db, Bw_cli_commands, plugin_id="alpha") == 2
        plugin = _alpha()
        plugin["bwcli"] = {"show": "changed.py"}
        assert db.init_tables([_general(), plugin]) == (True, "")
        with session(db) as s:
            rows = {r.name: r.file_name for r in s.query(Bw_cli_commands).filter_by(plugin_id="alpha")}
        assert rows == {"show": "changed.py"}
        plugin = _alpha()
        plugin["bwcli"] = ["not", "a", "dict"]
        assert db.init_tables([_general(), plugin]) == (True, "")
        assert _count(db, Bw_cli_commands, plugin_id="alpha") == 0


class TestSettingAndJobSync:
    def test_changed_setting_fields_and_choices_are_updated_and_removed_ones_pruned_with_their_values(self, db, root):
        first = _alpha()
        first["settings"]["ALPHA_CHOICE"] = {
            "id": "alpha-choice",
            "context": "multisite",
            "default": "one",
            "help": "h",
            "label": "L",
            "regex": "^.*$",
            "type": "select",
            "select": ["one", "two"],
        }
        first["settings"]["ALPHA_FLAGS"] = {
            "id": "alpha-flags",
            "context": "multisite",
            "default": "a",
            "help": "h",
            "label": "L",
            "regex": "^.*$",
            "type": "multiselect",
            "multiselect": [{"id": "a", "label": "A", "value": "a"}, {"id": "b", "label": "B", "value": "b"}],
        }
        assert db.init_tables([_general(), first]) == (True, "")
        add_global_value(db, setting_id="ALPHA_GLOBAL", value="mine", method="ui")
        add_global_value(db, setting_id="ALPHA_CHOICE", value="two", method="ui")
        add_service(db, "app1.example.com")
        add_service_setting(db, service_id="app1.example.com", setting_id="ALPHA_MS", value="svc", method="ui")

        second = _alpha(version="2.0")
        second["settings"].pop("ALPHA_GLOBAL")
        second["settings"]["ALPHA_MS"]["default"] = "newdefault"
        second["settings"]["ALPHA_CHOICE"] = {
            "id": "alpha-choice",
            "context": "multisite",
            "default": "three",
            "help": "h",
            "label": "L",
            "regex": "^.*$",
            "type": "select",
            "select": ["three"],
        }
        second["settings"]["ALPHA_FLAGS"] = {
            "id": "alpha-flags",
            "context": "multisite",
            "default": "a",
            "help": "h",
            "label": "L",
            "regex": "^.*$",
            "type": "multiselect",
            "multiselect": [{"id": "b", "label": "B2", "value": "b"}],
        }
        assert db.init_tables([_general(), second]) == (True, "")

        with session(db) as s:
            assert s.get(Plugins, "alpha").version == "2.0"
            assert s.get(Settings, "ALPHA_MS").default == "newdefault"
            assert s.get(Settings, "ALPHA_GLOBAL") is None
            assert [r.value for r in s.query(Selects).filter_by(setting_id="ALPHA_CHOICE").order_by(Selects.order)] == ["three"]
            assert [(r.option_id, r.label) for r in s.query(Multiselects).filter_by(setting_id="ALPHA_FLAGS")] == [("b", "B2")]
        # SQLite does not enforce foreign keys here, so the value rows of the removed setting are engine dependent and not asserted
        assert _count(db, Global_values, setting_id="ALPHA_CHOICE", value="two") == 1
        assert _count(db, Services_settings, setting_id="ALPHA_MS", value="svc") == 1

    def test_a_setting_removed_from_a_plugin_takes_its_stored_values_with_it(self, db, root):
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        add_global_value(db, setting_id="ALPHA_GLOBAL", value="mine", method="ui")
        shrunk = _alpha()
        shrunk["settings"].pop("ALPHA_GLOBAL")
        assert db.init_tables([_general(), shrunk]) == (True, "")
        assert _count(db, Settings, id="ALPHA_GLOBAL") == 0
        assert _count(db, Global_values, setting_id="ALPHA_GLOBAL") == 0

    def test_the_renamed_crs_plugin_urls_setting_keeps_the_stored_values(self, db, root, logs):
        old = _alpha()
        old["settings"] = {
            "MODSECURITY_CRS_PLUGIN_URLS": {
                "id": "crs-plugin-urls",
                "context": "multisite",
                "default": "",
                "help": "h",
                "label": "L",
                "regex": "^.*$",
                "type": "text",
            }
        }
        assert db.init_tables([_general(), old]) == (True, "")
        add_global_value(db, setting_id="MODSECURITY_CRS_PLUGIN_URLS", value="https://example.invalid/plugin.zip", method="ui")
        new = _alpha()
        new["settings"] = {
            "MODSECURITY_CRS_PLUGINS": {"id": "crs-plugins", "context": "multisite", "default": "", "help": "h", "label": "L", "regex": "^.*$", "type": "text"}
        }
        assert db.init_tables([_general(), new]) == (True, "")
        assert any("has been renamed to MODSECURITY_CRS_PLUGINS" in m for m in _messages(logs, logging.WARNING))
        assert _count(db, Settings, id="MODSECURITY_CRS_PLUGIN_URLS") == 0
        with session(db) as s:
            assert [r.value for r in s.query(Global_values).filter_by(setting_id="MODSECURITY_CRS_PLUGINS")] == ["https://example.invalid/plugin.zip"]

    def test_job_changes_are_applied_and_a_removed_job_takes_its_runs_and_cache(self, db, root):
        job = {"name": "alpha-job", "file": "alpha.py", "every": "hour", "reload": False}
        assert db.init_tables([_general(), _alpha(jobs=[dict(job)])]) == (True, "")
        assert db.add_job_run("alpha-job", True, FIXED_DT) == ""
        assert db.upsert_job_cache(None, "c.txt", b"c", job_name="alpha-job") == ""
        assert db.init_tables([_general(), _alpha(jobs=[dict(job, every="day", reload=True)])]) == (True, "")
        with session(db) as s:
            row = s.get(Jobs, "alpha-job")
            assert (row.every, row.reload) == ("day", True)
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        assert (_count(db, Jobs, name="alpha-job"), _count(db, Jobs_runs, job_name="alpha-job"), _count(db, Jobs_cache, job_name="alpha-job")) == (0, 0, 0)

    def test_a_removed_manual_plugin_is_deleted_but_an_externally_managed_one_is_kept(self, db, root, logs):
        assert db.init_tables([_general(), _alpha(), make_core_plugin("beta")]) == (True, "")
        with session(db) as s:
            s.query(Plugins).filter_by(id="beta").update({"method": "ui"})
        assert db.init_tables([_general()]) == (True, "")
        assert _count(db, Plugins, id="alpha") == 0 and _count(db, Plugins, id="beta") == 1
        assert any('plugin "alpha" has been removed, deleting it' in m for m in _messages(logs, logging.WARNING))

    def test_a_plugin_that_appears_in_a_populated_database_is_announced(self, db, root, logs):
        assert db.init_tables([_general()]) == (True, "")
        assert db.init_tables([_general(), _alpha()]) == (True, "")
        assert any('Plugin "alpha" does not exist, creating it' in m for m in _messages(logs, logging.WARNING))

    def test_read_only_mode_refuses_without_touching_the_schema(self, db, root):
        db.readonly = True
        assert db.init_tables([_general()]) == (False, "The database is read-only, the changes will not be saved")

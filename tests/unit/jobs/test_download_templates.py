"""``templates/jobs/download-templates.py``: service templates installed from ``EXTERNAL_TEMPLATE_URLS``.

The job runs against a real sqlite ``Database`` and a real local HTTPS server (``conftest.url_server``,
certificate verification on). Only ``Job`` (whose cache would write under /var/cache/bunkerweb) and
the logger are stubbed. It is a script -- the worker imports it and its last statement exits -- so
only its definitions are loaded and ``main()`` is called directly; its return value is the exit code.

What is pinned:

* the transport rules (https or ``file:///`` only, the ``#sha256=`` pin, the 1 MiB cap) and both
  template shapes (a ``bunkerweb-template/1`` package, a ``<id>/template.json`` folder archive);
* ownership: the job writes ``method="scheduler"`` templates with no plugin, updates only those,
  and never touches a template the web UI, the API or a plugin owns;
* removal: a template whose URL left the setting is deleted, unless a service or the global
  settings still use it (kept, warned, retried next run), and a run in which any URL failed deletes
  nothing -- a transient outage must not wipe templates;
* the exit code is 0 or 2, never 1: a template is DB state rendered by push-configs, so the job
  raises the plugins' ``config_changed`` flags instead of shipping a cache, and an unchanged re-run
  raises nothing (it runs again every time those flags are raised, so anything else would loop).
"""

import ast
import io
import json
import sys
import tarfile
from hashlib import sha256
from pathlib import Path
from types import ModuleType

import pytest

from fixtures.seed import add_global_value, add_service, add_service_setting, make_core_plugin, make_general_settings

ROOT = Path(__file__).resolve().parents[3]
JOB_FILE = ROOT / "src" / "common" / "core" / "templates" / "jobs" / "download-templates.py"
FORMAT = "bunkerweb-template/1"


class _Logger:
    def __init__(self):
        self.lines = {"info": [], "warning": [], "error": [], "debug": []}

    def __getattr__(self, level):
        return lambda msg, *a, **k: self.lines[level].append(str(msg))


def _load_job(monkeypatch):
    tree = ast.parse(JOB_FILE.read_text(encoding="utf-8"), filename=str(JOB_FILE))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.ClassDef))]
    stubs = {name: ModuleType(name) for name in ("jobs", "logger", "Database")}
    stubs["jobs"].Job = object
    stubs["logger"].getLogger = lambda name: None
    stubs["Database"].Database = object
    module = ModuleType("bw_download_templates")
    module.__dict__["__file__"] = str(JOB_FILE)
    # setitem, not patch.dict: patch.dict drops every module first imported inside it on exit
    # (requests' cookiejar among them), and the re-import breaks requests' isinstance checks.
    for name, stub in stubs.items():
        monkeypatch.setitem(sys.modules, name, stub)
    exec(compile(tree, str(JOB_FILE), "exec"), module.__dict__)  # noqa: S102
    return module


def _package(template_id="web", *, name=None, value="one", config="# one\n", **over):
    package = {
        "format": FORMAT,
        "id": template_id,
        "name": name or f"{template_id} template",
        "settings": {"TPLPLUG_MS": value},
        "steps": [{"title": "Step 1", "subtitle": "", "settings": ["TPLPLUG_MS"], "configs": ["modsec/extra.conf"]}],
        "configs": [{"type": "modsec", "name": "extra", "data": config}],
    }
    package.update(over)
    return json.dumps(package).encode()


def _folder_archive(template_id="folder"):
    template = {
        "id": template_id,
        "name": "From a folder",
        "settings": {"TPLPLUG_MS": "tar"},
        "steps": [{"title": "S", "settings": ["TPLPLUG_MS"], "configs": ["modsec/x.conf"]}],
        "configs": ["modsec/x.conf"],
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in ((f"{template_id}/template.json", json.dumps(template).encode()), (f"{template_id}/configs/modsec/x.conf", b"# from tar\n")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def run(db, monkeypatch):
    general = make_general_settings()
    general["USE_TEMPLATE"] = {"id": "use-template", "context": "multisite", "default": "", "help": "h", "label": "T", "regex": "^.*$", "type": "text"}
    db.init_tables([general, make_core_plugin("tplplug"), make_core_plugin("templates")])
    db.initialize_db("1.7.0", "Docker")
    job = _load_job(monkeypatch)
    cache = {}

    class FakeJob:
        def __init__(self, *args, **kwargs):
            pass

        def get_cache(self, name, **kwargs):
            return cache.get(name)

        def cache_file(self, name, content, **kwargs):
            cache[name] = content if isinstance(content, bytes) else content.encode()
            return True, "success"

    monkeypatch.setattr(job, "Database", lambda *args, **kwargs: db)
    monkeypatch.setattr(job, "Job", FakeJob)

    def _run(*urls):
        logger = _Logger()
        monkeypatch.setattr(job, "LOGGER", logger)
        monkeypatch.setenv("EXTERNAL_TEMPLATE_URLS", " ".join(urls))
        code = job.main()
        return code, logger

    _run.db = db
    return _run


def _state(db, template_id):
    details = db.get_template_details(template_id)
    if details is None:
        return None
    return {
        "name": details["name"],
        "method": details["method"],
        "plugin_id": details["plugin_id"],
        "settings": {s["key"]: s["default"] for s in details["settings"]},
        "configs": {c["key"]: c["data"] for c in details["configs"]},
    }


def _clear_flags(db):
    assert db.checked_changes(["config", "custom_configs"], plugins_changes="all", value=False) == ""
    assert db.get_metadata()["plugins_config_changed"] == {}


# ── transport and shapes ────────────────────────────────────────────────────────


def test_no_urls_and_nothing_installed_is_a_quiet_success(run):
    code, logger = run()
    assert code == 0
    assert logger.lines["error"] == []


def test_a_package_over_https_is_installed_as_a_scheduler_template(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    code, logger = run(url_server.https("/web.json"))
    assert code == 0, logger.lines
    assert _state(run.db, "web") == {
        "name": "web template",
        "method": "scheduler",
        "plugin_id": None,
        "settings": {"TPLPLUG_MS": "one"},
        "configs": {"modsec/extra.conf": "# one\n"},
    }


def test_a_folder_archive_is_installed(run, url_server):
    url_server.routes["/folder.tar.gz"] = (200, _folder_archive(), {})
    code, logger = run(url_server.https("/folder.tar.gz"))
    assert code == 0, logger.lines
    assert _state(run.db, "folder")["configs"] == {"modsec/x.conf": "# from tar\n"}


def test_a_local_file_is_installed(run, tmp_path):
    path = tmp_path / "local.json"
    path.write_bytes(_package("local"))
    code, _ = run(f"file://{path}")
    assert code == 0
    assert _state(run.db, "local")["method"] == "scheduler"


def test_plain_http_is_refused_without_a_request(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    code, logger = run(url_server.http("/web.json"))
    assert code == 2
    assert url_server.hits == []
    assert _state(run.db, "web") is None
    assert any("https" in line for line in logger.lines["error"])


def test_the_sha256_pin_is_enforced(run, url_server):
    body = _package()
    url_server.routes["/web.json"] = (200, body, {})
    code, _ = run(url_server.https(f"/web.json#sha256={'0' * 64}"))
    assert code == 2
    assert _state(run.db, "web") is None

    code, _ = run(url_server.https(f"/web.json#sha256={sha256(body).hexdigest()}"))
    assert code == 0
    assert _state(run.db, "web") is not None


def test_a_download_over_one_mib_is_refused(run, url_server):
    url_server.routes["/big.json"] = (200, [b" " * (512 * 1024), b" " * (512 * 1024), _package()], {})
    code, logger = run(url_server.https("/big.json"))
    assert code == 2
    assert _state(run.db, "web") is None
    assert any("exceeds" in line for line in logger.lines["error"])


def test_a_package_with_an_unknown_setting_is_refused_whole(run, url_server):
    url_server.routes["/bad.json"] = (200, _package(settings={"NOPE": "x"}, steps=[{"title": "S", "settings": ["NOPE"]}], configs=[]), {})
    code, logger = run(url_server.https("/bad.json"))
    assert code == 2
    assert _state(run.db, "web") is None
    assert any("Unknown settings" in line for line in logger.lines["error"])


# ── ownership ───────────────────────────────────────────────────────────────────


def test_a_template_the_ui_owns_is_never_overwritten(run, url_server):
    assert run.db.create_template("web", name="Mine", settings={"TPLPLUG_MS": "ui"}, steps=[{"title": "S", "settings": ["TPLPLUG_MS"]}]) == ""
    url_server.routes["/web.json"] = (200, _package(), {})
    code, logger = run(url_server.https("/web.json"))
    assert code == 2
    assert _state(run.db, "web")["settings"] == {"TPLPLUG_MS": "ui"}
    assert _state(run.db, "web")["method"] == "ui"
    # And removing the URL again must not delete it either: the job only removes its own.
    code, _ = run()
    assert code == 0
    assert _state(run.db, "web") is not None


def test_a_plugin_owned_template_is_never_overwritten(run, url_server):
    assert (
        run.db.create_template(
            "web", plugin_id="tplplug", name="Plugin", settings={"TPLPLUG_MS": "plugin"}, steps=[{"title": "S", "settings": ["TPLPLUG_MS"]}], method="manual"
        )
        == ""
    )
    url_server.routes["/web.json"] = (200, _package(), {})
    code, _ = run(url_server.https("/web.json"))
    assert code == 2
    assert _state(run.db, "web")["settings"] == {"TPLPLUG_MS": "plugin"}


def test_two_urls_delivering_the_same_id_install_the_first_only(run, url_server):
    url_server.routes["/a.json"] = (200, _package(value="first"), {})
    url_server.routes["/b.json"] = (200, _package(value="second", name="other name"), {})
    code, logger = run(url_server.https("/a.json"), url_server.https("/b.json"))
    assert code == 2
    assert _state(run.db, "web")["settings"] == {"TPLPLUG_MS": "first"}


# ── updates, flags and the exit code ────────────────────────────────────────────


def test_a_new_template_raises_the_templates_plugin_flag(run, url_server):
    _clear_flags(run.db)
    url_server.routes["/web.json"] = (200, _package(), {})
    code, _ = run(url_server.https("/web.json"))
    assert code == 0
    assert "templates" in run.db.get_metadata()["plugins_config_changed"]


def test_an_unchanged_rerun_writes_and_flags_nothing(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    assert run(url_server.https("/web.json"))[0] == 0
    before = run.db.get_template_details("web")["last_update"]
    _clear_flags(run.db)

    code, _ = run(url_server.https("/web.json"))
    assert code == 0
    assert run.db.get_template_details("web")["last_update"] == before
    assert run.db.get_metadata()["plugins_config_changed"] == {}


def test_a_changed_package_updates_the_template_in_place_and_flags_it(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    assert run(url_server.https("/web.json"))[0] == 0
    _clear_flags(run.db)

    url_server.routes["/web.json"] = (200, _package(value="two", config="# two\n"), {})
    code, logger = run(url_server.https("/web.json"))
    assert code == 0, logger.lines
    assert _state(run.db, "web")["settings"] == {"TPLPLUG_MS": "two"}
    assert _state(run.db, "web")["configs"] == {"modsec/extra.conf": "# two\n"}
    assert _state(run.db, "web")["method"] == "scheduler"
    assert run.db.get_metadata()["plugins_config_changed"]


def test_a_template_deleted_behind_the_jobs_back_is_recreated(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    assert run(url_server.https("/web.json"))[0] == 0
    assert run.db.delete_template("web") == ""
    assert run(url_server.https("/web.json"))[0] == 0
    assert _state(run.db, "web") is not None


# ── removal ─────────────────────────────────────────────────────────────────────


def test_a_url_removed_from_the_setting_deletes_its_template(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    url_server.routes["/api.json"] = (200, _package("api", config="# api\n"), {})
    assert run(url_server.https("/web.json"), url_server.https("/api.json"))[0] == 0

    code, _ = run(url_server.https("/api.json"))
    assert code == 0
    assert _state(run.db, "web") is None
    assert _state(run.db, "api") is not None

    code, _ = run()
    assert code == 0
    assert _state(run.db, "api") is None


@pytest.mark.parametrize("where", ["service", "global"])
def test_a_removed_template_still_in_use_is_kept_then_deleted_once_free(run, url_server, where):
    url_server.routes["/web.json"] = (200, _package(), {})
    assert run(url_server.https("/web.json"))[0] == 0
    if where == "service":
        add_service(run.db, "app1.example.com")
        add_service_setting(run.db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low web")
    else:
        add_global_value(run.db, setting_id="USE_TEMPLATE", value="web")

    code, logger = run()
    assert code == 0
    assert _state(run.db, "web") is not None
    assert any("web" in line and "used" in line for line in logger.lines["warning"])

    with run.db._db_session() as session:
        from model import Global_values, Services_settings

        session.query(Services_settings).filter_by(setting_id="USE_TEMPLATE").delete()
        session.query(Global_values).filter_by(setting_id="USE_TEMPLATE").delete()
        session.commit()

    assert run()[0] == 0
    assert _state(run.db, "web") is None


def test_a_run_with_a_failed_url_deletes_nothing(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    url_server.routes["/api.json"] = (200, _package("api", config="# api\n"), {})
    assert run(url_server.https("/web.json"), url_server.https("/api.json"))[0] == 0

    # web.json is now unreachable and api.json left the setting: nothing may be removed, because
    # the job cannot tell which templates the failed URL would still have delivered.
    del url_server.routes["/web.json"]
    code, _ = run(url_server.https("/web.json"))
    assert code == 2
    assert _state(run.db, "web") is not None
    assert _state(run.db, "api") is not None


def test_the_exit_code_is_never_one(run, url_server):
    url_server.routes["/web.json"] = (200, _package(), {})
    codes = {run(url_server.https("/web.json"))[0], run(url_server.https("/web.json"))[0], run()[0]}
    url_server.routes["/web.json"] = (200, _package(value="two"), {})
    codes |= {run(url_server.https("/web.json"))[0], run(url_server.http("/web.json"))[0]}
    assert 1 not in codes
    assert codes <= {0, 2}


def test_update_template_only_lets_the_owning_method_change_a_template(run):
    step = [{"title": "S", "settings": ["TPLPLUG_MS"]}]
    assert run.db.create_template("sched", name="Sched", settings={"TPLPLUG_MS": "a"}, steps=step, method="scheduler") == ""
    assert run.db.create_template("mine", name="Mine", settings={"TPLPLUG_MS": "a"}, steps=step) == ""

    assert "managed by scheduler" in run.db.update_template("sched", settings={"TPLPLUG_MS": "b"}, steps=step)
    assert run.db.update_template("sched", settings={"TPLPLUG_MS": "b"}, steps=step, method="scheduler") == ""
    assert _state(run.db, "sched")["method"] == "scheduler"

    assert "managed by ui" in run.db.update_template("mine", settings={"TPLPLUG_MS": "b"}, steps=step, method="scheduler")
    assert run.db.update_template("mine", settings={"TPLPLUG_MS": "b"}, steps=step) == ""

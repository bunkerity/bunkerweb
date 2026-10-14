"""``misc/jobs/download-plugins.py`` and ``EXTERNAL_PLUGIN_URLS``: the pin, the cap, the http warning, and
what removing a URL does.

The shipped script runs whole, against a real local HTTPS server (``conftest.url_server``) and a
real sqlite ``Database``. Two constants are redirected before it runs -- the plugin directory
(``/etc/bunkerweb/plugins``) and its scratch directory -- plus, for the cap case, the cap itself.
``magic`` (libmagic) is not in the unit venv; it is stubbed to answer ``application/octet-stream``,
the case where the script falls back to the URL's extension -- the path a ``#sha256=`` fragment
must not break.
"""

import ast
import io
import json
import sys
import tarfile
import zipfile
from hashlib import sha256
from pathlib import Path
from types import ModuleType

import pytest

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore
from fixtures.seed import make_general_settings, session
from model import Plugins, Templates  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
JOB_FILE = ROOT / "src" / "common" / "core" / "misc" / "jobs" / "download-plugins.py"


class _Logger:
    def __init__(self):
        self.lines = {"info": [], "warning": [], "error": [], "debug": []}

    def __getattr__(self, level):
        return lambda msg, *a, **k: self.lines[level].append(str(msg))


def _plugin_tar(plugin_id, version="1.0"):
    metadata = {"id": plugin_id, "name": plugin_id, "description": "d", "version": version, "stream": "no", "settings": {}, "jobs": []}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = json.dumps(metadata).encode()
        info = tarfile.TarInfo(f"{plugin_id}/plugin.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _plugin_tar_with_id(plugin_id):
    metadata = {"id": plugin_id, "name": "n", "description": "d", "version": "1.0", "stream": "no", "settings": {}, "jobs": []}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = json.dumps(metadata).encode()
        info = tarfile.TarInfo("evil/plugin.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def run(db, tmp_path, monkeypatch):
    db.init_tables([make_general_settings()])
    db.initialize_db("1.7.0", "Docker")
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    monkeypatch.setattr(type(db), "_uep_resolve_plugin_dir", lambda self, plugin_id, _type: plugins_dir / plugin_id)

    def _run(*urls, overrides=None):
        constants = {"EXTERNAL_PLUGINS_DIR": plugins_dir, "TMP_DIR": tmp_path / "scratch"} | (overrides or {})
        tree = ast.parse(JOB_FILE.read_text(encoding="utf-8"), filename=str(JOB_FILE))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants:
                value = constants[node.targets[0].id]
                node.value = ast.parse(f"Path({str(value)!r})" if isinstance(value, Path) else repr(value), mode="eval").body
        ast.fix_missing_locations(tree)

        logger = _Logger()
        stubs = {name: ModuleType(name) for name in ("magic", "logger", "Database")}
        stubs["magic"].Magic = lambda **kwargs: type("M", (), {"from_buffer": lambda self, buffer: "application/octet-stream"})()
        stubs["logger"].getLogger = lambda name: logger
        stubs["Database"].Database = lambda *args, **kwargs: db
        monkeypatch.setenv("EXTERNAL_PLUGIN_URLS", " ".join(urls))
        # setitem, not patch.dict: patch.dict drops every module first imported inside it on exit
        # (requests' cookiejar among them), and the re-import breaks requests' isinstance checks.
        for name, module in stubs.items():
            monkeypatch.setitem(sys.modules, name, module)
        with pytest.raises(SystemExit) as exit_info:
            exec(compile(tree, str(JOB_FILE), "exec"), {"__file__": str(JOB_FILE), "__name__": "bw_download_plugins"})  # noqa: S102
        return exit_info.value.code, logger

    _run.db = db
    _run.plugins_dir = plugins_dir
    return _run


def _installed(db):
    return sorted(plugin["id"] for plugin in db.get_plugins(_type="external"))


def test_a_matching_pin_installs_and_the_fragment_does_not_break_type_detection(run, url_server):
    body = _plugin_tar("pinned")
    url_server.routes["/pinned.tar.gz"] = (200, body, {})
    code, logger = run(url_server.https(f"/pinned.tar.gz#sha256={sha256(body).hexdigest()}"))
    assert code == 1, logger.lines
    assert _installed(run.db) == ["pinned"]


def test_a_pin_mismatch_installs_nothing_and_fails_the_job(run, url_server):
    url_server.routes["/pinned.tar.gz"] = (200, _plugin_tar("pinned"), {})
    code, logger = run(url_server.https(f"/pinned.tar.gz#sha256={'0' * 64}"))
    assert code == 2
    assert _installed(run.db) == []
    assert not (run.plugins_dir / "pinned").exists()
    assert any("sha256" in line for line in logger.lines["error"])


def test_a_download_over_the_cap_is_refused(run, url_server):
    body = _plugin_tar("big")
    url_server.routes["/big.tar.gz"] = (200, body, {})
    code, logger = run(url_server.https("/big.tar.gz"), overrides={"PLUGIN_DOWNLOAD_MAX": len(body) - 1})
    assert code == 2
    assert _installed(run.db) == []
    assert any("exceeds" in line for line in logger.lines["error"])


def test_a_later_success_does_not_mask_an_earlier_failed_url(run, url_server):
    url_server.routes["/good.tar.gz"] = (200, _plugin_tar("good"), {})

    code, logger = run(url_server.https("/missing.tar.gz"), url_server.https("/good.tar.gz"))

    assert code == 2, logger.lines
    assert _installed(run.db) == ["good"]


def test_plain_http_still_installs_but_warns(run, url_server):
    url_server.routes["/plain.tar.gz"] = (200, _plugin_tar("plain"), {})
    code, logger = run(url_server.http("/plain.tar.gz"))
    assert code == 1, logger.lines
    assert _installed(run.db) == ["plain"]
    assert any("http://" in line and "https" in line for line in logger.lines["warning"])


def test_https_does_not_warn(run, url_server):
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    code, logger = run(url_server.https("/a.tar.gz"))
    assert code == 1
    assert not any("http://" in line for line in logger.lines["warning"])


def _methods(db):
    return {plugin["id"]: plugin["method"] for plugin in db.get_plugins(_type="external")}


def _hand_mounted(run, plugin_id, method="manual", plugin_type="external"):
    """A plugin the job did not install: its directory under the plugins dir and its row, whatever the method."""
    folder = run.plugins_dir / plugin_id
    folder.mkdir()
    (folder / "plugin.json").write_text(json.dumps({"id": plugin_id, "name": plugin_id, "description": "d", "version": "1.0", "stream": "no", "settings": {}}))
    with session(run.db) as s:
        s.add(Plugins(id=plugin_id, name=plugin_id, description="d", version="1.0", type=plugin_type, method=method))
    return folder


def _set_method(db, plugin_id, method):
    with session(db) as s:
        s.get(Plugins, plugin_id).method = method


def test_removing_a_url_uninstalls_what_came_from_it(run, url_server):
    """EXTERNAL_PLUGIN_URLS is the list of what is installed: a plugin leaves with its URL, directory and row."""
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    url_server.routes["/b.tar.gz"] = (200, _plugin_tar("b"), {})
    assert run(url_server.https("/a.tar.gz"))[0] == 1
    assert _methods(run.db) == {"a": "download"}

    code, logger = run(url_server.https("/b.tar.gz"))
    assert code == 1, logger.lines
    assert _methods(run.db) == {"b": "download"}
    assert not (run.plugins_dir / "a").exists()
    assert (run.plugins_dir / "b").is_dir()
    assert any("a" in line and "removed" in line.lower() for line in logger.lines["info"]), logger.lines["info"]
    metadata = run.db.get_metadata()
    assert metadata["external_plugins_changed"] is True and metadata["reload_ui_plugins"] is True


def test_an_emptied_setting_uninstalls_everything_it_installed_and_reports_a_change(run, url_server):
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    url_server.routes["/b.tar.gz"] = (200, _plugin_tar("b"), {})
    assert run(url_server.https("/a.tar.gz"), url_server.https("/b.tar.gz"))[0] == 1
    assert _installed(run.db) == ["a", "b"]

    code, logger = run()

    assert code == 1, logger.lines
    assert _installed(run.db) == []
    assert not (run.plugins_dir / "a").exists() and not (run.plugins_dir / "b").exists()

    code, logger = run()  # nothing left to remove: not a change
    assert code == 0
    assert any("No external plugins to download" in line for line in logger.lines["info"])


@pytest.mark.parametrize("urls_left", [False, True], ids=["empty-setting", "other-url-left"])
def test_what_the_job_did_not_install_is_never_removed(run, url_server, urls_left):
    """Hand-mounted ("manual"), UI-uploaded ("ui") and legacy ("scheduler") plugins survive both kinds of run."""
    url_server.routes["/b.tar.gz"] = (200, _plugin_tar("b"), {})
    _hand_mounted(run, "mounted")
    _hand_mounted(run, "legacy", method="scheduler")
    _hand_mounted(run, "uploaded", method="ui", plugin_type="ui")

    code, logger = run(*([url_server.https("/b.tar.gz")] if urls_left else []))

    assert code == (1 if urls_left else 0), logger.lines
    assert _methods(run.db) == ({"b": "download"} if urls_left else {}) | {"mounted": "manual", "legacy": "scheduler", "uploaded": "ui"}
    for plugin_id in ("mounted", "legacy", "uploaded"):
        assert (run.plugins_dir / plugin_id / "plugin.json").is_file()


@pytest.mark.parametrize("failing", ["missing", "pin-mismatch", "not-an-archive"])
def test_a_failing_url_prunes_nothing(run, url_server, failing):
    """A URL that cannot be read says nothing about which plugins it carries: keep everything installed."""
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    url_server.routes["/b.tar.gz"] = (200, _plugin_tar("b"), {})
    url_server.routes["/junk.tar.gz"] = (200, b"not a tar at all", {})
    assert run(url_server.https("/a.tar.gz"))[0] == 1

    bad = {
        "missing": url_server.https("/missing.tar.gz"),
        "pin-mismatch": url_server.https(f"/a.tar.gz#sha256={'0' * 64}"),
        "not-an-archive": url_server.https("/junk.tar.gz"),
    }[failing]
    code, logger = run(url_server.https("/b.tar.gz"), bad)

    assert code == 2, logger.lines
    assert _methods(run.db) == {"a": "download", "b": "download"}
    assert (run.plugins_dir / "a").is_dir()
    assert any("not removed" in line.lower() or "removal" in line.lower() for line in logger.lines["warning"]), logger.lines["warning"]


def test_an_archive_without_any_plugin_prunes_nothing(run, url_server):
    """The URL answered but its archive holds no plugin.json (moved, wrong asset): no evidence of removal."""
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    assert run(url_server.https("/a.tar.gz"))[0] == 1
    empty = io.BytesIO()
    with tarfile.open(fileobj=empty, mode="w:gz") as tar:
        info = tarfile.TarInfo("README")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    url_server.routes["/a.tar.gz"] = (200, empty.getvalue(), {})

    run(url_server.https("/a.tar.gz"))

    assert _methods(run.db) == {"a": "download"}


def test_a_legacy_scheduler_plugin_in_the_urls_is_claimed_by_the_job(run, url_server):
    """Rows written before the label existed carry "scheduler": the job claims the ones it can prove it fetched."""
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    assert run(url_server.https("/a.tar.gz"))[0] == 1
    # The plugin ships a template; the database is brought to what an upgrade leaves: every row labelled "scheduler".
    folder = run.plugins_dir / "a"
    folder.joinpath("templates").mkdir()
    folder.joinpath("templates", "a_tpl.json").write_text(json.dumps({"name": "a_tpl", "settings": {}, "steps": []}))
    content = create_plugin_tar_gz(folder, arc_root="a")
    row = json.loads(folder.joinpath("plugin.json").read_text()) | {
        "type": "external",
        "page": False,
        "method": "download",
        "data": content.getvalue(),
        "checksum": bytes_hash(content, algorithm="sha256"),
    }
    assert run.db.update_external_plugins([row], delete_missing=False) == ""
    _set_method(run.db, "a", "scheduler")
    with session(run.db) as s:
        s.get(Templates, "a_tpl").method = "scheduler"
    _hand_mounted(run, "legacy_other", method="scheduler")

    code, logger = run(url_server.https("/a.tar.gz"))  # same archive: nothing to install, still a relabel

    assert code == 1, logger.lines
    assert _methods(run.db) == {"a": "download", "legacy_other": "scheduler"}
    with session(run.db) as s:
        assert s.get(Templates, "a_tpl").method == "download"


@pytest.mark.parametrize("bad_id", ["../escape", "a/b", "..", ".", ".hidden_x", "x" * 65])
def test_an_archive_cannot_name_a_path_through_its_plugin_id(run, url_server, bad_id):
    """The id becomes a directory under the plugins dir (installed, later removed): it must stay one component."""
    url_server.routes["/evil.tar.gz"] = (200, _plugin_tar_with_id(bad_id), {})

    code, logger = run(url_server.https("/evil.tar.gz"))

    assert _installed(run.db) == []
    assert not run.plugins_dir.parent.joinpath("escape").exists()
    assert list(run.plugins_dir.iterdir()) == []


def test_a_hand_mounted_plugin_with_the_same_id_keeps_its_row(run, url_server):
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    _hand_mounted(run, "a")

    code, logger = run(url_server.https("/a.tar.gz"))

    assert _methods(run.db) == {"a": "manual"}, logger.lines
    assert (run.plugins_dir / "a" / "plugin.json").is_file()
    assert any("already installed by method manual" in line for line in logger.lines["warning"])

    run()  # and the URL leaving does not take it either
    assert _methods(run.db) == {"a": "manual"}
    assert (run.plugins_dir / "a" / "plugin.json").is_file()


def _zip_with(name, data=b"x"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "path, body",
    [
        ("/broken.zip", b"not a zip at all"),  # BadZipFile branch
        ("/broken.tar.gz", b"not a tar at all"),  # TarError branch
        ("/evil.zip", _zip_with("../evil/plugin.json")),  # safe_zip_extractall refuses: ValueError, outer branch
    ],
    ids=["bad-zip", "bad-tar", "traversal"],
)
def test_an_archive_that_cannot_be_extracted_fails_the_job(run, url_server, path, body):
    """A refused or undecompressable archive must fail the job (exit 2), not log and exit 0."""
    url_server.routes[path] = (200, body, {})
    code, logger = run(url_server.https(path))
    assert code == 2, logger.lines
    assert _installed(run.db) == []

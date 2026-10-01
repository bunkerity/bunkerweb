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

from fixtures.seed import make_general_settings

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


def test_measured_removing_a_url_uninstalls_nothing(run, url_server):
    """Design P4, marked unverified there: what happens to a plugin when its URL leaves the setting.

    Measured: nothing. The job only ever adds. The next run with a different URL re-registers every
    directory still under the plugins dir, the old plugin included; a run with the setting emptied
    exits 0 at once without touching the database. Removal is a manual delete (UI or API).
    """
    url_server.routes["/a.tar.gz"] = (200, _plugin_tar("a"), {})
    url_server.routes["/b.tar.gz"] = (200, _plugin_tar("b"), {})
    assert run(url_server.https("/a.tar.gz"))[0] == 1
    assert _installed(run.db) == ["a"]

    assert run(url_server.https("/b.tar.gz"))[0] == 1
    assert _installed(run.db) == ["a", "b"]
    assert (run.plugins_dir / "a").is_dir()

    code, logger = run()
    assert code == 0
    assert _installed(run.db) == ["a", "b"]
    assert any("No external plugins to download" in line for line in logger.lines["info"])


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

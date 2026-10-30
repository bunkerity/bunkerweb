"""External archives publish real plugin trees and preserve operator-managed plugins."""

import json
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo, open as tar_open
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from _other_jobs_helpers import load_job
from common_utils import bytes_hash, create_plugin_tar_gz

JOB = "misc/jobs/download-plugins.py"


def _db():
    database = Mock()
    database.get_plugins.return_value = []
    database.update_external_plugins.return_value = ""
    return database


def _archive(path, kind):
    members = {"sample/plugin.json": json.dumps({"id": "sample", "version": "2"}).encode(), "sample/jobs/run.py": b"print('job')\n"}
    if kind == "zip":
        with ZipFile(path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
    else:
        with tar_open(path, "w:" + kind) as archive:
            for name, content in members.items():
                info = TarInfo(name)
                info.size = len(content)
                archive.addfile(info, BytesIO(content))


@pytest.mark.parametrize("kind, suffix", [("zip", ".zip"), ("gz", ".tar.gz"), ("bz2", ".tar.bz2"), ("xz", ".tar.xz"), ("", ".tar")])
def test_local_archive_publishes_content_and_permissions(tmp_path, monkeypatch, kind, suffix):
    source = tmp_path / ("plugins" + suffix)
    _archive(source, kind)
    db = _db()
    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, env={"EXTERNAL_PLUGIN_URLS": source.as_uri()})
    assert status == 1
    plugin = module.EXTERNAL_PLUGINS_DIR / "sample"
    assert (plugin / "jobs/run.py").read_bytes() == b"print('job')\n"
    assert (plugin / "jobs/run.py").stat().st_mode & 0o777 == 0o750
    published = db.update_external_plugins.call_args.args[0]
    assert [(entry["id"], entry["type"], entry["method"], entry["page"]) for entry in published] == [("sample", "external", "scheduler", False)]
    assert published[0]["checksum"] == bytes_hash(published[0]["data"], algorithm="sha256")
    assert not module.TMP_DIR.exists()


def test_http_download_uses_local_fixture_server(tmp_path, monkeypatch, url_server):
    source = tmp_path / "plugins.zip"
    _archive(source, "zip")
    url_server.routes["/plugins.zip"] = (200, source.read_bytes(), {})
    # Capture requests.get before the loader installs its fail-closed default.
    import requests

    module, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        database=_db(),
        get=requests.get,
        env={"EXTERNAL_PLUGIN_URLS": url_server.http("/plugins.zip")},
    )
    assert status == 1
    assert url_server.hits == ["/plugins.zip"]
    assert (module.EXTERNAL_PLUGINS_DIR / "sample/plugin.json").read_text() == '{"id": "sample", "version": "2"}'


def test_no_urls_cleans_stale_staging_directories_only(tmp_path, monkeypatch):
    root = tmp_path / "system/etc/bunkerweb/plugins"
    (root / ".sample.tmp-dead").mkdir(parents=True)
    (root / ".sample.bak-dead").mkdir()
    (root / "keep").mkdir()
    (root / "keep/plugin.json").write_text("{}")
    db = _db()
    _, status = load_job(monkeypatch, tmp_path, JOB, database=db)
    assert status == 0
    assert sorted(path.name for path in root.iterdir()) == ["keep"]
    db.update_external_plugins.assert_not_called()


def test_manual_plugin_survives_database_publication(tmp_path, monkeypatch):
    source = tmp_path / "plugins.zip"
    _archive(source, "zip")
    db = _db()
    manual = {"id": "manual", "method": "ui", "version": "1", "data": b"operator"}
    db.get_plugins.return_value = [manual]
    _, status = load_job(monkeypatch, tmp_path, JOB, database=db, env={"EXTERNAL_PLUGIN_URLS": source.as_uri()})
    assert status == 1
    assert db.update_external_plugins.call_args.args[0][-1] == manual
    assert db.update_external_plugins.call_args.kwargs == {"per_plugin_commit": False}


@pytest.mark.parametrize("manifest", [None, "{bad"])
def test_invalid_plugin_manifest_never_installs(tmp_path, monkeypatch, manifest):
    module, _ = load_job(monkeypatch, tmp_path, JOB)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    if manifest:
        (candidate / "plugin.json").write_text(manifest)
    assert module.install_plugin(candidate, _db()) is False
    assert not module.EXTERNAL_PLUGINS_DIR.exists()


@pytest.mark.parametrize("method, checksum_matches", [("ui", True), ("scheduler", True), ("scheduler", False)])
def test_existing_plugin_respects_ownership_and_integrity(tmp_path, monkeypatch, method, checksum_matches):
    source = tmp_path / "plugins.zip"
    _archive(source, "zip")
    db = _db()
    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, env={"EXTERNAL_PLUGIN_URLS": source.as_uri()})
    assert status == 1
    installed = module.EXTERNAL_PLUGINS_DIR / "sample"
    checksum = bytes_hash(create_plugin_tar_gz(installed, arc_root="sample"), algorithm="sha256")
    db.get_plugins.return_value = [{"id": "sample", "version": "2", "method": method, "checksum": checksum if checksum_matches else "different"}]
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "plugin.json").write_text('{"id": "sample", "version": "2"}')
    (candidate / "new.txt").write_text("replacement")
    assert module.install_plugin(candidate, db) is (method == "scheduler" and not checksum_matches)
    assert (installed / "jobs/run.py").exists() is (method != "scheduler" or checksum_matches)


def test_atomic_install_restores_previous_tree_on_rename_failure(tmp_path, monkeypatch):
    module, _ = load_job(monkeypatch, tmp_path, JOB)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "plugin.json").write_text('{"id":"sample","version":"2"}')
    installed = module.EXTERNAL_PLUGINS_DIR / "sample"
    installed.mkdir(parents=True)
    (installed / "old.txt").write_text("retained")
    original = Path.rename

    def fail_publish(path, target):
        if ".tmp-" in path.name:
            raise OSError("injected rename failure")
        return original(path, target)

    monkeypatch.setattr(Path, "rename", fail_publish)
    with pytest.raises(OSError, match="injected rename failure"):
        module._install_plugin_atomically(candidate, installed)
    assert (installed / "old.txt").read_text() == "retained"
    assert [path.name for path in installed.parent.iterdir()] == ["sample"]

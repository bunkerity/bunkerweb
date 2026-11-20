"""Execute CRS downloads through real extraction, patching and staged publication."""

import json
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo, open as tar_open
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import requests

from _other_jobs_helpers import Cache, load_job

JOB = "modsecurity/jobs/download-crs-plugins.py"
ROOT = Path(__file__).resolve().parents[3]


def _prepare(tmp_path):
    patch = tmp_path / "system/usr/share/bunkerweb/core/modsecurity/misc/patch.sh"
    patch.parent.mkdir(parents=True)
    patch.write_bytes((ROOT / "src/common/core/modsecurity/misc/patch.sh").read_bytes())
    patch.chmod(0o750)
    (tmp_path / "system/var/tmp/bunkerweb").mkdir(parents=True)
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/modsecurity")
    rows = {}

    def persist(entries, **_):
        rows.update({entry["file_name"]: entry for entry in entries})
        return ""

    cache.db.upsert_job_caches.side_effect = persist
    cache.db.get_job_cache_file.side_effect = lambda _job, name, **_: rows.get(name)
    return cache


def _archive(version="1.2", name="demo"):
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("package/demo-config.conf", f"# Plugin name: {name}\n# Plugin version: {version}\n")
        archive.writestr("package/rules.conf", "setvar:'tx.inbound_anomaly_score_pl1=+%{tx.critical_anomaly_score}'\n")
        archive.writestr("package/data/lookup.txt", "lookup\n")
    return content.getvalue()


def _response(content, status=200):
    resp = requests.Response()
    resp.status_code = status
    resp._content = content
    resp._content_consumed = True
    return resp


def test_archive_patch_manifest_and_cache_transaction_are_idempotent(tmp_path, monkeypatch, url_server):
    cache = _prepare(tmp_path)
    url_server.routes["/plugin.zip"] = (200, _archive(), {})
    get = requests.get
    env = {"MODSECURITY_CRS_PLUGINS": url_server.http("/plugin.zip")}
    module, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env=env)
    assert status == 1
    plugin = module.CRS_PLUGINS_DIR / "demo-1.2"
    assert "tx.bunkerweb_anomaly_score" in (plugin / "rules.conf").read_text()
    assert (plugin / "data/lookup.txt").read_text() == "lookup\n"
    assert json.loads((cache.job_path / "crs-plugins.json").read_bytes()) == {"app.example": ["demo-1.2"], "alias.example": []}
    entries = cache.db.upsert_job_caches.call_args.args[0]
    assert {entry["file_name"] for entry in entries} == {"crs-plugins.json", f"folder:{module.CRS_PLUGINS_DIR}.tgz"}
    archive = next(entry["data"] for entry in entries if entry["file_name"].startswith("folder:"))
    with tar_open(fileobj=BytesIO(archive), mode="r:gz") as tar:
        assert tar.extractfile("./demo-1.2/data/lookup.txt").read() == b"lookup\n"
        assert all(member.mtime == 0 for member in tar.getmembers())
    first_checksums = [entry["checksum"] for entry in entries]
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env=env)
    assert status == 0
    assert [entry["checksum"] for entry in cache.db.upsert_job_caches.call_args.args[0]] == first_checksums
    assert list((tmp_path / "system/var/tmp/bunkerweb").iterdir()) == []


@pytest.mark.parametrize("failure", ["http", "corrupt-zip", "missing-version", "unsafe-name", "database"])
def test_failed_download_or_publication_keeps_previous_generation(tmp_path, monkeypatch, failure):
    cache = _prepare(tmp_path)
    live = cache.job_path / "crs/plugins/previous"
    live.mkdir(parents=True)
    (live / "previous-config.conf").write_text("previous\n")
    manifest = cache.job_path / "crs-plugins.json"
    manifest.write_bytes(b'{"app.example": ["previous"]}')
    payload = _archive()
    if failure == "corrupt-zip":
        payload = b"not a ZIP"
    elif failure == "missing-version":
        content = BytesIO()
        with ZipFile(content, "w") as archive:
            archive.writestr("demo-config.conf", "# Plugin name: demo\n")
        payload = content.getvalue()
    elif failure == "unsafe-name":
        payload = _archive(name="../outside")
    elif failure == "database":
        cache.db.upsert_job_caches.side_effect = None
        cache.db.upsert_job_caches.return_value = "transaction rejected"
    get = Mock(return_value=_response(payload, 503 if failure == "http" else 200))
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env={"MODSECURITY_CRS_PLUGINS": "https://unit.invalid/plugin.zip"})
    assert status == 2
    assert (live / "previous-config.conf").read_text() == "previous\n"
    assert manifest.read_bytes() == b'{"app.example": ["previous"]}'
    assert sorted(path.name for path in live.parent.iterdir()) == ["previous"]
    if failure != "database":
        cache.db.upsert_job_caches.assert_not_called()


def test_empty_selection_publishes_empty_manifest_and_removes_old_plugins(tmp_path, monkeypatch):
    cache = _prepare(tmp_path)
    live = cache.job_path / "crs/plugins/obsolete"
    live.mkdir(parents=True)
    (live / "rules.conf").write_text("old")
    module, status = load_job(monkeypatch, tmp_path, JOB, cache=cache)
    assert status == 1
    assert list(module.CRS_PLUGINS_DIR.iterdir()) == []
    assert json.loads((cache.job_path / "crs-plugins.json").read_text()) == {"app.example": [], "alias.example": []}


def test_fresh_registry_resolves_named_version_once_for_two_services(tmp_path, monkeypatch):
    cache = _prepare(tmp_path)
    cache.cache_file("plugin_registry.json", json.dumps({"demo": {"repository": "https://github.com/unit/demo", "status": "tested"}}).encode())
    get = Mock(return_value=_response(_archive()))
    module, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        get=get,
        env={
            "MULTISITE": "yes",
            "SERVER_NAME": "one.example two.example",
            "one.example_MODSECURITY_CRS_PLUGINS": "demo/v1",
            "two.example_MODSECURITY_CRS_PLUGINS": "demo/v1",
        },
    )
    assert status == 1
    get.assert_called_once_with("https://github.com/unit/demo/archive/refs/tags/v1.zip", headers={"User-Agent": "BunkerWeb"}, stream=True, timeout=8)
    assert json.loads((cache.job_path / "crs-plugins.json").read_text()) == {"one.example": ["demo-1.2"], "two.example": ["demo-1.2"]}
    assert (module.CRS_PLUGINS_DIR / "demo-1.2").is_dir()


def test_registry_download_parses_table_and_chooses_latest_release(tmp_path, monkeypatch):
    cache = _prepare(tmp_path)
    registry = b"| Name | Repository | Status |\n| --- | --- | --- |\n| demo | [repo](https://github.com/unit/demo) | tested |\n"
    # get_download_url selects tar.gz for releases; provide a real gzip tar archive.
    tar_bytes = BytesIO()
    with ZipFile(BytesIO(_archive())) as zipped, tar_open(fileobj=tar_bytes, mode="w:gz") as tar:
        for name in zipped.namelist():
            blob = zipped.read(name)
            info = TarInfo(name)
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    get = Mock(side_effect=[_response(registry), _response(b'[{"prerelease": false, "tag_name": "v1"}]'), _response(tar_bytes.getvalue())])
    module, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env={"MODSECURITY_CRS_PLUGINS": "demo"})
    assert status == 1
    assert json.loads(cache.data["", "plugin_registry.json"])["demo"]["repository"] == "https://github.com/unit/demo"
    assert get.call_args.args[0] == "https://github.com/unit/demo/archive/refs/tags/v1.tar.gz"
    assert (module.CRS_PLUGINS_DIR / "demo-1.2/demo-config.conf").is_file()


@pytest.mark.parametrize("env", [{"USE_MODSECURITY_CRS_PLUGINS": "no"}, {"MODSECURITY_CRS_VERSION": "3"}, {"SERVER_NAME": ""}])
def test_disabled_or_incompatible_crs_leaves_live_tree_untouched(tmp_path, monkeypatch, env):
    cache = _prepare(tmp_path)
    live = cache.job_path / "crs/plugins/previous"
    live.mkdir(parents=True)
    (live / "rules.conf").write_text("old")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    assert status == 0
    assert (live / "rules.conf").read_text() == "old"
    cache.db.upsert_job_caches.assert_not_called()

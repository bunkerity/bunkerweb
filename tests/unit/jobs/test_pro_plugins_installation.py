"""PRO checks and installation never contact a real license or download endpoint."""

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import requests

from _other_jobs_helpers import load_job
from common_utils import bytes_hash, create_plugin_tar_gz

JOB = "pro/jobs/download-pro-plugins.py"


def database(**metadata):
    db = Mock()
    db.get_metadata.return_value = {
        "is_pro": False,
        "pro_license": "",
        "last_pro_check": None,
        "pro_status": "invalid",
        **metadata,
    }
    db.get_plugins.return_value = []
    db.set_metadata.return_value = ""
    db.update_external_plugins.return_value = ""
    return db


def response(status=200, content=b"", content_type="application/zip", data=None):
    result = requests.Response()
    result.status_code = status
    result._content = content
    result._content_consumed = True
    result.headers["Content-Type"] = content_type
    if data is not None:
        result._content = json.dumps(data).encode()
    return result


def archive():
    content = BytesIO()
    with ZipFile(content, "w") as zipped:
        zipped.writestr("sample/plugin.json", json.dumps({"id": "sample", "version": "1.0"}))
        zipped.writestr("sample/jobs/run.py", "print('ok')\n")
        zipped.writestr("sample/ui/page.py", "value = 1\n")
    return content.getvalue()


def test_preview_archive_installs_and_persists_exact_plugin(tmp_path, monkeypatch):
    db = database()
    get = Mock(return_value=response(content=archive()))
    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, get=get)
    assert status == 1
    installed = module.PRO_PLUGINS_DIR / "sample"
    assert (installed / "jobs/run.py").read_text() == "print('ok')\n"
    assert (installed / "jobs/run.py").stat().st_mode & 0o777 == 0o750
    plugins = db.update_external_plugins.call_args.args[0]
    assert [(p["id"], p["version"], p["type"], p["method"], p["page"]) for p in plugins] == [("sample", "1.0", "pro", "scheduler", True)]
    assert plugins[0]["checksum"] == bytes_hash(plugins[0]["data"], algorithm="sha256")
    assert db.set_metadata.call_args.args[0]["last_pro_check"].tzinfo is not None
    assert list(module.TMP_DIR.iterdir()) == []
    assert get.call_args.args[0].startswith(module.PREVIEW_ENDPOINT)


@pytest.mark.parametrize(
    ("http_status", "content_type", "expected"), [(404, "application/zip", 2), (429, "application/zip", 0), (500, "application/zip", 2), (200, "text/html", 2)]
)
def test_preview_failure_never_marks_successful_check(tmp_path, monkeypatch, http_status, content_type, expected):
    db = database()
    get = Mock(return_value=response(http_status, content_type=content_type))
    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, get=get)
    assert status == expected
    assert get.call_count == 1 and get.call_args.args[0] == module.PREVIEW_ENDPOINT + "/v1.6.18.zip"
    db.update_external_plugins.assert_not_called()
    assert all("last_pro_check" not in call.args[0] for call in db.set_metadata.call_args_list)
    assert not module.PRO_PLUGINS_DIR.exists()


def test_same_day_same_license_skips_download(tmp_path, monkeypatch):
    db = database(last_pro_check=datetime.now(timezone.utc).replace(tzinfo=None))
    get = Mock(side_effect=AssertionError("daily check should skip download"))
    _, status = load_job(monkeypatch, tmp_path, JOB, database=db, get=get)
    assert status == 0
    get.assert_not_called()
    db.set_metadata.assert_not_called()


@pytest.mark.parametrize("http_status, expected", [(403, 0), (429, 0), (500, 2)])
def test_license_status_errors_keep_installed_plugins(tmp_path, monkeypatch, http_status, expected):
    db = database(is_pro=True)
    get = Mock(return_value=response(http_status, content_type="application/json", data={}))
    module, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        database=db,
        env={"PRO_LICENSE_KEY": "unit-license"},
        get=get,
    )
    assert status == expected
    assert get.call_count == 1 and get.call_args.args[0] == module.API_ENDPOINT + "/pro/status"
    db.update_external_plugins.assert_not_called()
    assert not module.PRO_PLUGINS_DIR.exists()


def test_active_license_downloads_authenticated_archive(tmp_path, monkeypatch):
    db = database(is_pro=True)
    get = Mock(
        side_effect=[
            response(content_type="application/json", data={"data": {"pro_status": "active", "pro_services": 3, "pro_expire": "2099-01-01"}}),
            response(content=archive(), content_type="application/octet-stream"),
        ]
    )
    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, env={"PRO_LICENSE_KEY": "unit-license"}, get=get)
    assert status == 1
    assert [call.args[0] for call in get.call_args_list] == [module.API_ENDPOINT + "/pro/status", module.API_ENDPOINT + "/pro/download"]
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer unit-license"
    assert db.set_metadata.call_args_list[0].args[0]["is_pro"] is True
    assert (module.PRO_PLUGINS_DIR / "sample/plugin.json").is_file()


def test_database_failure_removes_only_new_plugins(tmp_path, monkeypatch):
    db = database()
    existing = tmp_path / "system/etc/bunkerweb/pro/plugins/existing"
    existing.mkdir(parents=True)
    (existing / "plugin.json").write_text('{"id": "existing", "version": "1"}')
    (existing / "code.lua").write_text("retained")
    db.get_plugins.return_value = [{"id": "existing", "version": "1", "method": "scheduler"}]
    db.update_external_plugins.return_value = "max_allowed_packet exceeded"
    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, get=Mock(return_value=response(content=archive())))
    assert status == 2
    db.update_external_plugins.assert_called_once()
    assert not (module.PRO_PLUGINS_DIR / "sample").exists()
    assert (existing / "code.lua").read_text() == "retained"
    assert all("last_pro_check" not in call.args[0] for call in db.set_metadata.call_args_list)


def test_license_connection_failures_are_bounded(tmp_path, monkeypatch):
    db = database()
    get = Mock(side_effect=requests.ConnectionError("offline"))
    _, status = load_job(monkeypatch, tmp_path, JOB, database=db, env={"PRO_LICENSE_KEY": "unit-license"}, get=get)
    assert status == 2
    assert get.call_count == 3
    db.update_external_plugins.assert_not_called()


def test_force_denied_download_keeps_metadata(tmp_path, monkeypatch):
    db = database(is_pro=True, force_pro_update=True)
    get = Mock(return_value=response(403, content_type="application/json", data={"action": "clean"}))
    _, status = load_job(monkeypatch, tmp_path, JOB, database=db, env={"PRO_LICENSE_KEY": "unit-license"}, get=get)
    assert status == 0
    assert get.call_count == 1
    assert get.call_args.args[0].endswith("/pro/download")
    db.set_metadata.assert_called_once_with({"force_pro_update": False})
    db.update_external_plugins.assert_not_called()


def test_clean_retains_metadata_and_removes_runtime_code(tmp_path, monkeypatch):
    db = database()
    module, _ = load_job(monkeypatch, tmp_path, JOB, database=db, get=Mock(return_value=response(429)))
    plugin = module.PRO_PLUGINS_DIR / "sample"
    (plugin / "jobs").mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"id": "sample"}')
    (plugin / "jobs/run.py").write_text("old")
    (plugin / "code.lua").write_text("old")
    invalid = module.PRO_PLUGINS_DIR / "invalid"
    invalid.mkdir()
    module.clean_pro_plugins(db)
    assert [path.name for path in plugin.iterdir()] == ["plugin.json"]
    assert not invalid.exists()
    assert module.cleaned_up_plugins is True
    db.update_external_plugins.assert_called_once_with([], _type="pro", only_clear_metadata=True)


@pytest.mark.parametrize("metadata", [None, "{invalid"])
def test_missing_or_invalid_manifest_is_rejected(tmp_path, monkeypatch, metadata):
    db = database()
    module, _ = load_job(monkeypatch, tmp_path, JOB, database=db, get=Mock(return_value=response(429)))
    source = tmp_path / "candidate"
    source.mkdir()
    if metadata is not None:
        (source / "plugin.json").write_text(metadata)
    assert module.install_plugin(source, db) is False
    assert not module.PRO_PLUGINS_DIR.exists()


def test_checksum_skip_and_forced_reinstall(tmp_path, monkeypatch):
    db = database()
    module, _ = load_job(monkeypatch, tmp_path, JOB, database=db, get=Mock(return_value=response(content=archive())))
    installed = module.PRO_PLUGINS_DIR / "sample"
    checksum = bytes_hash(create_plugin_tar_gz(installed, arc_root="sample"), algorithm="sha256")
    db.get_plugins.return_value = [{"id": "sample", "version": "1.0", "checksum": checksum, "method": "scheduler"}]
    source = tmp_path / "sample"
    source.mkdir()
    (source / "plugin.json").write_text(json.dumps({"id": "sample", "version": "1.0"}))
    assert module.install_plugin(source, db) is False
    assert (installed / "jobs/run.py").is_file()
    assert module.install_plugin(source, db, force=True) is True
    assert not (installed / "jobs").exists()

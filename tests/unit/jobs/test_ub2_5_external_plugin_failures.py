"""Failed downloads never publish plugins or replace the installed tree."""

import json
import logging
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from requests.exceptions import ConnectionError

from _other_jobs_helpers import load_job
from fixtures.seed import session
from model import Plugins

JOB = "misc/jobs/download-plugins.py"


def _zip():
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("sample/plugin.json", '{"id":"sample","version":"2"}')
        archive.writestr("sample/jobs/run.py", "print('job')")
    return content.getvalue()


def _response(status=200, content=b"broken archive"):
    return SimpleNamespace(status_code=status, iter_content=lambda **_: iter([content]))


def _installed(tmp_path):
    root = tmp_path / "system/etc/bunkerweb/plugins"
    plugin = root / "keep"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"id":"keep","version":"1"}')
    (plugin / "operator.txt").write_bytes(b"retained")
    return root


def _tree(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize(
    "case, suffix, message",
    [
        ("404", ".zip", "Got status code 404"),
        ("503", ".zip", "Got status code 503"),
        ("connection", ".zip", "Exception while downloading plugin(s)"),
        ("zip", ".zip", "Invalid ZIP file"),
        ("tar", ".tar", "Invalid TAR file"),
        ("unknown", ".txt", "Unknown file type"),
        ("partial", ".zip", "Exception while downloading plugin(s)"),
        ("partial-extract", ".zip", "Invalid ZIP file"),
        ("unsafe", ".zip", "Exception while decompressing plugin(s)"),
        ("missing-file", ".zip", "Exception while downloading plugin(s)"),
    ],
)
def test_failed_download_installs_nothing_and_reports_failure(db, tmp_path, monkeypatch, caplog, case, suffix, message):
    caplog.set_level(logging.INFO, logger="DOWNLOAD-EXTERNAL-PLUGINS")
    root = _installed(tmp_path)
    before = _tree(root)
    with session(db) as s:
        s.add(
            Plugins(
                id="keep", name="Keep", description="Operator plugin", version="1", type="external", method="ui", data=b"operator archive", checksum="retained"
            )
        )
    before_rows = db.get_plugins(_type="external", with_data=True)
    publish = Mock(wraps=db.update_external_plugins)
    monkeypatch.setattr(db, "update_external_plugins", publish)
    get = Mock(return_value=_response())
    url = "https://plugins.invalid/plugin" + suffix
    if case.isdigit():
        get.return_value = _response(int(case))
    elif case == "connection":
        get.side_effect = ConnectionError("offline")
    elif case == "missing-file":
        url = (tmp_path / "missing.zip").as_uri()
    elif case == "partial-extract":
        get.return_value = _response(content=_zip().replace(b"print('job')", b"print('bad')"))
    elif case == "unsafe":
        content = BytesIO()
        with ZipFile(content, "w") as archive:
            archive.writestr("sample/plugin.json", '{"id":"sample","version":"2"}')
            archive.writestr("../escape", "unsafe")
        get.return_value = _response(content=content.getvalue())
    elif case == "partial":

        def chunks(**_):
            yield _zip()
            raise ConnectionError("interrupted stream")

        get.return_value.iter_content = chunks

    module, status = load_job(monkeypatch, tmp_path, JOB, database=db, get=get, env={"EXTERNAL_PLUGIN_URLS": url})

    assert _tree(root) == before
    assert sorted(path.name for path in root.iterdir()) == ["keep"]
    assert db.get_plugins(_type="external", with_data=True) == before_rows
    publish.assert_not_called()
    assert not module.TMP_DIR.exists()
    assert status == 2
    assert message in caplog.text
    if case == "connection":
        assert get.call_count == 3
        assert caplog.text.count("retrying in 3 seconds") == 2


def test_connection_retries_can_recover_and_publish(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="DOWNLOAD-EXTERNAL-PLUGINS")
    database = Mock()
    database.get_plugins.return_value = []
    database.update_external_plugins.return_value = ""
    get = Mock(side_effect=[ConnectionError("offline"), ConnectionError("offline"), _response(content=_zip())])

    module, status = load_job(monkeypatch, tmp_path, JOB, database=database, get=get, env={"EXTERNAL_PLUGIN_URLS": "https://plugins.invalid/plugin.zip"})

    assert status == 1
    assert get.call_count == 3
    assert caplog.text.count("retrying in 3 seconds") == 2
    assert json.loads((module.EXTERNAL_PLUGINS_DIR / "sample/plugin.json").read_text()) == {"id": "sample", "version": "2"}
    assert [plugin["id"] for plugin in database.update_external_plugins.call_args.args[0]] == ["sample"]
    assert not module.TMP_DIR.exists()


@pytest.mark.parametrize("failed_first", [True, False])
def test_one_successful_download_does_not_hide_another_failure(tmp_path, monkeypatch, caplog, failed_first):
    database = Mock()
    database.get_plugins.return_value = []
    database.update_external_plugins.return_value = ""
    urls = ["https://plugins.invalid/bad.zip", "https://plugins.invalid/good.zip"]
    if not failed_first:
        urls.reverse()

    def get(url, **_):
        return _response(503) if url.endswith("bad.zip") else _response(content=_zip())

    module, status = load_job(monkeypatch, tmp_path, JOB, database=database, get=get, env={"EXTERNAL_PLUGIN_URLS": " ".join(urls)})

    assert status == 2
    assert "Got status code 503" in caplog.text
    assert (module.EXTERNAL_PLUGINS_DIR / "sample/plugin.json").is_file()
    assert [plugin["id"] for plugin in database.update_external_plugins.call_args.args[0]] == ["sample"]
    assert not module.TMP_DIR.exists()

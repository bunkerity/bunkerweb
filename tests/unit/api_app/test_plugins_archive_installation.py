"""Archive uploads persist safe plugin content and reject malformed/duplicate plugins."""

from hashlib import sha256
from io import BytesIO
import json
from tarfile import TarInfo, open as tar_open
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from _api_http_helpers import ADMIN_HEADERS, router_client

import app.routers.plugins as plugins


def archive(kind="zip", *, root="bundle", plugin_id="demo", metadata=None, with_meta=True):
    files = {"ui/index.html": b"plugin page", "jobs/check.py": b"print('ok')", "../escape.txt": b"outside", "/absolute.txt": b"outside"}
    if with_meta:
        files["plugin.json"] = metadata if metadata is not None else json.dumps({"id": plugin_id, "name": "Demo", "version": "1.0"}).encode()
    output = BytesIO()
    if kind == "zip":
        with ZipFile(output, "w") as zipped:
            zipped.writestr(f"{root}/" if root else "ui/", b"")
            for name, content in files.items():
                zipped.writestr(f"{root}/{name}" if root else name, content)
            if root:
                zipped.writestr("unrelated.txt", b"ignore")
    else:
        with tar_open(fileobj=output, mode="w:gz" if kind == "tar.gz" else "w:xz") as tar:
            directory = TarInfo(root or "ui")
            directory.type = b"5"
            tar.addfile(directory)
            for name, content in files.items():
                member = TarInfo(f"{root}/{name}" if root else name)
                member.size = len(content)
                tar.addfile(member, BytesIO(content))
            link = TarInfo(f"{root}/link")
            link.type = b"2"
            link.linkname = "/etc/passwd"
            tar.addfile(link)
            if root:
                other = TarInfo("unrelated.txt")
                other.size = 6
                tar.addfile(other, BytesIO(b"ignore"))
    return output.getvalue()


@pytest.fixture
def plugin_client(monkeypatch, tmp_path):
    db = Mock()
    db.get_plugins.return_value = []
    db.update_external_plugins.return_value = ""
    db.delete_plugin.return_value = ""
    monkeypatch.setattr(plugins, "TMP_UI_ROOT", tmp_path / "plugins")
    return router_client(monkeypatch, plugins, db), db, tmp_path


@pytest.mark.parametrize("kind,root", [("zip", "bundle"), ("zip", ""), ("tar.gz", "bundle"), ("tar.xz", "")])
def test_install_repackages_content_with_checksum_and_no_traversal(plugin_client, kind, root):
    client, db, tmp_path = plugin_client
    stale = tmp_path / "plugins/demo/old/nested"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("stale")
    response = client.post("/plugins/upload", headers=ADMIN_HEADERS, files={"files": (f"plugin.{kind}", archive(kind, root=root))})
    assert response.status_code == 201, response.text
    assert response.json() == {"status": "success", "created": ["demo"]}
    args, kwargs = db.update_external_plugins.call_args
    item = args[0][0]
    assert kwargs == {"_type": "ui", "delete_missing": False}
    assert {k: item[k] for k in ("id", "type", "page", "method")} == {"id": "demo", "type": "ui", "page": True, "method": "ui"}
    assert item["checksum"] == sha256(item["data"]).hexdigest()
    with tar_open(fileobj=BytesIO(item["data"]), mode="r:gz") as tar:
        assert tar.extractfile("demo/ui/index.html").read() == b"plugin page"
        assert all(not m.issym() and not (m.mode & 0o022) for m in tar.getmembers())
        assert not any("escape" in n or "stale" in n or "unrelated" in n for n in tar.getnames())
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize("kind", ["zip", "tar.gz"])
@pytest.mark.parametrize(
    "case,expected", [("missing", "plugin.json not found"), ("json", "Invalid plugin.json"), ("id", "Invalid plugin id"), ("duplicate", "already exists")]
)
def test_invalid_plugin_never_reaches_database(plugin_client, kind, case, expected):
    client, db, _ = plugin_client
    db.get_plugins.return_value = [{"id": "demo"}] if case == "duplicate" else []
    data = archive(kind, with_meta=case != "missing", metadata=b"{" if case == "json" else None, plugin_id="bad" if case == "id" else "demo")
    response = client.post("/plugins/upload", headers=ADMIN_HEADERS, files={"files": (f"plugin.{kind}", data)})
    assert response.status_code == 400
    assert response.json()["status"] == "error"
    assert expected in response.json()["errors"][0]["error"]
    db.update_external_plugins.assert_not_called()


@pytest.mark.parametrize(
    "filename,data,error", [("p.txt", b"x", "Unsupported archive format"), ("p.zip", b"x", "Invalid zip archive"), ("p.tar.gz", b"x", "Invalid tar archive")]
)
def test_bad_archive_reports_client_error(plugin_client, filename, data, error):
    client, db, _ = plugin_client
    response = client.post("/plugins/upload", headers=ADMIN_HEADERS, files={"files": (filename, data)})
    assert response.status_code == 400
    assert error in response.json()["errors"][0]["error"]
    db.update_external_plugins.assert_not_called()


def test_mixed_upload_reports_partial_success_and_duplicate(plugin_client):
    client, db, _ = plugin_client
    data = archive()
    response = client.post("/plugins/upload", headers=ADMIN_HEADERS, files=[("files", ("one.zip", data)), ("files", ("two.zip", data))])
    assert response.status_code == 207
    assert response.json()["created"] == ["demo"]
    assert response.json()["status"] == "partial"
    assert "already exists" in response.json()["errors"][0]["error"]
    assert db.update_external_plugins.call_count == 1


@pytest.mark.parametrize("kind", ["zip", "tar.gz"])
def test_database_failure_is_returned_without_claiming_install(plugin_client, kind):
    client, db, _ = plugin_client
    db.update_external_plugins.return_value = "database read-only"
    response = client.post("/plugins/upload", headers=ADMIN_HEADERS, files={"files": (f"p.{kind}", archive(kind))})
    assert response.status_code == 400
    assert response.json()["errors"] == [{"file": f"p.{kind}", "error": "database read-only"}]


def test_upload_requires_ui_method(plugin_client):
    client, db, _ = plugin_client
    response = client.post("/plugins/upload", headers=ADMIN_HEADERS, data={"method": "external"}, files={"files": ("p.zip", archive())})
    assert response.status_code == 422
    db.update_external_plugins.assert_not_called()


def test_listing_filter_and_delete_errors(plugin_client):
    client, db, _ = plugin_client
    db.get_plugins.return_value = [{"id": "demo"}]
    assert client.get("/plugins?type=pro&with_data=true", headers=ADMIN_HEADERS).json()["plugins"] == [{"id": "demo"}]
    db.get_plugins.assert_called_with(_type="pro", with_data=True)
    assert client.get("/plugins?type=invalid", headers=ADMIN_HEADERS).status_code == 422
    assert client.delete("/plugins/.bw-hidden", headers=ADMIN_HEADERS).status_code == 422
    db.delete_plugin.assert_not_called()
    db.delete_plugin.return_value = "not found"
    assert client.delete("/plugins/demo", headers=ADMIN_HEADERS).status_code == 404
    db.delete_plugin.return_value = ""
    assert client.delete("/plugins/demo", headers=ADMIN_HEADERS).json() == {"status": "success"}
    db.delete_plugin.assert_called_with("demo", "ui", changes=True)


@pytest.mark.parametrize("method,path", [("GET", "/plugins"), ("DELETE", "/plugins/demo"), ("POST", "/plugins/upload")])
def test_unauthenticated_plugin_access_is_refused(plugin_client, method, path):
    client, db, _ = plugin_client
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    db.update_external_plugins.assert_not_called()
    db.delete_plugin.assert_not_called()

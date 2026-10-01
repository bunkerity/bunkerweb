"""`/plugins/upload`: a file with an archive extension but no archive inside is refused with a
readable reason (QA-UI M27).

`bad.zip` holding plain text raised `zipfile.BadZipFile` straight out of the route: a 500, a
traceback in the UI log, and a bare "Failed" next to the file. Same for a broken tarball.
"""

import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "plugins.py"


@pytest.fixture(scope="module")
def route_module():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.DATA = {}
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.LOGGER = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DB = Mock()
    dependencies.PLUGIN_API = Mock()
    dependencies.CORE_PLUGINS_PATH = Path("/tmp/_core")
    dependencies.EXTERNAL_PLUGINS_PATH = Path("/tmp/_ext")
    dependencies.PRO_PLUGINS_PATH = Path("/tmp/_pro")
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._plugins_upload_invalid_archive_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client


@pytest.mark.parametrize("file_name", ["bad.zip", "bad.tar.gz", "bad.tar.xz"])
def test_a_non_archive_is_refused_with_a_reason_not_a_500(route_module, monkeypatch, tmp_path, file_name):
    module, client = route_module
    client.readonly = False
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True))
    monkeypatch.setattr(module, "TMP_DIR", tmp_path)
    monkeypatch.setattr(module, "translated", lambda key, **variables: f"<{key}>", raising=False)
    app = Flask(__name__)
    app.secret_key = "test"

    data = {"file": (BytesIO(b"this is not an archive\n"), file_name)}
    with app.test_request_context("/plugins/upload", method="POST", data=data, content_type="multipart/form-data"):
        body, status = module.upload_plugin.__wrapped__()

    assert status == 422
    assert body == {"status": "ko", "message": "<plugins.flash.invalid_archive>"}


@pytest.mark.parametrize("file_name", ["bomb.zip", "bomb.tar.gz"])
def test_an_archive_past_the_expansion_budget_is_refused_not_a_500(route_module, monkeypatch, tmp_path, file_name):
    """A multi-plugin upload is extracted in the route itself; `safe_*_extractall` refusing it
    (ValueError) must read like any other bad archive, and leave nothing extracted."""
    import tarfile
    import zipfile

    import common_utils  # type: ignore

    module, client = route_module
    client.readonly = False
    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True))
    monkeypatch.setattr(module, "TMP_DIR", tmp_path)
    monkeypatch.setattr(module, "translated", lambda key, **variables: f"<{key}>", raising=False)
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_EXTRACTED_BYTES", 1024)
    files = {"one/plugin.json": b"{}", "two/plugin.json": b"{}", "two/zeros.bin": b"\0" * 4096}
    archive = BytesIO()
    if file_name.endswith(".zip"):
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                zf.writestr(name, content)
    else:
        with tarfile.open(fileobj=archive, mode="w:gz") as tar:
            for name, content in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(content)
                tar.addfile(info, BytesIO(content))
    archive.seek(0)
    app = Flask(__name__)
    app.secret_key = "test"

    with app.test_request_context("/plugins/upload", method="POST", data={"file": (archive, file_name)}, content_type="multipart/form-data"):
        body, status = module.upload_plugin.__wrapped__()

    assert status == 422
    assert body == {"status": "ko", "message": "<plugins.flash.invalid_archive>"}
    assert not (tmp_path / "ui" / "two").exists()

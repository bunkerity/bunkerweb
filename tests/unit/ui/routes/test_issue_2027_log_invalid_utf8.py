"""Opening a log file that held invalid UTF-8 bytes was an HTTP 500 on the Logs page and on the support log export.

Pins that both read the file leniently: the bad bytes become replacement characters and the valid lines stay intact. Ref: #2027.
"""

from io import BytesIO
from zipfile import ZipFile

import pytest

BAD = b"valid before\nbroken \xff\xfe bytes\nvalid after\n"


@pytest.fixture
def logs(h, tmp_path, monkeypatch):
    module = h.routes.logs
    root = tmp_path / "bunkerweb"
    (root / "letsencrypt").mkdir(parents=True)
    monkeypatch.setattr(module, "LOGS_PATH", root)
    monkeypatch.setattr(module, "_LINECOUNT_CACHE", {})
    (root / "ui.log").write_bytes(BAD)
    return module


def test_the_logs_page_replaces_invalid_bytes_and_keeps_the_valid_lines(h, logs):
    response = h.client().get("/logs?file=ui.log")

    assert response.status_code == 200
    text = h.renders[-1][1]["logs"]
    assert "valid before" in text and "valid after" in text and "broken �� bytes" in text


def test_the_support_log_export_replaces_invalid_bytes(h, tmp_path, monkeypatch):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com"}
    monkeypatch.setattr(h.routes.support, "Path", lambda *parts: tmp_path)
    (tmp_path / "ui.log").write_bytes(BAD)

    response = h.client().get("/support/logs")

    assert response.status_code == 200
    content = ZipFile(BytesIO(response.get_data())).read("ui.log").decode()
    assert content == "valid before\nbroken �� bytes\nvalid after\n"

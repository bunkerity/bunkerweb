"""Report dates carry their UTC offset in the table, the CSV export and the Excel export (dev 8b9df2e5d, #4118).

`datetime.fromtimestamp(ts).isoformat()` yields an offset-less string. The browser reads one as ITS
local time, so a report shown by a viewer outside the UI container's zone was shifted by the
difference. The ban routes already send `.astimezone().isoformat()`; the reports routes did not.
"""

import csv
import importlib.util
import inspect
import io
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "reports.py"


class _Sheet:
    """What the Excel route uses of a worksheet: it records the rows it appends."""

    columns = ()

    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(list(row))

    def __getitem__(self, _index):
        return []


SHEETS = []


class _Workbook:
    def __init__(self):
        self.active = _Sheet()
        SHEETS.append(self.active)

    def save(self, output):
        output.write(b"xlsx")


@pytest.fixture
def reports_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = None
    dependencies.BW_INSTANCES_UTILS = Mock()
    openpyxl = ModuleType("openpyxl")
    openpyxl.Workbook = _Workbook
    openpyxl_styles = ModuleType("openpyxl.styles")
    openpyxl_styles.Font = Mock()
    openpyxl_styles.PatternFill = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._reports_date_offsets_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "openpyxl": openpyxl,
        "openpyxl.styles": openpyxl_styles,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def paris(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Paris")
    time.tzset()
    try:
        yield
    finally:
        monkeypatch.undo()
        time.tzset()


def _client(module):
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    for rule, view, methods in (
        ("/reports/fetch", module.reports_fetch, ["POST"]),
        ("/reports/export/csv", module.reports_export_csv, ["GET"]),
        ("/reports/export/excel", module.reports_export_excel, ["GET"]),
    ):
        app.add_url_rule(rule, endpoint=view.__name__, view_func=inspect.unwrap(view), methods=methods)
    return app.test_client()


@pytest.mark.parametrize("month, offset", [(1, 1), (7, 2)])
@pytest.mark.parametrize("path", ["fetch", "csv", "excel"])
def test_the_date_includes_the_offset_and_names_the_same_instant(reports_route, paris, monkeypatch, month, offset, path):
    timestamp = datetime(2026, month, 15, 10, 30, tzinfo=timezone.utc).timestamp()
    report = {"date": timestamp, "id": "abc"}
    monkeypatch.setattr(reports_route, "_query_reports", lambda **_kwargs: {"total": 1, "filtered": 1, "data": [report]})
    monkeypatch.setattr(reports_route, "_fetch_all_reports", lambda **_kwargs: [report])
    client = _client(reports_route)

    if path == "fetch":
        response = client.post("/reports/fetch")
        assert response.status_code == 200
        value = response.get_json()["data"][0]["date"]
    elif path == "csv":
        response = client.get("/reports/export/csv")
        assert response.status_code == 200
        value = list(csv.reader(io.StringIO(response.get_data(as_text=True))))[1][0]
    else:
        response = client.get("/reports/export/excel")
        assert response.status_code == 200
        value = SHEETS[-1].rows[1][0]

    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(hours=offset), value
    assert parsed.timestamp() == timestamp


def test_a_report_without_a_date_is_still_na(reports_route, monkeypatch):
    monkeypatch.setattr(reports_route, "_query_reports", lambda **_kwargs: {"total": 1, "filtered": 1, "data": [{"id": "abc"}]})

    response = _client(reports_route).post("/reports/fetch")

    assert response.get_json()["data"][0]["date"] == "N/A"

"""Browser and export dates retain their source instant outside UTC."""

import csv
import io
import time
from datetime import datetime, timedelta, timezone

import openpyxl
import pytest


@pytest.fixture
def paris_tz(monkeypatch):
    with monkeypatch.context() as patch:
        patch.setenv("TZ", "Europe/Paris")
        time.tzset()
        try:
            yield
        finally:
            patch.undo()
            time.tzset()


@pytest.mark.parametrize("month, offset", [(1, 1), (7, 2)])
@pytest.mark.parametrize("path", ["/reports/fetch", "/reports/export/csv", "/reports/export/excel", "ban"])
def test_dates_include_offset_and_preserve_timestamp(h, paris_tz, month, offset, path):
    timestamp = datetime(2026, month, 15, 10, 30, tzinfo=timezone.utc).timestamp()
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [{"date": timestamp}]}
    h.config.get_config.return_value = {}

    if path == "ban":
        value = h.routes.bans.format_ban({"date": timestamp})["date"]
    else:
        client = h.client()
        if path == "/reports/fetch":
            response = client.post(path, headers={"Sec-Fetch-Mode": "cors"})
            assert response.status_code == 200
            value = response.get_json()["data"][0]["date"]
        else:
            response = client.get(path)
            assert response.status_code == 200
            if path.endswith("csv"):
                value = list(csv.reader(io.StringIO(response.get_data(as_text=True))))[1][0]
            else:
                value = openpyxl.load_workbook(io.BytesIO(response.get_data())).active["A2"].value

    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(hours=offset)
    assert parsed.timestamp() == timestamp

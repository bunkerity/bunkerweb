"""`/bans/fetch`: the Date column carries its UTC offset, and the country/service panes label
what the row shows (QA-UI H7, M8).

H7: `format_ban` serialised the ban date with a naive `datetime.fromtimestamp(...).isoformat()`.
The UI container runs on UTC, the browser parses an offset-less ISO string as ITS local time, so
the Date column was shifted by the viewer's UTC offset while End Date (built offset-aware in
`_collect_all_bans`) was right.

M8: an IP with no country is stored with an EMPTY country, which the pane turned into
`/img/flags/.svg` and the label "— ."; and every global ban lands on the "_" service bucket,
which the pane labelled "default server" while the row says "All services".

Route loading follows `test_bans_flash_i18n.py`.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask


@pytest.fixture(scope="module")
def bans_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = None
    dependencies.BW_INSTANCES_UTILS = None
    openpyxl = ModuleType("openpyxl")
    openpyxl.Workbook = Mock()
    openpyxl_styles = ModuleType("openpyxl.styles")
    openpyxl_styles.Font = Mock()
    openpyxl_styles.PatternFill = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._bans_dates_and_panes_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "bans.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
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


BAN_DATE = 1_758_702_308  # 2025-09-24 08:25:08 UTC


def _fetch(module, monkeypatch, bans):
    monkeypatch.setattr(module, "_collect_all_bans", lambda: [dict(ban) for ban in bans])
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.bans)
    with app.test_request_context("/bans/fetch", method="POST", data={"draw": "1", "start": "0", "length": "10"}):
        response = module.bans_fetch.__wrapped__.__wrapped__()
    return response.get_json()


def test_the_date_column_is_offset_aware_and_names_the_same_instant(bans_route, monkeypatch):
    payload = _fetch(bans_route, monkeypatch, [{"ip": "1.2.3.4", "date": BAN_DATE, "country": "FR", "ban_scope": "global", "service": "unknown"}])

    date = payload["data"][0]["date"]
    parsed = datetime.fromisoformat(date)
    assert parsed.tzinfo is not None, f"naive ISO date {date!r}: the browser reads it as local time"
    assert parsed.timestamp() == BAN_DATE


def test_an_ip_without_country_gets_the_unknown_flag_and_label(bans_route, monkeypatch):
    payload = _fetch(bans_route, monkeypatch, [{"ip": "1.2.3.4", "date": BAN_DATE, "country": "", "ban_scope": "global", "service": "unknown"}])

    (option,) = payload["searchPanes"]["options"]["country"]
    assert "/.svg" not in option["label"], option["label"]
    assert "flags/zz.svg" in option["label"], option["label"]
    assert 'data-i18n="country.not_applicable"' in option["label"], option["label"]


def test_a_global_ban_is_listed_under_all_services_not_the_default_server(bans_route, monkeypatch):
    payload = _fetch(bans_route, monkeypatch, [{"ip": "1.2.3.4", "date": BAN_DATE, "country": "FR", "ban_scope": "global", "service": "unknown"}])

    (option,) = payload["searchPanes"]["options"]["service"]
    assert option["value"] == "_"
    assert "default server" not in option["label"], option["label"]
    assert 'data-i18n="scope.all_services"' in option["label"], option["label"]

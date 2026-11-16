"""Bans page: permanent bans count in "More than 30 days", and "time left" sorts by remaining time (dev 53e745781).

The pane's `end_date` filter already kept a permanent ban under `future_30d`, but the option's
total/count excluded it, so the badge disagreed with the rows shown. Sorting by "time left" compared
a `time_left` key no ban carries (every row ties), where dev sorts by the remaining seconds with
permanent bans last in both directions.

Route loading follows `test_bans_dates_and_panes.py`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

BAN_DATE = 1_758_702_308


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
    module_name = "app.routes._bans_time_left_test"
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


def _ban(index, exp, permanent=False):
    return {
        "ip": f"192.0.2.{index}",
        "date": BAN_DATE,
        "exp": exp,
        "permanent": permanent,
        "remain": "permanent" if permanent else f"{exp}s",
        "end_date": "permanent" if permanent else f"2026-01-01T00:00:{index:02d}",
        "country": "FR",
        "ban_scope": "global",
        "service": "unknown",
    }


FEED = [_ban(1, 600), _ban(2, 90), _ban(3, 0, permanent=True), _ban(4, 86400 * 40), _ban(5, 3600)]


def _sorted(module, direction):
    column = module._BAN_COLUMNS.index("time_left")
    return [ban["ip"] for ban in module._filter_and_sort_bans(list(FEED), "", {}, column, direction)]


def test_time_left_ascending_follows_the_remaining_time_with_permanent_last(bans_route):
    assert _sorted(bans_route, "asc") == [f"192.0.2.{index}" for index in (2, 1, 5, 4, 3)]


def test_time_left_descending_follows_the_remaining_time_with_permanent_last(bans_route):
    assert _sorted(bans_route, "desc") == [f"192.0.2.{index}" for index in (4, 5, 1, 2, 3)]


def test_time_left_sort_is_numeric_not_textual(bans_route):
    # "9000" > "10000" as text; as seconds the order is the reverse.
    feed = [_ban(1, 10000), _ban(2, 9000)]
    column = bans_route._BAN_COLUMNS.index("time_left")

    ordered = [ban["ip"] for ban in bans_route._filter_and_sort_bans(feed, "", {}, column, "asc")]

    assert ordered == ["192.0.2.2", "192.0.2.1"]


def test_the_more_than_30_days_pane_counts_the_permanent_bans_it_shows(bans_route, monkeypatch):
    monkeypatch.setattr(bans_route, "_collect_all_bans", lambda: [dict(ban) for ban in FEED])
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    app.register_blueprint(bans_route.bans)
    with app.test_request_context("/bans/fetch", method="POST", data={"draw": "1", "start": "0", "length": "10"}):
        payload = bans_route.bans_fetch.__wrapped__.__wrapped__().get_json()

    option = next(item for item in payload["searchPanes"]["options"]["end_date"] if item["value"] == "future_30d")
    assert option["total"] == option["count"] == 2  # the 40-day ban and the permanent one


def test_the_filter_and_the_badge_agree(bans_route):
    column = bans_route._BAN_COLUMNS.index("end_date")
    shown = bans_route._filter_and_sort_bans(list(FEED), "", {"end_date": ["future_30d"]}, column, "asc")

    assert sorted(ban["ip"] for ban in shown) == ["192.0.2.3", "192.0.2.4"]

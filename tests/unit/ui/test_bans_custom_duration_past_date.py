"""`/bans/update_duration`, duration="custom": a past custom end date is silently accepted
(QA-UI M30, second half).

Root cause (`bans.py` in the `duration == "custom"` branch): both the JS payload builder and
this route clamp the computed remaining seconds with `max(0, ...)`. `exp == 0` is the sentinel
this codebase uses for a PERMANENT ban (`duration == "permanent": new_exp = 0`, and
`_collect_all_bans`'s `ban.get("exp") == 0` check). So picking a date already in the past does
not get refused: it gets silently turned into a permanent ban, and the route still flashes
"Updated ban duration ... successfully." The JS always sends both `end_date` and a pre-clamped
`custom_exp`, so the server must treat `end_date` as authoritative (it can still see the sign)
rather than trust the client's already-clamped `custom_exp`.

Route loading follows `test_bans_flash_i18n.py`.
"""

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from json import dumps
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages


@pytest.fixture(scope="module")
def bans_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
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

    module_name = "app.routes._bans_custom_duration_past_date_test"
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


@pytest.fixture(autouse=True)
def _a_writing_session(bans_route, monkeypatch):
    monkeypatch.setattr(bans_route, "is_readonly_request", lambda api_readonly: api_readonly)


@pytest.fixture
def route_app(bans_route):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(bans_route.bans)
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "", methods=["GET"])
    return bans_route, app


def _update_duration(module, app, monkeypatch, end_date: str):
    # translated() calls flask_babel's gettext, which needs the extension registered on the
    # app; that's covered by test_bans_flash_i18n.py, not this fix, so fall back to English.
    monkeypatch.setattr(module, "translated", lambda key, **variables: None)
    module.API_CLIENT.readonly = False
    module.API_CLIENT.get_bans.return_value = []
    module.API_CLIENT.ban.reset_mock()
    # Mirror bans.js exactly: it always sends both fields, and `custom_exp` is pre-clamped with
    # `Math.max(0, ...)` client-side -- so a past date and a genuinely zero-length one look
    # identical by the time `custom_exp` reaches the server. Only `end_date` still carries the sign.
    remaining = int(datetime.fromisoformat(end_date).timestamp() - datetime.now(timezone.utc).timestamp())
    updates = [
        {
            "ip": "1.2.3.4",
            "duration": "custom",
            "ban_scope": "global",
            "service": "",
            "end_date": end_date,
            "custom_exp": max(0, remaining),
        }
    ]
    with app.test_request_context(
        "/bans/update_duration",
        method="POST",
        data={"selection_mode": "explicit", "updates": dumps(updates)},
    ):
        module.bans_update_duration.__wrapped__()
        messages = get_flashed_messages(with_categories=True)
    return messages


def test_a_past_custom_end_date_is_refused_not_turned_permanent(bans_route, route_app, monkeypatch):
    module, app = route_app
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    messages = _update_duration(module, app, monkeypatch, past)

    module.API_CLIENT.ban.assert_not_called()
    assert messages, "a past custom end date must flash an error instead of failing silently"
    assert messages[0][0] == "error"


def test_a_future_custom_end_date_still_succeeds(bans_route, route_app, monkeypatch):
    module, app = route_app
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    messages = _update_duration(module, app, monkeypatch, future)

    module.API_CLIENT.ban.assert_called_once()
    (payload,), _kwargs = module.API_CLIENT.ban.call_args
    assert payload[0]["exp"] > 0, "a future custom date must not collapse to the permanent (0) sentinel"
    # app.utils.flash() only passes a Flask category for non-"success" calls, so a success flash
    # lands in Flask's default "message" bucket.
    assert messages == [("message", "Updated ban duration for 1.2.3.4 successfully.")]

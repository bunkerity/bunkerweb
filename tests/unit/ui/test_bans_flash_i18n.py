"""``bans.py``'s flash() calls now route through ``app.i18n.translated`` (wave-13 RES-1 item 3),
matching the ``translated(key, **vars) or "English fallback"`` idiom ``login.py`` already uses
for ``notice.dismiss_mfa``. Two things have to hold at once, so both get a test:

* until the key is merged into the catalog, ``translated()`` returns None and the user must see
  the exact same English sentence the route flashed before this change (no user-visible regression);
* once the key *is* translated, the route must actually surface that translation rather than
  always falling back to the hardcoded English (proving the ``translated()`` call is live, not
  dead code sitting in front of an ``or`` that never triggers).

Route loading follows ``test_bans_stats.py``'s module-loader pattern.
"""

import importlib.util
import sys
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
    from pathlib import Path

    module_name = "app.routes._bans_flash_i18n_test"
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


@pytest.fixture
def route_app(bans_route):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(bans_route.bans)
    # bans_ban()/bans_unban()/bans_update_duration() all end with a redirect to "loading" --
    # unregistered in this route-only app, so url_for() would raise BuildError before the flash
    # under test is even reached.
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "", methods=["GET"])
    return bans_route, app


def _ban_one_invalid_ip(module, app, monkeypatch, translated_stub):
    """Post a single malformed IP through /bans/ban and return the flashed (category, message)."""
    module.API_CLIENT.readonly = False
    calls = []

    def recording_translated(key, **variables):
        calls.append((key, variables))
        return translated_stub(key, **variables)

    monkeypatch.setattr(module, "translated", recording_translated)

    with app.test_request_context("/bans/ban", method="POST", data={"bans": '[{"ip": "not-an-ip"}]'}):
        module.bans_ban.__wrapped__()
        messages = get_flashed_messages(with_categories=True)

    return messages, calls


def test_invalid_ip_flash_falls_back_to_the_original_english_when_untranslated(route_app, monkeypatch):
    """No behaviour change while the key is unmerged: `translated()` returns None (catalog
    miss, exactly what a real gettext lookup does for a key that does not exist yet) and the
    flash must read exactly as it did before this lane touched the file."""
    module, app = route_app

    messages, calls = _ban_one_invalid_ip(module, app, monkeypatch, lambda key, **variables: None)

    assert messages == [("error", "Invalid IP address: not-an-ip")]
    assert calls == [("bans.flash.invalid_ip", {"ip": "not-an-ip"})]


def test_invalid_ip_flash_uses_the_catalog_once_it_is_translated(route_app, monkeypatch):
    """Once `bans.flash.invalid_ip` lands in the catalog, `translated()` returns a real string
    and the route must surface it -- not silently keep flashing the hardcoded English. This is
    what would stay red if the `or "Invalid IP address: ..."` fallback were the only path (e.g.
    a stray `translated(...) and fallback` typo, or the call being deleted outright and only the
    hardcoded string left behind)."""
    module, app = route_app

    messages, calls = _ban_one_invalid_ip(
        module,
        app,
        monkeypatch,
        lambda key, **variables: f"[translated] not a valid address: {variables['ip']}",
    )

    assert messages == [("error", "[translated] not a valid address: not-an-ip")]
    assert calls == [("bans.flash.invalid_ip", {"ip": "not-an-ip"})]

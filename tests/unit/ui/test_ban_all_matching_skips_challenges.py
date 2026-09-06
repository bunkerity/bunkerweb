""" "Ban all matching reports" must not ban a client that was only challenged.

The Reports page's bulk action (``static/js/pages/reports.js``, ``selection_mode=filtered``) does
not send a list of IPs — it re-runs the report query server-side and bans every row it returns
(``routes/bans.py::_get_filtered_report_bans``). That was safe while every report row was a request
something had blocked.

It stopped being safe the moment a plugin could record a reason for a remediation that let the
client through: antibot records one for every challenge page it serves, CrowdSec for a served
AppSec challenge or captcha, a workflow rule for a redirect. Those rows are in Reports on purpose —
the operator asked to see them — but one click on an *unfiltered* Reports page would then ban every
visitor who was merely shown a captcha. On a feature that is on by default, that is a self-inflicted
outage, and the operator's own users are the casualties.

The skip is keyed on the remediation the plugin recorded (``reason_data.action``) rather than on the
reason token, so a future plugin that challenges instead of blocking inherits it. Same rule, same
keying as the guard in ``bunkernet:log()``.

Loads ``routes/bans.py`` through ``test_bans_timeseries_panel.py``'s module-loader fixture shape:
stub ``app.dependencies`` and the container-only imports, then exec the file.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

UI = Path(__file__).resolve().parents[3] / "src" / "ui"


@pytest.fixture(scope="module")
def bans_route():
    instances = Mock()
    config = Mock()
    config.get_config.return_value = {}
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = config
    dependencies.BW_INSTANCES_UTILS = instances
    openpyxl = ModuleType("openpyxl")
    openpyxl.Workbook = Mock()
    openpyxl_styles = ModuleType("openpyxl.styles")
    openpyxl_styles.Font = Mock()
    openpyxl_styles.PatternFill = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._bans_ban_all_test"
    spec = importlib.util.spec_from_file_location(module_name, UI / "app" / "routes" / "bans.py")
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
        yield module, instances


def _row(request_id, ip, reason, action=None, **over):
    row = {
        "request_id": request_id,
        "ip": ip,
        "reason": reason,
        "server_name": "app.example.com",
        "data": {} if action is None else {"action": action},
    }
    row.update(over)
    return row


def _targets(bans_route, rows):
    module, instances = bans_route
    instances.get_reports_query.return_value = {"data": rows}
    return module._get_filtered_report_bans({})


def test_the_no_instances_early_return_matches_the_unpacking_caller(bans_route):
    """``bans_ban()`` unpacks the result as ``bans, skipped = …``. The early return when there is no
    instances utility is dead code today — ``InstancesUtils`` defines no ``__bool__`` so it is always
    truthy — but a bare ``return []`` there is a ``ValueError`` waiting for the day it is not, in the
    one branch no other test reaches."""
    module, instances = bans_route
    with patch.object(module, "BW_INSTANCES_UTILS", None):
        targets, skipped = module._get_filtered_report_bans({})
    assert (targets, skipped) == ([], 0)


class TestAChallengedClientIsNotABanTarget:
    def test_an_antibot_challenge_is_skipped(self, bans_route):
        targets, skipped = _targets(
            bans_route,
            [_row("challenged", "1.1.1.1", "antibot", "challenge", data={"source": "antibot", "provider": "captcha", "action": "challenge"})],
        )
        assert targets == []
        assert skipped == 1

    def test_a_crowdsec_captcha_is_skipped(self, bans_route):
        targets, skipped = _targets(bans_route, [_row("captcha", "1.1.1.1", "crowdsec", "captcha")])
        assert targets == []
        assert skipped == 1

    def test_a_workflow_redirect_is_skipped(self, bans_route):
        targets, skipped = _targets(bans_route, [_row("redirected", "2.2.2.2", "workflows", "redirect")])
        assert targets == []
        assert skipped == 1

    def test_the_action_is_matched_case_insensitively(self, bans_route):
        targets, skipped = _targets(bans_route, [_row("challenged", "1.1.1.1", "antibot", "Challenge")])
        assert targets == []
        assert skipped == 1


class TestARealBlockIsStillABanTarget:
    def test_a_plain_block_is_kept(self, bans_route):
        """The control. Without it the tests above would pass on a function that returned nothing."""
        targets, skipped = _targets(bans_route, [_row("blocked", "9.9.9.9", "blacklist")])
        assert [t["ip"] for t in targets] == ["9.9.9.9"]
        assert skipped == 0

    def test_a_crowdsec_ban_is_kept(self, bans_route):
        targets, _ = _targets(bans_route, [_row("banned", "9.9.9.9", "crowdsec", "ban")])
        assert [t["ip"] for t in targets] == ["9.9.9.9"]

    def test_a_workflow_block_is_kept(self, bans_route):
        targets, _ = _targets(bans_route, [_row("blocked", "9.9.9.9", "workflows", "block")])
        assert [t["ip"] for t in targets] == ["9.9.9.9"]

    def test_a_mixed_page_bans_only_the_blocked_and_counts_the_rest(self, bans_route):
        """The realistic shape: a busy antibot service where the attacker is a minority of rows."""
        targets, skipped = _targets(
            bans_route,
            [
                _row("c1", "1.1.1.1", "antibot", "challenge"),
                _row("c2", "1.1.1.2", "antibot", "challenge"),
                _row("blocked", "9.9.9.9", "modsecurity"),
                _row("c3", "1.1.1.3", "crowdsec", "challenge"),
            ],
        )
        assert [t["ip"] for t in targets] == ["9.9.9.9"]
        assert skipped == 3

    def test_a_badbehavior_array_payload_does_not_crash(self, bans_route):
        """``data`` is whatever JSON the plugin stored, and badbehavior's is an **array** of per-IP
        increment records (``badbehavior.lua``) that the ban replay carries into the report. A
        ``.get`` on it raises ``AttributeError`` inside a route with no ``try`` around the call —
        a 500 on the very button this guard protects, on a plugin that is on by default. The JS
        twin already pins this shape (``test_a_badbehavior_ban_payload_is_left_alone``)."""
        targets, skipped = _targets(bans_route, [_row("bb", "9.9.9.9", "bad behavior", data=[{"ip": "9.9.9.9", "count": 12}])])
        assert [t["ip"] for t in targets] == ["9.9.9.9"]
        assert skipped == 0

    def test_a_string_payload_does_not_crash(self, bans_route):
        """Same class: a plugin that stored a bare JSON scalar."""
        targets, skipped = _targets(bans_route, [_row("odd", "9.9.9.9", "blacklist", data="challenge")])
        assert [t["ip"] for t in targets] == ["9.9.9.9"]
        assert skipped == 0

    def test_a_null_payload_does_not_skip(self, bans_route):
        """``data`` is nullable on a row written before reason_data existed; indexing it must not
        turn every legacy report into a non-target."""
        targets, skipped = _targets(bans_route, [_row("legacy", "9.9.9.9", "blacklist", data=None)])
        assert [t["ip"] for t in targets] == ["9.9.9.9"]
        assert skipped == 0

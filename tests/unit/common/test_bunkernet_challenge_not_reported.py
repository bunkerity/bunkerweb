"""A challenged visitor is not reported to the shared BunkerNet database as an attacker.

``bunkernet:log()`` opens with ``-- Check if IP has been blocked`` and then uses
``utils.get_reason(ctx)`` as that test: a reason exists, therefore the IP was blocked, therefore
push it to BunkerNet. ``USE_BUNKERNET`` defaults to **yes**, so this runs on nearly every install.

That equivalence used to hold — a reason implied a 4xx, or a detect-mode would-be block. It does
not any more. Three plugins now record a reason for a remediation that *let the client carry on*:

* ``crowdsec`` on a served AppSec challenge or captcha (the row is a 200),
* ``antibot`` on every challenge page it serves (also a 200),
* ``workflows`` on a redirect action (a 3xx).

Those are precisely the rows ``is_report()`` keeps on their reason rather than on a status. Without
the guard this file pins, every unidentified visitor of an antibot-protected service — most of them
human, which is the entire point of a challenge — is published to a shared threat feed. The dedup
key is ``ip .. "_" .. reason``, so it is once per distinct visitor, not once per request; that is
not a mitigation.

The guard keys on ``reason_data.action`` — the remediation the plugin recorded — and not on the
reason token, so a future plugin that challenges instead of blocking inherits the behaviour without
editing bunkernet.lua.

The shipped guard is spliced out and run through the ``lua`` binary against stubs, so what is
proven is the branch taken for a given payload, not the spelling of the condition.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BUNKERNET_LUA = ROOT / "src" / "common" / "core" / "bunkernet" / "bunkernet.lua"
SOURCE = BUNKERNET_LUA.read_text(encoding="utf-8")

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# Everything from the "Check if IP has been blocked" comment down to the "Check if IP is global"
# one: the whole decision about whether this request is reportable at all. Sliced rather than
# hand-copied so a rewrite of the guard is executed here rather than silently bypassed.
GUARD = re.search(
    r"\t-- Check if IP has been blocked\n(.*?)\n\t-- Check if IP is global",
    SOURCE,
    re.S,
)


def _reaches_the_report(reason, reason_data):
    """Run the shipped guard and report whether control fell through to the reporting code."""
    assert LUA is not None
    assert GUARD, "the reportability guard is gone from bunkernet:log() — did it get rewritten?"
    data = "nil" if reason_data is None else "{ " + ", ".join(f"{k} = [==[{v}]==]" for k, v in reason_data.items()) + " }"
    reason_literal = "nil" if reason is None else f"[==[{reason}]==]"
    script = "\n".join(
        [
            f"local REASON, REASON_DATA = {reason_literal}, {data}",
            "local function get_reason() return REASON, REASON_DATA end",
            # plugin:ret() returns a table; only whether we returned early matters here.
            "local self = { ctx = {}, ret = function(self, ok, msg) return { returned = true, msg = msg } end }",
            "local function log()",
            GUARD.group(1),
            "  return { returned = false }",
            "end",
            "local out = log()",
            "print('RETURNED=' .. tostring(out.returned) .. '|' .. tostring(out.msg))",
        ]
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    returned, message = result.stdout.strip().split("=", 1)[1].split("|", 1)
    return returned == "false", message


@needs_lua
class TestAServedRemediationIsNotAnAttack:
    def test_an_antibot_challenge_is_not_reported(self):
        """The regression this guard exists for: one report per unidentified visitor, worldwide."""
        reported, message = _reaches_the_report("antibot", {"source": "antibot", "provider": "captcha", "action": "challenge"})
        assert not reported, "an antibot challenge reached the BunkerNet report"
        assert "not blocked" in message

    def test_a_crowdsec_appsec_challenge_is_not_reported(self):
        """Same shape, recorded by crowdsec:access() on its served branch."""
        reported, _ = _reaches_the_report("crowdsec", {"source": "appsec", "action": "challenge", "http_status": "200"})
        assert not reported

    def test_a_crowdsec_captcha_is_not_reported(self):
        """A captcha is an invitation to prove you are human, not a verdict that you are not."""
        reported, _ = _reaches_the_report("crowdsec", {"source": "lapi", "action": "captcha"})
        assert not reported

    def test_a_workflow_redirect_is_not_reported(self):
        reported, _ = _reaches_the_report("workflows", {"workflow": "api-shield", "rule": "r1", "action": "redirect"})
        assert not reported


@needs_lua
class TestARealBlockStillIs:
    def test_a_crowdsec_ban_is_still_reported(self):
        """The guard must not become "never report anything with a payload"."""
        reported, _ = _reaches_the_report("crowdsec", {"source": "lapi", "action": "ban", "scenario": "crowdsecurity/http-probing"})
        assert reported

    def test_a_workflow_block_is_still_reported(self):
        reported, _ = _reaches_the_report("workflows", {"workflow": "api-shield", "rule": "r1", "action": "block"})
        assert reported

    def test_a_plain_blacklist_block_is_still_reported(self):
        """Most reasons carry a payload with no ``action`` field at all; indexing it must not
        change their verdict."""
        reported, _ = _reaches_the_report("blacklist", {"kind": "ip"})
        assert reported

    def test_a_reason_with_no_payload_is_still_reported(self):
        reported, _ = _reaches_the_report("modsecurity", None)
        assert reported

    def test_no_reason_is_still_not_reported(self):
        reported, message = _reaches_the_report(None, None)
        assert not reported
        assert "not blocked" in message

    def test_bunkernet_own_reason_is_still_skipped(self):
        reported, _ = _reaches_the_report("bunkernet", {"action": "ban"})
        assert not reported

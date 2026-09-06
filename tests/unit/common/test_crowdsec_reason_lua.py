"""A CrowdSec remediation names itself in the report/ban reason.

Before this, every CrowdSec row read ``crowdsec`` and nothing else — a LAPI ban, an AppSec
bot-detection challenge and a captcha were indistinguishable in Reports, and the two that do not
end on a 403 were not even shown. Two things had to hold:

* ``csmod.Allow()`` must hand back a verdict table (``source``, ``action``, ``http_status``, plus
  ``scenario``/``origin``/``duration`` on a live LAPI decision) on every remediation, including
  the ``no_render`` path that ``SECURITY_MODE=detect`` takes — detect is precisely where the
  bouncer's own ALERT lines never fire, so the verdict is the *only* record of which remediation
  was suppressed.
* ``crowdsec:access()`` must attach it. On the deny branch that means passing it as ``ret.data``,
  which the dispatcher stores. On the *served* branch it means calling ``set_reason()`` by hand:
  a served challenge ends the access phase with ``ngx.OK``, which is not in the dispatcher's
  ``reason_statuses``, so the dispatcher records nothing at all and the security action would be
  invisible.

The bouncer half runs the shipped ``csmod.Allow`` through the ``lua`` binary, reusing the harness
of ``test_crowdsec_challenge_lua`` (same file, same splicing). The plugin half is asserted on the
shipped source of ``crowdsec:access()``: it closes over the whole BunkerWeb plugin base class and
the dispatcher, and what matters there is the wiring, not a re-execution of it.
"""

import re
from pathlib import Path

from test_crowdsec_challenge_lua import CHALLENGE_JSON, field, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "crowdsec.lua"

# A live LAPI decision, the shape lib/bouncer.lua's live_query() hands back to Allow().
LAPI_DECISION = {
    "type": "ban",
    "scenario": "crowdsecurity/http-probing",
    "origin": "crowdsec",
    "duration": "3h59m",
}

VERDICT_DUMP = """
local ok, msg, banned, served, verdict = csmod.Allow("1.2.3.4", NO_RENDER_ARG)
print("RET=" .. tostring(ok) .. "|" .. tostring(banned) .. "|" .. tostring(served))
if verdict == nil then
  print("VERDICT=nil")
else
  print("VERDICT_SOURCE=" .. tostring(verdict.source))
  print("VERDICT_ACTION=" .. tostring(verdict.action))
  print("VERDICT_STATUS=" .. tostring(verdict.http_status))
  print("VERDICT_SCENARIO=" .. tostring(verdict.scenario))
  print("VERDICT_ORIGIN=" .. tostring(verdict.origin))
  print("VERDICT_DURATION=" .. tostring(verdict.duration))
end
dump()
"""


def _lapi_body(no_render: bool) -> str:
    """Override the harness' allowIp stub with one that also returns the decoded decision, the
    fourth value live_query() carries so Allow() can name the scenario."""
    decision = "{ " + ", ".join(f'["{k}"] = "{v}"' for k, v in LAPI_DECISION.items()) + " }"
    return (
        "csmod.allowIp = function() return false, "
        + f'"{LAPI_DECISION["type"]}", nil, {decision} end\n'
        + f"NO_RENDER_ARG = {'true' if no_render else 'false'}\n"
        + VERDICT_DUMP
    )


class TestTheVerdictReachesTheCaller:
    def test_an_appsec_challenge_names_itself(self):
        out = run(VERDICT_DUMP.replace("NO_RENDER_ARG", "false"), allowip_ok=True)
        assert field(out, "RET") == "true|false|true", "the challenge page was served"
        assert field(out, "VERDICT_SOURCE") == "appsec"
        assert field(out, "VERDICT_ACTION") == "challenge"
        assert field(out, "VERDICT_STATUS") == str(CHALLENGE_JSON["http_status"])
        # AppSec verdicts do not come from a LAPI decision, so there is no scenario to name
        assert field(out, "VERDICT_SCENARIO") == "nil"

    def test_a_lapi_ban_names_its_scenario(self):
        out = run(_lapi_body(no_render=False), conf={"APPSEC_ENABLED": False})
        assert field(out, "RET") == "true|true|nil", "the request was denied"
        assert field(out, "VERDICT_SOURCE") == "lapi"
        assert field(out, "VERDICT_ACTION") == "ban"
        assert field(out, "VERDICT_SCENARIO") == LAPI_DECISION["scenario"]
        assert field(out, "VERDICT_ORIGIN") == LAPI_DECISION["origin"]
        assert field(out, "VERDICT_DURATION") == LAPI_DECISION["duration"]

    def test_detect_mode_still_gets_the_verdict(self):
        """no_render returns before anything is written. The bouncer's ALERT lines are inside the
        render branches, so without this the suppressed remediation is recorded nowhere."""
        out = run(VERDICT_DUMP.replace("NO_RENDER_ARG", "true"), allowip_ok=True)
        assert field(out, "RET") == "true|true|nil", "detect reports, never renders"
        assert field(out, "BODY") == "", "detect must not write a body"
        assert field(out, "VERDICT_SOURCE") == "appsec"
        assert field(out, "VERDICT_ACTION") == "challenge"

    def test_a_malformed_challenge_reports_the_fallback_it_took(self):
        """The empty-body fallback rewrites `remediation`; the verdict must follow it, or the
        report claims a challenge was served when a ban was applied."""
        broken = dict(CHALLENGE_JSON)
        broken["user_body_content"] = ""
        out = run(VERDICT_DUMP.replace("NO_RENDER_ARG", "false"), appsec_json=broken)
        assert field(out, "RET") == "true|true|nil", "it fell back to a ban"
        assert field(out, "VERDICT_ACTION") == "ban"
        assert field(out, "VERDICT_SOURCE") == "appsec"

    def test_an_allowed_request_allocates_no_verdict(self):
        """The allow path is the hot path: no table per request."""
        out = run(
            VERDICT_DUMP.replace("NO_RENDER_ARG", "false"),
            allowip_ok=True,
            conf={"APPSEC_ENABLED": False},
        )
        assert field(out, "RET") == "true|nil|nil"
        assert field(out, "VERDICT") == "nil"


class TestThePluginAttachesIt:
    """Source-level, on the shipped crowdsec:access()."""

    @staticmethod
    def _access() -> str:
        source = CROWDSEC_LUA.read_text(encoding="utf-8")
        match = re.search(r"^function crowdsec:access\(\).*?^end$", source, re.S | re.M)
        assert match, "crowdsec:access() is gone from crowdsec.lua"
        return match.group(0)

    def test_the_verdict_is_read_off_allow(self):
        """Matched on the destructuring alone, not on the whole call: lane CS-B added a sixth
        return value (`antibot_provider`) and stylua then wrapped the call onto its own line, so a
        literal that spans the `= bouncer.Allow(` boundary pins formatting rather than behaviour."""
        assert "local ok, err, banned, served, verdict" in self._access()
        assert "bouncer.Allow(self.ctx.bw.remote_addr" in self._access()

    def test_the_served_branch_records_the_reason_itself(self):
        """ngx.OK is not one of the dispatcher's reason_statuses (access-lua.conf), so a served
        challenge leaves no Reports row unless the plugin sets it here."""
        served = self._access().split("if served then")[1].split("if banned then")[0]
        assert "set_reason(self.id, verdict, self.ctx)" in served

    def test_the_deny_branch_passes_it_as_ret_data(self):
        banned = self._access().split("if banned then")[1]
        assert "get_deny_status(), nil, verdict)" in banned, "ret.data is the 5th argument of plugin:ret"

    def test_ret_data_is_really_the_fifth_parameter(self):
        """The two assertions above pin a *position* in a call. Reorder `plugin:ret`'s signature and
        they stay green while every verdict silently lands in `redirect` instead of `data`."""
        plugin_lua = (ROOT / "src" / "bw" / "lua" / "bunkerweb" / "plugin.lua").read_text(encoding="utf-8")
        assert "function plugin:ret(ret, msg, status, redirect, data)" in plugin_lua

    def test_set_reason_is_the_shared_helper(self):
        source = CROWDSEC_LUA.read_text(encoding="utf-8")
        assert "local set_reason = utils.set_reason" in source


def test_the_api_probe_is_untouched():
    """crowdsec:api()'s /crowdsec/ping probe reuses Allow() on the live request; it must keep
    ignoring the extra return values rather than recording a reason for a connectivity test."""
    source = CROWDSEC_LUA.read_text(encoding="utf-8")
    api = re.search(r"^function crowdsec:api\(\).*?^end$", source, re.S | re.M)
    assert api
    assert 'local ok, err = bouncer.Allow("127.0.0.1", true)' in api.group(0)
    assert "set_reason" not in api.group(0)

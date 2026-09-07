"""`crowdsec:access()` hands a `captcha` remediation to the BunkerWeb antibot -- or refuses to.

`lib/bouncer.lua` decides *that* a captcha was asked for (proved in
``test_crowdsec_challenge_lua.py``); this file covers what the plugin does with that answer, which
is where the three things an operator can observe live:

* the flag. ``ctx.bw.workflow_antibot_provider`` is the field ``antibot:access()`` reads -- reused
  rather than duplicated, because its three effects are exactly the ones a CrowdSec captcha wants:
  the provider overrides ``USE_ANTIBOT``, the ``ANTIBOT_IGNORE_*`` lists are skipped, and a
  non-navigation request is denied instead of bounced to a page it could never complete.
* the reason. Recorded here, *before* the antibot answers, so the Reports row names the LAPI
  scenario or the AppSec verdict instead of reading as a bare "antibot" challenge nobody asked for.
* the refusal. The antibot's challenge location is only rendered for a service whose ``USE_ANTIBOT``
  is set (``core/antibot/confs/server-http/antibot.conf``), so flagging a service without it would
  redirect the client to a 404. There the request falls back to the bouncer's FALLBACK_REMEDIATION
  -- ``ban`` in the shipped ``misc/crowdsec.conf``, i.e. the deny status -- and logs one line.

The shipped ``crowdsec:access()`` is spliced out and run through the ``lua`` binary against stubs,
the way ``test_crowdsec_challenge_lua.py`` splices ``csmod.Allow``: narrowing a branch fails the
extraction or the assertion here rather than passing against a copy.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "crowdsec.lua"
SOURCE = CROWDSEC_LUA.read_text(encoding="utf-8")

LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="the lua interpreter is not installed")

DENY_STATUS = 403


def _method(name: str, source: str | None = None) -> str:
    match = re.search(rf"^function crowdsec:{name}\(.*?^end$", source or SOURCE, re.S | re.M)
    assert match, f"crowdsec:{name}() is gone from {CROWDSEC_LUA}"
    return match.group(0)


HARNESS = """
local LOGS = {}
CAPTURED_REASON = nil

-- module-level locals of crowdsec.lua that access() closes over
-- challenge_prefixes: the per-service captcha namespace init() builds and access() hands to
-- Allow (port of dev c54c49e7e). Keyed by scope, so the harness mirrors init()'s own shape.
challenge_prefixes = { global = "captcha-v2|deadbeef|", ["www.example.com"] = "captcha-v2|feedface|" }
WARN = "WARN"
ERR = "ERR"
OK = 0
GLOBAL_SCOPE = "global"
local function get_security_mode() return SECURITY_MODE end
local function get_variable(name) return VARIABLES[name] end
local function set_reason(reason, data, ctx) CAPTURED_REASON = { reason = reason, data = data, ctx = ctx } end
local function get_deny_status() return %(deny)d end

local function bouncer()
  return {
    Allow = function(ip, no_render, antibot_provider, challenge_prefix)
      ALLOW_ARGS = {
        ip = ip,
        no_render = no_render,
        antibot_provider = antibot_provider,
        challenge_prefix = challenge_prefix,
      }
      return true, ALLOW_MSG, ALLOW_BANNED, ALLOW_SERVED, ALLOW_VERDICT, ALLOW_PROVIDER
    end,
  }
end

-- Two scopes, as a multisite fleet has them: access() must pick the namespace of the service
-- being served, not the singlesite fallback. One bouncer per scope, because two services sharing
-- a rendered configuration share a bouncer but never a challenge namespace.
bouncers = { global = bouncer(), ["www.example.com"] = bouncer() }

local crowdsec = {}
%(access)s

local self = {
  id = "crowdsec",
  ctx = { bw = { server_name = SERVER_NAME, remote_addr = "1.2.3.4" } },
  variables = VARIABLES,
  is_needed = function() return true end,
  ret = function(_, ret, msg, status, redirect, data)
    return { ret = ret, msg = msg, status = status, redirect = redirect, data = data }
  end,
  log_throttled = function(_, level, key, msg) LOGS[#LOGS + 1] = level .. " " .. key .. " " .. msg end,
  -- CROWDSEC_DEFER_TO_WORKFLOWS, lane CS-C2. This harness lifts access() out of the module, so
  -- the sibling method it calls on the deny branch has to be stubbed. Answering false is the
  -- default (the setting off), which is what every case in this file exercises; the real one is
  -- covered by test_crowdsec_defer_lua.py, which executes it.
  defer_verdict = function() return DEFER == true end,
}

local answer = crowdsec.access(self)
print("STATUS=" .. tostring(answer.status))
print("MSG=" .. tostring(answer.msg))
print("FLAG=" .. tostring(self.ctx.bw.workflow_antibot_provider))
print("PASSED_PROVIDER=" .. tostring(ALLOW_ARGS.antibot_provider))
print("PASSED_PREFIX=" .. tostring(ALLOW_ARGS.challenge_prefix))
print("REASON=" .. tostring(CAPTURED_REASON and CAPTURED_REASON.reason))
print("REASON_ACTION=" .. tostring(CAPTURED_REASON and CAPTURED_REASON.data.action))
-- Read back from the returned ret.data, which is what the dispatcher stores as reason_data --
-- not from the global, which a branch building its own table would leave untouched.
print("VERDICT_ACTION=" .. tostring(answer.data and answer.data.action))
print("VERDICT_SUPPRESSED=" .. tostring(answer.data and answer.data.suppressed))
print("PUBLISHED=" .. tostring(self.ctx.bw.crowdsec_ok) .. "|" .. tostring(self.ctx.bw.crowdsec_source) .. "|" .. tostring(self.ctx.bw.crowdsec_remediation))
for _, entry in ipairs(LOGS) do print("LOG=" .. entry) end
"""


# `None` is a meaningful value for `verdict` (a bouncer arm that returned none), so "caller said
# nothing" needs a sentinel of its own.
_DEFAULT = object()


def to_lua(value) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return "[==[" + value + "]==]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"[ {to_lua(k)} ] = {to_lua(v)}" for k, v in value.items()) + "}"
    raise TypeError(value)


def run(
    *,
    use_antibot: str | None = "cookie",
    captcha_provider: str | None = "captcha",
    provider_returned: str | None = "captcha",
    verdict=_DEFAULT,
    banned: bool = False,
    served: bool = False,
    security_mode: str = "block",
    source: str | None = None,
    defer: bool = False,
    server_name: str = "www.example.com",
):
    variables = {"USE_CROWDSEC": "yes"}
    if captcha_provider is not None:
        variables["CROWDSEC_CAPTCHA_PROVIDER"] = captcha_provider
    if use_antibot is not None:
        variables["USE_ANTIBOT"] = use_antibot
    preamble = "\n".join(
        [
            f"VARIABLES = {to_lua(variables)}",
            f"SECURITY_MODE = {to_lua(security_mode)}",
            f"ALLOW_MSG = {to_lua('captcha delegated to the BunkerWeb antibot')}",
            f"ALLOW_BANNED = {to_lua(banned)}",
            f"ALLOW_SERVED = {to_lua(served)}",
            f"ALLOW_VERDICT = {to_lua({'source': 'lapi', 'action': 'captcha'} if verdict is _DEFAULT else verdict)}",
            f"ALLOW_PROVIDER = {to_lua(provider_returned)}",
            "ALLOW_ARGS = {}",
            f"DEFER = {to_lua(defer)}",
            f"SERVER_NAME = {to_lua(server_name)}",
        ]
    )
    script = preamble + "\n" + HARNESS % {"deny": DENY_STATUS, "access": _method("access", source)}
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


def logs(out: str) -> list:
    return [line.split("=", 1)[1] for line in out.splitlines() if line.startswith("LOG=")]


class TestTheSettingReachesTheBouncer:
    def test_the_provider_is_passed_to_allow(self):
        """Nothing else tells the bouncer to keep a `captcha` alive: without it, the fallback
        rewrites the decision into a ban before anything here can see it."""
        assert field(run(captcha_provider="javascript"), "PASSED_PROVIDER") == "javascript"

    def test_no_is_passed_through_unchanged(self):
        """The bouncer treats "no" as "not set" -- resolving it here as well would be two places to
        keep in step."""
        assert field(run(captcha_provider="no", provider_returned=None), "PASSED_PROVIDER") == "no"


class TestADelegatedCaptchaFlagsTheRequest:
    def test_the_antibot_flag_is_set_to_the_configured_provider(self):
        assert field(run(), "FLAG") == "captcha"

    def test_the_request_is_neither_denied_nor_redirected(self):
        """A status here would end the request before the antibot ever runs."""
        out = run()
        assert field(out, "STATUS") == "nil"
        assert "delegated to the antibot" in field(out, "MSG")

    def test_the_crowdsec_verdict_is_recorded_before_the_antibot_answers(self):
        out = run(verdict={"source": "lapi", "action": "captcha", "scenario": "crowdsecurity/http-probing"})
        assert field(out, "REASON") == "crowdsec"
        assert field(out, "REASON_ACTION") == "captcha"

    def test_nothing_is_flagged_when_the_bouncer_did_not_delegate(self):
        out = run(provider_returned=None)
        assert field(out, "FLAG") == "nil"
        assert field(out, "REASON") == "nil"


class TestAServiceWithoutTheAntibotIsBannedInstead:
    @pytest.mark.parametrize("use_antibot", ["no", None])
    def test_the_request_is_denied_and_never_flagged(self, use_antibot):
        """The challenge location is not rendered there, so flagging would 404 the client. `None` is
        the unset case: get_variable() returns nil, which must be read as "off", not as "on"."""
        out = run(use_antibot=use_antibot)
        assert field(out, "FLAG") == "nil"
        assert field(out, "STATUS") == str(DENY_STATUS)

    def test_the_recorded_remediation_is_the_one_that_was_applied(self):
        """`action` is what CS-C3's guards read to tell a challenged visitor from a blocked one:
        leaving "captcha" there would describe a banned client as merely challenged, and BunkerNet
        would stop reporting them. What CrowdSec asked for survives as `suppressed`."""
        out = run(use_antibot="no")
        assert field(out, "VERDICT_ACTION") == "ban"
        assert field(out, "VERDICT_SUPPRESSED") == "captcha"

    def test_a_missing_verdict_still_denies_instead_of_raising(self):
        """A nil index here is caught by helpers.lua's pcall, which logs an ERR and then serves the
        request UNCHECKED -- a fail-open in the branch whose whole job is to deny."""
        for absent in (None, {}):
            out = run(use_antibot="no", verdict=absent)
            assert field(out, "STATUS") == str(DENY_STATUS), absent
            assert field(out, "VERDICT_ACTION") == "ban", absent
            assert field(out, "VERDICT_SUPPRESSED") == "captcha", absent

    def test_one_log_line_names_both_settings_the_operator_has_to_touch(self):
        entries = logs(run(use_antibot="no"))
        assert len(entries) == 1, entries
        assert entries[0].startswith("WARN captcha_no_antibot "), entries
        assert "USE_ANTIBOT" in entries[0] and "CROWDSEC_CAPTCHA_PROVIDER" in entries[0], entries
        assert "www.example.com" in entries[0], "the service has to be named: the setting is per-service"

    def test_a_healthy_delegation_logs_nothing(self):
        assert logs(run()) == []


class TestTheOtherRemediationsAreUntouched:
    def test_a_ban_still_denies_and_flags_nothing(self):
        out = run(provider_returned=None, banned=True, verdict={"source": "lapi", "action": "ban"})
        assert field(out, "FLAG") == "nil"
        assert field(out, "STATUS") == str(DENY_STATUS)

    def test_a_served_challenge_still_ends_the_phase_and_flags_nothing(self):
        out = run(provider_returned=None, served=True, verdict={"source": "appsec", "action": "challenge"})
        assert field(out, "FLAG") == "nil"
        assert field(out, "STATUS") == "0", "ngx.OK: the bouncer already wrote the response"
        assert field(out, "REASON") == "crowdsec"


class TestTheVerdictIsPublishedAndCanBeDeferred:
    """Lane CS-C2. `access()` publishes the verdict for the workflow engine on every arm, and
    hands the DENY over only when defer_verdict() says the engine will apply it."""

    def test_every_remediation_publishes_the_verdict_for_the_workflow_leaf(self):
        banned = run(provider_returned=None, banned=True, verdict={"source": "lapi", "action": "ban"})
        assert field(banned, "PUBLISHED") == "true|lapi|ban"

        served = run(provider_returned=None, served=True, verdict={"source": "appsec", "action": "challenge"})
        assert field(served, "PUBLISHED") == "true|appsec|challenge"

    def test_an_allowed_request_publishes_the_flag_but_no_verdict(self):
        """The flag is what separates "CrowdSec had nothing against it" (FALSE for the leaf)
        from "CrowdSec never judged it" (UNKNOWN). Both must not be the same value."""
        allowed = run(provider_returned=None, verdict=None)
        assert field(allowed, "PUBLISHED") == "true|nil|nil"
        assert field(allowed, "STATUS") == "nil", "publication must not change the allow path"

    def test_the_deny_is_handed_over_only_when_the_engine_will_apply_it(self):
        verdict = {"source": "appsec", "action": "ban"}
        kept = run(provider_returned=None, banned=True, verdict=verdict)
        assert kept.count("STATUS=" + str(DENY_STATUS)) == 1, "the default keeps denying here"

        handed = run(provider_returned=None, banned=True, verdict=verdict, defer=True)
        assert field(handed, "STATUS") == "nil", "a deferred verdict must not end the access phase"
        assert "deferred to the security workflows" in field(handed, "MSG")
        assert field(handed, "REASON") == "nil", "no Reports row yet: a workflow rule may still allow it"


class TestTheGuardIsWhatRefuses:
    def test_removing_the_use_antibot_check_flags_a_service_that_cannot_render(self):
        """Mutation: drop the refusal and a service with the antibot off is redirected to a
        challenge URI nginx never rendered -- a 404 in place of the ban it used to get.

        Mutates the spliced copy, never the file on disk.
        """
        method = _method("access")
        mutated = method.replace(
            'if use_antibot == nil or use_antibot == "no" then',
            "if false then",
        )
        assert mutated != method, "the refusal no longer reads as expected -- update this mutation"
        out = run(use_antibot="no", source=SOURCE.replace(method, mutated))
        assert field(out, "FLAG") == "captcha"
        assert field(out, "STATUS") == "nil"


class TestTheChallengeNamespaceFollowsTheService:
    """`access()` hands `Allow` the namespace of the service being served.

    `bouncers` and `challenge_prefixes` are keyed alike, and the port of dev `c54c49e7e` keeps the
    *scope* rather than just the bouncer for exactly this reason: two services with a byte-identical
    rendered configuration share one bouncer instance, so reading the namespace off the bouncer -- or
    off the singlesite fallback -- would put them back in one challenge namespace, which is the bug
    the argument exists to close.
    """

    def test_the_served_service_gets_its_own_namespace(self):
        assert field(run(captcha_provider="captcha"), "PASSED_PREFIX") == "captcha-v2|feedface|"

    def test_falling_back_to_the_singlesite_namespace_is_what_breaks_it(self):
        """Mutation: read the namespace off the global scope. Every service in a multisite fleet
        shares one challenge namespace again and a captcha solved on any of them passes everywhere."""
        method = _method("access")
        mutated = method.replace("challenge_prefixes[scope]", "challenge_prefixes[GLOBAL_SCOPE]")
        assert mutated != method, "the namespace lookup no longer reads as expected -- update this mutation"
        out = run(captcha_provider="captcha", source=SOURCE.replace(method, mutated))
        assert field(out, "PASSED_PREFIX") == "captcha-v2|deadbeef|"

    def test_a_service_without_its_own_bouncer_falls_back_to_the_singlesite_one(self):
        """`MULTISITE=no` keys `bouncers` by `global` while `server_name` is the real host, so the
        `… or GLOBAL_SCOPE` fallback is what every singlesite deployment runs on. Looking the bouncer
        up by `server_name` instead of by the resolved scope makes `if not bouncer then` fire on
        every request and the whole fleet is served UNCHECKED -- which is the regression the ERR line
        at that branch was added to catch.

        This case exists because the two-scope `bouncers` fixture above stopped exercising the
        fallback at all (found by Criticos round 2)."""
        out = run(captcha_provider="captcha", server_name="other.example.com")
        assert field(out, "PASSED_PREFIX") == "captcha-v2|deadbeef|", "the singlesite namespace"
        assert field(out, "STATUS") == "nil", "a bouncer was found: the request was not served unchecked"

    def test_looking_the_bouncer_up_by_server_name_serves_the_fleet_unchecked(self):
        """Mutation: index `bouncers` with the server name instead of the resolved scope. The scope
        line stays byte-identical, so this is a behavioural kill, not an anchor trip."""
        method = _method("access")
        mutated = method.replace(
            "local bouncer = bouncers[scope]",
            "local bouncer = bouncers[self.ctx.bw.server_name]",
        )
        assert mutated != method, "the bouncer lookup no longer reads as expected -- update this mutation"
        out = run(captcha_provider="captcha", server_name="other.example.com", source=SOURCE.replace(method, mutated))
        assert field(out, "PASSED_PREFIX") == "nil", "no bouncer was found"

    def test_the_scope_is_not_read_off_the_bouncer(self):
        """Mutation: pick the scope the pre-port way -- the bouncer, with the singlesite fallback --
        and a service that resolves to the global bouncer loses its own namespace."""
        method = _method("access")
        mutated = method.replace(
            "local scope = bouncers[self.ctx.bw.server_name] and self.ctx.bw.server_name or GLOBAL_SCOPE",
            "local scope = GLOBAL_SCOPE",
        )
        assert mutated != method, "the scope selection no longer reads as expected -- update this mutation"
        out = run(captcha_provider="captcha", source=SOURCE.replace(method, mutated))
        assert field(out, "PASSED_PREFIX") == "captcha-v2|deadbeef|"

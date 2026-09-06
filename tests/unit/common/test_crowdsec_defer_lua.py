"""``CROWDSEC_DEFER_TO_WORKFLOWS``: handing the verdict to the workflow engine, fail-closed.

The setting inverts the one thing this plugin exists to do — it stops CrowdSec from applying
its own deny so a security workflow can answer instead — so the only interesting cases are the
ones where the hand-over must NOT happen. ``crowdsec:defer_verdict()`` is therefore executed for
real under plain Lua rather than asserted on its source: a deferral nobody enforces is a request
served to a client CrowdSec wanted banned, and that failure is silent.

The publication half (``ctx.bw.crowdsec_*``) is asserted on the shipped source of
``crowdsec:access()``, which closes over the whole plugin base class and the bouncer.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "crowdsec.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local logs = {}

ngx = { ERR = "ERR", WARN = "WARN", OK = 0, HTTP_OK = 200, HTTP_INTERNAL_SERVER_ERROR = 500 }

package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["crowdsec.cache_partition"] = {}
package.loaded["bunkerweb.plugin"] = {
    initialize = function(self) self.logger = { log = function() end } end,
    ret = function(_, ok, msg, status, redirect, data)
        return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
    end,
    log_throttled = function(_, level, _, message) logs[#logs + 1] = level .. " " .. message end,
}
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return false end,
    get_variable = function() return nil end,
    get_multiple_variables = function() return {} end,
    get_deny_status = function() return 403 end,
    get_security_mode = function() return "block" end,
    set_reason = function() end,
}
-- The module name is the SLASH form on purpose: helpers.require_plugin loads plugins as
-- `id .. "/" .. id`, and require() caches by name, so the dotted spelling would load a second
-- copy of workflows.lua whose PLAN was never filled.
package.loaded["workflows/workflows"] = { attached = function(server) return WORKFLOWS(server) end }

local crowdsec = dofile("%s")

local function probe(setting)
    local instance = setmetatable({}, crowdsec)
    instance:initialize({})
    instance.variables = { CROWDSEC_DEFER_TO_WORKFLOWS = setting }
    instance.ctx = { bw = { server_name = "app.example.com" } }
    return instance
end

local VERDICT = { source = "appsec", action = "ban", http_status = 403 }

-- ---- the happy path --------------------------------------------------------------
WORKFLOWS = function(server) return server == "app.example.com" end
local on = probe("yes")
assert(on:defer_verdict(VERDICT, false) == true, "a workflow is attached, the verdict must be deferred")
assert(on.ctx.bw.crowdsec_deferred.status == 403, "the deferred deny must carry the deny status")
-- The verdict itself, so workflows:enforce_deferred() hands the report pipeline the same payload
-- the immediate deny does : same Reports row, same rendered sentence.
assert(on.ctx.bw.crowdsec_deferred.verdict == VERDICT, "and the bouncer verdict itself, untouched")

-- ---- every refusal ---------------------------------------------------------------
local off = probe("no")
assert(off:defer_verdict(VERDICT, false) == false, "the default must keep blocking here")
assert(off.ctx.bw.crowdsec_deferred == nil, "nothing is handed over when the setting is off")
assert(#logs == 0, "the default path must not log")

local detect = probe("yes")
assert(detect:defer_verdict(VERDICT, true) == false, "detect mode never defers")
assert(detect.ctx.bw.crowdsec_deferred == nil)

WORKFLOWS = function() return false end
local unattached = probe("yes")
assert(unattached:defer_verdict(VERDICT, false) == false, "no workflow attached: enforce here instead")
assert(unattached.ctx.bw.crowdsec_deferred == nil)
assert(#logs == 1, "the operator must be told, once per minute")
assert(logs[1]:find("CROWDSEC_DEFER_TO_WORKFLOWS", 1, true), "the warning names the setting")
assert(logs[1]:find("app.example.com", 1, true), "and the service")

WORKFLOWS = function() error("workflows blew up") end
local raising = probe("yes")
assert(raising:defer_verdict(VERDICT, false) == false, "an engine that raises must leave the request denied")
assert(raising.ctx.bw.crowdsec_deferred == nil)
assert(logs[2]:find("workflows engine unavailable", 1, true), "and say why")

-- The workflow engine already ran for this request: PLUGINS_ORDER_ACCESS can put `workflows`
-- ahead of `crowdsec` (helpers.lua inserts the override before the order.json defaults), and a
-- deferral handed to a plugin that already ran is enforced by NOBODY -- the ban would reach the
-- origin. attached() cannot see this: it answers about the artefact, not about ordering.
WORKFLOWS = function() return true end
local late = probe("yes")
late.ctx.bw.workflows_ran = true
assert(late:defer_verdict(VERDICT, false) == false, "workflows already ran: enforce here instead")
assert(late.ctx.bw.crowdsec_deferred == nil, "nothing may be handed to a plugin that already ran")
assert(logs[3]:find("already ran", 1, true), "and the operator must be told why")
assert(logs[3]:find("PLUGINS_ORDER_ACCESS", 1, true), "naming the setting that causes it")

package.loaded["workflows/workflows"] = nil
local missing = probe("yes")
assert(missing:defer_verdict(VERDICT, false) == false, "an engine that will not load must leave the request denied")
assert(missing.ctx.bw.crowdsec_deferred == nil)

print("OK")
"""


def test_the_deferral_is_fail_closed():
    result = subprocess.run(["lua", "-e", HARNESS % CROWDSEC_LUA.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def _access() -> str:
    source = CROWDSEC_LUA.read_text(encoding="utf-8")
    match = re.search(r"^function crowdsec:access\(\).*?^end$", source, re.S | re.M)
    assert match, "crowdsec:access() is gone from crowdsec.lua"
    return match.group(0)


def test_the_verdict_is_published_before_any_branch_reads_it():
    """The workflow leaf reads three ctx.bw facts, and publication must happen on the path every
    remediation takes — after Allow() answered, before the arms that terminate the request."""
    access = _access()
    published = access.split("if antibot_provider then")[0]
    assert "self.ctx.bw.crowdsec_ok = true" in published
    assert "self.ctx.bw.crowdsec_source = verdict.source" in published
    assert "self.ctx.bw.crowdsec_remediation = verdict.action" in published
    # Publication is inert: the arms below it still return what they returned before.
    assert "get_deny_status(), nil, verdict)" in access.split("if banned then")[1]


def test_the_early_returns_publish_nothing():
    """`crowdsec_ok` is the flag that separates "CrowdSec had nothing against it" from "CrowdSec
    never judged it". Setting it on a path where the bouncer never ran would turn every workflow
    rule reading a verdict from UNKNOWN into a confident FALSE."""
    head = _access().split("local ok, err, banned, served, verdict")[0]
    assert "crowdsec_ok" not in head


def test_the_deferral_is_asked_only_on_the_deny_branch():
    banned = _access().split("if banned then")[1]
    assert "self:defer_verdict(verdict, detect)" in banned
    # The served and delegated arms answered the request already; there is nothing to defer.
    assert "defer_verdict" not in _access().split("if banned then")[0]


# Every access plugin ordered between crowdsec and workflows, audited one by one: each can end
# the access phase with a DENY (fine — the request is refused either way), and the last three
# with a self-served ALLOW, which is the residual this feature accepts. None of them reaches the
# origin, and every request that would has to pass through workflows first.
#
#   bunkernet.lua:182 deny · reversescan.lua:80,148 deny · limit.lua:254,323 429
#   authbasic.lua:447 401 · misc.lua:24,35 400/405 · cors.lua:123 deny
#   cors.lua:133 204 on an OPTIONS preflight · securitytxt.lua:131 OK on its own URI
#   robotstxt.lua:250 OK on /robots.txt
BETWEEN_CROWDSEC_AND_WORKFLOWS = ["bunkernet", "reversescan", "limit", "authbasic", "misc", "cors", "securitytxt", "robotstxt"]


def _gap(order: list) -> list:
    first, last = order.index("crowdsec"), order.index("workflows")
    assert first < last, "crowdsec must run before the plugin that enforces its deferral"
    # Not a slice: black spaces the colon of a computed slice and flake8 answers E203.
    return [plugin for index, plugin in enumerate(order) if first < index < last]


def test_nothing_new_slips_between_crowdsec_and_the_plugin_that_enforces_its_deferral():
    """A deferred verdict is applied by workflows:access(), so anything ordered between the two
    can answer the request first. The plugins that can do that were audited; a new one in that
    gap has to be audited too, which is what this pin forces."""
    order = json.loads((ROOT / "src" / "common" / "core" / "order.json").read_text(encoding="utf-8"))["access"]
    assert _gap(order) == BETWEEN_CROWDSEC_AND_WORKFLOWS


def test_the_order_the_runtime_actually_uses_stays_inside_the_audited_gap():
    """`order.json` is only the FALLBACK. `PLUGINS_ORDER_ACCESS` is a multisite setting whose
    default is a non-empty list, so helpers.lua:183-191 builds the phase from it first and the
    order.json defaults only fill in what it left out — and the two disagree today (order.json
    has `dnsbl crowdsec bunkernet`, the setting has `dnsbl bunkernet crowdsec`). A plugin added
    to the setting's default between crowdsec and workflows would pass the pin above and never
    be audited, so the list the runtime really walks is pinned too."""
    default = json.loads((ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8"))["PLUGINS_ORDER_ACCESS"]["default"]
    unaudited = set(_gap(default.split())) - set(BETWEEN_CROWDSEC_AND_WORKFLOWS)
    assert not unaudited, f"{sorted(unaudited)} run between crowdsec and workflows and were never audited for a self-served allow"

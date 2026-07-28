"""Leaf compilation, rule selection and the terminal actions of the workflow runtime.

``eval.lua`` covers the algebra; this covers everything around it — which fact each
predicate reads, what it does when that fact is unknown, that the loop stops at the first
*effective* match, and that each action maps onto the return shape the access dispatcher
expects. Runs under plain Lua with OpenResty stubbed, because these are pure decisions and
every one of them fails open silently when it is wrong.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src" / "common" / "core" / "workflows"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local PLUGIN = "%s"
-- cjson decodes a JSON null to a truthy sentinel, never to nil. The artefact below uses the
-- same shape, because feeding an absent key instead once hid a crash the e2e caught.
local NULL = setmetatable({}, { __tostring = function() return "null" end })
local ARTEFACT = %s

-- ---- OpenResty and BunkerWeb stubs -----------------------------------------------
local logs, reasons, metrics, counters = {}, {}, {}, {}
SECURITY_MODE = "block"
RATE_STORE_FAILS = false

ngx = {
    ERR = "ERR",
    INFO = "INFO",
    re = {
        -- Lua patterns stand in for PCRE: enough to exercise the leaf, and the patterns
        -- used below are deliberately valid in both dialects.
        find = function(subject, pattern)
            if pattern == "((" then
                return nil, nil, "unmatched parenthesis"
            end
            return string.find(subject, pattern), nil, nil
        end,
    },
}

package.loaded["cjson"] = { decode = function() return ARTEFACT end, null = NULL }
package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.ipmatcher"] = {
    new = function(values)
        if values[1] == "not-an-ip" then
            return nil, "invalid ip"
        end
        local set = {}
        for _, value in ipairs(values) do set[value] = true end
        return { match = function(_, ip) return set[ip] == true end }
    end,
}
package.loaded["bunkerweb.plugin"] = {
    initialize = function(self)
        self.logger = { log = function(_, level, message) logs[#logs + 1] = level .. " " .. message end }
    end,
    ret = function(_, ok, msg, status, redirect, data)
        return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
    end,
    set_metric = function(_, _, key, value) metrics[key] = value end,
    log_throttled = function(_, level, _, message) logs[#logs + 1] = level .. " " .. message end,
}
package.loaded["bunkerweb.ratelimit"] = {
    incr = function(_, key, _)
        if RATE_STORE_FAILS then
            return nil, "connection refused"
        end
        counters[key] = (counters[key] or 0) + 1
        return counters[key]
    end,
}
package.loaded["bunkerweb.utils"] = {
    get_variable = function() return "512" end,
    get_deny_status = function() return 403 end,
    get_security_mode = function() return SECURITY_MODE end,
    is_whitelisted = function(ctx) return ctx and ctx.bw and ctx.bw.whitelisted == true end,
    set_reason = function(reason, data, _, mode)
        reasons[#reasons + 1] = { reason = reason, data = data, mode = mode }
    end,
}
package.loaded["workflows.eval"] = dofile(PLUGIN .. "/eval.lua")

local real_open = io.open
io.open = function(path, mode)
    if path:find("workflows/config.json", 1, true) then
        return { read = function() return "{}" end, close = function() end }
    end
    return real_open(path, mode)
end

-- ---- load ------------------------------------------------------------------------
local workflows = dofile(PLUGIN .. "/workflows.lua")

local instance = setmetatable({}, workflows)
instance:initialize({})
local loaded = instance:init()
assert(loaded.ret, "init failed: " .. tostring(loaded.msg))

-- `nil` cannot be carried in a table literal, so removing a fact needs a sentinel.
local ABSENT = {}

local function base(extra)
    local bw = {
        server_name = "app.example.com",
        remote_addr = "203.0.113.7",
        uri = "/",
        request_method = "GET",
        country = "FR",
        country_ok = true,
        asn_number = 64496,
        asn_ok = true,
    }
    for key, value in pairs(extra or {}) do
        if value == ABSENT then
            bw[key] = nil
        else
            bw[key] = value
        end
    end
    return bw
end

local function access(extra)
    local probe = setmetatable({}, workflows)
    probe:initialize({})
    probe.ctx = { bw = base(extra) }
    local result = probe:access()
    result.ctx = probe.ctx
    return result
end

local function check(label, got, want)
    assert(got:find(want, 1, true), label .. " : expected to match " .. want .. ", got " .. got)
end

-- ---- selection -------------------------------------------------------------------
check("unattached service", access({ server_name = "other.example.com" }).msg, "no workflow attached")
check("whitelisted", access({ uri = "/login", whitelisted = true }).msg, "client is whitelisted")

check("country and prefix", access({ uri = "/login" }).msg, "workflow rule r-country-uri blocks")
check("wrong country", access({ uri = "/login", country = "BE" }).msg, "no rule matched")
check("wrong path", access({}).msg, "no rule matched")
-- An unresolved country is UNKNOWN, and an UNKNOWN rule must not match.
check("country unknown", access({ uri = "/login", country_ok = false }).msg, "no rule matched")

check("method", access({ uri = "/api", request_method = "POST" }).msg, "workflow rule r-method blocks")
check("other method", access({ uri = "/api" }).msg, "no rule matched")

check("ip group", access({ uri = "/admin", remote_addr = "198.51.100.4" }).msg, "workflow rule r-group blocks")
check("ip outside group", access({ uri = "/admin" }).msg, "no rule matched")

-- A private IP has no ASN, which is a fact (FALSE), not an unknown, so NOT of it is TRUE.
check("no asn is false not unknown", access({ uri = "/asn", asn_number = ABSENT }).msg, "workflow rule r-not-asn blocks")
check("asn present", access({ uri = "/asn" }).msg, "no rule matched")

check("regex", access({ uri = "/re/x" }).msg, "workflow rule r-regex blocks")
check("broken regex never matches", access({ uri = "/anything" }).msg, "no rule matched")

-- ---- terminal actions ------------------------------------------------------------
local blocked = access({ uri = "/login" })
assert(blocked.status == 403, "a block must carry the deny status, got " .. tostring(blocked.status))
assert(blocked.redirect == nil, "a block must not redirect")
assert(blocked.data.rule == "r-country-uri", "the report data must name the rule")
assert(metrics["workflow_block"] == 1, "a block must count a metric")

local redirected = access({ uri = "/go" })
assert(redirected.redirect == "https://example.com/moved", "the redirect target must be returned")
assert(redirected.status == 302, "the redirect status must be returned")
-- The dispatcher calls set_reason on its deny branch but not on its redirect branch.
assert(reasons[#reasons].reason == "workflows", "a redirect must record its own reason")

local challenged = access({ uri = "/challenge-me" })
assert(challenged.status == nil and challenged.redirect == nil, "a challenge must not terminate the chain")
assert(challenged.ctx.bw.workflow_antibot_provider == "hcaptcha", "the provider must be handed to antibot")

-- ---- detect mode -----------------------------------------------------------------
SECURITY_MODE = "detect"
local detected = access({ uri = "/login" })
-- A status here would hit the dispatcher's detect branch, which breaks the loop and would
-- silently skip antibot and every later access plugin.
assert(detected.status == nil and detected.redirect == nil, "detect must not enforce anything")
check("detect logs the action", detected.msg, "detected workflow block")
assert(reasons[#reasons].mode == "detect", "detect must still record the observation")
local detected_challenge = access({ uri = "/challenge-me" })
assert(detected_challenge.ctx.bw.workflow_antibot_provider == nil, "detect must not prepare a challenge")
SECURITY_MODE = "block"

-- ---- rate gate -------------------------------------------------------------------
-- The gate is a match gate: under the threshold the rule loses and evaluation continues,
-- which is how "over 2 requests block, otherwise challenge" is expressed as two rules.
check("under the threshold", access({ uri = "/burst" }).msg, "workflow rule r-burst-challenge requests")
check("still under", access({ uri = "/burst" }).msg, "workflow rule r-burst-challenge requests")
check("over the threshold", access({ uri = "/burst" }).msg, "workflow rule r-burst-block blocks")

-- A different client has its own bucket.
check("separate bucket per IP", access({ uri = "/burst", remote_addr = "203.0.113.9" }).msg, "r-burst-challenge requests")

-- A store failure makes the gate unknown: the rule loses, the request is not blocked.
RATE_STORE_FAILS = true
check("store failure falls through", access({ uri = "/burst" }).msg, "workflow rule r-burst-challenge requests")
RATE_STORE_FAILS = false

local errors = 0
for _, line in ipairs(logs) do
    if line:sub(1, 3) == "ERR" then errors = errors + 1 end
end
-- Two at load (bad regex, bad IP list) plus one throttled gate failure.
assert(errors == 3, "expected 3 errors, got " .. tostring(errors))

print("OK")
"""

# Rules are ordered: the runtime stops at the first effective match.
ARTEFACT = """{
    schema_version = 1,
    groups = { ["g-office"] = { ip = { "198.51.100.4" }, country = {}, asn = {} } },
    services = { ["app.example.com"] = { "wf-1" } },
    workflows = {
        ["wf-1"] = { name = "policy", rules = {
            { id = "r-country-uri", counter = "wf-1/r-country-uri", threshold = NULL, action = { type = "block" },
              condition = { op = "all", nodes = {
                  { op = "country", values = { "FR" } },
                  { op = "uri", match = "prefix", value = "/login" } } } },
            { id = "r-method", counter = "wf-1/r-method", threshold = NULL, action = { type = "block" },
              condition = { op = "all", nodes = {
                  { op = "method", values = { "POST" } },
                  { op = "uri", match = "exact", value = "/api" } } } },
            { id = "r-group", counter = "wf-1/r-group", threshold = NULL, action = { type = "block" },
              condition = { op = "all", nodes = {
                  { op = "group", kind = "ip", group_id = "g-office" },
                  { op = "uri", match = "exact", value = "/admin" } } } },
            { id = "r-not-asn", counter = "wf-1/r-not-asn", threshold = NULL, action = { type = "block" },
              condition = { op = "all", nodes = {
                  { op = "not", node = { op = "asn", values = { 64496 } } },
                  { op = "uri", match = "exact", value = "/asn" } } } },
            { id = "r-regex", counter = "wf-1/r-regex", threshold = NULL, action = { type = "block" },
              condition = { op = "uri", match = "regex", value = "^/re/" } },
            { id = "r-broken-regex", counter = "wf-1/r-broken-regex", threshold = NULL, action = { type = "block" },
              condition = { op = "uri", match = "regex", value = "((" } },
            { id = "r-broken-ip", counter = "wf-1/r-broken-ip", threshold = NULL, action = { type = "block" },
              condition = { op = "ip", values = { "not-an-ip" } } },
            { id = "r-redirect", counter = "wf-1/r-redirect", threshold = NULL,
              action = { type = "redirect", url = "https://example.com/moved", status = 302 },
              condition = { op = "uri", match = "exact", value = "/go" } },
            { id = "r-challenge", counter = "wf-1/r-challenge", threshold = NULL,
              action = { type = "challenge", provider = "hcaptcha" },
              condition = { op = "uri", match = "exact", value = "/challenge-me" } },
            { id = "r-burst-block", counter = "wf-1/r-burst-block",
              threshold = { count = 2, window = 60, key = "ip" }, action = { type = "block", status = 429 },
              condition = { op = "uri", match = "exact", value = "/burst" } },
            { id = "r-burst-challenge", counter = "wf-1/r-burst-challenge", threshold = NULL,
              action = { type = "challenge", provider = "hcaptcha" },
              condition = { op = "uri", match = "exact", value = "/burst" } },
        } },
    },
}"""


def test_leaf_compilation_selection_and_actions():
    script = HARNESS % (PLUGIN.as_posix(), ARTEFACT)
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"

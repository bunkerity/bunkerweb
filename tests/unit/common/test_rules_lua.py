"""The composite (AND) rule engine shared by greylist, whitelist and blacklist.

Three things are load-bearing here and all three fail silently when wrong:

* the parser, because a rule it mis-splits becomes a rule that quietly never matches (or,
  worse for a whitelist, one that matches on fewer terms than the operator wrote);
* the fold, because ``NOT`` inverting the wrong side turns an allow list inside out;
* the cache, because the whole point of caching *term* truth rather than *rule* verdicts is
  that two rules disagreeing over the same term must not poison each other.

Runs the real ``src/bw/lua/bunkerweb/rules.lua`` through the ``lua`` binary with OpenResty
stubbed, the way test_ratelimit_lua.py does. Note the harness is plain Lua 5.4, not LuaJIT.
"""

import json
import shutil
import subprocess
from pathlib import Path
from re import search as re_search

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "rules.lua"
PLUGIN_JSON = ROOT / "src" / "common" / "core" / "greylist" / "plugin.json"
BLACKLIST_MODULE = ROOT / "src" / "common" / "core" / "blacklist" / "blacklist.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
ngx = { ERR = "ERR" }

-- Counting stubs: every matcher records that it ran, which is how the cache assertions below
-- tell a cached truth from a recomputed one.
CALLS = { ip = 0, rdns = 0, ua = 0, uri = 0 }
RDNS_LIST = { "host.example.com" }
FORWARD_CONFIRMED = true

package.loaded["resty.ipmatcher"] = {
    new = function(values)
        for _, value in ipairs(values) do
            if value == "not-an-ip" then
                return nil, "invalid ip"
            end
        end
        return {
            match = function(_, ip)
                CALLS.ip = CALLS.ip + 1
                for _, value in ipairs(values) do
                    -- Prefix match stands in for the radix tree: enough to tell the terms apart.
                    if ip:sub(1, #value - 3) == value:sub(1, #value - 3) then
                        return true
                    end
                end
                return false
            end,
        }
    end,
}
package.loaded["bunkerweb.utils"] = {
    get_rdns = function()
        CALLS.rdns = CALLS.rdns + 1
        return RDNS_LIST
    end,
    rdns_forward_confirmed = function(rdns_list, suffixes)
        if not FORWARD_CONFIRMED then
            return nil
        end
        for _, rdns in ipairs(rdns_list) do
            for _, suffix in ipairs(suffixes) do
                if rdns:sub(-#suffix) == suffix then
                    return suffix
                end
            end
        end
        return nil
    end,
    regex_match = function(subject, regex)
        CALLS.ua = CALLS.ua + 1
        return subject:find(regex:gsub("^%^", ""), 1, true) == 1 or nil
    end,
}

local rules = dofile("__MODULE__")

local failures = 0
local function check(label, got, want)
    if got ~= want then
        failures = failures + 1
        print("FAIL " .. label .. " : got " .. tostring(got) .. ", wanted " .. tostring(want))
    end
end

-- ---------------------------------------------------------------- 1. parser
local VALID = {
    { "ip:10.0.0.0/8 AND ua:^MyBot", 2 },
    { "NOT ua:^curl", 1 },
    { "user_agent:^Bot", 1 },
    { "ip:@office AND country:FR", 2 },
    { "asn:12345 AND NOT uri:^/health AND rdns:.example.com", 3 },
    { "uri:^/a{1,3}$", 1 },
    { "  ip:10.0.0.1  ", 1 },
    -- A value that merely starts with "and" is fine; only the separator spelling is refused,
    -- and the setting's regex draws the line in the same place.
    { "uri:and-then", 1 },
    { "ua:android AND ip:10.0.0.0/8", 2 },
}
for _, case in ipairs(VALID) do
    local terms, err = rules.parse(case[1])
    check("parse ok [" .. case[1] .. "]", terms ~= nil, true)
    if terms then
        check("parse arity [" .. case[1] .. "]", #terms, case[2])
    else
        print("       err = " .. tostring(err))
    end
end

local INVALID = {
    "",
    "   ",
    "foo:bar",
    "ip:",
    "ip:1.2.3.4 AND ",
    "ip:1.2.3.4 AND",
    "ua:a AND b",
    "NOT NOT ua:x",
    "ip:1.2.3.4 and ua:x",
    "IP:1.2.3.4 AND ua:x",
    "UA:^curl",
    "uri:^/search and destroy",
}
for _, text in ipairs(INVALID) do
    local terms = rules.parse(text)
    check("parse refuses [" .. text .. "]", terms, nil)
end

-- The alias and the negation flag land where the evaluator expects them.
local terms = rules.parse("NOT user_agent:^curl AND ip:10.0.0.0/8,192.168.0.0/16")
check("alias kind", terms[1].kind, "ua")
check("alias negate", terms[1].negate, true)
check("second term negate", terms[2].negate, false)
check("comma-split values", #terms[2].values, 2)
check("regex value not split", #rules.parse("uri:^/a,b")[1].values, 1)

-- ---------------------------------------------------------------- 2. family + scope merge
local family, errors = rules.parse_family({
    GREYLIST_RULE_2 = "ip:10.0.0.0/8",
    GREYLIST_RULE_1 = "ua:^Bot",
    GREYLIST_RULE_3 = "nope:x",
    GREYLIST_IP = "1.2.3.4",
    GREYLIST_RULE_4 = "   ",
}, "GREYLIST_RULE")
check("family size", #family, 2)
check("family order", family[1].id, "GREYLIST_RULE_1")
check("family errors", #errors, 1)

local merged = rules.for_server({
    global = { { id = "GREYLIST_RULE_1", text = "g1" }, { id = "GREYLIST_RULE_2", text = "g2" } },
    ["app.example.com"] = { { id = "GREYLIST_RULE_2", text = "s2" }, { id = "GREYLIST_RULE_3", text = "s3" } },
}, "app.example.com")
check("merge size", #merged, 3)
check("merge keeps global 1", merged[1].text, "g1")
check("merge overrides 2", merged[2].text, "s2")
check("merge adds 3", merged[3].text, "s3")
check("merge unknown server", #rules.for_server({ global = { { id = "R_1", text = "g" } } }, "other"), 1)

-- ---------------------------------------------------------------- 3. warnings
local warned = rules.warnings(rules.parse_family({
    R_1 = "ip:10.0.0.0/8 AND uri:^/admin",
    R_2 = "NOT ip:10.0.0.0/8",
    R_3 = "ip:@office",
    R_4 = "ip:10.0.0.0/8",
}, "R"))
local joined = table.concat(warned, "\\n")
check("stream flag", joined:find("R_1 has a uri: term") ~= nil, true)
check("all-NOT flag", joined:find("R_2 is made only of NOT terms") ~= nil, true)
check("unexpanded token flag", joined:find("R_3 has an unexpanded group token @office") ~= nil, true)
check("no false positive", joined:find("R_4") == nil, true)

-- ---------------------------------------------------------------- 4. fold truth table
local function new_cache_early()
    local store = {}
    return store, {
        cache_get = function(key)
            local v = store[key]
            if v == nil then
                return nil
            end
            return v == "1"
        end,
        cache_set = function(key, truth)
            store[key] = truth and "1" or "0"
        end,
    }
end

local function ctx(over)
    local bw = {
        remote_addr = "10.0.0.1",
        http_user_agent = "MyBot/1.0",
        uri = "/api/v1",
        country = "FR",
        asn_number = 12345,
        ip_is_global = true,
    }
    for k, v in pairs(over or {}) do
        bw[k] = v
    end
    return { bw = bw }
end

local function fold(text, request)
    local parsed = { { id = "R_1", text = text, terms = rules.parse(text) } }
    return rules.evaluate(parsed, { ctx = request or ctx(), rdns_forward_confirm = true }) ~= nil
end

check("both terms true", fold("ip:10.0.0.0/8 AND ua:^MyBot"), true)
check("second term false", fold("ip:10.0.0.0/8 AND ua:^Other"), false)
check("first term false", fold("ip:192.0.2.0/24 AND ua:^MyBot"), false)
check("neither true", fold("ip:192.0.2.0/24 AND ua:^Other"), false)
check("NOT inverts a false term", fold("ip:10.0.0.0/8 AND NOT ua:^Other"), true)
check("NOT inverts a true term", fold("ip:10.0.0.0/8 AND NOT ua:^MyBot"), false)
check("three terms", fold("ip:10.0.0.0/8 AND country:FR AND asn:12345"), true)
check("country mismatch", fold("country:DE"), false)
check("country is case-insensitive", fold("country:fr"), true)
check("asn AS prefix accepted", fold("asn:AS12345"), true)
check("asn skipped on a private ip", fold("asn:12345", ctx({ ip_is_global = false })), false)
check("rdns forward-confirmed", fold("rdns:.example.com"), true)
check("uri term", fold("uri:^/api"), true)

-- A missing subject makes the term false, never true: that is what keeps a ua:/uri: rule from
-- matching in stream (where fill_ctx leaves both nil) instead of matching on its other terms.
-- Built by hand: nil cannot be stored in a Lua table, so the ctx() override helper cannot
-- express "this field is absent" -- which is exactly the stream shape being tested.
local stream = { bw = { remote_addr = "10.0.0.1", country = "FR", asn_number = 12345, ip_is_global = true } }
check("stream kills a ua term", fold("ip:10.0.0.0/8 AND ua:^MyBot", stream), false)
check("stream kills a uri term", fold("ip:10.0.0.0/8 AND uri:^/api", stream), false)
check("stream keeps ip terms", fold("ip:10.0.0.0/8 AND country:FR", stream), true)
-- NOT over an unevaluable term must not resurrect the rule either.
check("stream NOT ua stays false", fold("ip:10.0.0.0/8 AND NOT ua:^MyBot", stream), false)

-- Unknown terms: a failed lookup is not a false, and NOT must not turn it into a match.
local no_asn = { bw = { remote_addr = "10.0.0.1", country = "FR", ip_is_global = true } }
check("asn lookup failure kills the rule", fold("ip:10.0.0.0/8 AND asn:12345", no_asn), false)
check("NOT over a failed asn lookup stays false", fold("ip:10.0.0.0/8 AND NOT asn:12345", no_asn), false)
local unknown_country = ctx({ country = "unknown" })
check("country lookup failure kills the rule", fold("NOT country:FR", unknown_country), false)
-- A private IP has no ASN and country "local": definite answers, so NOT may rely on them.
local private = { bw = { remote_addr = "192.168.1.5", country = "local", uri = "/api/v1", ip_is_global = false } }
check("NOT asn on a private ip matches", fold("uri:^/api AND NOT asn:12345", private), true)
check("NOT country on a private ip matches", fold("uri:^/api AND NOT country:FR", private), true)
-- rDNS that does not forward-confirm is a definite no, not an unknown.
FORWARD_CONFIRMED = false
check("unconfirmed rdns does not match", fold("rdns:.example.com"), false)
FORWARD_CONFIRMED = true

-- An unknown is never written to the cache: a transient resolver failure must not freeze into
-- the answer for the whole TTL.
local unknown_store, unknown_cache = new_cache_early()
rules.evaluate({ { id = "R_1", text = "asn:12345", terms = rules.parse("asn:12345") } }, {
    ctx = no_asn,
    cache_get = unknown_cache.cache_get,
    cache_set = unknown_cache.cache_set,
})
local unknown_keys = 0
for _ in pairs(unknown_store) do
    unknown_keys = unknown_keys + 1
end
check("unknown term not cached", unknown_keys, 0)

-- First matching rule wins, and the rest are not evaluated.
CALLS.ua = 0
local ordered = {
    { id = "R_1", text = "ip:10.0.0.0/8", terms = rules.parse("ip:10.0.0.0/8") },
    { id = "R_2", text = "ua:^MyBot", terms = rules.parse("ua:^MyBot") },
}
local hit = rules.evaluate(ordered, { ctx = ctx() })
check("first rule wins", hit.id, "R_1")
check("later rules not evaluated", CALLS.ua, 0)

-- ---------------------------------------------------------------- 5. cache
local new_cache = new_cache_early

-- Two rules over the SAME ip term with opposite verdicts. The shared term is evaluated once,
-- and the negated rule must not write its own (inverted) answer into that shared slot.
local store, cache = new_cache()
local shared = {
    { id = "R_1", text = "ip:10.0.0.0/8 AND ua:^MyBot", terms = rules.parse("ip:10.0.0.0/8 AND ua:^MyBot") },
    { id = "R_2", text = "NOT ip:10.0.0.0/8 AND ua:^MyBot", terms = rules.parse("NOT ip:10.0.0.0/8 AND ua:^MyBot") },
}
CALLS.ip = 0
local opts = { ctx = ctx(), cache_get = cache.cache_get, cache_set = cache.cache_set }
check("positive rule matches", rules.evaluate(shared, opts).id, "R_1")
check("ip term evaluated once", CALLS.ip, 1)
-- Now ask only the negated rule: it reads the same cached term and must still say no.
check("negated rule does not match", rules.evaluate({ shared[2] }, opts), nil)
check("ip term still evaluated once", CALLS.ip, 1)
local ip_keys = 0
for key, value in pairs(store) do
    if key:find("rule_term:ip:", 1, true) then
        ip_keys = ip_keys + 1
        check("cached term truth is the TERM's, not the rule's verdict", value, "1")
    end
end
check("one cache slot for the shared term", ip_keys, 1)

-- The SAME pair with the negated rule FIRST. The order is the proof, not decoration: with the
-- positive rule first it matches on the very first term, evaluate() returns, and a write-side bug
-- that folds negation into the cached value never gets a chance to run -- the assertions above
-- stay green through it. Negated first, the shared slot is *written* by the NOT rule and *read*
-- by the positive one, which is the poisoning direction that actually ships.
local neg_store, neg_cache = new_cache()
local negated_first = {
    { id = "R_1", text = "NOT ip:10.0.0.0/8 AND ua:^MyBot", terms = rules.parse("NOT ip:10.0.0.0/8 AND ua:^MyBot") },
    { id = "R_2", text = "ip:10.0.0.0/8 AND ua:^MyBot", terms = rules.parse("ip:10.0.0.0/8 AND ua:^MyBot") },
}
CALLS.ip = 0
local neg_opts = { ctx = ctx(), cache_get = neg_cache.cache_get, cache_set = neg_cache.cache_set }
local neg_hit = rules.evaluate(negated_first, neg_opts)
check("the positive rule still matches after the negated one wrote the shared slot", neg_hit and neg_hit.id, "R_2")
check("the shared ip term was evaluated once, by the negated rule", CALLS.ip, 1)
local neg_ip_keys = 0
for key, value in pairs(neg_store) do
    if key:find("rule_term:ip:", 1, true) then
        neg_ip_keys = neg_ip_keys + 1
        check("the NOT rule stored the TERM's truth, not its own inverted verdict", value, "1")
    end
end
check("one cache slot for the shared term, whichever rule wrote it", neg_ip_keys, 1)

-- A cached false is a hit, not a miss: without the nil/false distinction every false term
-- would be recomputed on every request.
CALLS.ip = 0
local miss_store, miss_cache = new_cache()
local far = { { id = "R_1", text = "ip:192.0.2.0/24", terms = rules.parse("ip:192.0.2.0/24") } }
local far_opts = { ctx = ctx(), cache_get = miss_cache.cache_get, cache_set = miss_cache.cache_set }
rules.evaluate(far, far_opts)
rules.evaluate(far, far_opts)
check("false term cached, not recomputed", CALLS.ip, 1)
local cached_false = nil
for _, value in pairs(miss_store) do
    cached_false = value
end
check("false stored as 0", cached_false, "0")

-- Terms of different kinds, and the same kind with different values, never share a slot.
local key_a = rules.cache_key(rules.parse("ip:10.0.0.0/8")[1], ctx())
local key_b = rules.cache_key(rules.parse("ip:10.0.0.0/9")[1], ctx())
local key_c = rules.cache_key(rules.parse("rdns:10.0.0.0/8")[1], ctx())
check("value change changes the key", key_a ~= key_b, true)
check("kind change changes the key", key_a ~= key_c, true)
-- The length prefix is what stops a crafted value from forging another term's key.
local forge_a = rules.cache_key(rules.parse("uri:a:b")[1], ctx())
local forge_b = rules.cache_key(rules.parse("uri:a")[1], ctx({ uri = "b:/api/v1" }))
check("no key forgery across value/subject boundary", forge_a ~= forge_b, true)
-- No subject, no key: a ua term in stream must not be cached under a nil subject.
check("no key without a subject", rules.cache_key(rules.parse("ua:^x")[1], stream), nil)

if failures == 0 then
    print("OK")
else
    print("FAILURES " .. failures)
end
"""


def run_lua(harness: str) -> str:
    result = subprocess.run(
        [shutil.which("lua") or "lua", "-e", harness],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    assert result.returncode == 0, f"lua exited {result.returncode}\n{result.stdout}\n{result.stderr}"
    return result.stdout


def test_rules_engine():
    output = run_lua(HARNESS.replace("__MODULE__", MODULE.as_posix()))
    assert output.strip().endswith("OK"), output


# --- the two gates must not drift apart ------------------------------------------------
# A rule is validated twice: by the `<LIST>_RULE` regex in plugin.json when it is saved, and by
# rules.parse when the configuration loads. If they disagree, either a value the operator was
# allowed to save dies in the error log with no UI feedback, or a value the UI refused would
# have worked. Changing one without the other is the easy mistake, so the two are compared
# here on the same corpus.

PARITY_CASES = [
    "ip:10.0.0.0/8 AND ua:^MyBot",
    "NOT ua:^curl",
    "user_agent:^Bot",
    "ip:@office AND country:FR",
    "asn:12345 AND NOT uri:^/health AND rdns:.example.com",
    "uri:^/a{1,3}$",
    "ua:^Mozilla/5\\.0 .*Chrome",
    "uri:and-then",
    "ua:android AND ip:10.0.0.0/8",
    "ua:and",
    "ip:10.0.0.0/8,192.168.0.0/16",
    "NOT ip:1.2.3.4 AND NOT ua:^x",
    "foo:bar",
    "ip:",
    "ip:1.2.3.4 AND ",
    "ip:1.2.3.4 AND",
    "ua:a AND b",
    "NOT NOT ua:x",
    "ip:1.2.3.4 and ua:x",
    "IP:1.2.3.4",
    "UA:^curl",
    "uri:^/search and destroy",
    "ua:foo and",
    " ip:1.2.3.4",
    "ip:1.2.3.4 ",
    "",
]

# The one place the two gates are *meant* to disagree, asserted rather than excluded so a change
# on either side is still red.
#
# ``""`` is the setting's own default. The regex has to accept it -- Configurator validates every
# default against its setting's regex, and a rule family that refused its own default would make
# the plugin unloadable -- while ``rules.parse`` refuses it as an empty rule. Nothing ever sees
# the disagreement: ``parse_family`` filters on ``value:match("%S")`` before it calls ``parse``,
# so an unset ``<LIST>_RULE`` is simply absent from the family, not an error-log line.
EXPECTED_DIVERGENCES = {"": ("accept", "refuse")}

PARITY_HARNESS = """
ngx = { ERR = "ERR" }
package.loaded["resty.ipmatcher"] = { new = function() return { match = function() return false end } end }
package.loaded["bunkerweb.utils"] = {
    get_rdns = function() return {} end,
    rdns_forward_confirmed = function() return nil end,
    regex_match = function() return nil end,
}
local rules = dofile("__MODULE__")
for line in io.lines() do
    -- One leading sentinel byte, so a trailing space survives the round trip.
    print(rules.parse(line:sub(2)) and "accept" or "refuse")
end
"""


def test_the_setting_regex_and_the_parser_agree():
    regex = json.loads((PLUGIN_JSON).read_text())["settings"]["GREYLIST_RULE"]["regex"]
    binary = shutil.which("lua") or "lua"
    result = subprocess.run(
        [binary, "-e", PARITY_HARNESS.replace("__MODULE__", MODULE.as_posix())],
        input="".join(f"|{case}\n" for case in PARITY_CASES),
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    verdicts = result.stdout.split()
    assert len(verdicts) == len(PARITY_CASES)

    disagreements = []
    for case, from_lua in zip(PARITY_CASES, verdicts):
        # A `text` setting is stripped (trim_scalar_value) before its regex runs.
        stripped = case.strip()
        from_regex = "accept" if re_search(regex, stripped) else "refuse"
        expected = EXPECTED_DIVERGENCES.get(case)
        if expected is not None:
            assert (from_regex, from_lua) == expected, f"{case!r}: the documented divergence changed shape: regex={from_regex} parser={from_lua}"
            continue
        if from_regex != from_lua:
            disagreements.append(f"{case!r}: regex={from_regex} parser={from_lua}")
    assert not disagreements, "\n".join(disagreements)


# --- the blacklist ignore lists must not waive a rule they have no business in ----------
# BLACKLIST_IGNORE_* is the only ignore family in the three plugins, and it is the one place a
# rule verdict can be *turned off*. The flat pass suppresses per kind -- IGNORE_URI shields the
# URI check and nothing else -- so a rule must be waived per kind too. Waiving on ANY ignore
# entry makes a rule strictly weaker than the flat lists it mirrors: with
# ``BLACKLIST_RULE_1 = "ip:203.0.113.0/24 AND country:CN"`` and ``BLACKLIST_IGNORE_URI = "^/static"``
# every request to /static bypasses the rule, and the URI is attacker-chosen.
#
# Both directions are asserted for every kind, because a guard that is simply always false would
# satisfy the "not ignored" half alone. The rule is parsed by the REAL rules.lua, so the term-kind
# spellings the guard keys off cannot drift away from the parser's.

IGNORE_SCOPE_HARNESS = """
ngx = { ERR = "ERR", INFO = "INFO", WARN = "WARN", var = {}, get_phase = function() return "access" end }

package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.ipmatcher"] = {
    new = function(values)
        return {
            -- Network-prefix match: enough to tell "203.0.113.0/24" from "198.51.100.0/24"
            -- for this test's two fixed addresses.
            match = function(_, ip)
                for _, value in ipairs(values) do
                    local network = value:gsub("%.%d+/%d+$", ".")
                    if ip:sub(1, #network) == network then
                        return true
                    end
                end
                return false
            end,
        }
    end,
}
package.loaded["bunkerweb.plugin"] = {
    initialize = function() end,
    ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_multiple_variables = function() return {} end,
    get_variable = function() return "", "success" end,
    get_deny_status = function() return 403 end,
    deduplicate_list = function(list) return list end,
    get_rdns = function() return { "host.ignore.example" } end,
    rdns_forward_confirmed = function(rdns_list, suffixes)
        for _, rdns in ipairs(rdns_list) do
            for _, suffix in ipairs(suffixes) do
                if rdns:sub(-#suffix) == suffix then
                    return suffix
                end
            end
        end
        return nil
    end,
    regex_match = function(subject, regex)
        return subject:find(regex:gsub("^%^", ""), 1, true) == 1 or nil
    end,
}
-- The REAL engine: the kinds is_ignored() switches on are the kinds parse() produces.
package.loaded["bunkerweb.rules"] = dofile("__RULES__")
local rules = package.loaded["bunkerweb.rules"]
local blacklist = dofile("__BLACKLIST__")

local failures = 0
local function check(label, got, want)
    if got ~= want then
        failures = failures + 1
        print("FAIL " .. label .. " : got " .. tostring(got) .. ", wanted " .. tostring(want))
    end
end

-- Every ignore list below matches this request; only the rule's own kinds decide which one counts.
local function ignored(rule_text, lists)
    local instance = setmetatable({
        logger = { log = function() end },
        variables = { BLACKLIST_RDNS_GLOBAL = "no" },
        lists = {
            IGNORE_IP = lists.IGNORE_IP or {},
            IGNORE_RDNS = lists.IGNORE_RDNS or {},
            IGNORE_ASN = lists.IGNORE_ASN or {},
            IGNORE_USER_AGENT = lists.IGNORE_USER_AGENT or {},
            IGNORE_URI = lists.IGNORE_URI or {},
        },
        ctx = {
            bw = {
                remote_addr = "203.0.113.5",
                uri = "/static/app.js",
                http_user_agent = "GoodBot/1.0",
                asn_number = 64500,
                ip_is_global = true,
            },
        },
    }, blacklist)
    local terms = rules.parse(rule_text)
    assert(terms, "the fixture rule does not parse: " .. rule_text)
    return instance:is_ignored({ id = "BLACKLIST_RULE_1", text = rule_text, terms = terms }) == true
end

local ALL = {
    IGNORE_IP = { "203.0.113.0/24" },
    IGNORE_RDNS = { ".ignore.example" },
    IGNORE_ASN = { "64500" },
    IGNORE_USER_AGENT = { "^GoodBot" },
    IGNORE_URI = { "^/static" },
}

-- One kind at a time, both directions. The "out of scope" half is the security assertion.
local MATRIX = {
    { "ip", "ip:203.0.113.0/24 AND country:CN", "country:CN AND asn:64501" },
    { "uri", "uri:^/static AND country:CN", "ip:203.0.113.0/24 AND country:CN" },
    { "ua", "ua:^GoodBot AND country:CN", "ip:203.0.113.0/24 AND country:CN" },
    { "asn", "asn:64500 AND country:CN", "uri:^/static AND country:CN" },
    { "rdns", "rdns:.ignore.example AND country:CN", "uri:^/static AND country:CN" },
}
local LIST_OF = {
    ip = "IGNORE_IP",
    uri = "IGNORE_URI",
    ua = "IGNORE_USER_AGENT",
    asn = "IGNORE_ASN",
    rdns = "IGNORE_RDNS",
}
for _, case in ipairs(MATRIX) do
    local kind, in_scope, out_of_scope = case[1], case[2], case[3]
    local only = { [LIST_OF[kind]] = ALL[LIST_OF[kind]] }
    check(kind .. " ignore waives a rule that tests " .. kind, ignored(in_scope, only), true)
    check(kind .. " ignore must NOT waive a rule with no " .. kind .. " term", ignored(out_of_scope, only), false)
end

-- The headline case, spelled out: a matching IGNORE_URI cannot turn off an ip+country rule.
check("attacker-chosen URI cannot waive an ip AND country rule", ignored("ip:203.0.113.0/24 AND country:CN", ALL), true)
check(
    "…and with only the URI ignore set, it is not waived at all",
    ignored("ip:203.0.113.0/24 AND country:CN", { IGNORE_URI = ALL.IGNORE_URI }),
    false
)

-- country has no ignore counterpart, so a country-only rule is waived by nothing, even with
-- every other ignore list set and matching.
check("a country-only rule is never waived", ignored("country:CN", ALL), false)

-- The guard keys off the PARSED kind, not the spelling in the rule text: `user_agent:` is an
-- alias of `ua:` and must reach the IGNORE_USER_AGENT block just the same.
check("the ua alias is in scope too", ignored("user_agent:^GoodBot", { IGNORE_USER_AGENT = ALL.IGNORE_USER_AGENT }), true)

if failures == 0 then
    print("OK")
else
    print("FAILURES " .. failures)
end
"""


def test_a_blacklist_ignore_only_waives_a_rule_of_its_own_kind():
    harness = IGNORE_SCOPE_HARNESS.replace("__RULES__", MODULE.as_posix()).replace("__BLACKLIST__", BLACKLIST_MODULE.as_posix())
    output = run_lua(harness)
    assert output.strip().endswith("OK"), output

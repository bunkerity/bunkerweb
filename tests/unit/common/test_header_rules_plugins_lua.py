"""The six plugin wire-ups of the header criterion (hand-port of dev f61c03838 into 1.7).

The utility trio is covered by ``test_header_rules_lua.py``; what this file covers is the part
that could not be taken from dev verbatim, because 1.7 restructured all six plugins (composite
AND rules in ``rules.lua``, the workflow provider override in antibot). Every assertion here is
about **where** the check sits in ``access()``/``set()``, which is exactly what a grep cannot tell
you and what turns the feature into a bypass when it is wrong:

* a blacklist ignore header has to beat the **cache**, or a client that was denied once stays
  denied for 24h despite the operator's exemption;
* a blacklist header match has to deny with ``get_deny_status()`` and count a metric, not merely
  log;
* a whitelist header match has to be taken in ``set()`` too -- the ModSecurity kill switch reads
  ``ENV:is_whitelisted`` in phase 1, before ``access`` runs, and the header verdict is never
  cached, so a header-whitelisted probe would otherwise still trip the CRS;
* an antibot ignore header must **not** waive a challenge a workflow rule explicitly asked for.
  This is the one deliberate difference from dev's diff: dev has no workflow provider, so it puts
  the check at the top of ``access()``; in 1.7 that placement would let the header override a
  policy decision.

Runs the real plugin files under plain Lua with OpenResty stubbed, the way
``test_blacklist_retired_lists_lua.py`` does.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

# ------------------------------------------------------------------ shared Lua harness
HARNESS = r"""
ngx = {
    ERR = "ERR", INFO = "INFO", WARN = "WARN", OK = "OK",
    var = {},
    get_phase = function() return PHASE end,
    thread = { spawn = function() return {} end, wait = function() return false end },
    timer = { at = function() return true end },
}
PHASE = "access"

package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.ipmatcher"] = { new = function() return { match = function() return false end } end }
package.loaded["resty.dns.resolver"] = { new = function() return nil, "stubbed" end }
package.loaded["resty.env"] = { set = function(k, v) ENV[k] = v end }
package.loaded["bunkerweb.rules"] = {
    parse_family = function() return {}, {} end,
    warnings = function() return {} end,
    for_server = function() return {} end,
    evaluate = function() return nil end,
}
package.loaded["bunkerweb.plugin"] = {
    initialize = function() end,
    ret = function(_, ok, msg, status, redirect, data)
        return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
    end,
}

-- The header rules the plugin is handed, driven per case.
HEADER_RULES = {}
IGNORE_HEADER_RULES = {}
HEADERS = {}
ENV = {}
CACHE = {}
METRICS = {}
MATCH_CALLS = {}

package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_multiple_variables = function() return {} end,
    get_deny_status = function() return 403 end,
    get_variable = function() return "", "success" end,
    get_ips = function() return {} end,
    get_rdns = function() return {} end,
    rdns_forward_confirmed = function() return nil end,
    regex_match = function() return nil end,
    deduplicate_list = function(l) return l end,
    -- Faithful stand-in for the real matcher: returns the NAME of the first rule whose header is
    -- present (and whose value matches exactly, when it has one).
    match_header_rules = function(_, rules, source)
        MATCH_CALLS[#MATCH_CALLS + 1] = source
        for _, rule in ipairs(rules or {}) do
            local value = HEADERS[rule.name]
            -- Anchored-literal stand-in for PCRE, enough to tell a right value from a wrong one.
            local literal = rule.value and rule.value:gsub("^%^", ""):gsub("%$$", "") or nil
            if value ~= nil and (literal == nil or literal == value) then
                return rule.name
            end
        end
        return nil
    end,
}

local PLUGIN = dofile("__MODULE__")

-- Instance shaped like what plugin:initialize() leaves behind, with the two header-rule fields
-- filled the way the plugin's own initialize() fills them from the internalstore.
function instance(overrides)
    local self = setmetatable({
        is_loading = false,
        is_request = true,
        logger = { log = function() end },
        log_throttled = function() end,
        variables = VARIABLES,
        lists = LISTS,
        rules = {},
        header_rules = HEADER_RULES,
        ignore_header_rules = IGNORE_HEADER_RULES,
        ctx = { bw = { server_name = "www.example.com", remote_addr = "1.2.3.4", uri = "/", http_headers = HEADERS } },
        cachestore_local = {
            get = function(_, key) return true, CACHE[key] end,
            set = function(_, key, value) CACHE[key] = value return true end,
        },
        internalstore = {
            get = function(_, key) return STORE[key], "ok" end,
            set = function(_, key, value) STORE[key] = value return true end,
        },
        set_metric = function(_, kind, key, value) METRICS[key] = value end,
        get_data = function(_, blacklisted)
            local data = {}
            if blacklisted:lower() == "ip" then
                data["id"] = "ip"
            else
                local id, value = blacklisted:match("^(%w+) (.+)$")
                if id and value then
                    id = id:lower()
                    data["id"] = id
                    data[id] = value
                end
            end
            return data
        end,
    }, PLUGIN)
    for k, v in pairs(overrides or {}) do self[k] = v end
    return self
end

VARIABLES = {}
LISTS = {}
STORE = {}
"""


def run(plugin: str, body: str, *, module: Path | None = None) -> str:
    path = module or (CORE / plugin / f"{plugin}.lua")
    script = HARNESS.replace("__MODULE__", str(path)) + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


BLACKLIST_VARS = """
VARIABLES = {
    USE_BLACKLIST = "yes", BLACKLIST_RDNS_GLOBAL = "yes",
    BLACKLIST_IP = "", BLACKLIST_RDNS = "", BLACKLIST_ASN = "", BLACKLIST_USER_AGENT = "", BLACKLIST_URI = "",
    BLACKLIST_IGNORE_IP = "", BLACKLIST_IGNORE_RDNS = "", BLACKLIST_IGNORE_ASN = "",
    BLACKLIST_IGNORE_USER_AGENT = "", BLACKLIST_IGNORE_URI = "",
}
LISTS = {
    IP = {}, RDNS = {}, ASN = {}, USER_AGENT = {}, URI = {},
    IGNORE_IP = {}, IGNORE_RDNS = {}, IGNORE_ASN = {}, IGNORE_USER_AGENT = {}, IGNORE_URI = {},
}
"""


class TestBlacklistIgnoreHeaderBeatsTheCache:
    def test_a_cached_deny_is_overridden_by_the_ignore_header(self):
        # The cache is keyed by client attribute and lives 24h. If the ignore header were checked
        # after it, an operator exempting a client would not actually exempt it until the entry
        # expired -- the exact "wins over everything, cached verdicts included" property.
        out = run(
            "blacklist",
            BLACKLIST_VARS + r"""
CACHE["plugin_blacklist_www.example.comip1.2.3.4"] = "ip"
IGNORE_HEADER_RULES = { { name = "x-bypass", value = "^s3cr3t$" } }
HEADERS = { ["x-bypass"] = "s3cr3t" }
local result = instance():access()
print(tostring(result.status), result.msg)
""",
        )
        status, msg = out.rstrip("\n").split("\t", 1)
        assert status == "nil", "a cached deny must not survive the ignore header"
        assert msg == "header x-bypass is ignored"

    def test_without_the_header_the_cached_deny_still_applies(self):
        out = run(
            "blacklist",
            BLACKLIST_VARS + r"""
CACHE["plugin_blacklist_www.example.comip1.2.3.4"] = "ip"
IGNORE_HEADER_RULES = { { name = "x-bypass", value = "^s3cr3t$" } }
HEADERS = {}
local result = instance():access()
print(tostring(result.status))
""",
        )
        assert out.strip() == "403", "the ignore header must not disarm the cache for everyone"

    def test_the_wrong_value_does_not_exempt(self):
        out = run(
            "blacklist",
            BLACKLIST_VARS + r"""
CACHE["plugin_blacklist_www.example.comip1.2.3.4"] = "ip"
IGNORE_HEADER_RULES = { { name = "x-bypass", value = "^s3cr3t$" } }
HEADERS = { ["x-bypass"] = "guess" }
local result = instance():access()
print(tostring(result.status))
""",
        )
        assert out.strip() == "403"


class TestBlacklistHeaderMatchDenies:
    def test_a_matching_header_denies_and_counts_a_metric(self):
        out = run(
            "blacklist",
            BLACKLIST_VARS + r"""
HEADER_RULES = { { name = "x-flagged", value = "^bad$" } }
HEADERS = { ["x-flagged"] = "bad" }
local result = instance():access()
print(tostring(result.status), tostring(METRICS["failed_header"]), tostring(result.data.header))
""",
        )
        assert out.split() == ["403", "1", "x-flagged"]

    def test_the_ignore_header_wins_over_a_matching_header(self):
        out = run(
            "blacklist",
            BLACKLIST_VARS + r"""
HEADER_RULES = { { name = "x-flagged", value = "^bad$" } }
IGNORE_HEADER_RULES = { { name = "x-bypass", value = "^s3cr3t$" } }
HEADERS = { ["x-flagged"] = "bad", ["x-bypass"] = "s3cr3t" }
local result = instance():access()
print(tostring(result.status), result.msg)
""",
        )
        assert out.split("\t", 1)[0] == "nil"
        assert "is ignored" in out


class TestWhitelistHeaderInSetPhase:
    def test_set_marks_the_request_whitelisted_for_the_modsecurity_kill_switch(self):
        # set() runs in phase 1, before access(). ENV:is_whitelisted is what the ModSecurity
        # kill switch tests, so a header decision taken only in access() leaves a whitelisted
        # request tripping the CRS.
        out = run(
            "whitelist",
            r"""
VARIABLES = { USE_WHITELIST = "yes" }
LISTS = { IP = {}, RDNS = {}, ASN = {}, USER_AGENT = {}, URI = {} }
HEADER_RULES = { { name = "x-trusted", value = "^s3cr3t$" } }
HEADERS = { ["x-trusted"] = "s3cr3t" }
local result = instance():set()
print(tostring(ENV["is_whitelisted"]), tostring(ngx.var.is_whitelisted), result.msg)
""",
        )
        env, ngx_var, msg = out.rstrip("\n").split("\t", 2)
        assert env == "yes" and ngx_var == "yes"
        assert msg.strip() == "header x-trusted is whitelisted"

    def test_set_leaves_a_request_without_the_header_alone(self):
        out = run(
            "whitelist",
            r"""
VARIABLES = { USE_WHITELIST = "yes" }
LISTS = { IP = {}, RDNS = {}, ASN = {}, USER_AGENT = {}, URI = {} }
HEADER_RULES = { { name = "x-trusted", value = "^s3cr3t$" } }
HEADERS = {}
instance():set()
print(tostring(ENV["is_whitelisted"]))
""",
        )
        assert out.strip() == "no"

    def test_access_marks_it_too_and_counts_the_metric(self):
        out = run(
            "whitelist",
            r"""
VARIABLES = { USE_WHITELIST = "yes" }
LISTS = { IP = {}, RDNS = {}, ASN = {}, USER_AGENT = {}, URI = {} }
HEADER_RULES = { { name = "x-trusted", value = "^s3cr3t$" } }
HEADERS = { ["x-trusted"] = "s3cr3t" }
local result = instance():access()
print(tostring(result.status), tostring(METRICS["passed_whitelist"]), result.msg)
""",
        )
        assert out.split()[:2] == ["OK", "1"]


class TestGreylistHeader:
    def test_a_matching_header_greylists_before_the_cache(self):
        out = run(
            "greylist",
            r"""
VARIABLES = { USE_GREYLIST = "yes", GREYLIST_IP = "", GREYLIST_RDNS = "", GREYLIST_ASN = "", GREYLIST_USER_AGENT = "", GREYLIST_URI = "" }
LISTS = { IP = {}, RDNS = {}, ASN = {}, USER_AGENT = {}, URI = {} }
HEADER_RULES = { { name = "x-grey", value = "^v$" } }
HEADERS = { ["x-grey"] = "v" }
local result = instance():access()
print(result.msg)
""",
        )
        assert out.strip() == "header x-grey is in greylist"


class TestDnsblIgnoreHeader:
    def test_the_ignore_header_skips_the_dnsbl_lookup(self):
        out = run(
            "dnsbl",
            r"""
VARIABLES = { USE_DNSBL = "yes", DNSBL_LIST = "bl.example.com", DNSBL_IGNORE_IP = "" }
LISTS = { IGNORE_IP = {} }
HEADER_RULES = { { name = "x-skip", value = "^v$" } }
HEADERS = { ["x-skip"] = "v" }
-- The ip_is_global guard sits above the header check, exactly as in dev: a non-global client
-- never reaches a DNSBL lookup in the first place.
local i = instance()
i.ctx.bw.ip_is_global = true
local result = i:access()
print(result.msg)
""",
        )
        assert out.strip() == "header x-skip is ignored for DNSBL checks"


# ------------------------------------------------------------------ source-shape assertions
#
# These four facts are positional, so they are asserted on the source. Each names the exact
# failure mode moving the call would produce.


def _access_body(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    body = re.search(rf"^function {name}:access\(\).*?^end$", text, re.S | re.M)
    assert body, f"{name}:access() not found"
    return body.group(0)


class TestAntibotIgnoreHeaderRespectsTheWorkflowProvider:
    def test_the_check_sits_inside_the_workflow_guard(self):
        # dev's own diff puts this at the very top of access(), which is right for dev -- it has
        # no workflow provider. In 1.7 that placement would let the service's ignore header waive
        # a challenge a workflow rule explicitly demanded, and the ignore lists next to it are
        # deliberately inside the guard for exactly that reason.
        body = _access_body(CORE / "antibot" / "antibot.lua", "antibot")
        guard = body.index("if not self.ctx.bw.workflow_antibot_provider then")
        call = body.index('match_header_rules(self.ctx, self.header_rules, "ANTIBOT_IGNORE_HEADER_VALUE")')
        checks = body.index("-- Check the caches and ignore lists")
        assert guard < call < checks, "the antibot ignore header must be checked inside the workflow-provider guard and " "before the cache/ignore-list pass"

    def test_it_is_checked_before_the_cache(self):
        body = _access_body(CORE / "antibot" / "antibot.lua", "antibot")
        call = body.index('match_header_rules(self.ctx, self.header_rules, "ANTIBOT_IGNORE_HEADER_VALUE")')
        cache = body.index("self:is_in_cache(v)")
        assert call < cache


class TestCountryIgnoreHeader:
    def test_it_is_checked_before_the_country_cache(self):
        body = _access_body(CORE / "country" / "country.lua", "country")
        call = body.index('match_header_rules(self.ctx, self.header_rules, "COUNTRY_IGNORE_HEADER_VALUE")')
        cache = body.index("self:is_in_cache(self.ctx.bw.remote_addr)")
        assert call < cache, "a cached country verdict must not survive the ignore header"


class TestEveryPluginResolvesItsFamilyAtInit:
    # (plugin, prefix, internalstore key) -- init() must resolve the family once per configuration
    # load. Resolving it per request would walk every scoped variable on the request path and,
    # worse, compile the operator's secret pattern there, where a compile error is logged verbatim.
    EXPECTED = [
        ("antibot", "ANTIBOT_IGNORE_HEADER", "plugin_antibot_header_rules"),
        ("blacklist", "BLACKLIST_HEADER", "plugin_blacklist_header_rules"),
        ("blacklist", "BLACKLIST_IGNORE_HEADER", "plugin_blacklist_ignore_header_rules"),
        ("country", "COUNTRY_IGNORE_HEADER", "plugin_country_header_rules"),
        ("dnsbl", "DNSBL_IGNORE_HEADER", "plugin_dnsbl_header_rules"),
        ("greylist", "GREYLIST_HEADER", "plugin_greylist_header_rules"),
        ("whitelist", "WHITELIST_HEADER", "plugin_whitelist_header_rules"),
    ]

    @pytest.mark.parametrize("plugin,prefix,key", EXPECTED)
    def test_init_resolves_and_stores_the_family(self, plugin, prefix, key):
        text = (CORE / plugin / f"{plugin}.lua").read_text(encoding="utf-8")
        assert f'self:init_header_rules("{prefix}", "{key}")' in text
        assert f'self:load_header_rules("{key}")' in text

    @pytest.mark.parametrize("plugin,prefix,key", EXPECTED)
    def test_the_settings_exist_in_plugin_json(self, plugin, prefix, key):
        from json import loads

        settings = loads((CORE / plugin / "plugin.json").read_text(encoding="utf-8"))["settings"]
        for suffix in ("NAME", "VALUE"):
            name = f"{prefix}_{suffix}"
            assert name in settings, f"{plugin}: {name} is missing"
            assert settings[name]["context"] == "multisite"
            assert settings[name]["default"] == ""
        # The value is the operator's shared secret: it must not be rendered in clear in the UI.
        assert settings[f"{prefix}_VALUE"]["type"] == "password"
        # Both halves must share one `multiple` group, or the UI cannot pair NAME_2 with VALUE_2.
        assert settings[f"{prefix}_NAME"]["multiple"] == settings[f"{prefix}_VALUE"]["multiple"]


class TestTheBaseClassHelpersExist:
    def test_plugin_lua_exposes_both_halves(self):
        text = (ROOT / "src" / "bw" / "lua" / "bunkerweb" / "plugin.lua").read_text(encoding="utf-8")
        assert "function plugin:init_header_rules(prefix, key)" in text
        assert "function plugin:load_header_rules(key)" in text

"""Whitelist criteria, cached decisions and initialization against the real Lua module."""

import pytest
from _lua_plugin_helpers import CORE, LUA, run_module, to_lua

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "whitelist" / "whitelist.lua"
SERVER = "www.example.com"
KINDS = ("IP", "RDNS", "ASN", "USER_AGENT", "URI")
PREAMBLE = r"""
ENV = {}
package.loaded["resty.env"] = { set = function(k, v) ENV[k] = v end }
"""
SETUP = "VARIABLES = " + to_lua({"USE_WHITELIST": "yes", "WHITELIST_RDNS_GLOBAL": "no", **{f"WHITELIST_{k}": "" for k in KINDS}})


def run(body, *, fs_root=None, preamble=""):
    return run_module(MODULE, SETUP + "\n" + body, fs_root=fs_root, preamble=PREAMBLE + preamble)


def access(lists=None, *, context=None, setup="", method="access"):
    return run(f"""
STORE["plugin_whitelist_lists_{SERVER}"] = {to_lua(lists or {})}
{setup}
local p = new_plugin(PLUGIN, {to_lua(context or {})})
local r = p:{method}()
emit({{ result = summary(r), flags = {{ ngx.var.is_whitelisted, p.ctx.bw.is_whitelisted, ENV.is_whitelisted }},
        metrics = METRICS, cache = CACHE, ttl = CACHE_TTL, logs = LOGS }})
""")


@pytest.mark.parametrize(
    "lists,context,setup,info",
    [
        ({"IP": ["1.2.3.0/24"]}, {}, "", "IP is whitelisted (info : ip)"),
        ({"URI": ["^/health"]}, {"uri": "/health/live"}, "", "URI is whitelisted (info : URI ^/health)"),
        ({"USER_AGENT": ["Monitor"]}, {"http_user_agent": "Monitor/1"}, "", "UA is whitelisted (info : UA Monitor)"),
        ({"RDNS": [".trusted.example"]}, {}, 'RDNS = { "bot.trusted.example" }; FCRDNS = true', "IP is whitelisted (info : rDNS .trusted.example)"),
        ({"ASN": ["64496"]}, {"ip_is_global": True}, "ASN = 64496", "IP is whitelisted (info : ASN 64496)"),
    ],
)
def test_each_matching_criterion_grants_and_caches_only_its_verdict(lists, context, setup, info):
    out = access(lists, context=context, setup=setup)
    assert out["result"] == {"ret": True, "msg": info, "status": "OK"}
    assert out["flags"] == ["yes", "yes", "yes"]
    assert out["metrics"] == {"passed_whitelist": 1}
    assert out["ttl"] == 86400
    assert any(value != "ok" for value in out["cache"].values())


@pytest.mark.parametrize(
    "lists,context,setup",
    [
        ({"IP": ["1.2.4.0/24"]}, {}, ""),
        ({"URI": ["^/health"], "USER_AGENT": ["Monitor"]}, {"http_user_agent": "curl"}, ""),
        ({"RDNS": [".trusted.example"]}, {}, 'RDNS = { "bot.trusted.example" }; FCRDNS = false'),
        ({"RDNS": [".trusted.example"]}, {}, 'VARIABLES.WHITELIST_RDNS_GLOBAL = "yes"; RDNS = { "bot.trusted.example" }; FCRDNS = true'),
        ({"ASN": ["64496"]}, {"ip_is_global": False}, "ASN = 64496"),
        ({"ASN": ["64496"]}, {"ip_is_global": True}, "ASN = 64511"),
    ],
)
def test_nonmatching_or_unconfirmed_criteria_never_grant(lists, context, setup):
    out = access(lists, context=context, setup=setup)
    assert out["result"] == {"ret": True, "msg": "not whitelisted"}
    assert out["metrics"] == {}
    assert all(value == "ok" for value in out["cache"].values())


@pytest.mark.parametrize(
    "lists,context,error",
    [
        ({"IP": ["bad-address"]}, {}, "error while checking if IP is whitelisted : invalid address bad-address"),
        ({}, {"remote_addr": "bad-address"}, "error while checking if IP is whitelisted : invalid client address"),
        ({"RDNS": [".trusted.example"]}, {}, "error while getting rdns : rdns lookup failed"),
        ({"ASN": ["64496"]}, {"ip_is_global": True}, "can't get ASN of IP 1.2.3.4 : asn lookup failed"),
    ],
)
def test_lookup_failures_are_logged_without_granting(lists, context, error):
    out = access(lists, context=context)
    assert out["result"] == {"ret": True, "msg": "not whitelisted"}
    assert ["ERR", error] in out["logs"]
    assert out["metrics"] == {}


@pytest.mark.parametrize("method", ["set", "access"])
def test_cached_pass_sets_all_three_whitelist_flags(method):
    out = access(setup=f'CACHE["plugin_whitelist_{SERVER}ip1.2.3.4"] = "ip"', method=method)
    assert out["flags"] == ["yes", "yes", "yes"]
    assert out["result"]["msg"] == "IP is in cached whitelist (info : ip)"
    assert out["metrics"] == ({"passed_whitelist": 1} if method == "access" else {})


def test_cached_negative_skips_a_now_matching_ip():
    out = access({"IP": ["1.2.3.4"]}, setup=f'CACHE["plugin_whitelist_{SERVER}ip1.2.3.4"] = "ok"')
    assert out["result"]["msg"] == "not whitelisted"
    assert out["metrics"] == {}


def test_cache_read_failure_logs_then_evaluates_lists():
    out = access({"IP": ["1.2.3.4"]}, setup='CACHE_ERROR = "unavailable"')
    assert out["result"]["status"] == "OK"
    assert ["ERR", "error while checking cache : unavailable"] in out["logs"]


def test_cache_write_failure_preserves_positive_decision_and_logs():
    out = access({"IP": ["1.2.3.4"]}, setup='CACHE_SET_ERROR = "full"')
    assert out["result"]["status"] == "OK"
    assert ["ERR", "error while adding element to cache : full"] in out["logs"]
    assert out["cache"] == {}


@pytest.mark.parametrize("method", ["set", "access"])
def test_missing_lists_is_an_error_in_both_request_phases(method):
    out = run(f"""
local p = new_plugin(PLUGIN)
p.lists = nil
emit(summary(p:{method}()))
""")
    assert out == {"ret": False, "msg": "lists is nil"}


def test_set_resets_stale_flags_when_disabled():
    out = run("""
VARIABLES.USE_WHITELIST = "no"
local p = new_plugin(PLUGIN)
ngx.var.is_whitelisted, p.ctx.bw.is_whitelisted, ENV.is_whitelisted = "yes", "yes", "yes"
local r = p:set()
emit({ msg = r.msg, flags = { ngx.var.is_whitelisted, p.ctx.bw.is_whitelisted, ENV.is_whitelisted } })
""")
    assert out == {"msg": "whitelist not activated", "flags": ["no", "no", "no"]}


def test_initialize_copies_deduplicates_and_does_not_mutate_shared_lists():
    out = run(f"""
VARIABLES.WHITELIST_IP = "1.2.3.4 9.9.9.9"
STORE["plugin_whitelist_lists_{SERVER}"] = {{ IP = {{ "1.2.3.4" }} }}
local p = new_plugin(PLUGIN)
local other = new_plugin(PLUGIN)
emit({{ own = p.lists.IP, other = other.lists.IP, shared = STORE["plugin_whitelist_lists_{SERVER}"].IP }})
""")
    assert out == {"own": ["1.2.3.4", "9.9.9.9"], "other": ["1.2.3.4", "9.9.9.9"], "shared": ["1.2.3.4"]}


def test_missing_internalstore_lists_still_applies_manual_setting():
    out = access(setup='STORE = {}; VARIABLES.WHITELIST_IP = "1.2.3.4"')
    assert out["result"]["status"] == "OK"
    assert ["ERR", f"no such key plugin_whitelist_lists_{SERVER}"] in out["logs"]


def test_preread_keeps_the_access_decision():
    assert access({"IP": ["1.2.3.4"]}, method="preread")["result"]["status"] == "OK"


def test_init_merges_active_downloads_and_manual_entries_per_service(tmp_path):
    for server in ("a.example", "b.example"):
        folder = tmp_path / "whitelist" / server
        folder.mkdir(parents=True)
        (folder / "IP.list").write_text("1.2.3.4\n\n1.2.3.4\n", encoding="utf-8")
    out = run(
        """
PHASE, IS_REQUEST = "init", false
local r = new_plugin(PLUGIN):init()
emit({ result = summary(r), store = STORE })
""",
        fs_root=tmp_path,
        preamble="""
local settings = {
    ["a.example"] = { WHITELIST_IP_URLS = "https://example.test/list", WHITELIST_IP = "9.9.9.9 1.2.3.4" },
    ["b.example"] = { WHITELIST_IP_URLS = "", WHITELIST_URI = "^/health" },
}
package.loaded["bunkerweb.utils"].get_variable = function(name, _, context)
    if name == "SERVER_NAME" then return "a.example b.example" end
    return settings[context.bw.server_name][name]
end
""",
    )
    assert out["result"]["ret"] is True
    a = out["store"]["plugin_whitelist_lists_a.example"]
    b = out["store"]["plugin_whitelist_lists_b.example"]
    assert a["IP"] == ["1.2.3.4", "9.9.9.9"]
    assert not b["IP"]  # A retired downloaded file must not grant trust.
    assert b["URI"] == ["^/health"]
    assert out["store"]["plugin_whitelist_header_rules"] == {"name": "WHITELIST_HEADER"}


@pytest.mark.parametrize(
    "setup,msg",
    [
        ("HAS_VARIABLE = false", "init not needed"),
        ("GETVAR = {}", "can't get SERVER_NAME variable : no such variable SERVER_NAME"),
        ('STORE_SET_ERROR = "full"', f"can't store whitelist {SERVER} list into internalstore : full"),
        ('HEADER_RULES_ERROR = "invalid header"', "invalid header"),
    ],
)
def test_init_guards_and_failures(setup, msg):
    out = run(f"""
PHASE, IS_REQUEST = "init", false
GETVAR = {{ SERVER_NAME = "{SERVER}" }}
{setup}
emit(summary(new_plugin(PLUGIN):init()))
""")
    assert out == {"ret": msg == "init not needed", "msg": msg}

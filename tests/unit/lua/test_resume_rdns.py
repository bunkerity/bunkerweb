"""Run shipped DNS functions and callers in Lua with resolver/cache/ipmatcher doubles.

The matcher double models canonical address equality using Python's ipaddress;
this is request-path proof, not OpenResty/FFI or live DNS integration proof.
"""

import ipaddress
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src/bw/lua/bunkerweb/utils.lua"
LUA = shutil.which("lua") or shutil.which("luajit") or "/usr/local/bin/lua"
pytestmark = pytest.mark.skipif(not Path(LUA).exists(), reason="Lua interpreter unavailable")


def function_source(path, signature):
    match = re.search(rf"^{re.escape(signature)}.*?^end$", path.read_text(), re.M | re.S)
    assert match, signature
    return match.group(0)


PREAMBLE = r"""
local utils, cache, encoded, queries, logs = {}, {}, {}, {}, {}
local ERR, WARN = 'ERR', 'WARN'
local logger = {log = function(_, level, message) table.insert(logs, {level, message}) end}
local use_ipv6, setup_error, query_error = 'no', false, false
local ipv4, ipv6 = '192.0.2.1', '2001:db8::1'
local ptrs = {'bot.example.com'}
local function encode(value)
    local key = 'json:' .. (#encoded + 1)
    encoded[#encoded + 1] = value
    return key
end
local function decode(key) return encoded[tonumber(key:sub(6))] end
local cachestore = {
    get = function(_, key) return true, cache[key] end,
    set = function(_, key, value, ttl) assert(ttl == 3600); cache[key] = value; return true end,
}
utils.new_cachestore = function() return cachestore end
utils.get_variable = function(name) assert(name == 'USE_IPV6'); return use_ipv6 end
utils.get_resolvers = function()
    if setup_error then return nil, 'resolver unavailable' end
    return {'127.0.0.1'}
end
local resolver = {new = function()
    return {
        TYPE_A = 1, TYPE_AAAA = 28,
        query = function(_, fqdn, options)
            table.insert(queries, {fqdn, options.qtype})
            if query_error then return nil, 'timeout' end
            local address = options.qtype == 28 and ipv6 or ipv4
            if not address then return {} end
            return {{address = address}}
        end,
        reverse_query = function()
            if query_error then return nil, 'timeout' end
            local answers = {}
            for _, ptr in ipairs(ptrs) do table.insert(answers, {ptrdname = ptr}) end
            return answers
        end,
    }
end}
local canonical = __CANONICAL__
local matcher_error, match_error = false, false
local function ipmatcher_new(values)
    if matcher_error then return nil, 'invalid address' end
    return {match = function(_, address)
        if match_error then return nil, 'invalid client' end
        for _, value in ipairs(values) do
            if (canonical[value] or value) == (canonical[address] or address) then return true end
        end
        return false
    end}
end
local ipmatcher = {new = ipmatcher_new}
local ngx = {ERR = ERR}
local ctx = {bw = {remote_addr = '2001:0DB8:0000:0000:0000:0000:0000:0001', ip_is_global = true}}
"""


def run_lua(tmp_path, body):
    addresses = ["2001:db8::1", "2001:0DB8:0000:0000:0000:0000:0000:0001", "2001:db8::2", "192.0.2.1", "192.0.2.2"]
    mapping = "{" + ",".join(f"[{json.dumps(ip)}]={json.dumps(str(ipaddress.ip_address(ip)))}" for ip in addresses) + "}"
    source = PREAMBLE.replace("__CANONICAL__", mapping)
    for name in ("get_rdns", "get_ips", "rdns_forward_confirmed"):
        source += "\n" + function_source(UTILS, f"utils.{name} = function")
    script = tmp_path / "rdns.lua"
    script.write_text(source + "\n" + body)
    result = subprocess.run([LUA, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("client", ["2001:db8::1", "2001:0DB8:0000:0000:0000:0000:0000:0001", "192.0.2.1"])
@pytest.mark.parametrize("setting", ["yes", "no"])
def test_forward_confirmed_address(tmp_path, client, setting):
    run_lua(
        tmp_path, f"use_ipv6 = '{setting}'\nassert(utils.rdns_forward_confirmed(ptrs, {{'.example.com'}}, ctx, {json.dumps(client)}, logger) == '.example.com')"
    )


@pytest.mark.parametrize("first_force", [False, True])
def test_family_cache_isolation(tmp_path, first_force):
    forced = str(first_force).lower()
    run_lua(
        tmp_path,
        f"""
local first = utils.get_ips('bot.example.com', false, ctx, true, {forced})
local second = utils.get_ips('bot.example.com', false, ctx, true, not {forced})
assert(#first == ({forced} and 2 or 1), 'wrong initial family')
assert(#second == ({forced} and 1 or 2), 'cross-family cache contamination')
assert(#queries == 3)
utils.get_ips('bot.example.com', false, ctx, true, {forced})
assert(#queries == 3, 'cache miss')
""",
    )


def test_setting_change_selects_family_cache(tmp_path):
    run_lua(
        tmp_path,
        """
assert(#utils.get_ips('bot.example.com', nil, ctx, true) == 1)
use_ipv6 = 'yes'
assert(#utils.get_ips('bot.example.com', nil, ctx, true) == 2)
assert(#utils.get_ips('bot.example.com', false, ctx, true) == 1, 'DNSBL must stay A-only')
assert(#queries == 3)
""",
    )


@pytest.mark.parametrize(
    "failure", ["ipv4 = '192.0.2.2'; ipv6 = '2001:db8::2'", "query_error = true", "setup_error = true", "matcher_error = true", "match_error = true"]
)
def test_spoof_and_failures_do_not_grant(tmp_path, failure):
    run_lua(tmp_path, failure + "\nassert(utils.rdns_forward_confirmed(ptrs, {'.example.com'}, ctx, ctx.bw.remote_addr, logger) == nil)")


def test_negative_dns_cache_is_family_specific(tmp_path):
    run_lua(
        tmp_path,
        """
query_error = true
assert(#utils.get_ips('bot.example.com', false, ctx, true) == 0)
assert(#queries == 1)
query_error = false
assert(#utils.get_ips('bot.example.com', false, ctx, true) == 0)
assert(#queries == 1, 'negative A cache must avoid another query')
assert(utils.rdns_forward_confirmed(ptrs, {'.example.com'}, ctx, ctx.bw.remote_addr, logger) == '.example.com')
assert(#queries == 3, 'negative A cache must not suppress AAAA')
cache = {}; queries = {}; query_error = true
assert(#utils.get_ips('bot.example.com', nil, ctx, true, true) == 0)
query_error = false
assert(#utils.get_ips('bot.example.com', nil, ctx, true, true) == 0)
assert(#queries == 2, 'negative dual-stack cache must avoid another query')
""",
    )


def test_negative_reverse_cache(tmp_path):
    run_lua(
        tmp_path,
        """
query_error = true
assert(#utils.get_rdns(ctx.bw.remote_addr, ctx, true) == 0)
query_error = false
assert(#utils.get_rdns(ctx.bw.remote_addr, ctx, true) == 0)
""",
    )


@pytest.mark.parametrize(
    "plugin,method", [("whitelist", "is_whitelisted_ip"), ("greylist", "is_greylisted_ip"), ("antibot", "is_ignored_ip"), ("blacklist", "is_blacklisted_ip")]
)
def test_flat_callers_use_confirmation(tmp_path, plugin, method):
    path = ROOT / f"src/common/core/{plugin}/{plugin}.lua"
    source = function_source(path, f"function {plugin}:{method}(")
    run_lua(
        tmp_path,
        f"""
local {plugin} = {{}}
local get_rdns, get_ips, rdns_forward_confirmed = utils.get_rdns, utils.get_ips, utils.rdns_forward_confirmed
{source}
local self = setmetatable({{
    ctx = ctx, variables = {{}}, logger = logger,
    lists = {{IP = {{}}, RDNS = {{'.example.com'}}, ASN = {{}}, IGNORE_IP = {{}}, IGNORE_RDNS = {{'.example.com'}}, IGNORE_ASN = {{}}}},
}}, {{__index = {plugin}}})
local granted = self:{method}()
assert(granted == {str(plugin != 'blacklist').lower()}, 'caller failed IPv6 confirmation')
ipv6 = '2001:db8::2'; cache = {{}}
assert(self:{method}() == {str(plugin == 'blacklist').lower()}, 'caller granted spoofed PTR')
""",
    )


def test_blacklist_composite_ignore_confirmation(tmp_path):
    path = ROOT / "src/common/core/blacklist/blacklist.lua"
    source = function_source(path, "function blacklist:is_ignored(")
    run_lua(
        tmp_path,
        f"""
local blacklist = {{}}
local get_rdns, rdns_forward_confirmed = utils.get_rdns, utils.rdns_forward_confirmed
{source}
local self = setmetatable({{ctx = ctx, variables = {{}}, logger = logger, lists = {{IGNORE_RDNS = {{'.example.com'}}}}}}, {{__index = blacklist}})
local rule = {{terms = {{{{kind = 'rdns'}}}}}}
assert(self:is_ignored(rule) == true)
ipv6 = '2001:db8::2'; cache = {{}}
assert(self:is_ignored(rule) == false, 'composite ignore granted spoofed PTR')
""",
    )


def test_composite_rules_use_confirmation(tmp_path):
    path = ROOT / "src/bw/lua/bunkerweb/rules.lua"
    run_lua(
        tmp_path,
        f"""
package.loaded['resty.ipmatcher'] = ipmatcher
package.loaded['bunkerweb.utils'] = utils
_G.ngx = ngx
local rules = dofile({json.dumps(str(path))})
local term = {{kind = 'rdns', values = {{'.example.com'}}}}
assert(rules.match_term(term, {{ctx = ctx, rdns_forward_confirm = true}}) == true)
ipv6 = '2001:db8::2'; cache = {{}}
assert(rules.match_term(term, {{ctx = ctx, rdns_forward_confirm = true}}) == false)
assert(rules.match_term(term, {{ctx = ctx, rdns_forward_confirm = false}}) == true, 'deny PTR semantics changed')
""",
    )

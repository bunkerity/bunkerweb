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
local negative_answer
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
            if negative_answer then return negative_answer end
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


@pytest.mark.parametrize("negative_answer", ["{}", "{errcode = 3, errstr = 'name error'}"], ids=["empty", "nxdomain"])
def test_negative_dns_cache_is_family_specific(tmp_path, negative_answer):
    run_lua(
        tmp_path,
        f"negative_answer = {negative_answer}\n"
        + """
assert(#utils.get_ips('bot.example.com', false, ctx, true) == 0)
assert(#queries == 1)
negative_answer = nil
assert(#utils.get_ips('bot.example.com', false, ctx, true) == 0)
assert(#queries == 1, 'negative A cache must avoid another query')
assert(utils.rdns_forward_confirmed(ptrs, {'.example.com'}, ctx, ctx.bw.remote_addr, logger) == '.example.com')
assert(#queries == 3, 'negative A cache must not suppress AAAA')
cache = {}; queries = {}
"""
        + f"negative_answer = {negative_answer}\n"
        + """
assert(#utils.get_ips('bot.example.com', nil, ctx, true, true) == 0)
negative_answer = nil
assert(#utils.get_ips('bot.example.com', nil, ctx, true, true) == 0)
assert(#queries == 2, 'negative dual-stack cache must avoid another query')
assert(#utils.get_ips('bot.example.com', false, ctx, true) == 1)
assert(#queries == 3, 'negative dual-stack cache must not suppress A-only lookup')
""",
    )


@pytest.mark.parametrize("force_ipv6", [False, True])
def test_dns_timeout_is_not_cached_and_retries(tmp_path, force_ipv6):
    forced = str(force_ipv6).lower()
    run_lua(
        tmp_path,
        f"""
query_error = true
local ips, err = utils.get_ips('bot.example.com', false, ctx, true, {forced})
assert(ips == false, 'timeout must return false')
assert(type(err) == 'string' and #err > 0)
assert(next(cache) == nil, 'timeout must not write DNS cache')
assert(#queries == ({forced} and 2 or 1))
assert(utils.get_ips('bot.example.com', false, ctx, true, {forced}) == false)
assert(next(cache) == nil, 'repeated timeout must not write DNS cache')
assert(#queries == ({forced} and 4 or 2), 'timeout must retry')
query_error = false
assert(#utils.get_ips('bot.example.com', false, ctx, true, {forced}) == ({forced} and 2 or 1))
assert(next(cache) ~= nil, 'recovered answer must be cached')
assert(#queries == ({forced} and 6 or 3), 'recovery must query again')
utils.get_ips('bot.example.com', false, ctx, true, {forced})
assert(#queries == ({forced} and 6 or 3), 'recovered cache must avoid another query')
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

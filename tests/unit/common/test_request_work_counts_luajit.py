"""Deterministic warm HTTP request budgets; real set/access/header/log Lua and core plugins.

OpenResty boundaries are fakes. Datastore, clusterstore, mlcache/IPC, lrucache, middleclass,
utils, constructors and dispatch are real. Default lists contain no downloaded feed entries.
BW_GUARD_SOURCE_ROOT selects a scratch export for regression/mutation proofs.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(os.environ.get("BW_GUARD_SOURCE_ROOT", ROOT))
LUAJIT = os.environ.get("BW_LUAJIT") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(not LUAJIT, reason="no LuaJIT on PATH (BW_LUAJIT)")


def _lua(value):
    if isinstance(value, str):
        delimiter = "="
        while "]" + delimiter + "]" in value:
            delimiter += "="
        return "[" + delimiter + "[" + value + "]" + delimiter + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"[ {_lua(k)} ]={_lua(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "{" + ",".join(map(_lua, value)) + "}"
    return json.dumps(value)


HARNESS = r"""
package.path = ROOT .. '/src/bw/lua/?.lua;' .. ROOT .. '/src/common/core/?.lua;' .. package.path
for _, lib in ipairs({'lua-resty-lrucache', 'lua-resty-ipmatcher', 'lua-resty-mlcache', 'lua-resty-lock'}) do
    package.path = ROOT .. '/src/deps/src/' .. lib .. '/lib/?.lua;' .. package.path
end
package.path = ROOT .. '/src/deps/src/lua-resty-ipmatcher/?.lua;' .. package.path
local phase = 'init'
local now = 1000
os.time = function() return now end
local counts, keys = {}, {}
-- Count real calls; fake storage does not model expiration, eviction or contention.
local function dict(name)
    local data = {}
    local function hit(method, key)
        counts[name] = counts[name] or {}
        counts[name][method] = (counts[name][method] or 0) + 1
        keys[#keys + 1] = name .. ':' .. method .. ':' .. key
    end
    return {
        get = function(_, key) hit('get', key); return data[key] end,
        get_stale = function(_, key) hit('get', key); return data[key], nil, false end,
        set = function(_, key, value) hit('set', key); data[key] = value; return true end,
        safe_set = function(_, key, value) hit('set', key); data[key] = value; return true end,
        add = function(_, key, value) hit('add', key); if data[key] ~= nil then return nil, 'exists' end; data[key] = value; return true end,
        incr = function(_, key, value, init) hit('incr', key); data[key] = (data[key] or init or 0) + value; return data[key] end,
        delete = function(_, key) hit('delete', key); data[key] = nil; return true end,
    }
end
ngx = {
    ERR=4, WARN=5, NOTICE=6, INFO=7, DEBUG=8, OK=0, HTTP_OK=200, HTTP_FORBIDDEN=403, HTTP_CLOSE=444,
    HTTP_BAD_REQUEST=400, HTTP_NOT_ALLOWED=405, HTTP_TOO_MANY_REQUESTS=429, HTTP_MOVED_TEMPORARILY=302,
    config={subsystem='http'}, ctx={}, shared={}, header={}, status=200,
    var={remote_addr='127.0.0.1', server_name='www.example.com', uri='/', request_uri='/', request_method='GET',
         http_host='www.example.com', scheme='http', request_id='request', http_user_agent='client', time_local='now'},
    req={is_internal=function() return false end, http_version=function() return 1.1 end,
         start_time=function() return 1000 end, get_headers=function() return {} end},
    thread={kill=function() end}, worker={pid=function() return 1 end, count=function() return 1 end, id=function() return 0 end},
    get_phase=function() return phase end, now=function() return now end, time=function() return now end,
    update_time=function() end, sleep=function() error('unexpected sleep') end, log=function() end,
    exit=function(s) error('unexpected exit ' .. s) end, redirect=function() error('unexpected redirect') end,
    re={match=function(s, pattern) if pattern == '^[A-Z][A-Z_-]{2,}$' then return s:match('^[A-Z]+$') end error('unexpected regex ' .. pattern) end},
}
for _, name in ipairs({'datastore','internalstore','cachestore','cachestore_ipc','cachestore_miss','cachestore_locks','metrics_datastore','sessions_revocation','worker_lock'}) do
    ngx.shared[name] = dict(name)
end
-- Round-trip tables only: this guard does not measure JSON serialization work.
local encoded = {['{}']={}}
local json = {
    encode=function(v) local token='json:' .. tostring(v); encoded[token]=v; return token end,
    decode=function(v) assert(encoded[v], 'unexpected JSON ' .. tostring(v)); return encoded[v] end,
}
package.loaded['cjson'], package.loaded['cjson.safe'] = json, json
package.loaded['ngx.errlog'] = {get_sys_filter_level=function() return ngx.WARN end, raw_log=function(level, message)
    if level <= ngx.ERR then error(message) end
end}
package.loaded['resty.core.base'] = {new_tab=function() return {} end, get_request=function() return true end}
package.loaded['resty.core.shdict'] = {}
package.loaded['table.clear'] = function(t) for k in pairs(t) do t[k]=nil end end
package.loaded['table.nkeys'] = function(t) local n=0; for _ in pairs(t) do n=n+1 end; return n end
package.loaded['bunkerweb.ctx'] = {apply_ref=function() end, stash_ref=function() end}
for _, name in ipairs({'resty.http','resty.dns.resolver','resty.redis.connector','resty.redis','resty.openssl.kdf',
    'ngx.ssl','ngx.ssl.clienthello','resty.openssl.x509','resty.openssl.pkey','resty.template','resty.sha256','resty.string',
    'base64','antibot.captcha','crowdsec.lib.config'}) do package.loaded[name] = {} end
package.loaded['crowdsec.cache_partition'] = {}
package.loaded['bunkerweb.mmdb'] = {}
package.loaded['resty.random'] = {bytes=function(n) return string.rep('x',n) end}
package.loaded['resty.session'] = {init=function() end}
package.loaded['resty.env'] = {set=function() end}
local utils = require 'bunkerweb.utils'
local base_calls, total_calls, objects = 0, 0, 0
local base, base_initialize
local get_variable = utils.get_variable
utils.get_variable = function(...)
    total_calls = total_calls + 1
    if base_initialize and debug.getinfo(2,'f').func == base_initialize then base_calls = base_calls + 1 end
    return get_variable(...)
end
base = require 'bunkerweb.plugin'
base_initialize = base.initialize
base.initialize = function(...)
    objects = objects + 1
    return base_initialize(...)
end
local real_open = io.open
io.open = function(path, mode)
    if path == '/usr/share/bunkerweb/core/order.json' then
        return {read=function() return json.encode(ORDER) end, close=function() end}
    end
    return real_open(path, mode)
end
local helpers = require 'bunkerweb.helpers'
local store = require('bunkerweb.datastore'):new(ngx.shared.internalstore)
assert(store:set('variables', {global=VARIABLES}, nil, true))
for _, m in ipairs(METADATA) do assert(store:set('plugin_' .. m.id, m, nil, true)) end
ORDER.header = ORDER.headers
local plugins = {}
for _, m in ipairs(METADATA) do
    local module, err = helpers.require_plugin(m.id)
    assert(module ~= false, err)
    m.phases = {}
    if module then for _, p in ipairs(utils.get_phases()) do
        if module[p] then m.phases[#m.phases+1] = p end
    end end
    plugins[#plugins+1] = m
end
local ordered, order = helpers.order_plugins(plugins, {global=VARIABLES})
assert(ordered, order)
ORDER = order
assert(store:set('plugins_order', ORDER, nil, true))
assert(store:set('misc_version', '1.6.18', nil, true))
assert(store:set('misc_integration', 'Docker', nil, true))
for _, name in ipairs({'whitelist','blacklist','greylist','dnsbl'}) do
    assert(store:set('plugin_' .. name .. '_lists_www.example.com', {IP={},RDNS={},ASN={},USER_AGENT={},URI={}}, nil, true))
end
assert(store:set('plugin_bunkernet_id', 'unit-id', nil, true))
assert(store:set('plugin_bunkernet_db', {}, nil, true))
assert(store:set('plugin_headers_custom_headers', {global={}}, nil, true))
assert(store:set('plugin_limit_rules', {global={['/']=VARIABLES.LIMIT_REQ_RATE}}, nil, true))
assert(store:set('plugin_limit_global_rules', {}, nil, true))
local sessions = assert(helpers.require_plugin('sessions'))
local session_obj = sessions:new()
assert(session_obj:init().ret)
local cache = require('bunkerweb.cachestore'):new(false)
-- A processed bootstrap broadcast gives the steady-state two-read IPC poll.
assert(cache:set('guard-prime', 'value'))
phase = 'access'
assert(cache:update())
local chunks = {}
for _, p in ipairs({'set','access','header','log'}) do
    local f = assert(io.open(ROOT .. '/src/common/confs/server-http/' .. p .. '-lua.conf'))
    local source=f:read('*a'); f:close()
    chunks[p] = assert(loadstring(assert(source:match('_by_lua_block%s*[^%{]*{(.*)}%s*$'))))
end
for request=1,3 do
    now = now + 2
    ngx.ctx={}
    ngx.header={}
    counts, keys={}, {}
    objects, base_calls, total_calls=0,0,0
    for _, p in ipairs({'set','access','header','log'}) do
        phase = p == 'header' and 'header_filter' or p
        local result = chunks[p]()
        assert(p == 'log' or result == true, p .. ' did not complete')
    end
    print('request=' .. request .. ' objects=' .. objects .. ' base=' .. base_calls .. ' total=' .. total_calls)
    for zone, methods in pairs(counts) do for method, count in pairs(methods) do print(zone .. '.' .. method .. '=' .. count) end end
    for _, key in ipairs(keys) do print(key) end
end
"""


@pytest.fixture(scope="module", params=["g1", "defaults"])
def work_counts(request):
    metadata = [json.loads(path.read_text()) for path in sorted((SOURCE / "src/common/core").glob("*/plugin.json"))]
    settings = json.loads((SOURCE / "src/common/settings.json").read_text())
    variables = {key: setting["default"] for key, setting in settings.items()}
    for plugin in metadata:
        variables.update({key: setting["default"] for key, setting in plugin["settings"].items()})
    variables.update(SERVER_NAME="www.example.com", USE_REVERSE_PROXY="yes", REVERSE_PROXY_HOST="http://backend", IS_LOADING="no")
    # G1 used these explicit overrides; it was not the shipped security-default profile.
    if request.param == "g1":
        variables.update(
            dict.fromkeys(
                (
                    "USE_BUNKERNET",
                    "USE_METRICS",
                    "USE_BAD_BEHAVIOR",
                    "USE_DNSBL",
                    "USE_BLACKLIST",
                    "USE_WHITELIST",
                    "USE_LIMIT_REQ",
                    "USE_LIMIT_CONN",
                    "USE_MODSECURITY",
                    "USE_MODSECURITY_CRS",
                ),
                "no",
            )
        )
    header = "\n".join(
        f"{name}={_lua(value)}"
        for name, value in {
            "ROOT": str(SOURCE),
            "METADATA": metadata,
            "VARIABLES": variables,
            "ORDER": json.loads((SOURCE / "src/common/core/order.json").read_text()),
        }.items()
    )
    proc = subprocess.run([LUAJIT, "-"], input=header + "\n" + HARNESS, text=True, capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    print(proc.stdout)
    # Two warmup requests also drain self-broadcast cache events. Third request is the budget.
    last = proc.stdout.split("request=3 ")[1]
    counters = {key: int(value) for key, value in re.findall(r"([\w.]+)=(\d+)", last)}
    assert counters["objects"] > 0 and counters["base"] > 0 and counters["total"] > 0
    return request.param, counters


def test_plugin_object_ceiling(work_counts):
    _, counts = work_counts
    assert counts["objects"] <= 32, counts


def test_base_get_variable_ceiling(work_counts):
    _, counts = work_counts
    assert counts["base"] <= 464, counts


def test_total_get_variable_ceiling(work_counts):
    profile, counts = work_counts
    assert counts["total"] <= (536 if profile == "g1" else 538), counts


def test_shared_dict_operation_ceilings(work_counts):
    profile, counts = work_counts
    ceilings = {"datastore.get": 3 if profile == "g1" else 6, "cachestore_ipc.get": 2}
    if profile == "defaults":
        ceilings.update({"datastore.set": 1, "cachestore_locks.add": 1, "cachestore_locks.delete": 1})
    # Missing operations cost zero; any new zone or operation has a zero budget.
    for key, count in counts.items():
        if "." in key:
            assert count <= ceilings.get(key, 0), f"{key}: {count} > {ceilings.get(key, 0)}; {counts}"

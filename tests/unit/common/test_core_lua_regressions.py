"""Core Lua regressions for settings, plugin loading, DNS, bans, metrics and rate limits."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_load_plugin import BASE, PLUGIN_PREAMBLE, _lua

ROOT = Path(__file__).resolve().parents[3]
BW = ROOT / "src/bw/lua/bunkerweb"
CORE = ROOT / "src/common/core"
LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def source(path, pattern):
    match = re.search(pattern, path.read_text(), re.M | re.S)
    assert match, f"missing Lua function in {path}"
    return match.group(0)


def run(script):
    result = subprocess.run(
        [LUA, "-"],
        input=f'package.path = {_lua(str(BW.parent / "?.lua") + ";")} .. package.path\n' + PREAMBLE + script,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


PREAMBLE = r"""
unpack = unpack or table.unpack
local values, serial = {}, 0
local json = {
    encode = function(v) serial = serial + 1; values[tostring(serial)] = v; return tostring(serial) end,
    decode = function(v) if v == '{}' then return {} end; return assert(values[v], 'invalid JSON') end,
}
package.loaded.cjson = json
local logs, cache, metrics = {}, {}, {}
local logger = { log = function(_, _, msg) logs[#logs + 1] = msg end }
local utils = {
    get_phase = function() return 'access' end,
    get_deny_status = function() return 403 end,
    parse_duration = function() return 250 end,
    match_header_rules = function() return nil end,
    is_whitelisted = function() return false end,
    get_security_mode = function() return 'block' end,
    regex_match = function(uri, pattern) return uri:find(pattern) end,
}
local variables = {}
utils.get_variable = function(name) return variables[name], 'settings unavailable' end
local killed = 0
utils.kill_all_threads = function(threads) killed = killed + #threads end
package.loaded['bunkerweb.utils'] = utils
local class = require 'middleclass'
local plugin = class('plugin')
function plugin:initialize(id, ctx)
    self.ctx, self.variables, self.logger = ctx, variables, logger
    self.is_request = true
    self.internalstore = { get = function() return {} end }
end
function plugin:ret(ok, msg, status, redirect, data)
    return { ret = ok, msg = msg, status = status, data = data }
end
function plugin:set_metric(_, key, count) metrics[key] = (metrics[key] or 0) + count end
function plugin:load_header_rules() return {} end
package.loaded['bunkerweb.plugin'] = plugin
ngx = {
    ERR = 3, WARN = 4, INFO = 6, NOTICE = 5, HTTP_OK = 200, HTTP_BAD_REQUEST = 400,
    HTTP_INTERNAL_SERVER_ERROR = 500, HTTP_TOO_MANY_REQUESTS = 429,
    config = { subsystem = 'http' }, var = {}, shared = {}, req = {},
    get_phase = function() return 'access' end,
    thread = {
        spawn = function(fn, ...) return { fn = fn, args = {...} } end,
        wait = function(thread) return true, thread.fn(unpack(thread.args)) end,
    },
    socket = { tcp = function() return {
        settimeout = function() end, connect = function() return true end, close = function() end,
    } end },
}
local ctx = { bw = { server_name = 'example.com', remote_addr = '1.2.3.4', uri = '/challenge', ip_is_global = true } }
"""


@pytest.mark.parametrize("failure", ["multiple", "multisite"])
def test_robotstxt_logs_failed_settings_read(failure):
    run(f"""
ctx.bw.uri = '/robots.txt'
variables.USE_ROBOTSTXT = 'yes'
utils.get_multiple_variables = function() return {"nil" if failure == "multiple" else "{}"}, 'settings unavailable' end
local robotstxt = dofile({_lua(str(CORE / "robotstxt/robotstxt.lua"))})
robotstxt:new(ctx)
assert(#logs == 1 and logs[1]:find('settings unavailable', 1, true), 'settings failure must be logged')
""")


@pytest.mark.parametrize("count", ["nil", "false", "0", "12"])
def test_redis_stats_rejects_missing_count_and_closes_connection(count):
    run(f"""
local redis = dofile({_lua(str(CORE / "redis/redis.lua"))})
variables.USE_REDIS = 'yes'
ctx.bw.uri, ctx.bw.request_method = '/redis/stats', 'GET'
local p = redis:new(ctx)
local closed = 0
p.clusterstore = {{
    connect = function() return true end,
    call = function(_, cmd) if cmd == 'dbsize' then return {count} end; return '' end,
    close = function() closed = closed + 1 end,
}}
local r = p:api()
assert(r.status == {500 if count in ("nil", "false") else 200}, 'missing count must return 500; zero is valid')
assert(closed == 1)
""")


@pytest.mark.parametrize("stream,subsystem", [("no", "stream"), ("no", "http"), ("yes", "stream"), ("partial", "stream")])
@pytest.mark.parametrize("invalid", [False, True])
def test_stream_skips_http_code_after_validating_manifest(stream, subsystem, invalid):
    manifest = dict(BASE, stream=stream)
    if invalid:
        manifest["name"] = "x" * 129
    preamble = PLUGIN_PREAMBLE.replace("--[[PLUGIN_TABLE]]", _lua(manifest)).replace('subsystem = "http"', f'subsystem = "{subsystem}"')
    # Spy before load_plugin runs; the production function must remain intact.
    preamble = preamble.replace(
        "local ok, plugin_or_err = helpers.load_plugin",
        'local imports = 0\nhelpers.require_plugin = function() imports = imports + 1; return false, "HTTP module failed" end\n'
        "local ok, plugin_or_err = helpers.load_plugin",
    ).replace("dofile(arg[1])", f"dofile({_lua(str(BW / 'helpers.lua'))})")
    if invalid:
        assertion = 'assert(not ok and imports == 0); assert(plugin_or_err:find("name of plugin", 1, true))'
    elif stream == "no" and subsystem == "stream":
        assertion = (
            "assert(ok, tostring(plugin_or_err)); assert(imports == 0); assert(next(plugin_or_err.phases) == nil); assert(plugin_or_err.settings.MY_SETTING)"
        )
    else:
        assertion = 'assert(not ok and imports == 1); assert(plugin_or_err == "HTTP module failed")'
    run("package.loaded.cjson = nil\npackage.loaded['bunkerweb.utils'] = nil\n" + preamble + assertion)


@pytest.mark.parametrize("stop", ["cached_open", "new_open", "wait_error"])
def test_reversescan_cancels_pending_threads(stop):
    run(f"""
variables.USE_REVERSE_SCAN, variables.REVERSE_SCAN_PORTS, variables.REVERSE_SCAN_TIMEOUT = 'yes', '22 80', '250ms'
{"ngx.thread.wait = function() return false, 'thread failed' end" if stop == "wait_error" else ""}
local scan = dofile({_lua(str(CORE / 'reversescan/reversescan.lua'))})
local p = scan:new(ctx)
p.is_in_cache = function(_, key) return true, {"key:match(':80$') and 'open'" if stop == "cached_open" else "nil"} end
p.add_to_cache = function() return true end
local r = p:access()
assert(killed >= 1, 'pending scans must be cancelled')
assert(r.status == {"nil" if stop == "wait_error" else "403"})
""")


@pytest.mark.parametrize("body", ["123", "true", "false", "'text'", "io.stdout"])
def test_ban_scalar_body_is_bad_request(body):
    route = source(BW / "api.lua", r'^api.global.POST\["\^/ban\$"\] = function.*?^end$')
    run(
        "local api = {global = {POST = {}}}\nlocal HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR = 400, 500\n"
        "local read_body = function() end\nlocal get_body_data = function() return 'body' end\n"
        f"local decode = function() return {body} end\n" + route + """
local self = {ctx = ctx, response = function(_, status, _, msg) return status, msg end}
local status, msg = api.global.POST['^/ban$'](self)
assert(status == 400 and msg == 'request body must be a JSON object')
"""
    )


@pytest.mark.parametrize("value", ["no", "value"])
def test_has_not_variable_compares_supplied_value(value):
    run(
        "local internalstore = {get = function() return {global = {MULTISITE = 'yes', SERVER_NAME = 'a b'}, "
        f"a = {{SETTING = {_lua(value)}}}, b = {{SETTING = {_lua(value)}}}}} end}}\n"
        + source(BW / "utils.lua", r"^utils.has_not_variable = function.*?^end$")
        + f"\nassert(utils.has_not_variable('SETTING', {_lua(value)}) == false, 'all services equal requested value')\n"
        + "internalstore.get = function() return {global = {MULTISITE = 'yes', SERVER_NAME = 'a b'}, a = {SETTING = 'x'}, b = {SETTING = 'y'}} end\n"
        + "assert(utils.has_not_variable('SETTING', 'x') == true)"
    )


def test_multiple_variables_store_error_keeps_names():
    run(
        "local internalstore = {get = function() return nil, 'offline' end}\n"
        + source(BW / "utils.lua", r"^utils.get_multiple_variables = function.*?^end$")
        + "\nlocal result, err = utils.get_multiple_variables({'ONE', 'TWO'})\n"
        + 'assert(result == nil and err == "can\'t access variables ONE, TWO from internalstore : offline")'
    )


@pytest.mark.parametrize(
    "args",
    [{"start": x} for x in ["-1", "0.5", "invalid", "inf", ["0", "1"]]]
    + [{"length": x} for x in ["-2", "0.5", "invalid", "nan", ["1", "2"]]]
    + [{"order_dir": "sideways"}],
)
def test_metrics_refuses_invalid_paging(args):
    metrics_query(args, 400)


@pytest.mark.parametrize("args", [{}, {"length": "-1"}, {"length": "0"}, {"start": "99", "order_dir": "asc"}])
def test_metrics_accepts_valid_paging(args):
    metrics_query(args, 200)


def metrics_query(args, expected):
    run(
        f"ngx.req.get_uri_args = function() return {_lua(args)} end\n"
        "local metrics = {}\nlocal unescape_uri = function(v) return v end\nlocal HTTP_OK = 200\n"
        "local table_insert = table.insert\nlocal collect_buffered_requests = function() return {} end\n"
        + source(CORE / "metrics/metrics.lua", r"^function metrics:api_requests_query\(\).*?^end$")
        + f"\nlocal r = metrics.api_requests_query({{ret = plugin.ret}})\nassert(r.status == {expected}, 'unexpected query status: ' .. tostring(r.status))"
    )


@pytest.mark.parametrize("answer", ["nil, 'timeout'", "{errcode = 2}", "{errcode = 5, errstr = 'refused'}", "{errcode = 3}", "{}", "{{address = '192.0.2.1'}}"])
@pytest.mark.parametrize("dual", [False, True])
def test_dns_outage_is_retried_but_real_answers_are_cached(answer, dual):
    outage = answer.startswith("nil") or "errcode = 2" in answer or "errcode = 5" in answer
    run(
        "local encode, decode, ERR = json.encode, json.decode, ngx.ERR\n"
        "local queries, writes = 0, 0\n"
        "utils.new_cachestore = function() return {get = function(_, key) return true, cache[key] end, "
        "set = function(_, key, val) cache[key] = val; writes = writes + 1; return true end} end\n"
        "utils.get_resolvers = function() return {'127.0.0.1'} end\n"
        f"local resolver = {{new = function() return {{TYPE_A = 1, TYPE_AAAA = 28, query = function() queries = queries + 1; return {answer} end}} end}}\n"
        + source(BW / "utils.lua", r"^utils.get_ips = function.*?^end$")
        + f"""
local first = utils.get_ips('bot.example.com', false, nil, true, {_lua(dual)})
local second = utils.get_ips('bot.example.com', false, nil, true, {_lua(dual)})
assert(writes == {0 if outage else 1}, 'outages must not enter DNS cache')
assert(queries == {(2 if outage else 1) * (2 if dual else 1)}, 'outages must retry')
assert(type(first) == '{'boolean' if outage else 'table'}' and type(second) == type(first))
"""
    )


@pytest.mark.parametrize("case", ["outage", "clean", "listed", "partial", "recovery"])
def test_dnsbl_outage_cache_metric_and_cancellation(case):
    run(
        "package.loaded['resty.ipmatcher'] = {}\n"
        "package.loaded['resty.dns.resolver'] = {arpa_str = function() return '4.3.2.1.in-addr.arpa' end}\n"
        "variables.USE_DNSBL, variables.DNSBL_LIST = 'yes', 'a.bl b.bl'\n"
        "local queries, phase = 0, 0\nutils.get_ips = function(name) queries = queries + 1; "
        + {
            "outage": "return false, 'timeout'",
            "clean": "return {}",
            "listed": "return {'127.0.0.2'}",
            "partial": "if name:find('a.bl', 1, true) then return false, 'timeout' end; return {}",
            # a.bl is down for the first request, back and listing the IP for the second
            "recovery": "if name:find('a.bl', 1, true) then if phase == 1 then return false, 'timeout' end; return {'127.0.0.2'} end; return {}",
        }[case]
        + f""" end
local dnsbl = dofile({_lua(str(CORE / 'dnsbl/dnsbl.lua'))})
local p = setmetatable({{ctx = ctx, variables = variables, logger = logger}}, {{__index = dnsbl}})
p.is_needed = function() return true end
p.is_in_cache = function() phase = phase + 1; return true, cache.verdict end
p.add_to_cache = function(_, _, value) cache.verdict = value; return true end
local first = p:access()
local second = p:access()
assert(first.ret and second.ret)
"""
        + {
            "outage": "assert(cache.verdict == nil and queries == 4, 'resolver failure must retry without clean cache')",
            "clean": "assert(cache.verdict == 'ok' and queries == 2)",
            "listed": "assert(first.status == 403); assert(metrics.failed_dnsbl == 2, 'first denial must be counted'); assert(killed == 1, 'pending lookup must stop')",
            "partial": "assert(cache.verdict == nil and queries == 4, 'partial outage must not cache a clean verdict')",
            "recovery": "assert(first.status == nil and second.status == 403, 'recovered provider must be asked again and deny')"
            " assert(cache.verdict ~= 'ok' and metrics.failed_dnsbl == 1)",
        }[case]
    )


def test_capjs_default_limit_already_allows_solve_but_limits_flood():
    run(
        "package.loaded['bunkerweb.ratelimit'] = {}\npackage.loaded['bunkerweb.rediskeys'] = {}\n"
        "variables.USE_LIMIT_REQ, variables.USE_ANTIBOT, variables.ANTIBOT_URI = 'yes', 'capjs', '/challenge'\n"
        f"local limit = dofile({_lua(str(CORE / 'limit/limit.lua'))})\n"
        "local p = setmetatable({ctx = ctx, variables = variables, logger = logger, is_request = true, rules = {['/'] = '2r/s'}}, {__index = limit})\n"
        "p.datastore = {get = function(_, key) if cache[key] then return cache[key] end; return nil, 'not found' end, "
        "set_with_retries = function(_, key, value) cache[key] = value; return true end}\n"
        "for i = 1, 11 do\nngx.var.arg_capjs_frame = i == 2 and '1' or nil\n"
        "local r = p:access()\nassert(r.ret)\n"
        "if i <= 3 then assert(r.status == nil, 'page, frame, POST must pass') end\n"
        "if i == 11 then assert(r.status == 429, 'challenge flood must remain limited') end\nend\n"
        "ctx.bw.uri = '/other'\nfor i = 1, 3 do local r = p:access(); if i == 3 then assert(r.status == 429) end end"
    )

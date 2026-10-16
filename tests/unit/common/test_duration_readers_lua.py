"""The Lua readers of the 1.6.16 duration settings, run with suffixed values (stand-alone Lua 5.4).

Before this, ``BAD_BEHAVIOR_BAN_TIME=1d`` read through ``tonumber`` was nil, ``or 0`` made the ban
permanent, and antibot raised a comparison error on every request. Each plugin below is loaded as
shipped, against doubles for the OpenResty side, and driven with a 1.6.16-valid value. The parser
is the shipped ``bunkerweb/duration.lua``; ``utils.lua`` exports it (checked on the source, it
cannot be required outside OpenResty).
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA_DIR = ROOT / "src" / "bw" / "lua"
CORE = ROOT / "src" / "common" / "core"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

PREAMBLE = r"""
local ROOT = arg[1]
package.path = ROOT .. "/src/bw/lua/?.lua;" .. package.path
local parse_duration = dofile(ROOT .. "/src/bw/lua/bunkerweb/duration.lua").parse_duration
local class = dofile(ROOT .. "/src/bw/lua/middleclass.lua")
package.preload["middleclass"] = function() return class end
package.preload["cjson"] = function() return { encode = function(v) return v end, decode = function(v) return v end } end

local plugin = class("plugin")
PLUGIN_VARS = {}
function plugin:initialize(id, ctx)
    self.id, self.ctx = id, ctx
    self.variables = PLUGIN_VARS
    self.kind, self.is_loading = "http", false
    self.logger = { log = function() end }
    self.internalstore = { get = function() end, set = function() return true end }
end
function plugin:ret(ok, msg, status) return ok, msg, status end
function plugin:set_metric() end
package.preload["bunkerweb.plugin"] = function() return plugin end

ngx = { var = {}, ERR = 3, WARN = 4, NOTICE = 5, INFO = 6, status = 403, header = {}, null = {},
        config = { subsystem = "http" }, worker = { id = function() return 0 end }, shared = {} }
"""


def run(body: str) -> str:
    assert LUA is not None
    result = subprocess.run([LUA, "-", str(ROOT)], input=PREAMBLE + body, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def test_utils_exports_the_parser():
    source = (LUA_DIR / "bunkerweb" / "utils.lua").read_text()
    assert 'utils.parse_duration = require("bunkerweb.duration").parse_duration' in source


# ------------------------------------------------------------------ bad behavior

BADBEHAVIOR = r"""
local pushed
package.preload["bunkerweb.rediskeys"] = function() return {} end
package.preload["bunkerweb.utils"] = function()
    return {
        parse_duration = parse_duration,
        is_whitelisted = function() return false end,
        is_ip_whitelisted = function() return false, "" end,
        is_banned = function() return false end,
        get_security_mode = function() return "block" end,
    }
end
local badbehavior = dofile(ROOT .. "/src/common/core/badbehavior/badbehavior.lua")
local function log_with(ban, count)
    pushed = nil
    local bb = badbehavior:new({ bw = { remote_addr = "192.0.2.1", server_name = "www.example.com", request_id = "x" } })
    bb.datastore = { dict = { rpush = function(_, _, value) pushed = value return true end } }
    bb.variables = {
        USE_BAD_BEHAVIOR = "yes", BAD_BEHAVIOR_STATUS_CODES = "403", BAD_BEHAVIOR_THRESHOLD = "10",
        BAD_BEHAVIOR_BAN_SCOPE = "service", BAD_BEHAVIOR_BAN_TIME = ban, BAD_BEHAVIOR_COUNT_TIME = count,
    }
    bb.logger = { log = function() end }
    local ok, msg = bb:log()
    assert(ok and msg == "success", tostring(msg))
    return pushed.ban_time, pushed.count_time
end
"""


@needs_lua
@pytest.mark.parametrize(
    ("ban", "count", "expected_ban", "expected_count"),
    [("1d", "1m", 86400, 60), ("2h", "90s", 7200, 90), ("86400", "60", 86400, 60), ("1w", "5m", 604800, 300), ("0", "1m", 0, 60), ("500ms", "1m", 1, 60)],
)
def test_badbehavior_reads_suffixed_times(ban, count, expected_ban, expected_count):
    out = run(BADBEHAVIOR + f'\nlocal b, c = log_with("{ban}", "{count}")\nprint(b, c)')
    assert out.split() == [str(expected_ban), str(expected_count)]


@needs_lua
def test_badbehavior_one_day_is_never_a_permanent_ban():
    out = run(BADBEHAVIOR + '\nlocal b = log_with("1d", "1m")\nprint(b ~= 0 and "temporary" or "PERMANENT")')
    assert out == "temporary"


# ------------------------------------------------------------------ antibot


def _antibot_check_session() -> str:
    match = re.search(r"^function antibot:check_session\(.*?^end$", (CORE / "antibot" / "antibot.lua").read_text(), re.S | re.M)
    assert match
    return match.group(0)


def _antibot(valid, resolve, session):
    return (
        "local antibot = {}\nlocal now_value = 1000000\nlocal function now() return now_value end\nlocal tonumber = tonumber\n"
        + _antibot_check_session()
        + f"""
local self = {{ session_data = {session}, variables = {{ ANTIBOT_TIME_VALID = "{valid}", ANTIBOT_TIME_RESOLVE = "{resolve}" }}, set_session_data = function() end }}
print(antibot.check_session(self))
"""
    )


@needs_lua
@pytest.mark.parametrize(
    ("valid", "resolve", "session", "expected"),
    [
        # resolved 12 h ago: still valid under 1d, expired under 6h
        ("1d", "1m", "{ resolved = true, time_valid = now_value - 43200, time_resolve = now_value }", "valid"),
        ("6h", "1m", "{ resolved = true, time_valid = now_value - 43200, time_resolve = now_value }", "need new resolve"),
        # prepared 2 minutes ago, never resolved: expired under 1m, fine under 5m
        ("1d", "1m", "{ time_resolve = now_value - 120, time_valid = now_value }", "need new prepare"),
        ("1d", "5m", "{ time_resolve = now_value - 120, time_valid = now_value }", "valid"),
        ("86400", "60", "{ resolved = true, time_valid = now_value - 100, time_resolve = now_value }", "valid"),
    ],
)
def test_antibot_check_session_reads_suffixed_times(valid, resolve, session, expected):
    assert run(_antibot(valid, resolve, session)) == expected


# ------------------------------------------------------------------ cors

CORS = r"""
package.preload["bunkerweb.utils"] = function()
    return { parse_duration = parse_duration, regex_match = function() return true end, get_deny_status = function() return 403 end,
             public_authority = function() return "x" end }
end
ngx.HTTP_NO_CONTENT = 204
local cors = dofile(ROOT .. "/src/common/core/cors/cors.lua")
local function preflight(max_age)
    ngx.header = {}
    local c = cors:new({ bw = { http_origin = "https://a.example", request_method = "OPTIONS", server_name = "www.example.com" } })
    c.variables = { USE_CORS = "yes", CORS_ALLOW_ORIGIN = "*", CORS_MAX_AGE = max_age, CORS_ALLOW_CREDENTIALS = "no",
                    CORS_ALLOW_METHODS = "GET", CORS_ALLOW_HEADERS = "*", CORS_EXPOSE_HEADERS = "", CROSS_ORIGIN_OPENER_POLICY = "",
                    CROSS_ORIGIN_EMBEDDER_POLICY = "", CROSS_ORIGIN_RESOURCE_POLICY = "", CORS_DENY_REQUEST = "no" }
    c.logger = { log = function() end }
    c:header()
    return ngx.header["Access-Control-Max-Age"]
end
"""


@needs_lua
@pytest.mark.parametrize(("value", "expected"), [("1d", "86400"), ("2h", "7200"), ("30m", "1800"), ("600", "600"), ("0", "0"), ("1w", "604800")])
def test_cors_max_age_header_is_always_seconds(value, expected):
    assert run(CORS + f'\nprint(preflight("{value}"))') == expected


# ------------------------------------------------------------------ sessions

SESSIONS = r"""
local captured
package.preload["resty.session"] = function() return { init = function(config) captured = config end } end
package.preload["bunkerweb.rediskeys"] = function() return { nodes_value = function(v) return v ~= nil and v ~= "" end,
    cluster_config_error = function() return nil end, parse_nodes = function() return { { ip = "r", port = 6379 } } end } end
local env = {}
package.preload["bunkerweb.utils"] = function()
    return { parse_duration = parse_duration, get_variable = function(k) return env[k] or "" end }
end
ngx.shared = { sessions_revocation = {} }
local sessions = dofile(ROOT .. "/src/common/core/sessions/sessions.lua")
local function init(vars, redis)
    env = redis or {}
    captured = nil
    PLUGIN_VARS = vars
    local s = sessions:new({ bw = {} })
    local ok, msg = s:init()
    assert(ok, tostring(msg))
    return captured
end
"""


@needs_lua
def test_sessions_timeouts_accept_suffixes():
    out = run(SESSIONS + """
local c = init({ SESSIONS_SECRET = "s", SESSIONS_NAME = "n", SESSIONS_IDLING_TIMEOUT = "30m", SESSIONS_ROLLING_TIMEOUT = "1h", SESSIONS_ABSOLUTE_TIMEOUT = "1d" })
print(c.idling_timeout, c.rolling_timeout, c.absolute_timeout)
""")
    assert out.split() == ["1800", "3600", "86400"]


@needs_lua
def test_sessions_redis_timeouts_are_milliseconds():
    out = run(SESSIONS + """
local c = init({ SESSIONS_SECRET = "s", SESSIONS_NAME = "n", SESSIONS_IDLING_TIMEOUT = "1800", SESSIONS_ROLLING_TIMEOUT = "3600", SESSIONS_ABSOLUTE_TIMEOUT = "86400" },
    { USE_REDIS = "yes", REDIS_HOST = "r", REDIS_TIMEOUT = "2s", REDIS_KEEPALIVE_IDLE = "30s", REDIS_PORT = "6379" })
print(c.redis.connect_timeout, c.redis.send_timeout, c.redis.read_timeout, c.redis.keepalive_timeout)
""")
    assert out.split() == ["2000", "2000", "2000", "30000"]


@needs_lua
def test_sessions_redis_bare_numbers_stay_milliseconds():
    out = run(SESSIONS + """
local c = init({ SESSIONS_SECRET = "s", SESSIONS_NAME = "n", SESSIONS_IDLING_TIMEOUT = "1800", SESSIONS_ROLLING_TIMEOUT = "3600", SESSIONS_ABSOLUTE_TIMEOUT = "86400" },
    { USE_REDIS = "yes", REDIS_HOST = "r", REDIS_TIMEOUT = "1000", REDIS_KEEPALIVE_IDLE = "30000", REDIS_PORT = "6379" })
print(c.redis.connect_timeout, c.redis.keepalive_timeout)
""")
    assert out.split() == ["1000", "30000"]


# ------------------------------------------------------------------ reverse scan


def _method_source(path: Path, signature: str) -> str:
    match = re.search(rf"^{re.escape(signature)}.*?^end$", path.read_text(), re.S | re.M)
    assert match, signature
    return match.group(0)


@needs_lua
@pytest.mark.parametrize(("value", "expected"), [("500ms", "500"), ("1s", "1000"), ("500", "500"), ("2s", "2000")])
def test_reversescan_timeout_is_milliseconds(value, expected):
    source = (CORE / "reversescan" / "reversescan.lua").read_text()
    assert 'parse_duration(self.variables["REVERSE_SCAN_TIMEOUT"], "ms")' in source
    # the shipped call site, run: the spawned scan receives the parsed timeout
    out = run(f"""
local seen
package.preload["bunkerweb.utils"] = function()
    return {{ parse_duration = parse_duration, kill_all_threads = function() end, get_deny_status = function() return 403 end }}
end
ngx.thread = {{ spawn = function(fn, ip, port, timeout) seen = timeout return {{}} end, wait = function() end, kill = function() end }}
ngx.socket = {{}}
local reversescan = dofile(ROOT .. "/src/common/core/reversescan/reversescan.lua")
PLUGIN_VARS = {{ REVERSE_SCAN_PORTS = "22", REVERSE_SCAN_TIMEOUT = "{value}", USE_REVERSE_SCAN = "yes" }}
local r = reversescan:new({{ bw = {{ remote_addr = "192.0.2.1" }} }})
r.is_in_cache = function() return true, nil end
r.set_metric = function() end
pcall(function() r:access() end)
print(seen)
""")
    assert out == expected


# ------------------------------------------------------------------ clusterstore / metrics: shipped call sites


@pytest.mark.parametrize(
    ("path", "needles"),
    [
        (
            LUA_DIR / "bunkerweb" / "clusterstore.lua",
            ['parse_duration(variables["REDIS_TIMEOUT"], "ms")', 'parse_duration(variables["REDIS_KEEPALIVE_IDLE"], "ms")'],
        ),
        (CORE / "metrics" / "metrics.lua", ['parse_duration(self.variables["METRICS_REDIS_TTL"], "s")']),
    ],
)
def test_call_sites_go_through_the_duration_parser(path, needles):
    source = path.read_text()
    for needle in needles:
        assert needle in source
    assert 'tonumber(variables["REDIS_TIMEOUT"])' not in source
    assert 'parse_count(self.variables["METRICS_REDIS_TTL"])' not in source


# ------------------------------------------------------------------ clusterstore (behaviour)

CLUSTERSTORE = r"""
ngx.config = { subsystem = "http" }
local settings = {}
package.loaded["bunkerweb.utils"] = {
    parse_duration = parse_duration,
    get_variable = function(name) return settings[name] or "" end,
    is_cosocket_available = function() return true end,
    is_connection_error = function() return false end,
    is_protocol_error = function() return false end,
}
package.loaded["bunkerweb.logger"] = { new = function() return { log = function() end } end }
package.loaded["resty.redis"] = {}
local seen
package.loaded["resty.redis.connector"] = { new = function(options) seen = options return { connect = function() return {}, nil end }, nil end }
package.loaded["resty.rediscluster"] = { new = function(_, options) seen = options return {}, nil end }
local class = require "bunkerweb.clusterstore"
local function connect(vars)
    settings = { USE_REDIS = "yes", REDIS_HOST = "r", REDIS_PORT = "6379", REDIS_DATABASE = "0", REDIS_KEEPALIVE_POOL = "10",
                 REDIS_SSL = "no", REDIS_SSL_VERIFY = "no", TIMERS_LOG_LEVEL = "INFO" }
    for k, v in pairs(vars) do settings[k] = v end
    seen = nil
    -- the options are captured when the connector is built; what the stub client does after that is moot
    pcall(function() class:new():connect() end)
    return seen
end
"""


@needs_lua
@pytest.mark.parametrize(
    ("timeout", "idle", "ms_timeout", "ms_idle"), [("2s", "30s", 2000, 30000), ("1000", "30000", 1000, 30000), ("500ms", "1m", 500, 60000)]
)
def test_clusterstore_standalone_options_are_milliseconds(timeout, idle, ms_timeout, ms_idle):
    out = run(
        CLUSTERSTORE
        + f'\nlocal o = connect({{ REDIS_TIMEOUT = "{timeout}", REDIS_KEEPALIVE_IDLE = "{idle}" }})\nprint(o.connect_timeout, o.read_timeout, o.send_timeout, o.keepalive_timeout)'
    )
    assert out.split() == [str(ms_timeout)] * 3 + [str(ms_idle)]


@needs_lua
def test_clusterstore_cluster_options_are_milliseconds_and_seeds_default_to_6379():
    out = run(CLUSTERSTORE + """
local o = connect({ REDIS_CLUSTER_NODES = "r1 r2:7001", REDIS_TIMEOUT = "2s", REDIS_KEEPALIVE_IDLE = "30s" })
print(o.connect_timeout, o.keepalive_timeout, o.lock_timeout, #o.serv_list, o.serv_list[1].port, o.serv_list[2].port)
""")
    assert out.split() == ["2000", "30000", "2.0", "2", "6379", "7001"]

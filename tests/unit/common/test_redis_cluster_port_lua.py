"""Run the shipped Lua client and key module with transport-only stubs."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA_DIR = ROOT / "src/bw/lua"
pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="Lua is not installed")


def run_lua(body):
    result = subprocess.run(["lua", "-e", f'package.path = "{LUA_DIR}/?.lua;" .. package.path\n' + body], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_lua_cluster_client_uses_acl_tls_and_respects_phase_guard():
    run_lua("""
ngx = {ERR = 1, WARN = 4, INFO = 7, config = {subsystem = "http"}}
local can_connect = true
local settings = {USE_REDIS = "yes", REDIS_CLUSTER_NODES = "r1:7000 r2:7001",
    REDIS_DATABASE = "00", REDIS_PORT = "6379", REDIS_TIMEOUT = "1000",
    REDIS_KEEPALIVE_IDLE = "30000", REDIS_KEEPALIVE_POOL = "10",
    REDIS_USERNAME = "bunkerweb", REDIS_PASSWORD = "secret",
    REDIS_SSL = "yes", REDIS_SSL_VERIFY = "yes", TIMERS_LOG_LEVEL = "INFO"}
package.loaded["bunkerweb.utils"] = {
    get_variable = function(name) return settings[name] or "" end,
    is_cosocket_available = function() return can_connect end,
    is_connection_error = function() return false end,
    is_protocol_error = function() return false end,
}
package.loaded["bunkerweb.logger"] = {new = function() return {log = function() end} end}
package.loaded["resty.redis.connector"] = {new = function() error("cluster must not use standalone connector") end}
package.loaded["resty.redis"] = {}
local creations = 0
package.loaded["resty.rediscluster"] = {new = function(_, options)
    creations = creations + 1
    assert(options.username == "bunkerweb" and options.password == "secret")
    assert(options.connect_opts.ssl and options.connect_opts.ssl_verify)
    assert(#options.serv_list == 2 and options.serv_list[1].port == 7000)
    return {}, nil
end}
local class = require "bunkerweb.clusterstore"
local store = class:new()
assert(store:connect())
assert(creations == 1)
assert(store:close())
can_connect = false
store = class:new()
local ok = store:connect()
assert(not ok and creations == 1, "header/log phase must never instantiate a cosocket client")
print("OK")
""")


def test_lua_boundary_keys_keep_local_names_and_slot_tags_consistent():
    run_lua("""
local keys = require "bunkerweb.rediskeys"
local local_key = "bans_service_app{tenant}%name_ip_2001:db8::1"
assert(keys.ban(local_key, false) == local_key, "local/standalone bans must stay unchanged")
assert(keys.ban(local_key, true) == "bans_service_app%7Btenant%7D%25name_ip_{2001:db8::1}")
local ban = keys.ban("bans_ip_2001:db8::1", true)
local counter = keys.badbehavior("2001:db8::1", "app{tenant}%name", true)
assert(ban:match("{(.-)}") == counter:match("{(.-)}"), "ban/counter script keys must share a slot")
local reports = keys.reports(true, {"method", "status"})
for _, key in ipairs(reports) do assert(key:match("{(.-)}") == "requests") end
assert(keys.cluster_config_error("r1:7000", "", "00") == nil)
assert(keys.cluster_config_error("r1:7000", "s1:26379", "0"))
assert(keys.cluster_config_error("r1:7000", "", "invalid"))
assert(keys.cluster_config_error("r1:7000", "", "1"))
assert(keys.cluster_config_error("bad{host}:7000", "", "0"))
assert(keys.cluster_config_error("[not-ip]:7000", "", "0"))
print("OK")
""")


def test_fixed_window_escapes_only_redis_keys():
    run_lua("""
ngx = {ERR = 1}
local cluster = true
package.loaded["bunkerweb.utils"] = {get_variable = function() return cluster and "r1:7000" or "" end}
local rate = require "bunkerweb.ratelimit"
local prefix = "workflow_app{tenant}*%name_2001:db8::1"
local remote, local_key
local owner = {
  clusterstore = {connect = function() return true end, close = function() end,
    call = function(_, command, script, count, key) remote = key; return 1 end},
  datastore = {get = function(_, key) local_key = key; return nil, "not found" end,
    set_with_retries = function() return true end}}
assert(rate.incr_local(owner, prefix, 60) == 1)
assert(rate.incr_redis(owner, prefix, 60) == 1)
assert(remote == require("bunkerweb.rediskeys").escape(local_key), "Redis boundary must escape user-controlled braces and glob characters")
cluster = false
assert(rate.incr_redis(owner, prefix, 60) == 1)
assert(remote == local_key, "standalone keys must stay unchanged")
print("OK")
""")


def test_vendored_redirects_execute_command_on_target():
    import re

    source = (ROOT / "src/deps/src/resty-redis-cluster/lib/resty/rediscluster.lua").read_text()
    function = re.search(r"local function handle_command_with_retry\(.*?\nend", source, re.S).group()
    run_lua(
        """
ngx = {null = {}}
local NGX_NOTICE, NGX_ERR, NGX_DEBUG = 1, 2, 3
local ngx_log = function() end
local redis_slot = function() return 1 end
local generate_magic_seed = function() return 1 end
local redis7_with_host = false
local slot_cache = {bw = {[1] = {serv_list = {{ip = "old", port = 7000}}}}}
slot_cache.bw.serv_list = {}
local pick_node = function() return "old", 7000, false end
local connect_node = function(_, client, ip) client.ip = ip; return true end
local check_auth = function() return true end
local release_connection = function() end
local has_moved_signal = function(res) return type(res) == "string" and res:sub(1,5) == "MOVED" end
local string_sub, string_find = string.sub, string.find
local parse_ask_signal = function() return "new", 7001 end
local mode, calls, asks = "ASK", 0, 0
local redis = {new = function() return {
 set_timeouts = function() end, close = function() end,
 asking = function() asks = asks + 1; return true end,
 get = function(self)
   calls = calls + 1
   if calls == 1 then return false, mode .. " 1 new:7001" end
   return "found"
 end} end}
"""
        + function
        + """
local store = {config = {name = "bw", max_redirection = 2}, refresh_slots = function() return true end}
assert(handle_command_with_retry(store, nil, nil, false, "get", "key") == "found", "ASK must execute command after target connect")
assert(calls == 2 and asks == 1)
mode, calls, asks = "MOVED", 0, 0
assert(handle_command_with_retry(store, nil, nil, false, "get", "key") == "found", "MOVED error is returned separately from false response")
assert(calls == 2 and asks == 0)
print("OK")
"""
    )


def test_metrics_scripts_touch_only_the_reports_slot():
    import re

    source = (ROOT / "src/common/core/metrics/metrics.lua").read_text()
    for name in ("PUSH_SCRIPT", "TRIM_SCRIPT", "REBUILD_SCRIPT"):
        script = re.search(rf"local {name} = \[==\[(.*?)\]==\]", source, re.S).group(1)
        run_lua(
            """
local touched = 0
KEYS = {"{requests}", "{requests}:ids"}
ARGV = {"0", "id", "ip", "country", "GET", "/", "403", "reason", "service", "block"}
cjson = {null = {}, decode = function() return {id = "id"} end}
local function command(method, key)
 assert(key:match("{(.-)}") == "requests", "script key escaped the reports slot: " .. key)
 touched = touched + 1
 if method == "GET" then return "1" end
 if method == "LRANGE" then return {} end
 if method == "SISMEMBER" then return 0 end
 return 1
end
redis = {call = command, pcall = command}
local execute = function()
"""
            + script
            + """
end
execute()
assert(touched > 0)
print("OK")
"""
        )


def test_cluster_scan_visits_every_primary_and_keeps_cursor_bounded():
    run_lua("""
ngx = {ERR = 1, INFO = 7, config = {subsystem = "http"}}
package.loaded["bunkerweb.utils"] = {
 get_variable = function() return "" end,
 is_connection_error = function() return false end,
 is_protocol_error = function() return false end}
package.loaded["bunkerweb.logger"] = {new = function() return {log = function() end} end}
package.loaded["resty.redis.connector"] = {}
local visited = {}
package.loaded["resty.redis"] = {new = function() return {
 set_timeouts = function() end, connect = function(self, ip, port, opts) assert(opts.server_name == ip, "direct primary TLS name missing"); self.ip = ip; return true end,
 close = function() end,
 scan = function(self, cursor)
  visited[#visited + 1] = self.ip
  return {"0", {self.ip .. ":key"}}
 end} end}
local store = require("bunkerweb.clusterstore"):new()
store.cluster_mode = true
store.options = {connect_opts = {}}
store.redis_client = {masters = function() return {{ip="a",port=7000},{ip="b",port=7001},{ip="c",port=7002}} end}
local cursor, keys = "0", {}
repeat
 local page, err = store:call("scan", cursor, "MATCH", "metrics:*", "COUNT", 1000)
 assert(page, tostring(err))
 cursor = page[1]
 assert(#page[2] == 1, "one bounded primary page per call")
 keys[#keys + 1] = page[2][1]
until cursor == "0"
assert(#keys == 3 and table.concat(visited,",") == "a,b,c", "global scan must visit all primaries")
print("OK")
""")


def test_cluster_tls_binds_verification_to_each_node_hostname():
    import re

    source = (ROOT / "src/deps/src/resty-redis-cluster/lib/resty/rediscluster.lua").read_text()
    function = re.search(r"local function set_poolname\(.*?\nend", source, re.S).group()
    run_lua(
        """
local ngx_log = function() end
local NGX_DEBUG = 1
"""
        + function
        + """
local config = {base_pool = "tls", connect_opts = {ssl = true, ssl_verify = true}}
set_poolname("redis.example", 6380, config)
assert(config.connect_opts.server_name == "redis.example", "TLS must verify seed DNS identity, not just certificate chain")
local first_pool = config.connect_opts.pool
set_poolname("node2.example", 6380, config)
assert(config.connect_opts.server_name == "node2.example", "routed node must not reuse previous SNI")
assert(first_pool ~= config.connect_opts.pool)
set_poolname("[::1]", 6380, config)
assert(config.connect_opts.server_name == "::1", "IPv6 brackets are socket syntax, not certificate identity")
print("OK")
"""
    )


@pytest.mark.parametrize("failed_stage", ["auth", "status", "version", "masters", "slots"])
def test_discovery_tries_healthy_seed_after_connected_seed_failure(failed_stage):
    import re

    source = (ROOT / "src/deps/src/resty-redis-cluster/lib/resty/rediscluster.lua").read_text()
    function = re.search(r"local function try_hosts_slots\(.*?\nend", source, re.S).group()
    run_lua(
        f'local failed_stage = "{failed_stage}"\n'
        + """
ngx = {now = function() return 0 end}
local ngx_log = function() end
local NGX_ERR, NGX_DEBUG = 1, 2
local table_insert = table.insert
local attempted, closed, pooled = {}, 0, 0
local redis = {new = function() return {
 set_timeouts = function() end,
 close = function() closed = closed + 1 end} end}
local connect_node = function(_, client, ip) client.ip = ip; attempted[#attempted + 1] = ip; return true end
local function stage(name)
 return function(_, client)
  if client.ip == "paused" and name == failed_stage then return nil, "timeout" end
  return true
 end
end
local check_auth, check_status, check_version = stage("auth"), stage("status"), stage("version")
local parse_masters, parse_slots = stage("masters"), stage("slots")
local release_connection = function(client) assert(client.ip == "healthy"); pooled = pooled + 1 end
"""
        + function
        + """
local ok, err = try_hosts_slots({config = {connect_timeout = 1, send_timeout = 1, read_timeout = 1,
 max_connection_attempts = 1}}, {{ip = "paused", port = 7000}, {ip = "healthy", port = 7001}})
assert(ok, "a connected failing seed must not prevent healthy seed discovery")
assert(table.concat(attempted, ",") == "paused,healthy")
assert(closed == 1 and pooled == 1, "only healthy authenticated connections may be pooled")
ok, err = try_hosts_slots({config = {max_connection_attempts = 1}}, {{ip = "paused", port = 7000}})
assert(not ok and #err == 1 and err[1] == "timeout", "all failing seeds must still fail closed")
assert(closed == 2 and pooled == 1)
print("OK")
"""
    )


def test_slot_ranges_cache_each_primary_once_after_reshard():
    import re

    source = (ROOT / "src/deps/src/resty-redis-cluster/lib/resty/rediscluster.lua").read_text()
    function = re.search(r"local function parse_slots\(.*?\nend", source, re.S).group()
    run_lua(
        """
local new_tab = function() return {} end
local REDIS_SLOTS_TOTAL = 16384
local table_insert = table.insert
local ngx_log = function() end
local NGX_INFO, NGX_DEBUG = 1, 2
local redis7_with_host = false
local slot_cache, master_nodes = {}, {}
"""
        + function
        + """
for _, advertised in ipairs({false, true}) do
 local function node(ip, id)
  if advertised then return {id .. ".example", 7000, id, {"ip", ip}} end
  return {ip, 7000, id}
 end
 local ranges = {{0, 1, node("a", "A")}, {2, 2, node("b", "B")},
  {3, 4, node("a", "A")}, {5, 16383, node("c", "C")}}
 assert(parse_slots({config = {name = "bw"}}, {cluster = function() return ranges end}))
 local masters = master_nodes.bwmaster_list
 assert(#masters == 3, "split slot ranges must not duplicate a primary")
 assert(masters[1].ip == "a" and masters[2].ip == "b" and masters[3].ip == "c")
 assert(slot_cache.bw[0].serv_list[1].ip == "a" and slot_cache.bw[2].serv_list[1].ip == "b")
 assert(slot_cache.bw[3].serv_list[1].ip == "a" and slot_cache.bw[16383].serv_list[1].ip == "c")
end
print("OK")
"""
    )

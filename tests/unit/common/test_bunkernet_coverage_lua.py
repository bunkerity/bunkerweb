"""BunkerNet lifecycle, report decisions and transport failures against the real Lua module."""

import json

import pytest
from _lua_state_helpers import BASE_LUA, CORE, LUA, PLUGIN_LUA, last_json, run_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "bunkernet" / "bunkernet.lua"

BOUNDARIES = r"""
package.loaded["cjson"] = json
NOW, HEADERS, REPORTS, RECENT = 1000000, {accept="text/html", cookie="secret", authorization="secret"}, {}, {}
VARIABLES = {USE_BUNKERNET="yes", BUNKERNET_FILTER_HEADERS="yes", BUNKERNET_SERVER="https://feed.example"}
STORE.plugin_bunkernet_id = "instance-id"
STORE.plugin_bunkernet_db = {ip={"203.0.113.1"}}
REASON, REASON_DATA = "blacklist", {kind="ip"}
PHASE = "log"
ngx.time = function() return NOW end
ngx.req = {get_headers=function(max) HEADER_LIMIT=max return HEADERS end}
local u = package.loaded["bunkerweb.utils"]
u.get_version = function() return "1.6" end
u.get_integration = function() return "Docker" end
u.is_ipv4 = function(ip) return ip:match("^%d+%.%d+%.%d+%.%d+$") ~= nil end
u.is_ipv6 = function(ip) return ip:find(":") ~= nil end
u.ip_is_global = function(ip) return ip ~= "127.0.0.1" end
u.is_whitelisted = function() return WHITELISTED end
u.is_ip_in_networks = function() return PRESENT, MATCH_ERROR end
u.get_reason = function() return REASON, REASON_DATA end
u.get_variable = function(k) if k=="MAX_HEADERS" then return "12" end return DISABLE_DEFAULT, "lookup failed" end
HTTP_RESULT = {status=200, body='{"accepted":true}'}
package.loaded["resty.http"] = {new=function()
    if NEW_ERROR then return nil, NEW_ERROR end
    return {
        set_timeout=function(_, timeout) TIMEOUT=timeout end,
        request_uri=function(_, url, opts) SENT={url=url, options=opts} return HTTP_RESULT, "unreachable" end,
        close=function() CLOSED=true end,
    }
end}
-- All filesystem and process reads stay at a deterministic boundary, including instance.id.
FILES = {
    ["/var/cache/bunkerweb/bunkernet/instance.id"]="instance-id\r\n",
    ["/var/cache/bunkerweb/bunkernet/ip.list"]="203.0.113.1\n127.0.0.1\ninvalid\n2001:db8::1\n",
    ["/etc/os-release"]='NAME="Fixture Linux"\nVERSION="1"\nVERSION_ID="1"\nVERSION_CODENAME="test"\nID="fixture"\n',
}
local original_open=io.open
io.open=function(path,mode)
    if not path:match("^/var/cache/bunkerweb/bunkernet/") and path ~= "/etc/os-release" then
        return original_open(path,mode)
    end
    local data=FILES[path]
    if not data then return nil, "missing fixture" end
    return {read=function() return data end, close=function() end,
        lines=function() return data:gmatch("[^\n]+") end}
end
io.popen=function() return {read=function() return "fixture-arch\n" end, close=function() end} end
local original_init=package.loaded["bunkerweb.plugin"].initialize
package.loaded["bunkerweb.plugin"].initialize=function(self, name, ctx)
    original_init(self,name,ctx)
    self.datastore={
        get=function(_, key) if GET_ERROR then return nil, GET_ERROR end
            if RECENT[key] then return RECENT[key] end return nil,"not found" end,
        set_with_retries=function(_,key,value,ttl)
            if RECENT_ERROR then return false,RECENT_ERROR end RECENT[key]=value RECENT_TTL=ttl return true end,
        dict={rpush=function(_,key,value)
            if PUSH_ERROR then return nil,PUSH_ERROR end REPORTS[#REPORTS+1]=json.decode(value) return #REPORTS end},
        llen=function() return QUEUE and #QUEUE end,
        lpop=function() local v=table.remove(QUEUE,1) if v==false then return nil,"pop failed" end return v end,
    }
end
"""


def run(body):
    return last_json(run_lua(BASE_LUA + PLUGIN_LUA + BOUNDARIES + f"\nlocal plugin=dofile({json.dumps(str(MODULE))})\n" + body))


NEW = 'local p=new_plugin(plugin,{kind="http",ip_is_global=true,request_method="POST",request_uri="/login"})\n'


def test_report_payload_allowlist_and_deduplication():
    out = run(NEW + """
local first=p:log()
local second=p:log()
emit({first=first, second=second, reports=REPORTS, ttl=RECENT_TTL, limit=HEADER_LIMIT})
""")
    assert out["first"]["msg"] == "IP added to reports"
    assert out["second"]["msg"] == "IP already added to reports recently"
    assert len(out["reports"]) == 1
    assert out["reports"][0]["headers"] == {"accept": "text/html"}
    assert out["reports"][0]["data"] == {"kind": "ip"}
    assert out["ttl"] == 5400 and out["limit"] == 12


def test_report_payload_is_unfiltered_by_default():
    out = run(NEW + """
VARIABLES.BUNKERNET_FILTER_HEADERS = "no"
REASON_DATA = {matched_vars={"secret"}, matched_var_names={"REQUEST_HEADERS:Authorization"}}
local result=p:log()
emit({result=result, reports=REPORTS, limit=HEADER_LIMIT})
""")
    assert out["result"]["msg"] == "IP added to reports"
    assert out["reports"][0]["headers"] == {"accept": "text/html", "cookie": "secret", "authorization": "secret"}
    assert out["reports"][0]["data"] == {"matched_vars": ["secret"], "matched_var_names": ["REQUEST_HEADERS:Authorization"]}
    assert out["limit"] == 12


@pytest.mark.parametrize("action", ["challenge", "captcha", "redirect"])
def test_served_remediations_never_enter_report_queue(action):
    out = run(NEW + f'REASON_DATA={{action="{action}"}}\nlocal result=p:log()\nemit({{result=result,reports=REPORTS}})')
    assert out["result"]["ret"] is True
    assert "not blocked" in out["result"]["msg"]
    assert out["reports"] == {}


@pytest.mark.parametrize(
    ("setup", "message", "ok"),
    [
        ("REASON=nil", "ip is not blocked", True),
        ('REASON="modsecurity-body"', "skipping report because", True),
        ('REASON="bunkernet"', "skipping report because", True),
        ("p.ctx.bw.ip_is_global=false", "IP is not global", True),
        ("p.bunkernet_id=nil", "missing instance ID", True),
        ('GET_ERROR="broken"', "can't get IP", False),
        ('PUSH_ERROR="full"', "can't set IP report", False),
        ('RECENT_ERROR="full"', "can't add recent IP", False),
        ('VARIABLES.USE_BUNKERNET="no"', "skipping log", True),
    ],
)
def test_report_filters_and_storage_errors(setup, message, ok):
    out = run(NEW + setup + "\nemit(p:log())")
    assert out["ret"] is ok and message in out["msg"]


def test_init_filters_database_and_stores_id():
    out = run(NEW + "local result=p:init()\nemit({result=result,store=STORE})")
    assert out["result"]["ret"] is True
    assert "2 bad IPs" in out["result"]["msg"]
    assert out["store"]["plugin_bunkernet_id"] == "instance-id"
    assert out["store"]["plugin_bunkernet_db"]["ip"] == ["203.0.113.1", "2001:db8::1"]


@pytest.mark.parametrize(
    ("setup", "message", "ok"),
    [
        ('FILES["/var/cache/bunkerweb/bunkernet/instance.id"]=nil', "instance ID not found", True),
        ('FILES["/var/cache/bunkerweb/bunkernet/instance.id"]="\\r\\n"', "instance ID not found", True),
        ('STORE_SET_ERROR="full"', "can't save instance ID", False),
        ('FILES["/var/cache/bunkerweb/bunkernet/ip.list"]=nil', "error while reading database", False),
        (
            'p.internalstore.set=function(_,key,value) if key=="plugin_bunkernet_db" then return false,"full" end return true end',
            "can't store bunkernet database",
            False,
        ),
        ("IS_LOADING=true; p.is_loading=true", "skipping init", True),
    ],
)
def test_init_failure_paths(setup, message, ok):
    out = run(NEW + setup + "\nemit(p:init())")
    assert out["ret"] is ok and message in out["msg"]


@pytest.mark.parametrize(
    ("setup", "message", "status", "ok"),
    [
        ("PRESENT=true", "ip is in db", 403, True),
        ("PRESENT=false", "not in db", None, True),
        ('PRESENT=nil; MATCH_ERROR="invalid"', "can't check if ip", None, False),
        ("STORE.plugin_bunkernet_db=nil", "can't get bunkernet db", None, False),
        ("STORE.plugin_bunkernet_db={ip={}}", "not in db", None, True),
        ("WHITELISTED=true", "client is whitelisted", None, True),
        ("p.bunkernet_id=nil", "missing instance ID", None, True),
        ("p.ctx.bw.ip_is_global=false", "IP is not global", None, True),
        ('VARIABLES.USE_BUNKERNET="no"', "skipping access", None, True),
    ],
)
def test_access_decisions(setup, message, status, ok):
    out = run(NEW + setup + "\nemit(p:access())")
    assert out["ret"] is ok and message in out["msg"] and out.get("status") == status


def test_request_payload_and_transport_bounds():
    out = run(NEW + """
local ok,msg,status,data=p:report("203.0.113.1","blacklist",{id="ip"},"GET","/",{accept="x"},"example.com")
emit({ok=ok,msg=msg,status=status,data=data,sent=SENT,closed=CLOSED,timeout=TIMEOUT})
""")
    assert out["ok"] and out["status"] == 200 and out["data"] == {"accepted": True}
    assert out["closed"] and out["timeout"] == 5000
    assert out["sent"]["url"] == "https://feed.example/report"
    options = out["sent"]["options"]
    assert options["method"] == "POST" and options["headers"]["Content-Type"] == "application/json"
    payload = json.loads(options["body"])
    assert payload["ip"] == "203.0.113.1" and payload["id"] == "instance-id"
    assert payload["os"]["name"] == "Fixture Linux" and payload["os"]["arch"] == "fixture-arch"
    assert payload["os"]["version"] == "1" and payload["os"]["id"] == "fixture"


def test_request_preserves_os_release_version_metadata():
    out = run(NEW + "p:ping()\nemit(json.decode(SENT.options.body))")
    assert out["os"]["version_id"] == "1"
    assert out["os"]["version_codename"] == "test"


@pytest.mark.parametrize(
    ("setup", "message", "status"),
    [
        ('NEW_ERROR="no sockets"', "can't instantiate", None),
        ("HTTP_RESULT=nil", "error while sending", None),
        ('HTTP_RESULT={status=503,body=""}', "status code != 200", 503),
        ('HTTP_RESULT={status=200,body="invalid"}', "error while decoding", None),
    ],
)
def test_send_errors(setup, message, status):
    out = run(NEW + setup + "\nlocal ok,msg,status=p:ping()\nemit({ok=ok,msg=msg,status=status,closed=CLOSED})")
    assert out["ok"] is False and message in out["msg"] and out.get("status") == status
    if "NEW_ERROR" not in setup:
        assert out["closed"]


def test_reports_api_drains_batch_and_logs_failed_pop():
    out = run(NEW + """
p.ctx.bw.uri="/bunkernet/reports" p.ctx.bw.request_method="GET"
QUEUE={'{"ip":"203.0.113.1"}',false,'{"ip":"203.0.113.2"}'}
local result=p:api()
emit({result=result,remaining=#QUEUE,logs=LOGS})
""")
    assert out["result"]["msg"] == [{"ip": "203.0.113.1"}, {"ip": "203.0.113.2"}]
    assert out["result"]["status"] == 200 and out["remaining"] == 0
    assert any("can't lpop report" in entry[1] for entry in out["logs"])


def test_api_empty_and_unmatched_routes():
    out = run(NEW + """
local unmatched=p:api()
p.ctx.bw.uri="/bunkernet/reports" p.ctx.bw.request_method="GET"
emit({unmatched=unmatched,empty=p:api()})
""")
    assert out["unmatched"]["ret"] is False
    assert out["empty"]["msg"] == {} and out["empty"]["status"] == 200


@pytest.mark.parametrize(
    ("setup", "status", "message"),
    [
        ("", 200, "successful"),
        ("HTTP_RESULT=nil", 500, "error while sending request"),
        ("STORE.plugin_bunkernet_id=nil", 500, "error while getting bunkernet id"),
        ('p.internalstore.get=function() return nil,"not found" end', 200, "successful"),
        ('p.internalstore.get=function() return nil,"not found" end; FILES["/var/cache/bunkerweb/bunkernet/instance.id"]=nil', 500, "missing instance ID"),
    ],
)
def test_ping_api(setup, status, message):
    out = run(NEW + setup + '\np.ctx.bw.uri="/bunkernet/ping"\nemit(p:api())')
    assert out["status"] == status and message in out["msg"]


def test_worker_ping_and_default_server_log():
    out = run(NEW + """
local worker=p:init_worker()
DISABLE_DEFAULT="no" local enabled=p:log_default()
DISABLE_DEFAULT=nil local missing=p:log_default()
DISABLE_DEFAULT="yes" local disabled=p:log_default()
emit({worker=worker,enabled=enabled,missing=missing,disabled=disabled,reports=REPORTS})
""")
    assert out["worker"]["ret"] and "successful" in out["worker"]["msg"]
    assert out["enabled"]["msg"] == "default server is not disabled"
    assert out["missing"]["ret"] is False
    assert out["disabled"]["msg"] == "IP added to reports" and len(out["reports"]) == 1

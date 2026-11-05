"""Real CrowdSec bouncer startup and stream decisions, with OpenResty/FFI boundaries faked."""

import ipaddress
import struct
from pathlib import Path

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
package.path = ROOT .. '/src/common/core/?.lua;' .. ROOT .. '/src/bw/lua/?.lua;' .. package.path
json.new = function() return json end
json.decode_array_with_array_mt = function() end
package.loaded['cjson'] = json
package.loaded['cjson.safe'] = {decode=function(raw)
    local ok, value = pcall(json.decode, raw); if ok then return value end
end}
package.loaded['bit32'] = {band=function(a,b) return a & b end, bor=function(a,b) return a | b end}
package.loaded['resty.sha256'] = {new=function() local chunks={} return {
    update=function(_,s) chunks[#chunks+1]=s return true end,
    final=function() return SHA256(table.concat(chunks)) end} end}
package.loaded['resty.string'] = {to_hex=function(raw)
    return (raw:gsub('.', function(c) return string.format('%02x', c:byte()) end))
end}
package.loaded['resty.random'] = {bytes=function(n) return string.rep('x', n) end}
package.loaded['resty.ipmatcher'] = {}
package.loaded['resty.dns.resolver'] = {}
package.loaded['resty.session'] = {}
package.loaded['geoip.mmdb'] = {load_database=function() return {} end}
package.loaded['bunkerweb.datastore'] = {new=function() return {get=function() return nil, 'not found' end} end}

NOW, LOGS, REQUESTS, TIMERS = 1700000000, {}, {}, {}
RESPONSE = {status=200, body='{"new":[],"deleted":[]}'}
local function dict()
    local d = {data={}, deadlines={}, fail={}}
    function d:get(k)
        if self.deadlines[k] and NOW >= self.deadlines[k] then self:delete(k) end
        return self.data[k]
    end
    function d:set(k,v,ttl)
        if self.fail[k] or (self.fail_records and k:find('v2_decisions_',1,true)) then return nil, 'no memory' end
        self.data[k], self.deadlines[k] = v, ttl and ttl > 0 and NOW+ttl or nil
        return true
    end
    d.safe_set=d.set
    function d:delete(k) self.data[k],self.deadlines[k]=nil,nil end
    function d:add(k,v,ttl) if self:get(k) ~= nil then return nil, 'exists' end return self:set(k,v,ttl) end
    d.safe_add=d.add
    function d:incr(k,n,init)
        if self.fail[k] then return nil, 'no memory' end
        local old=self:get(k)
        if old==nil then if init==nil then return nil,'not found' end old=init end
        self.data[k]=old+n return old+n
    end
    function d:ttl(k) return self.deadlines[k] and self.deadlines[k]-NOW or 0 end
    function d:expire(k,ttl) self.deadlines[k]=NOW+ttl return true end
    function d:get_keys() local keys={} for k in pairs(self.data) do keys[#keys+1]=k end return keys end
    return d
end
CACHE, META = dict(), dict()
ngx = {ERR='ERR', WARN='WARN', NOTICE='NOTICE', DEBUG='DEBUG', INFO='INFO', HTTP_FORBIDDEN=403,
    shared={crowdsec_cache=CACHE,crowdsec_metadata=META,bans_meta=dict()},
    var={}, ctx={}, config={subsystem='http'}, re={match=function() end}, req={}, thread={kill=function() end},
    get_phase=function() return 'timer' end, worker={id=function() return 0 end},
    time=function() return math.floor(NOW) end, now=function() return NOW end,
    sleep=function(n) NOW=NOW+n end,
    log=function(level,...) local s={} for _,v in ipairs({...}) do s[#s+1]=tostring(v) end
        LOGS[#LOGS+1]={level,table.concat(s)} end,
    encode_args=function(t) local out={} for k,v in pairs(t) do out[#out+1]=k..'='..v end return table.concat(out,'&') end,
}
package.loaded['ngx.errlog'] = {raw_log=ngx.log}
ngx.timer = {at=function(delay,fn)
    if TIMER_FAIL then return nil, 'timer unavailable' end
    TIMERS[#TIMERS+1]={delay,fn}
    return true
end}
package.loaded['ngx.semaphore'] = {new=function()
    local posted=false
    return {post=function() posted=true end, wait=function()
        if WAIT_FAIL then return nil,'timeout' end
        for i=#TIMERS,1,-1 do
            if TIMERS[i][1]==0 then local t=table.remove(TIMERS,i); t[2](PREMATURE or false); break end
        end
        return posted, posted and nil or 'timeout'
    end}
end}
package.loaded['resty.http'] = {new=function()
    local timeout
    return {set_timeout=function(_,t) timeout=t end,
        request_uri=function(_,link,opts)
            REQUESTS[#REQUESTS+1]={link=link,options=opts,timeout=timeout}
            if BEFORE_RESPONSE then BEFORE_RESPONSE() end
            return RESPONSE, HTTP_ERROR
        end,
        close=function() CLOSED=(CLOSED or 0)+1 end}
end}

-- FFI models libc file/lock outcomes, keeping checkpoints in each test's private directory.
local function local_path(path) return (path:gsub('^/var/lib/bunkerweb', DIR)) end
local real_open, real_rename, real_remove = io.open, os.rename, os.remove
io.open=function(path,mode) return real_open(local_path(path),mode) end
os.rename=function(a,b) return real_rename(local_path(a),local_path(b)) end
os.remove=function(path) return real_remove(local_path(path)) end
local fds, serial = {}, 100
local C = {
    getpid=function() return 4242 end,
    fopen=function() if LOCK_ERROR then return nil end return {} end,
    fileno=function() return 7 end,
    flock=function()
        if LOCK_BUSY and LOCK_BUSY>0 then LOCK_BUSY=LOCK_BUSY-1 return -1 end
        return 0
    end,
    fclose=function() return 0 end,
    open=function(path)
        if WRITE_FAIL then return -1 end
        local exists=io.open(path,'rb'); if exists then exists:close(); return -1 end
        local f=io.open(path,'wb'); if not f then return -1 end
        serial=serial+1; fds[serial]=f; return serial
    end,
    write=function(fd,data,n) fds[fd]:write(data); return n end,
    close=function(fd) fds[fd]:close(); fds[fd]=nil; return 0 end,
    inet_pton=function(_,text,dst)
        local words=IP6[text]; if not words then return 0 end
        for i=0,3 do dst.uint32[i]=words[i+1] end return 1
    end,
}
package.loaded['ffi'] = {C=C,cdef=function() end, gc=function(v) return v end,errno=function() return 11 end,
    new=function(kind,value) if kind=='union ip6_address' then return {uint32={}} end return value end}

local b = dofile(ROOT .. '/src/common/core/crowdsec/lib/bouncer.lua')
function boot(prefix, fingerprint)
    return b.init(CONF,'unit-agent',prefix or 'p|',fingerprint or 'policy',{'alias'})
end
function poll(premature)
    b.SetupStream()
    for i,t in ipairs(TIMERS) do if t[1]>0 then table.remove(TIMERS,i); t[2](premature or false); return end end
    error('stream timer missing')
end
function advance() NOW=NOW+11 end
function stream(new,deleted)
    RESPONSE={status=200,body=json.encode({new=setmetatable(new or {},json.array_mt),deleted=setmetatable(deleted or {},json.array_mt)})}
end
function decision(id,value,scope,kind,duration)
    return {id=id,scope=scope or 'Ip',value=value or '192.0.2.1',type=kind or 'ban',duration=duration or '60s'}
end
function allowed(ip)
    local ok,kind,err,evidence=b.allowIp(ip or '192.0.2.1')
    return {allowed=ok,kind=kind,error=err,evidence=evidence}
end
function snapshot()
    return {info=b.ConnectionInfo(),startup=CACHE:get('p|startup'),inflight=CACHE:get('p|stream_inflight'),
        generation=CACHE:get('p|v3_generation'),requests=REQUESTS,logs=LOGS}
end
"""


def run(tmp_path, body, *, conf=None, setup=""):
    config = {
        "API_URL": "https://lapi.example",
        "API_KEY": "unit-key",
        "BOUNCING_ON_TYPE": "all",
        "FALLBACK_REMEDIATION": "ban",
        "CAPTCHA_PROVIDER": "",
        "CACHE_EXPIRATION": 30,
        **(conf or {}),
    }
    path = tmp_path / "bouncer.conf"
    path.write_text("".join(f"{key}={value}\n" for key, value in config.items()))
    # Native inet_pton's little-endian words for the IPv6 addresses used below.
    ip6 = {ip: struct.unpack("<4I", ipaddress.ip_address(ip).packed) for ip in ("2001:db8::1", "2001:db8::", "::1")}
    prelude = f"ROOT={to_lua(str(ROOT))}\nDIR={to_lua(str(tmp_path))}\nCONF={to_lua(str(path))}\nIP6={to_lua(ip6)}\n"
    return last_json(run_lua(BASE_LUA + prelude + HARNESS + setup + "\n" + body))


def test_deleted_decision_removes_cached_ban(tmp_path):
    out = run(
        tmp_path,
        """
assert(boot()); local d=decision(7); stream({d}); poll()
local before=allowed(); advance(); stream({}, {d}); poll()
emit({before=before,after=allowed(),state=snapshot()})
""",
    )
    assert out["before"]["allowed"] is False
    assert out["before"]["kind"] == "ban"
    assert out["after"] == {"allowed": True}
    assert out["state"]["requests"][1]["link"].endswith("startup=false")


def test_expired_decision_no_longer_blocks(tmp_path):
    out = run(
        tmp_path,
        """
assert(boot()); stream({decision(7,nil,nil,nil,'10s')}); poll()
local before=allowed(); NOW=NOW+10
emit({before=before,after=allowed()})
""",
    )
    assert out["before"]["kind"] == "ban"
    assert out["after"] == {"allowed": True}


@pytest.mark.parametrize(
    "body,healthy,error",
    [
        ("[]", True, None),
        ("null", True, None),
        ("{}", False, "Invalid Local API response"),
        ("123", False, "Invalid Local API response"),
        ("broken", False, "Invalid Local API response"),
    ],
)
def test_health_reads_authenticated_lapi_without_caching(tmp_path, body, healthy, error):
    out = run(
        tmp_path,
        """
assert(boot()); local ok,err,checked=b.Health()
emit({ok=ok,error=err,checked=checked,requests=REQUESTS,closed=CLOSED})
""",
        setup=f"RESPONSE={{status=200,body={to_lua(body)}}}",
    )
    assert out["ok"] is healthy
    assert out.get("error") == error
    assert out["closed"] == 1
    request = out["requests"][0]
    assert request["link"] == "https://lapi.example/v1/decisions?ip=127.0.0.1"
    assert request["options"] == {"method": "GET", "ssl_verify": True, "headers": {"Connection": "close", "x-api-key": "unit-key", "User-Agent": "unit-agent"}}
    assert request["timeout"] == 15000


@pytest.mark.parametrize(
    "setup,error", [("RESPONSE=nil; HTTP_ERROR='refused'", "Local API request failed"), ("RESPONSE={status=403,body='[]'}", "Local API returned HTTP 403")]
)
def test_health_reports_transport_and_authentication_failure(tmp_path, setup, error):
    out = run(tmp_path, "assert(boot()); local ok,err=b.Health(); emit({ok=ok,error=err})", setup=setup)
    assert out == {"ok": False, "error": error}


def test_uninitialised_and_missing_configuration(tmp_path):
    out = run(
        tmp_path,
        """
local ok,err=b.Health(); local init,why=b.init(DIR..'/missing','agent')
emit({healthy=ok,error=err,failed=init==nil,why=why})
""",
    )
    assert out["healthy"] is False
    assert out["error"] == "CrowdSec configuration is not loaded"
    assert out["failed"] is True
    assert out["why"].endswith("/missing doesn't exist")


@pytest.mark.parametrize("conf,expected", [({"API_URL": ""}, False), ({"API_URL": "", "APPSEC_URL": "https://appsec.example:7422"}, True)])
def test_health_without_lapi_does_not_claim_appsec_checked(tmp_path, conf, expected):
    out = run(tmp_path, "assert(boot()); local ok,err,checked=b.Health(); emit({ok=ok,error=err,checked=checked,requests=#REQUESTS,logs=LOGS})", conf=conf)
    assert out["ok"] is expected
    assert out["checked"] is False
    assert out["requests"] == 0
    assert out["error"] == "No Local API configured; AppSec health is not checked"
    assert any("defined" in row[1] for row in out["logs"])


def test_disabled_configuration_and_captcha_rejection(tmp_path):
    assert run(tmp_path, "emit(boot())", conf={"ENABLED": "false"}) == "Disabled"
    out = run(
        tmp_path,
        "assert(boot()); local ok,err=b.validateCaptcha('token','192.0.2.1'); emit({ok=ok,error=err,logs=LOGS})",
        conf={"CAPTCHA_PROVIDER": "invalid", "REDIRECT_LOCATION": "/"},
    )
    assert out["ok"] is False
    assert out["error"] == "captcha is not configured"
    assert any("infinite redirection" in row[1] for row in out["logs"])
    assert any("captcha configuration rejected" in row[1] for row in out["logs"])


def test_configured_captcha_validation_uses_real_provider(tmp_path):
    template = tmp_path / "captcha.html"
    template.write_text("captcha {{captcha_site_key}}\n")
    out = run(
        tmp_path,
        """
assert(boot()); RESPONSE={status=200,body='{"success":true}'}
local ok,err=b.validateCaptcha('token','192.0.2.1'); emit({ok=ok,error=err,requests=REQUESTS})
""",
        conf={"CAPTCHA_PROVIDER": "turnstile", "SITE_KEY": "site", "SECRET_KEY": "secret", "CAPTCHA_TEMPLATE_PATH": template},
    )
    assert out["ok"] is True
    assert out["requests"][0]["link"] == "https://challenges.cloudflare.com/turnstile/v0/siteverify"


@pytest.mark.parametrize("conf", [{"MODE": "live", "SSL_VERIFY": "false", "ALWAYS_SEND_TO_APPSEC": "true"}, {"APPSEC_URL": "http://appsec.example"}])
def test_init_request_options_and_appsec_host(tmp_path, conf):
    out = run(tmp_path, "assert(boot()); b.Health(); emit({requests=REQUESTS,logs=LOGS})", conf=conf)
    request = out["requests"][0]
    assert request["options"]["ssl_verify"] is (conf.get("SSL_VERIFY") != "false")
    assert request["timeout"] == (500 if conf.get("MODE") == "live" else 15000)
    if "APPSEC_URL" in conf:
        assert ["NOTICE", "APPSEC is enabled on 'appsec.example'"] in out["logs"]


@pytest.mark.parametrize("stale", ["none", "inflight", "full", "last", "policy"])
def test_startup_reuses_only_fresh_matching_completed_snapshot(tmp_path, stale):
    setup = ""
    if stale == "inflight":
        setup = "CACHE:set('p|stream_inflight',true)"
    elif stale == "full":
        setup = "CACHE:set('p|last_successful_full_sync',NOW-3601)"
    elif stale == "last":
        setup = "CACHE:set('p|last_successful_sync',NOW-301)"
    elif stale == "policy":
        setup = "CACHE:set('p|v3_generation','other|1:A')"
    out = run(
        tmp_path,
        f"""
assert(boot()); poll(); CACHE:set('p|startup',false)
{setup}
assert(boot()); emit(snapshot())
""",
    )
    assert out["startup"] is (stale != "none")


@pytest.mark.parametrize(
    "response,error",
    [
        (None, "Local API request failed"),
        ({"status": 500, "body": "{}"}, "Local API returned HTTP 500"),
        ({"status": 200, "body": "[]"}, "Invalid Local API response"),
    ],
)
def test_stream_error_keeps_ban_and_next_poll_recovers(tmp_path, response, error):
    out = run(
        tmp_path,
        f"""
assert(boot()); stream({{decision(7)}}); poll(); advance()
RESPONSE={to_lua(response)}; poll(); local failed=snapshot(); local denied=allowed()
advance(); stream(); poll(); emit({{failed=failed,denied=denied,recovered=snapshot(),after=allowed()}})
""",
    )
    assert out["failed"]["info"]["last_sync_error"] == error
    assert out["denied"]["kind"] == "ban"
    assert "last_sync_error" not in out["recovered"]["info"]
    assert any("sync recovered" in row[1] for row in out["recovered"]["logs"])
    assert out["after"]["allowed"] is True


@pytest.mark.parametrize(
    "body",
    [
        "broken",
        "null",
        '{"new":{}}',
        '{"deleted":1}',
        '{"new":[1]}',
        '{"new":[{"scope":1}]}',
        '{"new":[{"id":-1,"scope":"Ip","value":"192.0.2.1","type":"ban","duration":"1s"}]}',
    ],
)
def test_invalid_stream_payload_is_rejected_without_publishing(tmp_path, body):
    out = run(tmp_path, f"assert(boot()); RESPONSE={{status=200,body={to_lua(body)}}}; poll(); emit(snapshot())")
    assert out["info"]["last_sync_error"] == "Invalid Local API response"
    assert "generation" not in out
    assert len(out["requests"]) == 1


@pytest.mark.parametrize("field,value", [("value", "bad/ip"), ("value", "999.1.1.1"), ("scope", "Range"), ("duration", "0s"), ("type", "x" * 65)])
def test_invalid_decision_cannot_publish_stream_snapshot(tmp_path, field, value):
    out = run(tmp_path, f"assert(boot()); local d=decision(7); d[{to_lua(field)}]={to_lua(value)}; stream({{d}}); poll(); emit(snapshot())")
    assert out["info"]["last_sync_error"] == "Invalid Local API response"
    assert "generation" not in out


@pytest.mark.parametrize(
    "value,scope,ip", [("192.0.2.0/24", "Range", "192.0.2.9"), ("2001:db8::/32", "Range", "2001:db8::1"), ("2001:db8::1", "Ip", "2001:db8::1")]
)
def test_ip_and_covering_range_bans_are_enforced(tmp_path, value, scope, ip):
    out = run(tmp_path, f"assert(boot()); stream({{decision(7,{to_lua(value)},{to_lua(scope)})}}); poll(); emit(allowed({to_lua(ip)}))")
    assert out["allowed"] is False
    assert out["kind"] == "ban"
    assert out["evidence"]["matched_target"] == value


@pytest.mark.parametrize("scope,value", [("Range", "192.0.2.0/33"), ("Range", "2001:db8::/129")])
def test_out_of_range_prefix_is_rejected(tmp_path, scope, value):
    out = run(tmp_path, f"assert(boot()); stream({{decision(7,{to_lua(value)},{to_lua(scope)})}}); poll(); emit(snapshot())")
    assert out["info"]["last_sync_error"] == "Invalid Local API response"


def test_country_and_unselected_types_are_ignored_unknown_type_uses_fallback(tmp_path):
    out = run(
        tmp_path,
        """
assert(boot()); stream({decision(1,'FR','Country'),decision(2,nil,nil,'captcha')}); poll()
emit(allowed())
""",
        conf={"BOUNCING_ON_TYPE": "ban"},
    )
    assert out == {"allowed": True}
    out = run(tmp_path, "assert(boot()); stream({decision(3,nil,nil,'throttle')}); poll(); emit(allowed())", conf={"FALLBACK_REMEDIATION": "captcha"})
    assert out["kind"] == "captcha"


def test_empty_or_null_groups_publish_empty_snapshot(tmp_path):
    out = run(tmp_path, "assert(boot()); RESPONSE.body='{\"new\":null}'; poll(); emit({state=snapshot(),decision=allowed()})")
    assert out["decision"] == {"allowed": True}
    assert out["state"]["generation"].startswith("policy|")
    assert out["state"]["inflight"] is False


@pytest.mark.parametrize("failure", ["v2_generation_counter", "v2_config", "v3_generation", "last_successful_full_sync", "records"])
def test_cache_write_failure_requests_full_retry(tmp_path, failure):
    fail = "CACHE.fail_records=true" if failure == "records" else f"CACHE.fail['p|{failure}']=true"
    out = run(tmp_path, f"assert(boot()); {fail}; stream({{decision(7)}}); poll(); emit(snapshot())")
    assert out["startup"] is True
    assert out["info"]["last_sync_error"] == "Local decision cache is full"
    assert any("increase CROWDSEC_CACHE_SIZE" in row[1] for row in out["logs"])


def test_checkpoint_failure_keeps_enforcement_and_requests_full_retry(tmp_path):
    out = run(
        tmp_path,
        """
assert(boot()); WRITE_FAIL=true; stream({decision(7)}); poll()
emit({state=snapshot(),decision=allowed()})
""",
    )
    assert out["state"]["startup"] is True
    assert out["state"]["info"]["last_sync_error"] == "Enforcement checkpoint write failed"
    assert out["decision"]["kind"] == "ban"


def test_missing_inflight_marker_forces_future_full_snapshot(tmp_path):
    out = run(tmp_path, "assert(boot()); CACHE.fail['p|stream_inflight']=true; poll(); emit(snapshot())")
    assert out["generation"].startswith("policy|")
    assert out["info"]["last_successful_sync"] == 1700000000
    assert run(tmp_path, "assert(boot()); CACHE.fail['p|startup']=true; assert(boot()); emit(LOGS)")[-1][1] == "failed to add startup key in cache: no memory"


def test_timer_premature_throttle_and_busy_lock_do_not_contact_lapi(tmp_path):
    assert run(tmp_path, "assert(boot()); poll(true); emit({requests=#REQUESTS,timers=#TIMERS})") == {"requests": 0, "timers": 0}
    out = run(
        tmp_path,
        """
assert(boot())
poll(); local first=#REQUESTS; poll(); local throttled=#REQUESTS
advance(); LOCK_BUSY=1; poll()
emit({first=first,throttled=throttled,busy=#REQUESTS,info=b.ConnectionInfo()})
""",
    )
    assert (out["first"], out["throttled"], out["busy"]) == (1, 1, 1)
    assert "last_sync_error" not in out["info"]


def test_lock_and_reschedule_errors_are_reported(tmp_path):
    out = run(tmp_path, "assert(boot()); b.SetupStream(); TIMER_FAIL=true; LOCK_ERROR=true; poll(); emit(snapshot())")
    assert out["info"]["last_sync_error"] == "Stream lock unavailable"
    assert any("Failed to schedule Local API synchronization" in row[1] for row in out["logs"])


@pytest.mark.parametrize("metadata", [True, False])
def test_sync_failure_logging_is_rate_limited_with_or_without_metadata(tmp_path, metadata):
    out = run(
        tmp_path,
        """
assert(boot()); LOCK_ERROR=true; poll(); advance(); poll(); advance(); poll()
local errors=0; for _,row in ipairs(LOGS) do if row[2]:find('sync failed',1,true) then errors=errors+1 end end
emit({errors=errors,info=b.ConnectionInfo()})
""",
        setup="" if metadata else "ngx.shared.crowdsec_metadata=nil",
    )
    assert out["errors"] == 1
    assert out["info"]["last_sync_error"] == "Stream lock unavailable"


@pytest.mark.parametrize("setup", ["LOCK_BUSY=2", "LOCK_BUSY=100", "LOCK_ERROR=true", "TIMER_FAIL=true", "WAIT_FAIL=true", "PREMATURE=true"])
def test_disk_refresh_timer_waits_or_fails_closed(tmp_path, setup):
    out = run(tmp_path, f"assert(boot()); RESPONSE=nil; {setup}; emit(allowed())")
    if setup == "LOCK_BUSY=2":
        assert out["allowed"] is True
    else:
        assert out["allowed"] is False
        assert out["kind"] == "ban"

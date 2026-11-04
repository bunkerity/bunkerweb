"""Real bundled bouncer request paths, with OpenResty and libc boundaries faked."""

import json
from pathlib import Path

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
IP = "192.0.2.7"
DECISION = {"id": 7, "scope": "Ip", "value": IP, "type": "ban", "duration": "10m", "origin": "cscli", "scenario": "ssh"}

HARNESS = r"""
local F = dofile(ROOT .. '/tests/unit/lua_lease_fakes.lua')(ROOT)
F.reset()
package.path = ROOT .. '/src/common/core/?.lua;' .. package.path
json.new = function() return json end
json.decode_array_with_array_mt = function() end
package.loaded.cjson = json
local safe = {new = function() return json end, decode = function(s)
    local ok, value = pcall(json.decode, s); if ok then return value end
end}
package.loaded['cjson.safe'] = safe
package.loaded['resty.sha256'] = {new = function()
    local parts = {}; return {update = function(_, s) parts[#parts+1] = s return true end,
        final = function() return SHA256(table.concat(parts)) end}
end}
package.loaded['resty.string'].to_hex = function(s)
    return (s:gsub('.', function(c) return string.format('%02x', c:byte()) end))
end
package.loaded.bit32 = {bor = function(a,b) return a | b end, band = function(a,b) return a & b end}
local clock, logs, requests, timers = 1700000000, {}, {}, {}
local function dict()
    local d = {data = {}, flags = {}, expiry = {}}
    function d.get(self, k)
        if self.expiry[k] and self.expiry[k] <= clock then self:delete(k) end
        return self.data[k], self.flags[k]
    end
    function d.set(self, k, v, ttl, flags)
        if CACHE_FULL and k:find('v2_decisions_', 1, true) then return nil, 'no memory' end
        if CHALLENGE_FULL and k:find('captcha_', 1, true) then return nil, 'no memory', true end
        self.data[k], self.flags[k] = v, flags
        self.expiry[k] = ttl and ttl > 0 and clock + ttl or nil
        return true, nil, CHALLENGE_FORCIBLE
    end
    d.safe_set = d.set
    function d.delete(self,k) self.data[k], self.flags[k], self.expiry[k] = nil,nil,nil end
    function d.add(self,k,v,ttl) if self:get(k) ~= nil then return nil,'exists' end return self:set(k,v,ttl) end
    d.safe_add = d.add
    function d.incr(self,k,v,initial)
        local n = self:get(k); if n == nil and initial == nil then return nil,'not found' end
        n = (n or initial) + v; self:set(k,n); return n
    end
    function d.get_keys(self) local out = {}; for k in pairs(self.data) do out[#out+1] = k end return out end
    return d
end
ngx.shared.crowdsec_cache, ngx.shared.crowdsec_metadata = dict(), dict()
ngx.time = function() return math.floor(clock) end
ngx.now = function() return clock end
ngx.sleep = function(t) clock = clock + t end
ngx.DEBUG, ngx.ALERT, ngx.HTTP_FORBIDDEN, ngx.HTTP_GET = 'DEBUG','ALERT',403,2
ngx.log = function(level, ...) local s = {}; for _,v in ipairs({...}) do s[#s+1] = tostring(v) end
    logs[#logs+1] = {level,table.concat(s)} end
ngx.worker = {id = function() return 0 end}
ngx.ctx, ngx.header = {bw = {}}, {}
ngx.var = {uri = '/private', request_uri = '/private?q=1', request_method = 'GET',
    http_host = 'app.example', http_user_agent = 'browser'}
local req_headers = {}
ngx.req = {
    is_internal = function() return INTERNAL or false end,
    http_version = function() return HTTP_VERSION or 1.1 end,
    read_body = function() BODY_READ = true end,
    get_body_data = function() return BODY end,
    get_body_file = function() return BODY_FILE end,
    get_headers = function(limit) HEADER_LIMIT = limit; return req_headers end,
    get_post_args = function() return POST_ARGS or {} end,
    set_method = function(m) METHOD = m end,
    get_method = function() return ngx.var.request_method end,
}
ngx.say = function(s) OUTPUT = s end
ngx.redirect = function(uri) return true, uri end
ngx.encode_args = function(values)
    local parts = {}; for k,v in pairs(values) do parts[#parts+1] = k .. '=' .. tostring(v) end
    table.sort(parts); return table.concat(parts,'&')
end
ngx.timer = {at = function(delay, fn)
    if TIMER_ERROR then return nil,TIMER_ERROR end
    if delay == 0 then fn(false) else timers[#timers+1] = {delay=delay,fn=fn} end
    return true
end}
package.loaded['ngx.semaphore'] = {new = function() return {
    post = function() end, wait = function() if WAIT_ERROR then return nil,WAIT_ERROR end return true end} end}
local U = package.loaded['bunkerweb.utils']
local original_get = U.get_variable
U.get_variable = function(name, ...) if name == 'MAX_HEADERS' then return MAX_HEADERS end return original_get(name, ...) end
local real_open, real_rename, real_remove = io.open, os.rename, os.remove
local function mapped(path)
    return (path:gsub('^/var/lib/bunkerweb/', DIR .. '/'):gsub('^/var/run/bunkerweb/', DIR .. '/'))
end
io.open = function(path,mode) return real_open(mapped(path),mode) end
os.rename = function(a,b) return real_rename(mapped(a),mapped(b)) end
os.remove = function(path) return real_remove(mapped(path)) end
local fds, next_fd = {}, 10
package.loaded.ffi = {cdef = function() end, gc = function(v) return v end,
    errno = function() return 11 end,
    new = function(kind,v) if kind == 'int' then return v end return {uint32={}} end,
    C = {
        inet_pton = function() return 0 end, getpid = function() return 99 end,
        fopen = function(path) if LOCK_ERROR then return nil end return io.open(path,'a+') end,
        fileno = function() return 1 end, flock = function() return LOCK_BUSY and -1 or 0 end,
        fclose = function(f) f:close(); return 0 end,
        open = function(path)
            if WRITE_ERROR then return -1 end
            local exists = io.open(path,'rb'); if exists then exists:close(); return -1 end
            local f = io.open(path,'wb'); if not f then return -1 end
            next_fd = next_fd+1; fds[next_fd] = f; return next_fd
        end,
        write = function(fd,s,n) fds[fd]:write(s); return n end,
        close = function(fd) fds[fd]:close(); return 0 end,
    }}
package.loaded['resty.http'] = {new = function() return {
    set_timeout = function(_,v) TIMEOUT = v end,
    set_timeouts = function(_,a,b,c) TIMEOUTS = {a,b,c} end,
    close = function() CLOSED = (CLOSED or 0)+1 end,
    request_uri = function(_,uri,opts)
        requests[#requests+1] = {uri=uri,opts=opts}
        if BEFORE_RESPONSE then BEFORE_RESPONSE(uri) end
        if uri:find('siteverify',1,true) then
            if CAPTCHA_ERROR then return nil,'down' end
            return {status=200,body=json.encode({success=CAPTCHA_VALID ~= false})}
        end
        if uri:find('appsec',1,true) then
            if APPSEC_DOWN then return nil,'down' end
            return {status=APPSEC_STATUS or 200,body=APPSEC_BODY or '{}'}
        end
        if LAPI_DOWN then return nil,'down' end
        return {status=LAPI_STATUS or 200,body=LAPI_BODY or '[]'}
    end} end}
local b = require('crowdsec.lib.bouncer')
local lease = require('bunkerweb.banlease')
local partition = require('crowdsec.cache_partition')
local function init() assert(b.init(CONF_PATH,'unit-agent','live|','fingerprint')) end
local function allow() return table.pack(b.Allow('192.0.2.7','challenge|')) end
local function advance(t) clock = clock + t end
local function result(extra)
    extra = extra or {}; extra.logs,extra.requests,extra.timers = logs,requests,#timers
    extra.cache,extra.output,extra.headers = ngx.shared.crowdsec_cache.data,OUTPUT,ngx.header
    emit(extra)
end
"""


def run(tmp_path, body, *, conf=None, setup="", initialize=True):
    config = {
        "API_URL": "http://lapi:8080",
        "API_KEY": "unit-key",
        "MODE": "live",
        "BOUNCING_ON_TYPE": "all",
        "FALLBACK_REMEDIATION": "ban",
        "CACHE_EXPIRATION": 30,
        "CAPTCHA_PROVIDER": "",
        **(conf or {}),
    }
    path = tmp_path / "bouncer.conf"
    path.write_text("".join(f"{k}={v}\n" for k, v in config.items()))
    (tmp_path / "captcha.html").write_text("challenge {{captcha_site_key}}\n")
    header = f"\nROOT={to_lua(str(ROOT))}\nDIR={to_lua(str(tmp_path))}\nCONF_PATH={to_lua(str(path))}\n"
    return last_json(run_lua(BASE_LUA + header + HARNESS + setup + ("\ninit()\n" if initialize else "\n") + body))


def decision(**changes):
    return json.dumps([{**DECISION, **changes}])


def test_live_ban_denies_with_provenance_and_cached_ttl(tmp_path):
    out = run(tmp_path, "local a=allow(); local c=allow(); result({a=a,c=c})", setup=f"LAPI_BODY={to_lua(decision())}")
    assert out["a"]["1"] is True and out["a"]["2"] == "denied" and out["a"]["3"] is True
    evidence = out["a"]["4"]
    assert evidence["remediation"] == "ban" and evidence["decisions"][0]["id"] == 7
    assert evidence["decisions"][0]["expires_at"] == 1700000600
    assert out["c"]["3"] is True and len(out["requests"]) == 1


def test_live_allow_cache_expires_and_revalidates(tmp_path):
    out = run(tmp_path, "local a=allow(); allow(); advance(31); LAPI_BODY=" + to_lua(decision()) + "; result({a=a,b=allow()})")
    assert out["a"]["2"] == "allow" and out["b"]["3"] is True
    assert len(out["requests"]) == 2


@pytest.mark.parametrize("setup", ["LAPI_DOWN=true", "LAPI_STATUS=503", "LAPI_BODY='broken'", "LAPI_BODY='{}'"])
@pytest.mark.parametrize("saved", [False, True])
def test_lapi_outage_uses_durable_ban_or_allows_without_one(tmp_path, setup, saved):
    seed = f"LAPI_BODY={to_lua(decision())}; allow(); advance(31);" if saved else ""
    out = run(tmp_path, seed + setup + "; result({a=allow(),info=b.ConnectionInfo()})")
    assert out["a"]["2"] == ("denied" if saved else "allow")
    assert out["a"].get("3", False) is saved
    assert out["info"]["last_sync_error"].startswith(("Local API", "Invalid Local API"))


@pytest.mark.parametrize("policy,denied", [("passthrough", False), ("deny", True)])
@pytest.mark.parametrize("setup", ["APPSEC_DOWN=true", "APPSEC_STATUS=503", "APPSEC_STATUS=403; APPSEC_BODY='broken'"])
def test_appsec_outage_obeys_failure_policy(tmp_path, policy, denied, setup):
    out = run(
        tmp_path,
        "result({a=allow(),info=b.ConnectionInfo()})",
        conf={"API_URL": "", "APPSEC_URL": "http://appsec:7422", "APPSEC_FAILURE_ACTION": policy},
        setup=setup,
    )
    assert out["a"]["2"] == ("denied" if denied else "allow")
    assert out["a"].get("3", False) is denied
    observed = out["info"]["appsec_last_observed"]
    assert observed["action"] == ("ban" if denied else "allow") and observed["error"]
    if denied:
        assert out["a"]["4"]["source"] == "failure_policy"


@pytest.mark.parametrize("action", ["ban", "challenge", "unexpected"])
def test_appsec_denial_actions_fall_back_to_ban(tmp_path, action):
    out = run(
        tmp_path,
        "result({a=allow(),info=b.ConnectionInfo()})",
        conf={"APPSEC_URL": "http://appsec:7422"},
        setup=f"APPSEC_STATUS=403; APPSEC_BODY={to_lua(json.dumps({'action': action, 'http_status': 429}))}",
    )
    assert out["a"]["3"] is True and out["a"]["4"]["source"] == "appsec"
    assert out["info"]["appsec_last_observed"]["action"] == (action if action != "unexpected" else "unknown")


@pytest.mark.parametrize(
    "body,version,length,expected", [("payload", 1.1, None, "payload"), (None, 2, None, None), ("", 1.1, None, ""), ("payload", 2, "7", "payload")]
)
def test_appsec_forwards_body_and_original_request_headers(tmp_path, body, version, length, expected):
    out = run(
        tmp_path,
        "result({a=allow(),limit=HEADER_LIMIT,read=BODY_READ,closed=CLOSED})",
        conf={"APPSEC_URL": "http://appsec:7422"},
        setup=f"BODY={to_lua(body)}; HTTP_VERSION={version}; ngx.var.http_content_length={to_lua(length)}; MAX_HEADERS='321'",
    )
    request = out["requests"][-1]["opts"]
    assert request.get("body") == expected and request["method"] == ("POST" if expected else "GET")
    assert request["headers"]["host"] == "appsec:7422"
    assert request["headers"]["x-crowdsec-appsec-ip"] == IP
    assert request["headers"]["x-crowdsec-appsec-uri"] == "/private?q=1"
    assert out["limit"] == 321 and out["closed"] == 2 and out["a"]["2"] == "allow"


def test_appsec_reads_file_body(tmp_path):
    body = tmp_path / "body"
    body.write_text("file payload")
    out = run(tmp_path, "result({a=allow()})", conf={"APPSEC_URL": "http://appsec:7422"}, setup=f"BODY_FILE={to_lua(str(body))}")
    assert out["requests"][-1]["opts"]["body"] == "file payload"


@pytest.mark.parametrize(
    "setup,conf,message",
    [("", {"ENABLED": "false"}, "disabled"), ("INTERNAL=true", {}, "internal"), ("", {"EXCLUDE_LOCATION": "/private"}, "whitelisted /private")],
)
def test_request_bypasses(tmp_path, setup, conf, message):
    out = run(tmp_path, "result({a=allow()})", conf=conf, setup=setup)
    assert out["a"]["2"] == message and out["requests"] == {}


def test_rewritten_internal_request_is_still_denied(tmp_path):
    out = run(
        tmp_path,
        "result({a=allow(),missing=table.pack(b.Allow('192.0.2.7',''))})",
        setup=f"INTERNAL=true; ngx.ctx.bw.rewritten=true; LAPI_BODY={to_lua(decision())}",
    )
    assert out["a"]["3"] is True
    assert out["missing"] == {"1": False, "2": "missing CrowdSec challenge namespace", "n": 2}


def test_excluded_location_descendant_is_bypassed(tmp_path):
    out = run(tmp_path, "ngx.var.uri='/private/child'; result({a=allow()})", conf={"EXCLUDE_LOCATION": "/private"}, setup=f"LAPI_BODY={to_lua(decision())}")
    assert out["a"]["2"] == "whitelisted /private/" and not out["a"].get("3")


def test_excluded_location_does_not_bypass_sibling_prefix(tmp_path):
    out = run(tmp_path, "ngx.var.uri='/administrator'; result({a=allow()})", conf={"EXCLUDE_LOCATION": "/admin"}, setup=f"LAPI_BODY={to_lua(decision())}")
    assert out["a"]["2"] == "denied" and out["a"]["3"] is True


def test_unconfigured_bouncer_and_no_api_metadata(tmp_path):
    out = run(tmp_path, "result({a=table.pack(b.allowIp('bad')),info=b.ConnectionInfo(),excluded=b.HasExcludedLocations(),closed=b.close()})", initialize=False)
    assert out["a"]["3"] == "Configuration is bad, cannot run properly"
    assert out["info"] == {"lapi_url": "", "appsec_url": "", "management_configured": False}
    assert out["excluded"] is False


def test_invalid_ip_reports_error_and_captcha_unconfigured(tmp_path):
    out = run(tmp_path, "result({a=table.pack(b.allowIp('bad')),template=b.GetCaptchaTemplate(),key=b.GetCaptchaBackendKey()})")
    assert out["a"]["3"] == "Check failed 'bad' has no valid IP address"
    assert "template" not in out and "key" not in out


def test_stream_setup_schedules_once_and_timer_failure_is_reported(tmp_path):
    out = run(
        tmp_path,
        "TIMER_ERROR='no timers'; local failed=table.pack(b.SetupStream()); TIMER_ERROR=nil; b.SetupStream(); b.SetupStream(); result({failed=failed})",
        conf={"MODE": "stream"},
    )
    assert out["failed"]["3"] == "Failed to create the timer: no timers" and out["timers"] == 1


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://user:secret@lapi.example/path?q=secret#fragment", "https://lapi.example/path"),
        ("ftp://host", ""),
        ("http://bad%host/", ""),
        ("http://bad host/", ""),
        ("https://[2001:db8::1]:8080/path", "https://[2001:db8::1]:8080/path"),
    ],
)
def test_connection_info_strips_credentials_queries_and_invalid_urls(tmp_path, value, expected):
    out = run(
        tmp_path,
        "result({info=b.ConnectionInfo(),excluded=b.HasExcludedLocations()})",
        conf={"API_URL": value, "MANAGEMENT_LOGIN": '"machine"', "MANAGEMENT_PASSWORD": '"password"', "REDIRECT_LOCATION": "/redirect"},
    )
    assert out["info"]["lapi_url"] == expected and out["info"]["management_configured"] is True and out["excluded"] is True


def captcha_conf(tmp_path):
    return {"CAPTCHA_PROVIDER": "recaptcha", "SITE_KEY": "site", "SECRET_KEY": "secret", "CAPTCHA_TEMPLATE_PATH": str(tmp_path / "captcha.html")}


@pytest.mark.parametrize("source", [1, 2])
def test_captcha_challenge_then_valid_solution_redirects(tmp_path, source):
    appsec = source == 2
    setup = "BODY='solution'; POST_ARGS={['g-recaptcha-response']='token'}; "
    conf = captcha_conf(tmp_path)
    if appsec:
        conf["APPSEC_URL"] = "http://appsec:7422"
        conf["ALWAYS_SEND_TO_APPSEC"] = "true"
        setup += "APPSEC_STATUS=403; APPSEC_BODY='{" + '"action":"captcha"' + "}'"
        setup += f"; LAPI_BODY={to_lua(decision(type='captcha'))}"
    else:
        setup += f"LAPI_BODY={to_lua(decision(type='captcha'))}"
    out = run(
        tmp_path,
        """
local first=allow()
local state,flags=ngx.shared.crowdsec_cache:get('challenge|captcha_192.0.2.7')
local second=allow()
local after,after_flags=ngx.shared.crowdsec_cache:get('challenge|captcha_192.0.2.7')
result({first=first,second=second,state=state,flags=flags,after=after,after_flags=after_flags,
    method=METHOD,key=b.GetCaptchaBackendKey(),template=b.GetCaptchaTemplate()})
""",
        conf=conf,
        setup=setup,
    )
    assert out["first"] == {"n": 0} and out["output"] == "challenge site"
    assert out["flags"] == source | 4 and out["state"] == "/private"
    assert out["second"] == {"1": True, "2": "/private", "n": 2} and out["method"] == 2
    assert out["key"] == "g-recaptcha-response" and out["template"] == "challenge site"
    if appsec:
        assert "after" not in out
    else:
        assert out["after_flags"] == 9


@pytest.mark.parametrize("failure", ["CAPTCHA_VALID=false", "CAPTCHA_ERROR=true", "POST_ARGS={}"])
def test_invalid_captcha_does_not_redirect_or_allow(tmp_path, failure):
    out = run(
        tmp_path,
        "allow(); " + failure + "; result({a=allow(),method=METHOD})",
        conf=captcha_conf(tmp_path),
        setup=f"BODY='solution'; POST_ARGS={{['g-recaptcha-response']='token'}}; LAPI_BODY={to_lua(decision(type='captcha'))}",
    )
    assert out["a"] == {"n": 0} and "method" not in out and out["output"] == "challenge site"
    assert out["cache"]["challenge|captcha_192.0.2.7"] == "/private"


def test_appsec_only_captcha_solution_redirects(tmp_path):
    out = run(
        tmp_path,
        "allow(); result({a=allow(),method=METHOD})",
        conf={**captcha_conf(tmp_path), "APPSEC_URL": "http://appsec:7422"},
        setup="BODY='x'; POST_ARGS={['g-recaptcha-response']='ok'}; APPSEC_STATUS=403; APPSEC_BODY='{\"action\":\"captcha\"}'",
    )
    assert out["a"].get("2") == "/private" and out.get("method") == 2


@pytest.mark.parametrize("failure", ["CAPTCHA_VALID=false", "POST_ARGS={}", "advance(61)"])
def test_appsec_only_captcha_invalid_missing_or_expired_solution_is_refused(tmp_path, failure):
    out = run(
        tmp_path,
        "allow(); " + failure + "; result({a=allow(),method=METHOD})",
        conf={**captcha_conf(tmp_path), "APPSEC_URL": "http://appsec:7422"},
        setup="BODY='x'; POST_ARGS={['g-recaptcha-response']='ok'}; APPSEC_STATUS=403; APPSEC_BODY='{\"action\":\"captcha\"}'",
    )
    assert out["a"] == {"n": 0} and "method" not in out and out["output"] == "challenge site"
    assert out["cache"]["challenge|captcha_192.0.2.7"] == "/private"


def test_lapi_ban_blocks_pending_appsec_captcha_solution(tmp_path):
    out = run(
        tmp_path,
        "allow(); advance(31); LAPI_BODY=" + to_lua(decision()) + "; result({a=allow(),method=METHOD})",
        conf={**captcha_conf(tmp_path), "APPSEC_URL": "http://appsec:7422"},
        setup="BODY='x'; POST_ARGS={['g-recaptcha-response']='ok'}; APPSEC_STATUS=403; APPSEC_BODY='{\"action\":\"captcha\"}'",
    )
    assert out["a"]["2"] == "denied" and out["a"]["3"] is True and "method" not in out


@pytest.mark.parametrize("failure", ["CHALLENGE_FULL=true", "CHALLENGE_FORCIBLE=true"])
def test_captcha_cache_failures_are_logged(tmp_path, failure):
    out = run(tmp_path, "result({a=allow()})", conf=captcha_conf(tmp_path), setup=f"{failure}; LAPI_BODY={to_lua(decision(type='captcha'))}")
    assert out["a"] == {"n": 0} and out["output"] == "challenge site"
    assert any("cache) is full" in line[1] for line in out["logs"])


def test_captcha_post_remembers_referer_and_validated_state_allows(tmp_path):
    out = run(
        tmp_path,
        """
ngx.var.request_method='POST'; req_headers.referer='/original'
allow()
local previous=ngx.shared.crowdsec_cache:get('challenge|captcha_192.0.2.7')
ngx.shared.crowdsec_cache:set('challenge|captcha_192.0.2.7',previous,3600,9)
result({a=allow(),previous=previous})
""",
        conf=captcha_conf(tmp_path),
        setup=f"LAPI_BODY={to_lua(decision(type='captcha'))}",
    )
    assert out["previous"] == "/original" and out["a"]["2"] == "allow"


def test_captcha_validation_storage_failure_still_redirects_and_logs(tmp_path):
    out = run(
        tmp_path,
        "allow(); CHALLENGE_FULL=true; result({a=allow()})",
        conf=captcha_conf(tmp_path),
        setup=f"BODY='x'; POST_ARGS={{['g-recaptcha-response']='ok'}}; LAPI_BODY={to_lua(decision(type='captcha'))}",
    )
    assert out["a"]["2"] == "/private"
    assert any("failed to add key about captcha" in line[1] for line in out["logs"])


def test_live_allow_clears_stale_captcha_and_appsec_can_be_skipped(tmp_path):
    out = run(
        tmp_path,
        "ngx.shared.crowdsec_cache:set('challenge|captcha_192.0.2.7','/old'); ngx.var.no_appsec='1'; result({a=allow()})",
        conf={"APPSEC_URL": "http://appsec:7422"},
    )
    assert out["a"]["2"] == "allow" and "challenge|captcha_192.0.2.7" not in out["cache"]
    assert len(out["requests"]) == 1


@pytest.mark.parametrize("mode", ["live", "stream"])
def test_refresh_replaces_decision_and_bumps_lease_epoch(tmp_path, mode):
    out = run(
        tmp_path,
        """
allow()
local before=lease.lease_epoch('192.0.2.7',false)
LAPI_BODY='[]'
local refreshed,err,status=b.Control('refresh_ip',{ip='192.0.2.7'})
local after=lease.lease_epoch('192.0.2.7',false)
result({refreshed=refreshed,error=err,status=status,before=before,after=after,a=allow()})
""",
        conf={"MODE": mode},
        setup=f"LAPI_BODY={to_lua(decision())}",
    )
    assert out["status"] == 200 and out["refreshed"] == {"ip": IP, "decision_ids": [], "observed_at": 1700000000}
    assert out["after"] > out.get("before", 0) and out["a"]["2"] == "allow"
    assert any("contains=true" in req["uri"] for req in out["requests"])


@pytest.mark.parametrize("mode", ["live", "stream"])
def test_refresh_ban_reports_ids_and_enforces(tmp_path, mode):
    out = run(
        tmp_path, "local r,e,s=b.RefreshIp({ip='192.0.2.7'}); result({r=r,e=e,s=s,a=allow()})", conf={"MODE": mode}, setup=f"LAPI_BODY={to_lua(decision())}"
    )
    assert out["s"] == 200 and out["r"]["decision_ids"] == [7] and out["r"]["remediation"] == "ban"
    assert out["a"]["3"] is True


@pytest.mark.parametrize(
    "setup,error,status",
    [
        ("LAPI_DOWN=true", "Local API request failed", 502),
        ("LAPI_STATUS=401", "Local API returned HTTP 401", 502),
        ("LAPI_BODY='{}'", "Invalid Local API response", 502),
        ("LOCK_BUSY=true", "busy", 503),
        ("LOCK_ERROR=true", "Stream lock unavailable", 502),
        ("WRITE_ERROR=true", "Enforcement checkpoint write failed", 502),
        ("CACHE_FULL=true", "Local decision cache is full", 502),
    ],
)
def test_refresh_failures_are_actionable(tmp_path, setup, error, status):
    out = run(tmp_path, setup + "; local r,e,s=b.RefreshIp({ip='192.0.2.7'}); result({r=r,e=e,s=s})", setup=f"LAPI_BODY={to_lua(decision())}")
    assert (out["e"], out["s"]) == (error, status) and "r" not in out


@pytest.mark.parametrize("params", [None, "bad", {}, {"ip": "bad"}])
def test_refresh_rejects_invalid_ip(tmp_path, params):
    out = run(tmp_path, f"local r,e,s=b.RefreshIp({to_lua(params)}); result({{r=r,e=e,s=s}})")
    assert (out["e"], out["s"]) == ("invalid ip", 400) and out["requests"] == {}


def test_refresh_without_lapi_and_unknown_control(tmp_path):
    out = run(
        tmp_path, "local r,e,s=b.RefreshIp({ip='192.0.2.7'}); local x,y,z=b.Control('unknown',{}); result({r=r,s=s,e=e,other=y,status=z})", conf={"API_URL": ""}
    )
    assert out["s"] == 200 and out["r"]["decision_ids"] == [] and out["requests"] == {}
    assert out["status"] == 409 and out["other"] == "No valid CrowdSec Local API configured"


def test_inflight_epoch_change_cannot_install_ban(tmp_path):
    out = run(tmp_path, "BEFORE_RESPONSE=function() lease.bump_lease_epoch('192.0.2.7') end; result({a=allow()})", setup=f"LAPI_BODY={to_lua(decision())}")
    assert out["a"]["2"] == "allow" and not any("v2_decisions_" in k for k in out["cache"])


def test_bootstrap_outage_retry_and_published_snapshot_wins(tmp_path):
    out = run(
        tmp_path,
        """
LAPI_DOWN=true; local first=allow(); allow()
local attempts=#requests
advance(11); LAPI_DOWN=false
BEFORE_RESPONSE=function()
    ngx.shared.crowdsec_cache:set('live|v3_generation','fingerprint|1:A')
end
result({first=first,a=allow(),attempts=attempts})
""",
        conf={"MODE": "stream"},
        setup=f"LAPI_BODY={to_lua(decision())}",
    )
    assert out["attempts"] == 1 and len(out["requests"]) == 2 and out["a"]["2"] == "allow"


def test_corrupt_checkpoint_fails_closed_during_lapi_outage(tmp_path):
    out = run(
        tmp_path,
        """
local hash=partition.hash('live|')
local f=assert(io.open('/var/lib/bunkerweb/crowdsec-state-'..hash..'.json','w')); f:write('broken'); f:close()
LAPI_DOWN=true
result({a=allow(),info=b.ConnectionInfo()})
""",
    )
    assert out["a"].get("3") is True and out["info"]["last_sync_error"] == "Enforcement checkpoint refresh failed"


def test_live_checkpoint_save_failure_does_not_erase_ban(tmp_path):
    out = run(tmp_path, "WRITE_ERROR=true; result({a=allow(),info=b.ConnectionInfo()})", setup=f"LAPI_BODY={to_lua(decision())}")
    assert out["a"]["3"] is True and out["info"]["last_sync_error"] == "Enforcement checkpoint write failed"


def test_live_checkpoint_failure_without_decision_uses_failure_path(tmp_path):
    out = run(tmp_path, "WRITE_ERROR=true; result({a=allow(),info=b.ConnectionInfo()})")
    assert out["a"]["2"] == "allow" and out["info"]["last_sync_error"] == "Enforcement checkpoint write failed"


def test_live_cache_full_still_denies_from_fetched_decision(tmp_path):
    out = run(tmp_path, "CACHE_FULL=true; result({a=allow(),info=b.ConnectionInfo()})", setup=f"LAPI_BODY={to_lua(decision())}")
    assert out["a"]["3"] is True and out["info"]["last_sync_error"] == "Local decision cache is full"


def test_decision_type_filter_and_unknown_remediation(tmp_path):
    out = run(tmp_path, "result({a=allow()})", conf={"BOUNCING_ON_TYPE": "ban"}, setup=f"LAPI_BODY={to_lua(decision(type='captcha'))}")
    assert out["a"]["2"] == "allow"
    out = run(tmp_path, "result({a=allow()})", setup=f"LAPI_BODY={to_lua(decision(type='unknown'))}")
    assert out["a"]["3"] is True and out["a"]["4"]["decisions"][0]["remediation"] == "ban"

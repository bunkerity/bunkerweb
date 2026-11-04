"""Real Let's Encrypt module: runtime decisions with OpenResty boundaries replaced."""

import json

import pytest
from _lua_core_helpers import LUA, run_core
from _lua_state_helpers import CORE

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "letsencrypt" / "letsencrypt.lua"
PREFIX = "/.well-known/acme-challenge/"

STUBS = r"""
ngx.HTTP_OK, ngx.HTTP_BAD_REQUEST, ngx.HTTP_NOT_FOUND, ngx.HTTP_INTERNAL_SERVER_ERROR = 200, 400, 404, 500
ngx.var.host = "requested.example.com"
ngx.req = { read_body = function() end, get_body_data = function() return BODY end }
local class = require "middleclass"
local parent = class("plugin")
function parent:initialize(name, ctx) self.name = name self.ctx = ctx end
function parent:ret(ok, msg, data) return {ok=ok, msg=msg, data=data} end
package.loaded["bunkerweb.plugin"] = parent
package.loaded["bunkerweb.utils"] = {
    get_variable = function(name) return VARS[name], "missing variable" end,
    has_variable = function() return true end,
    get_multiple_variables = function() return {}, "success" end,
    read_files = function() return true, {"pem", "key"} end,
}
ENV = {}
package.loaded["resty.env"] = {set=function(k,v) ENV[k]=v end}
package.loaded["ngx.ssl"] = {
    server_name=function() return SNI, SNI_ERR end,
    raw_server_addr=function() return RAW, ADDR_TYPE end,
    parse_pem_cert=function(p) if CERT_ERR then return nil, "bad cert" end return "der:"..p end,
    parse_pem_priv_key=function(p) if KEY_ERR then return nil, "bad key" end return "der:"..p end,
}
package.loaded["resty.openssl.x509"] = {new=function()
    if X509_ERR then return nil, "bad x509" end
    return {get_subject_alt_name=function()
        if SAN_ERR then return nil, "bad SAN" end
        if NO_SAN then return nil end
        local i=0
        return {each=function() return function()
            i=i+1
            if SANS[i] then return SANS[i][1], SANS[i][2] end
        end end}
    end}
end}
local real_open, real_remove = io.open, os.remove
local folder = "/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/"
io.open=function(path, mode)
    if path:sub(1,#folder)==folder then
        if OPEN_ERR then return nil, "read only" end
        return real_open(FS_ROOT .. "/" .. path:sub(#folder+1), mode)
    end
    error("unexpected file: "..path)
end
os.remove=function(path)
    if REMOVE_ERR then return nil, "read only" end
    assert(path:sub(1,#folder)==folder)
    return real_remove(FS_ROOT .. "/" .. path:sub(#folder+1))
end
os.execute=function(cmd) assert(cmd=="mkdir -p "..folder) return true end
local le = dofile(MODULE)
-- Restore globals after capture so LuaCov can save its stats at shutdown.
io.open, os.remove = real_open, real_remove
local self = le:new({bw={uri=URI, request_method=METHOD}})
self.variables=VARS
self.logger={log=function(_,level,msg) LOGS[#LOGS+1]={level,msg} end}
self.internalstore={
    get=function(_,key) if GET_ERR==key then return nil,"store failed" end
        if STORE[key]==nil then return nil,"not found" end return STORE[key] end,
    set=function(_,key,value) if SET_ERR==key then return nil,"store full" end STORE[key]=value return true end,
}
"""


def run(tmp_path, body, **values):
    defaults = dict(
        FS_ROOT=str(tmp_path),
        VARS={"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http", "LETS_ENCRYPT_PASSTHROUGH": "no"},
        URI="/",
        METHOD="GET",
        STORE={},
        SANS=[],
        BODY="{}",
    )
    defaults.update(values)
    return run_core(MODULE, STUBS + body, **defaults)


@pytest.mark.parametrize(
    "sni,expected",
    [
        ("APP.Example.COM.", "wild"),
        ("example.com", "wild"),
        ("app.sub.example.com", "specific"),
        ("deep.app.example.com", None),
        ("app.notexample.com", None),
        ("example.com.evil.test", None),
        ("disabled.example.com", None),
        ("own.example.com", "own"),
    ],
)
def test_certificate_matches_sni_or_one_wildcard_label(tmp_path, sni, expected):
    store = {
        "plugin_letsencrypt_wildcard_servers": {"disabled.example.com": False, "own.example.com": "own.example.com"},
        "plugin_letsencrypt_wildcard_bases": ["sub.example.com", "example.com"],
        "plugin_letsencrypt_example.com": "wild",
        "plugin_letsencrypt_sub.example.com": "specific",
        "plugin_letsencrypt_own.example.com": "own",
    }
    out = run(tmp_path, "emit(self:ssl_certificate())", SNI=sni, STORE=store)
    assert out["ok"] is True
    assert out.get("data") == expected


@pytest.mark.parametrize(
    "values,message",
    [
        ({}, "no SNI provided"),
        ({"SNI_ERR": "broken"}, "can't get server_name : broken"),
        ({"SNI": "example.com"}, "can't get wildcard servers : not found"),
        (
            {"SNI": "example.com", "STORE": {"plugin_letsencrypt_wildcard_servers": {}}, "GET_ERR": "plugin_letsencrypt_wildcard_bases"},
            "can't get wildcard bases : store failed",
        ),
        (
            {"SNI": "example.com", "STORE": {"plugin_letsencrypt_wildcard_servers": {}}, "GET_ERR": "plugin_letsencrypt_example.com"},
            "error while getting plugin_letsencrypt_example.com from internalstore : store failed",
        ),
    ],
)
def test_sni_absence_and_store_errors(tmp_path, values, message):
    assert run(tmp_path, "emit(self:ssl_certificate())", **values)["msg"] == message


@pytest.mark.parametrize(
    "values,message,data",
    [
        ({"SNI": "example.com"}, "SNI present, nothing to do", None),
        ({"SNI_ERR": "broken"}, "can't get server_name : broken", None),
        ({"ADDR_TYPE": "inet6"}, "no IPv4 local address to match an IP certificate", None),
        ({"RAW": "xx"}, "no IPv4 local address to match an IP certificate", None),
        ({"GET_ERR": "plugin_letsencrypt_ip_names"}, "can't get IP names : store failed", None),
        ({"STORE": {"plugin_letsencrypt_ip_names": {}}}, "no IP certificate for 49.50.51.52", None),
        ({}, "IP certificate 49.50.51.52 found for 49.50.51.52", ["cert", "key"]),
        (
            {"GET_ERR": "plugin_letsencrypt_ipcert_49.50.51.52"},
            "error while getting plugin_letsencrypt_ipcert_49.50.51.52 from internalstore : store failed",
            None,
        ),
    ],
)
def test_default_certificate_requires_unambiguous_ip(tmp_path, values, message, data):
    defaults = dict(
        RAW="1234",
        ADDR_TYPE="inet",
        STORE={"plugin_letsencrypt_ip_names": {"49.50.51.52": "id"}, "plugin_letsencrypt_ipcert_49.50.51.52": ["cert", "key", "id"]},
    )
    defaults.update(values)
    out = run(tmp_path, "emit(self:ssl_certificate_default())", **defaults)
    assert out["msg"] == message
    assert out.get("data") == data


@pytest.mark.parametrize(
    "mapping,expected", [({}, None), ({"1.2.3.4": "a"}, "1.2.3.4"), ({"2.2.2.2": "a", "1.1.1.1": "a"}, "1.1.1.1"), ({"1.1.1.1": "a", "2.2.2.2": "b"}, None)]
)
def test_nat_fallback_accepts_only_one_lineage(tmp_path, mapping, expected):
    assert run(tmp_path, 'emit(le.select_ip_name("9.9.9.9", IPS))', IPS=mapping) == expected


@pytest.mark.parametrize(
    "fault,message",
    [
        ({"CERT_ERR": True}, "error while parsing pem cert : bad cert"),
        ({"KEY_ERR": True}, "error while parsing pem priv key : bad key"),
        ({"SET_ERR": "plugin_letsencrypt_example.com"}, "error while setting data into internalstore : store full"),
        ({"SET_ERR": "plugin_letsencrypt_ipcert_1.2.3.4"}, "error while setting data into internalstore : store full"),
    ],
)
def test_load_data_reports_parse_and_cache_failures(tmp_path, fault, message):
    assert run(tmp_path, 'local ok,err=self:load_data({"pem","key"},"example.com 1.2.3.4") emit({ok,err})', SANS=[["IP", "1.2.3.4"]], **fault) == [
        False,
        message,
    ]


@pytest.mark.parametrize("fault", [{}, {"X509_ERR": True}, {"SAN_ERR": True}, {"NO_SAN": True}])
def test_load_data_normalizes_names_and_requires_actual_ipv4_san(tmp_path, fault):
    out = run(
        tmp_path,
        'assert(self:load_data({"pem","key"},"EXAMPLE.COM. 1.2.3.4 300.2.3.4")) emit({store=STORE,logs=LOGS})',
        SANS=[["DNS", "300.2.3.4"], ["IP", "::1"], ["IP", "300.2.3.4"], ["IP", "1.2.3.4"]],
        **fault
    )
    assert out["store"]["plugin_letsencrypt_example.com"] == ["der:pem", "der:key", "example.com"]
    assert ("plugin_letsencrypt_ipcert_1.2.3.4" in out["store"]) is (not fault)
    assert "plugin_letsencrypt_ipcert_300.2.3.4" not in out["store"]
    if "X509_ERR" in fault or "SAN_ERR" in fault:
        assert "can't read the IP SANs" in out["logs"][0][1]


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST"])
@pytest.mark.parametrize("token", ["known", "unknown", "../escape", "a/b", ""])
def test_access_only_accepts_known_local_token_or_safe_passthrough(tmp_path, method, token):
    (tmp_path / "known").write_text("proof")
    for passthrough in ("no", "yes"):
        vars_ = {"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_CHALLENGE": "http", "LETS_ENCRYPT_PASSTHROUGH": passthrough}
        out = run(tmp_path, "emit(self:access())", URI=PREFIX + token, METHOD=method, VARS=vars_)
        accepted = token == "known" if passthrough == "no" else token in ("known", "unknown") and method in ("GET", "HEAD")
        assert (out.get("data") == "OK") is accepted


@pytest.mark.parametrize("custom_host", ["", "$host", "backend.example.com"])
def test_set_whitelists_passthrough_and_keeps_requested_host(tmp_path, custom_host):
    vars_ = {"AUTO_LETS_ENCRYPT": "no", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": custom_host, "USE_REVERSE_PROXY": "yes"}
    out = run(tmp_path, "local r=self:set() emit({r=r,bw=self.ctx.bw,vars=ngx.var,env=ENV})", URI=PREFIX + "abc-123_", VARS=vars_)
    assert out["bw"]["is_whitelisted"] == out["vars"]["is_whitelisted"] == out["env"]["is_whitelisted"] == "yes"
    assert out["vars"].get("bw_reverse_proxy_host") == ("requested.example.com" if custom_host == "backend.example.com" else None)


def test_set_enables_https_without_whitelisting_regular_request(tmp_path):
    out = run(tmp_path, "local r=self:set() emit({r=r,bw=self.ctx.bw})")
    assert out["bw"]["https_configured"] == "yes"
    assert "is_whitelisted" not in out["bw"]


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("token", ["../escape", "a/b", "..", "", "a\\b", "a.b", None, 7])
def test_api_rejects_traversal_and_invalid_tokens(tmp_path, method, token):
    outside = tmp_path.parent / (tmp_path.name + "-escape")
    body = json.dumps({"token": token, "validation": "proof"})
    out = run(tmp_path, "emit(self:api())", URI="/lets-encrypt/challenge", METHOD=method, BODY=body)
    assert out == {"ok": True, "msg": "invalid challenge token", "data": 400}
    assert list(tmp_path.iterdir()) == []
    assert not outside.exists()


def test_api_writes_then_removes_only_named_token(tmp_path):
    out = run(tmp_path, "emit(self:api())", URI="/lets-encrypt/challenge", METHOD="POST", BODY=json.dumps({"token": "abc-123_", "validation": "proof"}))
    assert out["data"] == 200
    assert (tmp_path / "abc-123_").read_text() == "proof"
    (tmp_path / "keep").write_text("untouched")
    out = run(tmp_path, "emit(self:api())", URI="/lets-encrypt/challenge", METHOD="DELETE", BODY=json.dumps({"token": "abc-123_"}))
    assert out["data"] == 200
    assert (tmp_path / "keep").read_text() == "untouched"
    assert not (tmp_path / "abc-123_").exists()


@pytest.mark.parametrize(
    "method,body,fault,status",
    [
        ("POST", "not json", {}, 400),
        ("POST", "7", {}, 400),
        ("POST", '{"token":"abc"}', {}, 400),
        ("POST", '{"token":"abc","validation":"proof"}', {"OPEN_ERR": True}, 500),
        ("DELETE", '{"token":"absent"}', {}, 500),
        ("DELETE", '{"token":"abc"}', {"REMOVE_ERR": True}, 500),
    ],
)
def test_api_errors_are_not_success(tmp_path, method, body, fault, status):
    assert run(tmp_path, "emit(self:api())", URI="/lets-encrypt/challenge", METHOD=method, BODY=body, **fault)["data"] == status


@pytest.mark.parametrize("uri,method", [("/other", "POST"), ("/lets-encrypt/challenge", "GET")])
def test_api_ignores_other_routes_and_methods(tmp_path, uri, method):
    assert run(tmp_path, "emit(self:api())", URI=uri, METHOD=method) == {"ok": False, "msg": "success"}


@pytest.mark.parametrize(
    "names,bases,aliases",
    [
        ("WWW.Example.COM.", ["example.com"], {"www.example.com": "example.com"}),
        ("example.com www.example.com", ["example.com"], {"example.com": "example.com", "www.example.com": "example.com"}),
        ("*.Example.COM. app.example.com example.com", ["example.com"], {"app.example.com": "example.com"}),
        (
            "app.a.example.com app.b.example.com",
            ["a.example.com", "b.example.com"],
            {"app.a.example.com": "a.example.com", "app.b.example.com": "b.example.com"},
        ),
        ("a.example.com deep.app.example.com", [], {"a.example.com": "a.example.com", "deep.app.example.com": "deep.app.example.com"}),
        ("localhost", ["localhost"], {"localhost": "localhost"}),
        ("...", [], {"..": ".."}),
    ],
)
def test_wildcard_grouping_publishes_only_covering_lineages(tmp_path, names, bases, aliases):
    vars_ = {"MULTISITE": "no", "SERVER_NAME": names, "USE_LETS_ENCRYPT_WILDCARD": "yes", "LETS_ENCRYPT_CHALLENGE": "dns"}
    out = run(tmp_path, "assert(self:init().ok) emit(STORE)", VARS=vars_)
    published = out["plugin_letsencrypt_wildcard_bases"]
    assert (sorted(published) if published else []) == sorted(bases)
    for name, alias in aliases.items():
        assert out["plugin_letsencrypt_wildcard_servers"][name] == alias


def test_collect_ip_names_excludes_uncertified_ips_and_reports_store_failure(tmp_path):
    out = run(
        tmp_path,
        'local ips={} le.collect_ip_names(self,{"EXAMPLE.COM.","1.2.3.4","2.3.4.5","3.4.5.6"},ips) emit({ips=ips,logs=LOGS})',
        STORE={"plugin_letsencrypt_ipcert_1.2.3.4": ["cert", "key", "example.com"]},
        GET_ERR="plugin_letsencrypt_ipcert_3.4.5.6",
    )
    assert out["ips"] == {"1.2.3.4": "example.com"}
    assert out["logs"] == [["ERR", "can't get IP certificate of 3.4.5.6 : store failed"]]


@pytest.mark.parametrize(
    "error,level,message",
    [
        ("not found for writing", "NOTICE", "keeping REVERSE_PROXY_CUSTOM_HOST"),
        ("unexpected variable error", "ERR", "can't override $bw_reverse_proxy_host"),
    ],
)
def test_set_reports_missing_or_unwritable_proxy_variable(tmp_path, error, level, message):
    vars_ = {"AUTO_LETS_ENCRYPT": "yes", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "backend.example.com", "USE_REVERSE_PROXY": "yes"}
    out = run(
        tmp_path,
        'setmetatable(ngx.var,{__newindex=function(t,k,v) if k=="bw_reverse_proxy_host" then error(WRITE_ERROR,0) end rawset(t,k,v) end}) local r=self:set() emit({r=r,logs=LOGS,bw=self.ctx.bw})',
        URI=PREFIX + "token",
        VARS=vars_,
        WRITE_ERROR=error,
    )
    assert out["r"]["ok"] is True
    assert out["bw"]["is_whitelisted"] == "yes"
    assert out["logs"][0][0] == level
    assert message in out["logs"][0][1]

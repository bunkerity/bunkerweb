"""Execute the complete LE plugin with controlled SAN and destination fixtures."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/common/core/letsencrypt/letsencrypt.lua"
LUA = shutil.which("lua") or shutil.which("luajit")

HARNESS = r"""local store = {}
local multisite = "no"
local sans = arg[2] == "valid" and {"8.8.8.8"} or {}
local sni = arg[3] ~= "none" and arg[3] or nil
local addr = arg[4] == "wrong" and string.char(1,1,1,1) or string.char(8,8,8,8)
local modules = {
 cjson = {}, middleclass = function() return {} end,
 ["bunkerweb.plugin"] = {}, ["bunkerweb.utils"] = {
 has_variable=function() return arg[5] ~= "unconfigured" end,
 get_variable=function(k) return ({MULTISITE=multisite,DISABLE_DEFAULT_SERVER=arg[9] or "no",SERVER_NAME="example.com 8.8.8.8",USE_LETS_ENCRYPT_WILDCARD="no",LETS_ENCRYPT_CHALLENGE="http"})[k] end,
 read_files=function() return true,{"IP-CERT","KEY"} end},
 ["ngx.ssl"] = {parse_pem_cert=function(p) return p end, parse_pem_priv_key=function(p) return p end,
 server_name=function() return sni end, raw_server_addr=function() return addr, "inet" end},
 ["resty.openssl.x509"] = {new=function() return {get_subject_alt_name=function() return {each=function()
 local i=0; return function() i=i+1; if sans[i] then return "IP",sans[i] end end end} end} end},
}
require = function(name) assert(modules[name], name); return modules[name] end
ngx = {ERR=3, NOTICE=5}
local le = dofile(arg[1])
local obj = {logger={log=function() end}, internalstore={
 set=function(_,k,v) store[k]=v; return true end,
 get=function(_,k) if store[k] == nil then return nil,"not found" end; return store[k] end},
 ret=function(_,ok,msg,status) return {ret=ok,msg=msg,status=status} end}
obj.is_loading = arg[10] == "yes"
obj.load_data = le.load_data
obj.ssl_certificate_default = le.ssl_certificate_default
assert(le.init(obj).ret)
multisite = arg[8] or "no"
if arg[5] ~= "unconfigured" then
 assert((store["plugin_letsencrypt_8.8.8.8"] ~= nil) == (arg[2] == "valid"), "IP alias requires its SAN")
end
if arg[6] == "custom" then store["plugin_customcert_8.8.8.8"]={"CUSTOM","KEY"} end
if arg[6] == "inventory" then
 store["plugin_customcert_8.8.8.8"]={"CUSTOM","KEY"}
 store["plugin_certificates_8.8.8.8"]={"INVENTORY","KEY"}
end
assert(le.ssl_certificate_default, "no no-SNI provider")
local ret = arg[7] == "service" and le.ssl_certificate(obj) or le.ssl_certificate_default(obj)
assert(ret.ret,ret.msg)
print(ret.status and ret.status[1] or "nil")
"""


@pytest.mark.skipif(LUA is None, reason="Lua interpreter unavailable")
@pytest.mark.parametrize(
    ("sans", "sni", "destination", "configured", "expected"),
    [
        ("valid", "none", "right", "configured", "IP-CERT"),
        ("valid", "none", "wrong", "configured", "nil"),
        ("invalid", "none", "right", "configured", "nil"),
        ("valid", "tenant.example", "right", "configured", "nil"),
        ("valid", "none", "right", "unconfigured", "nil"),
    ],
)
def test_no_sni_selection(tmp_path, sans, sni, destination, configured, expected):
    script = tmp_path / "phase.lua"
    script.write_text(HARNESS)
    result = subprocess.run([LUA, str(script), str(SOURCE), sans, sni, destination, configured], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.skipif(LUA is None, reason="Lua interpreter unavailable")
@pytest.mark.parametrize(("provider", "expected"), [("custom", "CUSTOM"), ("inventory", "INVENTORY")])
def test_existing_provider_priority(tmp_path, provider, expected):
    script = tmp_path / "priority.lua"
    script.write_text(HARNESS)
    result = subprocess.run([LUA, str(script), str(SOURCE), "valid", "none", "right", "configured", provider], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.skipif(LUA is None, reason="Lua interpreter unavailable")
@pytest.mark.parametrize(
    ("sans", "destination", "provider", "multisite", "disabled", "expected", "loading"),
    [
        ("valid", "right", "none", "no", "no", "IP-CERT", "no"),
        ("valid", "wrong", "none", "no", "no", "nil", "no"),
        ("invalid", "right", "none", "no", "no", "nil", "no"),
        ("valid", "right", "custom", "no", "no", "CUSTOM", "no"),
        ("valid", "right", "inventory", "no", "no", "INVENTORY", "no"),
        ("valid", "right", "none", "yes", "no", "nil", "no"),
        ("valid", "right", "none", "no", "yes", "nil", "no"),
        ("valid", "right", "none", "no", "no", "nil", "yes"),
    ],
)
def test_implicit_single_site_default_uses_destination_certificate(tmp_path, sans, destination, provider, multisite, disabled, expected, loading):
    script = tmp_path / "single-site.lua"
    script.write_text(HARNESS)
    result = subprocess.run(
        [LUA, str(script), str(SOURCE), sans, "none", destination, "configured", provider, "service", multisite, disabled, loading],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected

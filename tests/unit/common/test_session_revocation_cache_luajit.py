"""Real vendored revocation/shm/LRU paths; crypto and nginx request boundaries stubbed."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from test_sessions_coverage_lua import NEW, run

ROOT = Path(__file__).resolve().parents[3]
LUAJIT = os.environ.get("BW_LUAJIT") or shutil.which("luajit")
VENDOR = Path(os.environ.get("BW_DEPSESS_VENDOR", ROOT / "src/deps/src/lua-resty-session"))


@pytest.mark.skipif(not LUAJIT, reason="no LuaJIT on PATH (BW_LUAJIT)")
def test_destroy_reaches_another_worker_immediately():
    config = run(NEW + "p:init() emit(CONFIG)")
    script = r"""
local values = {}
ngx = {
    req={clear_header=function() end,set_header=function() end}, header={}, var={},
    time=function() return 1000 end, now=function() return 1000 end, log=function() end,
    shared={sessions_revocation={
        get=function(_,key) return values[key] end,
        set=function(_,key,value) values[key]=value return true end,
    }},
}
local utils = require "resty.session.utils"
-- Crypto is outside this check; no cookie is encrypted or decrypted.
utils.rand_bytes=function(n) return string.rep("x",n) end
utils.sha256=function(value) return value end
local function upvalue(fn, name)
    for i=1,100 do
        local key,value=debug.getupvalue(fn,i)
        if key==name then return value end
        if not key then break end
    end
    error("missing upvalue: " .. name)
end
local function worker()
    package.loaded["resty.session"]=nil
    local lib=require "resty.session"
    lib.init(CONFIG)
    local s=lib.new()
    s.hash_storage_key=function(sid) return sid end
    local destroy=upvalue(s.destroy,"destroy")
    local mark=upvalue(destroy,"mark_session_revoked")
    local lookup=upvalue(mark,"is_session_revoked")
    s.state=upvalue(s.destroy,"STATE_OPEN")
    s.meta={sid="same-cookie",creation_time=1000,rolling_offset=0}
    return s,lookup
end
local first=worker()
local second,lookup=worker()
assert(lookup(second,"same-cookie",second.cookie_name)==false)
assert(first:destroy())
assert(lookup(second,"same-cookie",second.cookie_name)==true,"worker accepted revoked cookie")
print("OK")
"""
    # Feed the real plugin's config, including absence of a TTL override on the broken version.
    settings = "\n".join(f"CONFIG[{json.dumps(key)}]={config[key]}" for key in ("revocation_cache_ttl", "revocation_error_cache_ttl") if key in config)
    prelude = (
        f"package.path={json.dumps(str(VENDOR / 'lib/?.lua') + ';' + str(ROOT / 'src/deps/src/lua-resty-lrucache/lib/?.lua') + ';')} .. package.path\n"
        'CONFIG={storage="cookie",revocation="shm",revocation_fail_mode="open",shm={zone="sessions_revocation",prefix="revoked_"}}\n' + settings + "\n"
    )
    result = subprocess.run([LUAJIT, "-"], input=prelude + script, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "OK"

"""Real Lua contracts for shared HTTP evidence, TTLs and Redis degradation."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/common/core/metrics/metrics.lua"
LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="requires Lua")


def _extract(name):
    match = re.search(r"^(?:local )?function " + re.escape(name) + r"\(.*?^end$", SOURCE.read_text(), re.M | re.S)
    assert match, f"missing production function {name}"
    return match.group()


def _run(body):
    prelude = r"""
local metrics, ERR, HTTP_OK, HTTP_BAD_REQUEST = {}, 3, 200, 400
local subsystem, worker_id = "http", function() return 0 end
local now, time = 100, function() return 100 end
local BAN_EVIDENCE_PENDING, BAN_EVIDENCE_RECOVERY_BATCH = "ban_evidence_pending", 32
local null, ngx = {}, {HTTP_BAD_REQUEST=400}
local utils = {rand=function() return string.rep("x",32) end}
local parse_duration = function(v) return tonumber(v) end
local store, ttls, pending, redis, calls = {}, {}, {}, {}, {}
local tokens, serial = {}, 0
local encode = function(v) serial=serial+1; tokens[tostring(serial)]=v; return tostring(serial) end
local decode = function(v) assert(tokens[v], "invalid JSON"); return tokens[v] end
local fail_local, fail_redis, connects, closes = false, false, 0, 0
local obj = setmetatable({variables={METRICS_REDIS_TTL="200"}, use_redis=true,
  metrics_datastore={
    set_with_retries=function(_,k,v,ttl) if fail_local then return false,"no memory" end; store[k]=v; ttls[k]=ttl; return true end,
    get=function(_,k) return store[k] end,
    ttl=function(_,k) return true,ttls[k] end,
    dict={lpush=function(_,_,v) table.insert(pending,1,v); return true end,
      rpush=function(_,_,v) pending[#pending+1]=v; return true end,
      rpop=function() return table.remove(pending) end}},
  clusterstore={cluster_mode=false,
    connect=function() connects=connects+1; return not fail_redis,"unavailable" end,
    close=function() closes=closes+1 end},
  redis_call=function(_,method,k,v,...)
    calls[#calls+1]={method,k,v,...}
    if fail_redis then return false,"OOM" end
    if method=="get" then return redis[k] or null end
    redis[k]=redis[k] or v; return "OK"
  end,
  log_throttled=function() end,
  ret=function(_,ok,msg,status) return {ret=ok,msg=msg,status=status} end,
  ctx={bw={uri="",request_method="GET"}},
}, {__index=metrics})
"""
    functions = "\n".join(
        _extract(name)
        for name in ("request_redis_key", "sync_ban_evidence", "metrics:store_ban_evidence", "metrics:recover_ban_evidence", "metrics:api_ban_evidence")
    )
    result = subprocess.run([LUA, "-"], input=prelude + functions + "\n" + body, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_reference_is_small_and_evidence_has_original_expiry():
    _run("""
local events={{url="/attack",counter=40}}
local summary=obj:store_ban_evidence(events,{counter=40,ban_time=60})
assert(summary.ban_id=="http:"..string.rep("x",32))
assert(summary.events==nil and summary.event_count==1 and summary.counter==40)
assert(summary.evidence_expires_at==360)
local key="ban_evidence:"..summary.ban_id..":data"
assert(ttls[key]==260 and decode(store[key]).events==events)
assert(redis["requests:ban_evidence:"..summary.ban_id]==store[key])
assert(calls[1][4]=="NX" and calls[1][5]=="EX" and calls[1][6]==260)
assert(connects==1 and closes==1)
""")


@pytest.mark.parametrize("retention,ban_time", [("0", 60), ("200", 0)])
def test_permanent_settings_keep_evidence_permanent(retention, ban_time):
    _run(f"""
obj.variables.METRICS_REDIS_TTL="{retention}"
local summary=obj:store_ban_evidence({{}},{{ban_time={ban_time}}})
assert(summary.evidence_expires_at==0)
assert(calls[1][4]=="NX" and calls[1][5]==nil)
""")


def test_redis_pressure_keeps_reference_and_recovery_uses_remaining_ttl():
    _run("""
fail_redis=true
local summary=obj:store_ban_evidence({{url="/x"}},{ban_time=60,counter=90})
assert(summary.ban_id and #pending==1 and connects==1)
fail_redis=false; obj.redis_ok=true
ttls["ban_evidence:"..summary.ban_id..":data"]=9
obj:recover_ban_evidence()
assert(#pending==0 and calls[#calls][6]==9,"recovery extended evidence expiry")
fail_local=true; fail_redis=true
assert(obj:store_ban_evidence({{url="/x"}},{ban_time=60}).ban_id)
""")


def test_cluster_keys_and_lookup_are_exact_and_missing_is_explicit():
    _run("""
obj.clusterstore.cluster_mode=true
local summary=obj:store_ban_evidence({{url="/x"}},{ban_time=60})
assert(calls[1][2]=="{requests}:ban_evidence:"..summary.ban_id)
assert(obj:api_ban_evidence(summary.ban_id).msg.events[1].url=="/x")
store={}
assert(obj:api_ban_evidence(summary.ban_id).msg.events[1].url=="/x","peer Redis fallback missing")
redis={}
assert(obj:api_ban_evidence(summary.ban_id).msg.evidence_missing==true)
for _,id in ipairs({"stream:"..string.rep("x",32), "http:short", "../key", "http:"..string.rep("x",33)}) do
  assert(obj:api_ban_evidence(id).status==400)
end
""")


def test_recovery_work_is_bounded_and_does_not_starve_on_failure():
    _run("""
obj.redis_ok=true
for i=1,40 do
  local id="http:"..string.rep("x",30)..string.format("%02d",i)
  pending[#pending+1]=id; store["ban_evidence:"..id..":data"]=encode({ban_id=id,events={}})
  ttls["ban_evidence:"..id..":data"]=10
end
obj:recover_ban_evidence()
assert(#pending==8 and #calls==32)
fail_redis=true; obj:recover_ban_evidence()
assert(#pending==8 and #calls==33)
""")

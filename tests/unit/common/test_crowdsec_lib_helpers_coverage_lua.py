"""Bundled CrowdSec helper contracts, loading real libraries with runtime boundaries faked."""

import hashlib
import json
from pathlib import Path

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
package.path = ROOT .. '/src/common/core/?.lua;' .. package.path
package.loaded['cjson'] = json
package.loaded['cjson.safe'] = {decode=function(raw)
    local ok, value = pcall(json.decode, raw)
    if ok then return value end
end}
package.loaded['resty.sha256'] = {new=function()
    local parts = {}
    return {update=function(_, s) parts[#parts+1]=s return true end,
        final=function() return SHA256(table.concat(parts)) end}
end}
package.loaded['resty.string'] = {to_hex=function(s)
    return (s:gsub('.', function(c) return string.format('%02x', c:byte()) end))
end}
package.loaded['bit32'] = {band=function(a,b) return a & b end}
NOW, LOGS = 1000, {}
ngx = {ERR='ERR', time=function() return NOW end,
    log=function(level, msg) LOGS[#LOGS+1]={level,msg} end}
for _, n in ipairs({200,202,204,301,302,400,401,403,404,405,406,444,500}) do
    local names = {[200]='OK',[202]='ACCEPTED',[204]='NO_CONTENT',[301]='MOVED_PERMANENTLY',
        [302]='MOVED_TEMPORARILY',[400]='BAD_REQUEST',[401]='UNAUTHORIZED',[403]='FORBIDDEN',
        [404]='NOT_FOUND',[405]='NOT_ALLOWED',[406]='NOT_ACCEPTABLE',[444]='CLOSE',[500]='INTERNAL_SERVER_ERROR'}
    ngx['HTTP_' .. names[n]] = n
end
function dict()
    local d = {data={}, ttls={}}
    function d:get(k) return self.data[k] end
    function d:safe_set(k,v,ttl)
        if self.full then return nil, 'no memory' end
        self.data[k], self.ttls[k] = v, ttl
        return true
    end
    function d:delete(k) self.data[k], self.ttls[k] = nil, nil end
    function d:get_keys()
        local keys = {}
        for k in pairs(self.data) do keys[#keys+1]=k end
        return keys
    end
    return d
end
CACHE, META = dict(), dict()
-- libc is the boundary: drive open, descriptor and flock failures independently.
LOCK, CLOSED, GC_ATTACHED = {}, 0, false
package.loaded['ffi'] = {
    cdef=function() end,
    gc=function(_, callback) GC_ATTACHED = callback ~= nil end,
    errno=function() return LOCK.errno or 11 end,
    C={fopen=function() if not LOCK.open_fail then return {} end end,
       fileno=function() return LOCK.fd or 7 end,
       flock=function() return LOCK.result or 0 end,
       fclose=function() CLOSED=CLOSED+1 end},
}
"""


def run(module, body):
    header = f"ROOT = {to_lua(str(ROOT))}\n"
    return last_json(run_lua(BASE_LUA + header + HARNESS + f"\nlocal lib = require('crowdsec.lib.{module}')\n" + body))


def config(tmp_path, content):
    path = tmp_path / "bouncer.conf"
    path.write_text(content)
    return run("config", f"local conf, err = lib.loadConfig({to_lua(str(path))}); emit({{conf=conf,err=err,logs=LOGS}})")


def test_config_missing_file_reports_path(tmp_path):
    path = str(tmp_path / "absent")
    out = run("config", f"local c,e=lib.loadConfig({to_lua(path)}); emit({{missing=c==nil,err=e}})")
    assert out == {"missing": True, "err": f"File {path} doesn't exist"}


def test_config_split_retains_each_field():
    assert run("config", "emit(split('one,two,three', ','))") == ["one", "two", "three"]


@pytest.mark.parametrize(
    ("key", "default"),
    [
        ("ENABLED", "true"),
        ("ENABLE_INTERNAL", "false"),
        ("BOUNCING_ON_TYPE", "ban"),
        ("SSL_VERIFY", "true"),
        ("MODE", "stream"),
        ("FALLBACK_REMEDIATION", "ban"),
        ("REQUEST_TIMEOUT", 500),
    ],
)
def test_config_invalid_value_keeps_default(tmp_path, key, default):
    out = config(tmp_path, f"{key}=invalid\n")
    assert out["conf"][key] == default
    if key != "REQUEST_TIMEOUT":
        assert out["logs"] == [["ERR", f"unsupported value 'invalid' for variable '{key}'. Using default value '{default}' instead"]]


def test_config_valid_values_credentials_exclusions_and_defaults(tmp_path):
    values = {
        "ENABLED": "false",
        "ENABLE_INTERNAL": "true",
        "BOUNCING_ON_TYPE": "all",
        "SSL_VERIFY": "false",
        "MODE": "live",
        "FALLBACK_REMEDIATION": "captcha",
        "API_URL": "http://lapi:8080/a=b",
        "REQUEST_TIMEOUT": 23,
        "CACHE_SIZE": 17,
        "MANAGEMENT_LOGIN": 'user"name',
        "MANAGEMENT_PASSWORD": "p=word",
    }
    content = (
        "# comment\n \n"
        + "\n".join(f" {k} = {json.dumps(v) if k.startswith('MANAGEMENT_') else v} " for k, v in values.items())
        + "\nEXCLUDE_LOCATION=/health,/ready\nUNKNOWN=ignored\n"
    )
    out = config(tmp_path, content)
    assert {k: out["conf"][k] for k in values} == values
    assert out["conf"]["EXCLUDE_LOCATION"] == ["/health", "/ready"]
    assert out["conf"]["STREAM_REQUEST_TIMEOUT"] == 15000
    assert out["conf"]["APPSEC_FAILURE_ACTION"] == "passthrough"
    assert "UNKNOWN" not in out["conf"]
    assert out["logs"] == [["ERR", "unsupported configuration 'UNKNOWN'"]]


@pytest.mark.parametrize("value", ["broken", "42", "null", "{}"])
def test_config_invalid_credential_refuses_configuration(tmp_path, value):
    out = config(tmp_path, "MANAGEMENT_PASSWORD=" + value + "\n")
    assert "conf" not in out
    assert out["err"] == "Invalid CrowdSec management credential encoding"


def test_config_empty_exclusions_and_bad_line_stop_reading(tmp_path):
    out = config(tmp_path, "EXCLUDE_LOCATION=\ninvalid line\nMODE=live\n")
    assert out["conf"]["EXCLUDE_LOCATION"] == {}
    assert out["conf"]["MODE"] == "stream"
    assert out["logs"] == [["ERR", "invalid configuration line: invalid line"]]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1h2m3.5s", 3723.5),
        ("0.5h", 1800),
        ("2m", 120),
        ("0s", None),
        ("", None),
        (4, None),
        ("1m1h", None),
        ("1s1s", None),
        ("x1s", None),
        ("1h!", None),
        ("-1s", None),
        ("9" * 400 + "h", None),
    ],
)
def test_duration_requires_ordered_positive_finite_units(value, expected):
    assert run("decision_cache", f"emit(lib.duration({to_lua(value)}))") == expected


@pytest.mark.parametrize("identity", ["decision", 0, 9007199254740991])
def test_identity_preserves_valid_ids(identity):
    assert run("decision_cache", f"emit(lib.identity({{id={to_lua(identity)}}}))") == str(identity)


@pytest.mark.parametrize("identity", ["", "x" * 129, "a\nb", -1, 1.5, 9007199254740992, True, {}])
def test_identity_refuses_invalid_ids(identity):
    assert run("decision_cache", f"emit(lib.identity({{id={to_lua(identity)}}}))") is None


def test_identity_fallback_hashes_provenance_and_refuses_invalid_fields():
    expected = "hash:" + hashlib.sha256(b'["origin","scenario","ban"]').hexdigest()
    assert run("decision_cache", 'emit(lib.identity({id=json.null, origin="origin",scenario="scenario",type="ban"}))') == expected
    for invalid in (True, "x" * 513):
        assert run("decision_cache", f"emit(lib.identity({{origin={to_lua(invalid)}}}))") is None


def test_cache_ban_priority_replacement_deletion_expiry_and_evidence():
    out = run(
        "decision_cache",
        r"""
CACHE.data.v3_generation='1:B'
local s=lib.new(CACHE,META)
assert(s.update('ip',{id='one',duration='30s',value='192.0.2.1',origin='test'},'captcha',30))
assert(s.update('ip',{id='two',duration='10s',scenario=string.rep('x',600)},'ban',10))
local ban,e=s.get('ip')
assert(ban=='ban' and #e.decisions==2 and e.metadata_available)
assert(e.matched_target=='192.0.2.1' and #e.decisions[2].scenario==512)
assert(e.decisions[1].generation==nil and e.decisions[1].expires_at==1030)
assert(CACHE.ttls['v2_decisions_B|ip']==30)
assert(s.update('ip',{id='two',duration='20s'},'captcha',20))
local replacement, evidence=s.get('ip')
assert(replacement=='captcha' and #evidence.decisions==2)
assert(s.update('ip',{id='one'},nil,nil,true))
assert(META:get('v2_evidence_B|ip|one')==nil)
NOW=1020
assert(s.get('ip')==nil)
assert(s.update('ip',{id='two'},nil,nil,true))
emit({empty=CACHE:get('v2_decisions_B|ip')==nil,source=e.source,captured=e.captured_at})
""",
    )
    assert out == {"empty": True, "source": "lapi", "captured": 1000}


def test_cache_bad_records_and_generation_mismatch_are_ignored():
    assert (
        run(
            "decision_cache",
            r"""
local s=lib.new(CACHE,META)
for _,raw in ipairs({'broken','42','{}','{"generation":"old","records":[]}','{"generation":"0:A","records":true}'}) do
    CACHE.data['v2_decisions_A|ip']=raw
    assert(s.get('ip')==nil)
end
local ok,err=s.update('ip',{id=false},'ban',10)
emit({invalid=ok==nil,error=err})
""",
        )
        == {"invalid": True, "error": "Invalid decision identity"}
    )


def test_cache_optional_metadata_failure_never_evicts_decision():
    assert (
        run(
            "decision_cache",
            r"""
local s=lib.new(CACHE,META)
META.full=true
META.data['v2_evidence_A|ip|1']='stale'
assert(s.update('ip',{id=1,duration='10s'},'ban',10))
local remediation,e=s.get('ip')
assert(META:get('v2_evidence_A|ip|1')==nil)
assert(remediation=='ban' and not e.metadata_available and #e.decisions==0)
for _,raw in ipairs({'broken','42','{"generation":"old"}'}) do
    META.data['v2_evidence_A|ip|1']=raw
    local _,missing=s.get('ip'); assert(not missing.metadata_available)
end
CACHE.full=true
local ok,err=s.update('ip',{id=2,duration='10s'},'captcha',10,nil,'3:B')
emit({failed=ok==nil,error=err})
""",
        )
        == {"failed": True, "error": "no memory"}
    )


def test_cache_without_metadata_and_explicit_generation_clear():
    assert (
        run(
            "decision_cache",
            r"""
local s=lib.new(CACHE)
assert(s.update('ip',{id=1},'ban',10))
local r,e=s.get('ip'); assert(r=='ban' and not e.metadata_available)
s.clear('ip'); assert(s.get('ip')==nil)
assert(s.update('ip',{id=2},'captcha',20,nil,'2:B'))
assert(s.get('ip')==nil)
CACHE.data.v3_generation='2:B'
local switched=s.get('ip')
s.clear('ip')
emit({switched=switched,empty=s.get('ip')==nil})
""",
        )
        == {"switched": "captcha", "empty": True}
    )


def test_cache_legacy_read_clear_and_retirement_preserve_active_generation():
    assert (
        run(
            "decision_cache",
            r"""
CACHE.data.v2_generation=7
CACHE.data['v2_decisions_7|ip']=json.encode({{'one',1010,'ban'}})
META.data['v2_evidence_7|ip|one']=json.encode({value='192.0.2.2'})
CACHE.data['v2_decisions_6|old']='obsolete'
META.data['v2_evidence_6|old|one']='obsolete'
CACHE.data['unrelated']='keep'
local s=lib.new(CACHE,META)
local r,e=s.get('ip')
assert(r=='ban' and e.metadata_available and e.matched_target=='192.0.2.2')
s.retire_legacy()
assert(CACHE:get('v2_decisions_6|old')==nil and META:get('v2_evidence_6|old|one')==nil)
assert(CACHE:get('v2_decisions_7|ip')~=nil and CACHE:get('unrelated')=='keep')
s.retire_legacy()
s.clear('ip'); assert(s.get('ip')==nil)
CACHE.data.v2_generation=nil; s.retire_legacy()
emit(true)
""",
        )
        is True
    )


@pytest.mark.parametrize(("flags", "source", "state"), [(None, 0, 0), (0, 0, 0), (5, 1, 4), (10, 2, 8), (15, 1, 4)])
def test_flags_source_and_state_priority(flags, source, state):
    out = run("flag", f"local a,b,e=lib.GetFlags({to_lua(flags)}); emit({{a,b,e}})")
    assert out == [source, state, ""]


@pytest.mark.parametrize(
    ("setup", "callback", "expected", "closed"),
    [
        ("", "return false", [True, None], 1),
        ("LOCK.open_fail=true", "", [None, "Stream lock unavailable"], 0),
        ("LOCK.fd=-1", "", [None, "busy"], 1),
        ("LOCK.result=-1", "", [None, "busy"], 1),
        ("LOCK.result=-1; LOCK.errno=13", "", [None, "Stream lock unavailable"], 1),
        ("", "error('callback failed')", [None, "Stream synchronization failed"], 1),
    ],
)
def test_stream_lock_returns_errors_and_always_closes_open_handle(setup, callback, expected, closed):
    out = run(
        "stream_lock",
        f"""
{setup}
local called=false
local ok,err=lib.run('/unused',function() called=true; {callback} end)
emit({{ok=ok or json.null,err=err or json.null,closed=CLOSED,gc=GC_ATTACHED,called=called}})
""",
    )
    assert [out["ok"], out["err"]] == expected
    assert out["closed"] == closed
    assert out["gc"] is False
    assert out["called"] == (setup == "")


def test_template_replaces_all_known_variables_and_retains_unknown():
    assert run("template", "emit(lib.compile('{{name}} / {{name}} {{other}}', {name='hello'}))") == "hello / hello {{other}}"
    assert run("template", "emit(lib.compile('unchanged', {}))") == "unchanged"


def test_utils_file_string_table_and_http_helpers(tmp_path):
    path = tmp_path / "page"
    path.write_text("hello\n")
    out = run(
        "utils",
        f"""
local path={to_lua(str(path))}
assert(lib.file_exist(path) and not lib.file_exist(path..'.absent') and lib.file_exist(nil)==nil)
assert(lib.read_file(path..'.absent')==nil)
assert(lib.starts_with('hello','he') and not lib.starts_with('hello','hi'))
assert(lib.ends_with('hello','lo') and lib.ends_with('hello','') and not lib.ends_with('hello','he'))
assert(lib.table_len({{a=1,b=false}})==2 and lib.table_len({{}})==0)
emit({{content=lib.read_file(path),codes=lib.HTTP_CODE}})
""",
    )
    assert out["content"] == "hello"
    assert out["codes"] == {str(n): n for n in (200, 202, 204, 301, 302, 400, 401, 403, 404, 405, 406, 444, 500)}


@pytest.mark.xfail(strict=True, reason="Bundled utils.read_file truncates last byte when file has no final newline")
def test_utils_read_file_preserves_content_without_final_newline(tmp_path):
    path = tmp_path / "page"
    path.write_text("hello")
    assert run("utils", f"emit(lib.read_file({to_lua(str(path))}))") == "hello"

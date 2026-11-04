"""Exercise complete utils.lua with OpenResty and storage boundaries stubbed."""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = BW_MODULES / "utils.lua"

PRELUDE = r"""
VARIABLES = {global = {MULTISITE='yes', SECURITY_MODE='block', DENY_HTTP_STATUS='403',
    SESSIONS_DOMAIN='', SESSIONS_CHECK_IP='yes', SESSIONS_CHECK_USER_AGENT='yes'},
    svc = {SECURITY_MODE='detect'}}
STORE, STARTS, QUEUE, KILLED = {}, {}, {}, {}
ngx.HTTP_FORBIDDEN = 403
ngx.ctx = {bw={}}
ngx.var = {server_name='svc', remote_addr='192.0.2.1'}
ngx.thread = {kill=function(thread)
    KILLED[#KILLED+1] = thread
    if thread == 'dead' then return nil, 'already dead' end
    return true
end}
ngx.re = {match=function(subject, regex, options)
    REGEX_CALLS = (REGEX_CALLS or 0) + 1
    REGEX_OPTIONS = options
    if regex == '[bad\n' then return nil, 'compile error' end
    if regex == 'runtime' and subject ~= '' then return nil, 'match limit' end
    return subject == regex and {subject} or nil
end}
os.time = function() return NOW end
package.loaded['bunkerweb.banlease'] = {}
package.loaded['bunkerweb.mmdb'] = {}
package.loaded['resty.ipmatcher'] = {}
package.loaded['resty.dns.resolver'] = {}
package.loaded['resty.random'] = {bytes=function(count, strong)
    assert(count == 1 and strong == true)
    local byte = table.remove(RANDOM_BYTES, 1)
    return string.char(byte)
end}
package.loaded['bunkerweb.datastore'] = {new=function() return {get=function(_, key)
    if key == 'variables' then return VARIABLES, 'store unavailable' end
    return STORE[key], 'not found'
end} end}
package.loaded['bunkerweb.cachestore'] = {new=function(_, redis, ctx, pool)
    return {redis=redis, ctx=ctx, pool=pool}
end}
package.loaded['resty.session'] = {start=function(config)
    STARTS[#STARTS+1] = config or false
    local entry = table.remove(QUEUE, 1)
    assert(entry, 'unexpected session start')
    return entry.session, entry.err, entry.exists, entry.refreshed
end}
local function new_session(metadata)
    local s = {metadata=metadata}
    function s:get(key) assert(key == 'metadata') return self.metadata end
    function s:set(key, value) assert(key == 'metadata') self.metadata=value end
    function s:clear_request_cookie() self.cookie_cleared=true end
    function s:destroy()
        assert(self.cookie_cleared, 'stale cookie must be cleared before destroy')
        self.destroyed=true
        return not DESTROY_ERROR, DESTROY_ERROR
    end
    function s:save() self.saved=true return not SAVE_ERROR, SAVE_ERROR end
    return s
end
local utils = dofile(MODULE)
"""


def check(body, *, subsystem="http", **env):
    assert run_core(MODULE, PRELUDE + body + "\nemit(true)", subsystem=subsystem, **env) is True


def test_detect_mode_survives_reason_roundtrip_and_service_precedence():
    check(r"""
local ctx = {bw={server_name='svc', remote_addr='192.0.2.1'}}
assert(utils.get_security_mode(ctx) == 'detect', 'service detect mode must survive')
assert(utils.get_security_mode({bw={server_name='other'}}) == 'block')
ngx.var.reason, ngx.var.reason_data = '', ''
local data = {rule='942100'}
utils.set_reason('modsecurity', data, ctx)
assert(ctx.bw.security_mode == 'detect', 'set_reason must preserve detect mode')
local reason, result, mode = utils.get_reason(ctx)
assert(reason == 'modsecurity' and result == data and mode == 'detect')
assert(ngx.var.reason == 'modsecurity' and json.decode(ngx.var.reason_data).rule == '942100')
utils.set_reason('blacklist', nil, nil)
assert(ngx.var.reason == 'blacklist' and next(json.decode(ngx.var.reason_data)) == nil)
utils.set_reason(nil, nil, ctx, 'detect')
assert(ctx.bw.reason == 'unknown' and next(ctx.bw.reason_data) == nil and ctx.bw.security_mode == 'detect')
ngx.var.reason, ngx.var.reason_data = nil, nil
utils.set_reason('dnsbl', data, {}, 'detect')
assert(ngx.var.reason == nil)
VARIABLES = nil
assert(utils.get_security_mode(ctx) == 'block')
""")


def test_reason_variable_json_errors_and_context_defaults():
    check(r"""
local ctx = {bw={reason='country', security_mode='detect'}}
local reason, data, mode = utils.get_reason(ctx)
assert(reason == 'country' and next(data) == nil and mode == 'detect')
ngx.var.reason, ngx.var.reason_data = 'limit', '{"count":3}'
reason, data, mode = utils.get_reason()
assert(reason == 'limit' and data.count == 3 and mode == 'detect')
for _, encoded in ipairs({'{broken', ''}) do
    ngx.var.reason_data = encoded
    reason, data = utils.get_reason({})
    assert(reason == 'limit' and next(data) == nil)
end
ngx.var.reason_data = nil
reason, data = utils.get_reason()
assert(reason == 'limit' and next(data) == nil)
""")


def test_modsecurity_metadata_is_bounded_without_splitting_utf8():
    check(r"""
ngx.var.modsecurity_reason = 'modsecurity'
ngx.var.modsecurity_rules = ' 942100 941100'
ngx.var.modsecurity_unique_id = 'literal.*'
local sep = '|literal.*|'
local long = string.rep('a', 511) .. '\195\169' .. string.rep('z', 20)
local items = {long, string.rep('b', 513), string.rep('c', 512), '', 'short'}
for i=1,40 do items[#items+1] = tostring(i) end
ngx.var.modsecurity_msgs = sep .. table.concat(items, sep)
ngx.var.modsecurity_matched_vars = 'first' .. sep .. 'last'
ngx.var.modsecurity_matched_var_names = 'none'
ngx.var.modsecurity_anomaly_score = '5'
local reason, data, mode = utils.get_reason()
assert(reason == 'modsecurity' and mode == 'detect')
assert(#data.ids == 2 and data.ids[1] == '942100' and data.ids[2] == '941100')
assert(#data.msgs == 32 and data.msgs[1] == string.rep('a',511) .. '...')
assert(data.msgs[2] == string.rep('b',512) .. '...' and data.msgs[3] == string.rep('c',512))
assert(data.msgs[4] == 'short' and data.msgs[32] == '28')
assert(#data.matched_vars == 2 and data.matched_vars[2] == 'last')
assert(data.matched_var_names == nil and data.anomaly_score[1] == '5')
ngx.var.modsecurity_rules = 'none'
ngx.var.modsecurity_unique_id = nil
reason, data = utils.get_reason()
assert(reason == 'modsecurity' and next(data) == nil)
for _, id in ipairs({'200002','200003','200004','200005','200006'}) do
    ngx.var.modsecurity_reason = 'modsecurity-body-' .. id
    reason, data = utils.get_reason()
    assert(reason == 'modsecurity-body' and #data.ids == 1 and data.ids[1] == id)
end
""")


def test_reason_ban_and_upstream_denial_precedence():
    check(r"""
STORE['bans_ip_192.0.2.1'] = '{"reason":"blacklist"}'
local reason, data, mode = utils.get_reason({bw={remote_addr='192.0.2.1', server_name='svc'}})
assert(reason == 'blacklist' and next(data) == nil and mode == 'detect')
STORE['bans_ip_192.0.2.1'] = 'legacy ban'
assert(utils.get_reason() == 'legacy ban')
STORE = {}
ngx.status = 403
assert(utils.get_reason() == 'unknown')
ngx.var.upstream_status = '502, 403 '
assert(utils.get_reason() == nil)
ngx.var.upstream_status = '403, 200'
assert(utils.get_reason() == 'unknown')
ngx.status = 200
assert(utils.get_reason() == nil)
""")


@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_deny_status_fallbacks_and_configured_status(subsystem):
    check(
        r"""
local expected = SUBSYSTEM == 'http' and 403 or 444
assert(utils.get_deny_status() == expected)
VARIABLES.global.DENY_HTTP_STATUS = '429'
assert(utils.get_deny_status() == (SUBSYSTEM == 'http' and 429 or 444))
VARIABLES.global.DENY_HTTP_STATUS = 'invalid'
assert(utils.get_deny_status() == expected)
VARIABLES = nil
assert(utils.get_deny_status() == expected)
if SUBSYSTEM == 'http' then assert(LOGS[1][2]:find('store unavailable',1,true)) end
""",
        subsystem=subsystem,
    )


@pytest.mark.parametrize(
    "no_numbers,alphabet,expected",
    [(False, None, "09AZaz07"), (True, None, "AJKjkJKv"), (False, "xy", "xyxyxyxy")],
)
def test_random_output_uses_selected_alphabet(no_numbers, alphabet, expected):
    check(
        "assert(utils.rand(8, NO_NUMBERS, ALPHABET) == EXPECTED); assert(utils.rand(0) == '')",
        NO_NUMBERS=no_numbers,
        ALPHABET=alphabet,
        EXPECTED=expected,
        RANDOM_BYTES=[0, 9, 10, 35, 36, 61, 62, 255],
    )


def test_session_create_cache_domain_and_save_outcomes():
    check(r"""
VARIABLES.svc.SESSIONS_DOMAIN = '.svc.example'
local s = new_session()
QUEUE = {{session=s}}
local ctx = {bw={server_name='svc', remote_addr='192.0.2.1'}}
assert(utils.save_session(ctx) == true)
local ok, msg = utils.save_session(ctx)
assert(ok and msg == 'no session')
assert(utils.get_session(ctx) == s and STARTS[1].cookie_domain == '.svc.example')
assert(s.metadata.IP == '192.0.2.1' and s.metadata.USER_AGENT == '' and ctx.bw.sessions_updated)
assert(utils.get_session(ctx) == s and #STARTS == 1)
ok, msg = utils.save_session(ctx)
assert(ok and msg == 'session saved' and s.saved)
SAVE_ERROR = 'write failed'
ok, msg = utils.save_session(ctx)
assert(not ok and msg == 'write failed')
ctx.bw.sessions_updated = nil
s.saved = nil
ok, msg = utils.save_session(ctx)
assert(ok and msg == 'session not updated' and s.saved == nil)
""")


def test_session_existing_refresh_warning_and_missing_settings():
    check(r"""
local s = new_session({IP='192.0.2.1',USER_AGENT='curl'})
QUEUE = {{session=s, err='refresh warning', exists=true, refreshed=true}}
local ctx = {bw={server_name='svc', remote_addr='192.0.2.1', http_user_agent='curl'}}
assert(utils.get_session(ctx) == s and STARTS[1] == false)
assert(not ctx.bw.sessions_updated and not s.destroyed)
assert(LOGS[1][1] == 'WARN' and LOGS[1][2]:find('refresh warning',1,true))
assert(LOGS[3][2] == '[UTILS] existing session refreshed')
VARIABLES = nil
QUEUE = {{session=new_session({IP='192.0.2.1',USER_AGENT='curl'}),exists=true}}
ctx.bw.sessions_session = nil
assert(utils.get_session(ctx) and STARTS[2] == false)
local messages = table.concat((function()
    local t={} for _, log in ipairs(LOGS) do t[#t+1]=log[2] end return t
end)(), '\n')
assert(messages:find('SESSIONS_DOMAIN',1,true) and messages:find('SESSIONS_CHECK_IP',1,true))
assert(messages:find('SESSIONS_CHECK_USER_AGENT',1,true))
""")


@pytest.mark.parametrize("check_name", ["IP", "USER_AGENT"])
def test_session_failed_check_discards_stale_cookie_and_reopens(check_name):
    check(
        r"""
VARIABLES.global['SESSIONS_CHECK_' .. (CHECK_NAME == 'IP' and 'USER_AGENT' or 'IP')] = 'no'
local metadata = {IP='192.0.2.1', USER_AGENT='curl'}
metadata[CHECK_NAME] = 'stale'
local stale, fresh = new_session(metadata), new_session()
QUEUE = {{session=stale,exists=true}, {session=fresh}}
local ctx = {bw={server_name='svc',remote_addr='192.0.2.1',http_user_agent='curl'}}
assert(utils.get_session(ctx) == fresh)
assert(stale.cookie_cleared and stale.destroyed and ctx.bw.sessions_session == fresh)
assert(fresh.metadata.IP == '192.0.2.1' and fresh.metadata.USER_AGENT == 'curl')
assert(ctx.bw.sessions_updated and #STARTS == 2)
""",
        CHECK_NAME=check_name,
    )


def test_session_open_and_destroy_errors_return_to_caller():
    check(r"""
local ctx = {bw={server_name='svc',remote_addr='192.0.2.1'}}
QUEUE = {{err='cannot open'}}
local s, err = utils.get_session(ctx)
assert(s == nil and err == 'cannot open' and not ctx.bw.sessions_session)
DESTROY_ERROR = 'cannot destroy'
QUEUE = {{session=new_session({IP='stale',USER_AGENT=''}),exists=true}}
s, err = utils.get_session(ctx)
assert(s == nil and err == 'cannot destroy' and not ctx.bw.sessions_session)
QUEUE = {{session=new_session(),exists=true}}
assert(utils.get_session(ctx) and not ctx.bw.sessions_updated)
""")


@pytest.mark.parametrize("setting,expected", [("yes", True), ("no", False), (None, False)])
def test_cachestore_redis_and_pool_configuration(setting, expected):
    check(
        r"""
VARIABLES.global.USE_REDIS = SETTING
local ctx = {bw={}}
local store = utils.new_cachestore(ctx)
assert(store.redis == EXPECTED and store.ctx == ctx and store.pool == true)
assert(utils.new_cachestore(nil, false).pool == false)
assert(utils.new_cachestore(nil, true).pool == true)
if SETTING == nil then assert(LOGS[1][2]:find('USE_REDIS',1,true)) end
""",
        SETTING=setting,
        EXPECTED=expected,
    )


def test_regex_compile_cache_flags_relog_and_runtime_errors():
    check(r"""
assert(utils.regex_match('match', 'match')[1] == 'match' and REGEX_OPTIONS == 'o')
assert(utils.regex_match('miss', 'match', 'i') == nil and REGEX_OPTIONS == 'oi')
assert(utils.regex_match('x', '[bad\n', nil, 'SETTING') == nil)
local calls = REGEX_CALLS
assert(#LOGS == 1 and LOGS[1][2]:find('SETTING on server svc',1,true))
assert(not LOGS[1][2]:find('\n',1,true) and LOGS[1][2]:find('\\n',1,true))
assert(utils.regex_match('x', '[bad\n') == nil and REGEX_CALLS == calls and #LOGS == 1)
NOW = NOW + 3599
utils.regex_match('x', '[bad\n')
assert(#LOGS == 1)
NOW = NOW + 1
utils.regex_match('x', '[bad\n')
assert(#LOGS == 2 and REGEX_CALLS == calls)
utils.regex_match('x', '[bad\n', 'i')
assert(REGEX_CALLS == calls + 2)
calls = REGEX_CALLS
assert(utils.regex_match('x', 'runtime') == nil)
assert(utils.regex_match('y', 'runtime') == nil)
assert(REGEX_CALLS == calls + 4)
setmetatable(ngx.var, {__index=function() error('var unavailable') end})
ngx.var.server_name = nil
utils.regex_match('x', '[bad\n', 'j')
assert(LOGS[#LOGS][2]:find('an unidentified setting on server -',1,true))
""")


def test_phases_cosockets_error_classifiers_threads_and_context():
    check(r"""
local phases = utils.get_phases()
assert(table.concat(phases, ',') == 'init,init_worker,set,rewrite,access,content,ssl_client_hello,ssl_client_hello_default,ssl_certificate_default,ssl_certificate,header,log,preread,log_stream,log_default,timer,init_workers')
local allowed = {timer=true,rewrite=true,server_rewrite=true,access=true,content=true,
    ssl_cert=true,ssl_client_hello=true,ssl_session_fetch=true,preread=true}
for phase in pairs(allowed) do PHASE=phase assert(utils.is_cosocket_available()) end
for _, phase in ipairs({'init','init_worker','header_filter','body_filter','log','set'}) do
    PHASE=phase assert(not utils.is_cosocket_available())
end
for _, err in ipairs({'closed','socket broken pipe','connection reset by peer'}) do assert(utils.is_connection_error(err)) end
assert(utils.is_connection_error(nil) == nil and utils.is_connection_error('timeout') == nil)
assert(utils.is_oom_error('Redis OOM command') == true)
assert(utils.is_oom_error('room') == false and utils.is_oom_error(nil) == nil)
utils.kill_all_threads({'live','dead','last'})
assert(table.concat(KILLED, ',') == 'live,dead,last')
assert(LOGS[1][2] == '[UTILS] error while killing thread : already dead')
ngx.ctx.bw.answer = 42
assert(utils.get_ctx_obj('answer') == 42)
assert(utils.get_ctx_obj('answer', {bw={answer=false}}) == false)
assert(utils.get_ctx_obj('missing', {}) == nil)
ngx.ctx = nil
assert(utils.get_ctx_obj('answer') == nil)
local object = {}
local result = utils.deduplicate_list({'b','a','b',false,false,object,object})
assert(#result == 4 and result[1] == 'b' and result[2] == 'a' and result[3] == false and result[4] == object)
assert(#utils.deduplicate_list({}) == 0)
""")


def test_read_files_preserves_order_empty_content_and_errors(tmp_path):
    first, empty = tmp_path / "first.txt", tmp_path / "empty.txt"
    first.write_text("first\nsecond\n")
    empty.write_text("")
    check(
        r"""
local ok, data = utils.read_files({FIRST, EMPTY})
assert(ok and #data == 2 and data[1] == 'first\nsecond\n' and data[2] == '')
ok, data = utils.read_files({})
assert(ok and #data == 0)
ok, data = utils.read_files({FIRST, MISSING})
assert(ok == false and data:find(MISSING .. ' = ',1,true) == 1)
""",
        FIRST=str(first),
        EMPTY=str(empty),
        MISSING=str(tmp_path / "missing.txt"),
    )

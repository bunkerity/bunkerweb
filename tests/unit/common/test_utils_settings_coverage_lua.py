"""Load complete utils.lua; exercise settings, header rules and whitelist decisions."""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = BW_MODULES / "utils.lua"

PRELUDE = r"""
VARIABLES = { global = { MULTISITE = 'yes', SERVER_NAME = 'svc', USE_WHITELIST = 'yes' }, svc = {} }
STORE, HEADERS, CACHE = {}, {}, {}
ngx.var.server_name = 'svc'
ngx.thread = {kill = function() end}
ngx.req = SUBSYSTEM == 'http' and {get_headers = function(cap) HEADER_CAP = cap return HEADERS end} or nil
ngx.re = {match = function(subject, pattern)
    if pattern == '[secret' then return nil, 'invalid pattern' end
    if subject ~= '' and pattern == '^runtime$' then return nil, 'match failed' end
    return string.match(subject, pattern)
end}
package.loaded['bunkerweb.datastore'] = {new = function() return {get = function(_, key)
    if key == 'variables' then return VARIABLES, 'store unavailable' end
    return STORE[key], 'not found'
end} end}
package.loaded['bunkerweb.banlease'] = {}
package.loaded['bunkerweb.mmdb'] = {}
package.loaded['resty.random'] = {}
package.loaded['resty.dns.resolver'] = {}
package.loaded['resty.session'] = {}
package.loaded['resty.ipmatcher'] = {new = function(networks)
    if MATCHER_ERROR then return nil, MATCHER_ERROR end
    return {match = function(_, ip)
        if MATCH_ERROR then return nil, MATCH_ERROR end
        for _, network in ipairs(networks) do if network == ip then return true end end
        return false
    end}
end}
package.loaded['bunkerweb.cachestore'] = {new = function()
    return {
        get = function(_, key) return not CACHE_ERROR, CACHE_ERROR or CACHE[key] end,
        get_local_nolock = function(_, key) return not CACHE_ERROR, CACHE_ERROR or CACHE[key] end,
    }
end}
local utils = dofile(MODULE)
local function result(fn, expected, message)
    local value, err = fn()
    assert(value == expected, tostring(value) .. ' ~= ' .. tostring(expected))
    if message then assert(err == message, tostring(err)) end
end
"""


def check(body, *, subsystem="http"):
    assert run_core(MODULE, PRELUDE + body + "\nemit(true)", subsystem=subsystem) is True


def test_settings_service_precedence_and_global_fallback():
    check(r"""
VARIABLES.global.MODE = 'global'
VARIABLES.svc.MODE = 'service'
VARIABLES.other = { MODE = '' }
result(function() return utils.get_variable('MODE') end, 'service', 'success')
result(function() return utils.get_variable('MODE', false) end, 'global', 'success')
result(function() return utils.get_variable('MODE', true, {bw={server_name='other'}}) end, '', 'success')
VARIABLES.svc.MODE = nil
result(function() return utils.get_variable('MODE') end, 'global', 'success')
ngx.var.server_name = 'absent'
result(function() return utils.get_variable('MODE') end, 'global', 'success')
result(function() return utils.get_variable('MISSING') end, nil, 'not found')
VARIABLES.global.MULTISITE = 'no'
result(function() return utils.get_variable('MODE') end, 'global', 'success')
""")


def test_has_variable_effective_values_and_empty_server_list():
    check(r"""
VARIABLES.global.MODE = 'yes'
result(function() return utils.has_variable('MODE', 'yes') end, true, 'success')
VARIABLES.svc.MODE = 'no'
result(function() return utils.has_variable('MODE', 'yes') end, false, 'success')
VARIABLES.global.SERVER_NAME = 'svc other'
VARIABLES.other = {MODE='yes'}
result(function() return utils.has_variable('MODE', 'yes') end, true, 'success')
VARIABLES.global.SERVER_NAME = ''
result(function() return utils.has_variable('MODE', 'yes') end, true, 'success')
result(function() return utils.has_not_variable('MODE', 'no') end, true, 'success')
result(function() return utils.has_not_variable('MODE', 'yes') end, false, 'success')
VARIABLES.global.SERVER_NAME = 'svc'
VARIABLES.svc.MODE = 'value'
result(function() return utils.has_not_variable('MODE', 'value') end, false, 'success')
VARIABLES.svc.MODE = 'different'
result(function() return utils.has_not_variable('MODE', 'value') end, true, 'success')
""")


def test_has_not_variable_compares_requested_value():
    check("VARIABLES.svc.MODE = 'yes'; assert(utils.has_not_variable('MODE', 'yes') == false)")


@pytest.mark.parametrize("function", ["get_variable", "has_variable", "has_not_variable"])
def test_settings_store_errors_return_diagnostics(function):
    check(f"""
VARIABLES = nil
local value, err = utils.{function}('MODE', false)
assert(value == nil and err:find('store unavailable', 1, true))
""")


def test_multiple_variables_store_error_returns_diagnostic():
    check("VARIABLES = nil; local value, err = utils.get_multiple_variables({'MODE'}); assert(value == nil and err)")


def test_multiple_variables_filters_exact_names_and_numeric_suffixes():
    check(r"""
VARIABLES.global = {MODE='base', MODE_1='one', MODE2='two', MODE_='empty', MODE_bad='bad', XMODE='bad', MODE_1X='bad'}
VARIABLES.svc = {OTHER='other', MODE_20='twenty'}
local values = utils.get_multiple_variables({'MODE'})
assert(values.global.MODE == 'base' and values.global.MODE_1 == 'one' and values.global.MODE2 == 'two')
assert(values.global.MODE_ == 'empty' and values.global.MODE_bad == nil and values.global.XMODE == nil)
assert(values.global.MODE_1X == nil and values.svc.MODE_20 == 'twenty' and values.svc.OTHER == nil)
""")


def test_header_rules_inherit_override_disable_and_redact_invalid_regex():
    check(r"""
VARIABLES.global = {H_NAME='X-Token', H_VALUE='^token$', H_NAME_1='X-Present', H_VALUE_1='', H_NAME_2='X-Bad', H_VALUE_2='[secret'}
VARIABLES.svc = {H_NAME='', H_NAME_1='X-Service', H_VALUE_1='^service$'}
local rules = utils.get_header_rules('H')
local global = {}
for _, rule in ipairs(rules.global) do global[rule.name] = rule.value or false end
assert(global['x-token'] == '^token$' and global['x-present'] == false and global['x-bad'] == nil)
assert(#rules.svc == 1 and rules.svc[1].name == 'x-service' and rules.svc[1].value == '^service$')
assert(#LOGS == 2)
for _, log in ipairs(LOGS) do
    assert(log[2]:find('not a valid regex', 1, true) and not log[2]:find('secret', 1, true))
end
assert(utils.pick_header_rules(rules, 'svc') == rules.svc)
assert(utils.pick_header_rules(rules, 'absent') == rules.global)
assert(utils.pick_header_rules(rules) == rules.global)
rules.empty = {}
assert(#utils.pick_header_rules(rules, 'empty') == 0)
assert(#utils.pick_header_rules(nil, 'svc') == 0)
assert(#utils.pick_header_rules({}, 'svc') == 0)
""")


def test_header_rules_propagate_collection_error():
    check(
        "utils.get_multiple_variables = function() return nil, 'unavailable' end; "
        "result(function() return utils.get_header_rules('H') end, nil, 'unavailable')"
    )


def test_headers_match_repeated_values_presence_and_cache_with_configured_cap():
    check(r"""
VARIABLES.global.MAX_HEADERS = '250'
HEADERS = {['x-token']={'wrong', 'token'}, ['x-empty']=''}
local ctx = {bw={}}
assert(utils.match_header_rules(ctx, {{name='missing'}, {name='x-token', value='^token$'}}) == 'x-token')
assert(HEADER_CAP == 250)
HEADERS = {}
assert(utils.match_header_rules(ctx, {{name='x-empty'}}) == 'x-empty')
assert(utils.match_header_rules(ctx, {{name='x-token', value='^wrong$'}}) == 'x-token')
assert(utils.match_header_rules(ctx, {{name='x-token', value='^absent$'}}) == nil)
assert(utils.match_header_rules(ctx, nil) == nil and utils.match_header_rules(ctx, {}) == nil)
VARIABLES.global.MAX_HEADERS = 'invalid'
HEADERS = {['x-token']='token'}
assert(utils.match_header_rules({bw={}}, {{name='x-token', value='^token$'}}) == 'x-token')
assert(HEADER_CAP == 100)
HEADERS = {['x-token']='runtime'}
assert(utils.match_header_rules({bw={}}, {{name='x-token', value='^runtime$'}}, 'whitelist') == nil)
assert(LOGS[1][2]:find('error while matching whitelist on header x-token : match failed', 1, true))
assert(utils.match_header_rules({bw={}}, {{name='x-token', value='^runtime$'}}) == nil)
assert(LOGS[2][2]:find('error while matching header rule on header x-token : match failed', 1, true))
""")


def test_stream_has_no_request_headers():
    check("assert(utils.match_header_rules({bw={}}, {{name='x-token'}}) == nil)", subsystem="stream")


def test_request_whitelist_context_overrides_ngx_variable():
    check(r"""
ngx.var.is_whitelisted = 'yes'
assert(utils.is_whitelisted({bw={is_whitelisted='no'}}) == false)
assert(utils.is_whitelisted({bw={is_whitelisted='yes'}}) == true)
assert(utils.is_whitelisted(nil) == true)
ngx.var.is_whitelisted = 'no'
assert(utils.is_whitelisted({bw={}}) == false and utils.is_whitelisted({}) == false)
ngx.var.is_whitelisted = nil
assert(utils.is_whitelisted(nil) == false)
""")


@pytest.mark.parametrize("local_only", [False, True])
def test_ip_whitelist_enabled_scope_cache_and_network_verdicts(local_only):
    check(r"""
local opts = {local_only=LOCAL_ONLY}
local function lookup() return utils.is_ip_whitelisted('192.0.2.1', 'svc', opts) end
STORE.plugin_whitelist_lists_svc = {IP={'192.0.2.1'}}
result(lookup, true, 'ip')
VARIABLES.svc.USE_WHITELIST = 'no'
result(lookup, false, 'ok')
VARIABLES.svc.USE_WHITELIST = 'yes'
CACHE['plugin_whitelist_svcip192.0.2.1'] = 'cached reason'
result(lookup, true, 'cached reason')
CACHE['plugin_whitelist_svcip192.0.2.1'] = 'ok'
result(lookup, false, 'ok')
CACHE = {}
STORE.plugin_whitelist_lists_svc = {IP={'192.0.2.2'}}
result(lookup, false, 'ok')
STORE.plugin_whitelist_lists_svc = {IP={}}
result(lookup, false, 'ok')
STORE.plugin_whitelist_lists_svc = {}
result(lookup, false, 'ok')
""".replace("LOCAL_ONLY", str(local_only).lower()))


@pytest.mark.parametrize(
    "failure,message",
    [
        ("VARIABLES = nil", "can't get variables : store unavailable"),
        ("CACHE_ERROR = 'cache down'", "can't check whitelist cache : cache down"),
        ("STORE = {}", "can't get whitelist lists : not found"),
        ("MATCHER_ERROR = 'bad networks'", "can't instantiate ipmatcher : bad networks"),
        ("MATCH_ERROR = 'bad ip'", "can't check ip : bad ip"),
    ],
)
def test_local_only_whitelist_errors_are_not_swallowed(failure, message):
    check(f"""
STORE.plugin_whitelist_lists_svc = {{IP={{'192.0.2.1'}}}}
{failure}
result(function() return utils.is_ip_whitelisted('192.0.2.1', 'svc', {{local_only=true}}) end, nil, {message!r})
""")


def test_default_service_fallback_and_global_whitelist():
    check(r"""
result(function() return utils.is_ip_whitelisted(nil) end, nil, 'ip is nil')
STORE.plugin_whitelist_lists_svc = {IP={'192.0.2.1'}}
result(function() return utils.is_ip_whitelisted('192.0.2.1') end, true, 'ip')
VARIABLES.global.SERVER_NAME = 'missing svc'
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_') end, true, 'ip')
result(function() return utils.is_ip_whitelisted('192.0.2.1', 'missing') end, true, 'ip')
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_', {local_only=true}) end,
       nil, "can't get whitelist lists : not found")
VARIABLES.global.SERVER_NAME = ''
VARIABLES.global.WHITELIST_IP = '192.0.2.2 192.0.2.1'
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_') end, true, 'ip')
result(function() return utils.is_ip_whitelisted('192.0.2.3', '_') end, false, 'ok')
MATCHER_ERROR = 'bad global networks'
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_') end, nil, "can't instantiate ipmatcher : bad global networks")
MATCHER_ERROR = nil
MATCH_ERROR = 'bad global ip'
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_') end, nil, "can't check ip : bad global ip")
MATCH_ERROR = nil
VARIABLES.global.WHITELIST_IP = '   '
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_') end, false, 'ok')
VARIABLES.global.WHITELIST_IP = '192.0.2.1'
VARIABLES.global.USE_WHITELIST = 'no'
result(function() return utils.is_ip_whitelisted('192.0.2.1', '_') end, false, 'ok')
""")

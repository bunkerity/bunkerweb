"""Unknown denials keep their mode; multipart reasons and matched data stay bounded."""

import re
import subprocess

import pytest

from test_modsecurity_body_reason_lua import LUA, PREAMBLE, ROOT, UTILS_LUA, needs_lua


def run(body):
    text = UTILS_LUA.read_text()
    start = text.find("local REASON_MAX_ITEM_SIZE")
    if start < 0:
        start = text.index("utils.get_reason = function(ctx)")
    end = text.index("\nutils.set_reason =", start)
    result = subprocess.run([str(LUA), "-"], input=PREAMBLE + text[start:end] + body, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_lua
@pytest.mark.parametrize("mode", ["detect", "block"])
def test_unknown_denial_keeps_security_mode(mode):
    run(f"""
ngx.status = 403
local reason, data, mode = utils.get_reason({{bw={{security_mode='{mode}', remote_addr='203.0.113.1'}}}})
assert(reason == 'unknown' and mode == '{mode}')
VAR.upstream_status = '502, 403'
assert(utils.get_reason({{bw={{remote_addr='203.0.113.1'}}}}) == nil)
""")


@needs_lua
@pytest.mark.parametrize("rule", range(200002, 200007))
def test_multipart_rules_report_their_id(rule):
    run(f"""
VAR.modsecurity_reason = 'modsecurity-body-{rule}'
local reason, data, mode = utils.get_reason({{bw={{security_mode='detect'}}}})
assert(reason == 'modsecurity-body' and #data.ids == 1 and data.ids[1] == '{rule}' and mode == 'detect')
""")


@needs_lua
def test_crs_data_is_bounded_without_splitting_utf8():
    run("""
VAR.modsecurity_reason = 'modsecurity'
VAR.modsecurity_unique_id = 'separator'
local long = string.rep('x', 511) .. string.char(0xc3, 0xa9) .. 'tail'
local value = '|separator|' .. string.rep(long .. '|separator|', 40) .. long
VAR.modsecurity_msgs, VAR.modsecurity_matched_vars, VAR.modsecurity_matched_var_names = value, value, value
local reason, data = utils.get_reason()
assert(reason == 'modsecurity')
for _, key in ipairs({'msgs', 'matched_vars', 'matched_var_names'}) do
    assert(#data[key] == 32)
    for _, item in ipairs(data[key]) do assert(item == string.rep('x', 511) .. '...') end
end
VAR.modsecurity_msgs = string.rep('a', 513)
local _, last = utils.get_reason()
assert(last.msgs[1] == string.rep('a', 512) .. '...')
VAR.modsecurity_msgs = string.rep('a', 512)
local _, exact = utils.get_reason()
assert(exact.msgs[1] == VAR.modsecurity_msgs)
""")


@needs_lua
def test_empty_matched_values_keep_their_position():
    run("""
VAR.modsecurity_reason = 'modsecurity'
VAR.modsecurity_unique_id = 'sep'
VAR.modsecurity_matched_var_names = '|sep|ARGS:a|sep|REQUEST_HEADERS:Authorization|sep|ARGS:b|sep|ARGS:c'
-- first, middle and last values are empty: a trailing separator is an empty last value
VAR.modsecurity_matched_vars = '|sep||sep|Bearer secret|sep||sep|'
local _, data = utils.get_reason()
assert(#data.matched_var_names == 4 and #data.matched_vars == 4, #data.matched_vars)
local expected = { '', 'Bearer secret', '', '' }
for i = 1, 4 do assert(data.matched_vars[i] == expected[i], i .. ' = ' .. tostring(data.matched_vars[i])) end
assert(data.matched_var_names[2] == 'REQUEST_HEADERS:Authorization')
""")


@needs_lua
def test_capped_matched_lists_stay_paired_with_empty_values():
    # 40 hits, the first value empty: dropping it shifted every later value one name early and,
    # with both lists cut at 32, left them the same length so no consumer could tell.
    run("""
VAR.modsecurity_reason = 'modsecurity'
VAR.modsecurity_unique_id = 'sep'
local names, values = {}, {}
for i = 1, 40 do
    names[i] = (i == 5) and 'REQUEST_HEADERS:Authorization' or ('ARGS:a' .. i)
    values[i] = (i == 1) and '' or (i == 5) and 'Bearer secret' or ('v' .. i)
end
VAR.modsecurity_matched_var_names = '|sep|' .. table.concat(names, '|sep|')
VAR.modsecurity_matched_vars = '|sep|' .. table.concat(values, '|sep|')
local _, data = utils.get_reason()
assert(#data.matched_var_names == 32 and #data.matched_vars == 32)
for i = 1, 32 do
    assert(data.matched_var_names[i] == names[i], 'name ' .. i)
    assert(data.matched_vars[i] == values[i], 'value ' .. i .. ' = ' .. tostring(data.matched_vars[i]))
end
assert(data.matched_var_names[5] == 'REQUEST_HEADERS:Authorization' and data.matched_vars[5] == 'Bearer secret')
""")


@pytest.mark.parametrize("kind", ["http/modsecurity-rules-global-crs", "server-http/modsecurity-rules"])
@pytest.mark.parametrize("rule", [200003, 200004, 200006])
def test_multipart_conf_sets_denial_reason(kind, rule):
    path = ROOT / f"src/common/core/modsecurity/confs/{kind}.conf.modsec"
    text = path.read_text()
    actions = re.search(rf'"id:\'{rule}\'.*?"', text, re.S)
    assert actions
    assert f"setvar:'tx.bunkerweb_reason=modsecurity-body-{rule}'" in actions.group()

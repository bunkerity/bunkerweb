"""Exercise the shipped get_ips function with resolver and cache boundaries stubbed."""

import re

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = module_path("UTILS", BW_MODULES / "utils.lua")


def lookup(answers, *, dual=True):
    source = re.search(r"^utils.get_ips = function.*?^end$", MODULE.read_text(), re.M | re.S)
    assert source
    return run_core(
        MODULE,
        """
local utils = {}
local encode, decode = json.encode, json.decode
local ERR = ngx.ERR
local logs = {}
local logger = {log = function(_, level, msg) logs[#logs + 1] = {level, msg} end}
local cache, writes, queries = {}, {}, {}
utils.new_cachestore = function()
    return {
        get = function(_, key) return true, cache[key] end,
        set = function(_, key, value, ttl)
            cache[key] = value
            writes[#writes + 1] = {key = key, value = decode(value), ttl = ttl}
            return true
        end,
    }
end
utils.get_resolvers = function() return {'127.0.0.1'} end
local resolver = {new = function()
    return {TYPE_A = 1, TYPE_AAAA = 28, query = function(_, name, options)
        queries[#queries + 1] = options.qtype
        local answer = ANSWERS[tostring(options.qtype)]
        if answer == false then return nil, 'timeout' end
        return answer
    end}
end}
"""
        + source.group(0)
        + f"""
local ips, err = utils.get_ips('bot.example.com', false, nil, true, {to_lua(dual)})
local first_writes = #writes
local second = utils.get_ips('bot.example.com', false, nil, true, {to_lua(dual)})
emit({{ips = ips, err = err, writes = writes, first_writes = first_writes,
    queries = queries, second = second, logs = logs}})
""",
        ANSWERS=answers,
    )


@pytest.mark.parametrize("dual", [False, True])
def test_total_resolver_failure_returns_false_and_retries_without_caching(dual):
    out = lookup({"1": False, "28": False}, dual=dual)
    assert out["ips"] is False, out
    assert out["second"] is False
    assert out["first_writes"] == 0
    assert not out["writes"]
    assert out["queries"] == ([28, 1, 28, 1] if dual else [1, 1])
    assert out["err"] == ('{"A":"timeout","AAAA":"timeout"} {}' if dual else '{"A":"timeout"} {}')


@pytest.mark.parametrize("dual", [False, True])
@pytest.mark.parametrize("errcode", [1, 2, 4, 5, 99])
@pytest.mark.parametrize("errstr", [None, "resolver failure"])
def test_error_rcodes_return_false_and_retry_without_caching(dual, errcode, errstr):
    answer = {"errcode": errcode}
    if errstr is not None:
        answer["errstr"] = errstr
    out = lookup({"1": answer, "28": answer}, dual=dual)
    assert out["ips"] is False, out
    assert out["second"] is False
    assert out["first_writes"] == 0
    assert not out["writes"]
    assert out["queries"] == ([28, 1, 28, 1] if dual else [1, 1])
    message = errstr or str(errcode)
    assert out["err"] == (f'{{}} {{"A":"{message}","AAAA":"{message}"}}' if dual else f'{{}} {{"A":"{message}"}}')
    for family in (["AAAA", "A"] if dual else ["A"]):
        assert sum(f"error while doing {family} DNS query for bot.example.com : {message}" in log for log in out["logs"]) == 2


@pytest.mark.parametrize("answer, expected", [({"errcode": 3, "errstr": "name error"}, {}), ([{"address": "192.0.2.1"}], ["192.0.2.1"])])
def test_servfail_on_other_family_does_not_prevent_caching_an_answer(answer, expected):
    out = lookup({"1": answer, "28": {"errcode": 2, "errstr": "server failure"}})
    assert out["ips"] == expected
    assert out["second"] == expected
    assert out["writes"] == [{"key": "dns_46_bot.example.com", "value": expected, "ttl": 3600}]
    assert out["first_writes"] == 1
    assert out["queries"] == [28, 1]
    assert '"AAAA":"server failure"' in out["err"]


@pytest.mark.parametrize(
    "answer, expected",
    [
        ([{"address": "192.0.2.1"}], ["192.0.2.1"]),
        ([], {}),
        ({"errcode": 3, "errstr": "name error"}, {}),
        ({"errcode": 3}, {}),
    ],
)
@pytest.mark.parametrize("other_fails", [False, True])
def test_valid_or_negative_answer_is_cached_even_when_other_family_fails(answer, expected, other_fails):
    out = lookup({"1": answer, "28": False if other_fails else []})
    assert out["ips"] == expected
    assert out["second"] == expected
    assert out["writes"] == [{"key": "dns_46_bot.example.com", "value": expected, "ttl": 3600}]
    assert out["first_writes"] == 1
    assert out["queries"] == [28, 1]
    assert ('"AAAA":"timeout"' in out["err"]) == other_fails
    assert ('"A":"name error"' in out["err"]) == (isinstance(answer, dict) and "errstr" in answer)

"""Badbehavior counts configured status tokens, never digit substrings (PR #4162)."""

import json

import pytest
from _t2_helpers import requires_lua, run_plugin_script

pytestmark = requires_lua

LISTS = ["400 401 403 404 405 429 444", "400", "  400   401  ", " ".join(str(code) for code in range(100, 600))]
SETTINGS = """
-- The shared JSON stand-in uses Lua 5.4 math.type; LuaJIT numbers are doubles.
math.type = math.type or function() return "float" end
VARIABLES = {
    USE_BAD_BEHAVIOR = "yes", BAD_BEHAVIOR_BAN_SCOPE = "service",
    BAD_BEHAVIOR_BAN_TIME = "3600", BAD_BEHAVIOR_COUNT_TIME = "60", BAD_BEHAVIOR_THRESHOLD = "10",
}
"""


@pytest.mark.parametrize("codes", LISTS, ids=["default", "single", "spaces", "all-codes"])
@pytest.mark.parametrize("status", [0, 4, 40, 400, 401, 404, 444, 499, 500])
def test_log_counts_only_listed_status_tokens(codes, status):
    out = run_plugin_script(
        "badbehavior",
        f"""
VARIABLES.BAD_BEHAVIOR_STATUS_CODES = {json.dumps(codes)}
ngx.status = {status}
local p = PLUGIN:new({{ bw = {{ remote_addr = "203.0.113.9", server_name = "app.example.com" }} }})
local result = p:log()
emit({{ ok = result.ret, msg = result.msg, queued = RPUSHES, metrics = METRICS }})
""",
        header=SETTINGS,
    )
    listed = str(status) in codes.split()
    assert out["ok"] is True
    assert out["msg"] == ("success" if listed else "not increasing counter")
    assert len(out["queued"]) == int(listed)
    if listed:
        queued = out["queued"][0]
        assert queued["key"] == "plugin_badbehavior_incr"
        assert json.loads(queued["value"])["status"] == str(status)
        assert out["metrics"][0] == {"kind": "counters", "key": f"status_{status}", "value": 1}
        assert out["metrics"][1]["value"]["status"] == str(status)
    else:
        assert len(out["metrics"]) == 0


def test_every_allowed_single_code_counts_itself_but_never_status_zero():
    out = run_plugin_script(
        "badbehavior",
        """
local p = PLUGIN:new({ bw = { remote_addr = "203.0.113.9", server_name = "app.example.com" } })
local accepted, zero_counted = 0, 0
for status = 100, 599 do
    VARIABLES.BAD_BEHAVIOR_STATUS_CODES = tostring(status)
    ngx.status = status
    if p:log().msg == "success" then accepted = accepted + 1 end
    ngx.status = 0
    if p:log().msg == "success" then zero_counted = zero_counted + 1 end
end
emit({ accepted = accepted, zero_counted = zero_counted })
""",
        header=SETTINGS,
    )
    assert out == {"accepted": 500, "zero_counted": 0}

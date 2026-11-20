"""A session whose check fails must be destroyed with its stale cookie cleared, and the cookie domain must follow the service.

When the stored IP or user agent no longer matched, ``utils.get_session`` destroyed the session but kept the request cookie,
so the next read re-opened the destroyed session and the browser looped on an empty page. The same function builds the
session cookie: ``SESSIONS_DOMAIN`` must reach ``session.start`` per service, and an empty value must keep the host-only
default. This test runs the real ``utils.lua`` against recording session stand-ins.
Refs: #556, #1018, #3415.
"""

import pytest
from _t2_helpers import LUA, run_script, utils_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

SESSION_STUBS = r"""
CALLS = {}
local function new_session(exists, metadata)
    local s = { id = #CALLS + 1 }
    local calls = {}
    CALLS[#CALLS + 1] = calls
    function s:get(key) calls[#calls + 1] = "get" return key == "metadata" and metadata or nil end
    function s:set(key, value) calls[#calls + 1] = "set:" .. key end
    function s:clear_request_cookie() calls[#calls + 1] = "clear_request_cookie" end
    function s:destroy() calls[#calls + 1] = "destroy" return true end
    return s, nil, exists, false
end
QUEUE = {}
NEXT_SESSION = function() return table.unpack(table.remove(QUEUE, 1)) end
local function push(exists, metadata) QUEUE[#QUEUE + 1] = table.pack(new_session(exists, metadata)) end
"""


def test_failed_check_clears_the_request_cookie_before_destroying_and_returns_a_fresh_session():
    out = run_script(utils_script(SESSION_STUBS + r"""
VARIABLES = { global = { SESSIONS_CHECK_IP = "yes", SESSIONS_CHECK_USER_AGENT = "no", SESSIONS_DOMAIN = "" } }
push(true, { IP = "9.9.9.9", USER_AGENT = "" })   -- stale session, client IP changed
push(false)                                       -- the fresh one
local ctx = { bw = { remote_addr = "1.2.3.4", http_user_agent = "curl" } }
local session = utils.get_session(ctx)
emit({ first = CALLS[1], fresh = session.id, cached = ctx.bw.sessions_session.id, starts = #SESSION_STARTS, second = CALLS[2] })
"""))
    assert out["first"] == ["get", "clear_request_cookie", "destroy"]
    assert out["fresh"] == 2
    assert out["cached"] == 2
    assert out["starts"] == 2
    assert out["second"] == ["set:metadata"]


def test_passing_check_keeps_the_existing_session_untouched():
    out = run_script(utils_script(SESSION_STUBS + r"""
VARIABLES = { global = { SESSIONS_CHECK_IP = "yes", SESSIONS_CHECK_USER_AGENT = "no", SESSIONS_DOMAIN = "" } }
push(true, { IP = "1.2.3.4", USER_AGENT = "" })
local session = utils.get_session({ bw = { remote_addr = "1.2.3.4", http_user_agent = "curl" } })
emit({ id = session.id, calls = CALLS[1], starts = #SESSION_STARTS })
"""))
    assert out["id"] == 1
    assert out["calls"] == ["get"]
    assert out["starts"] == 1


def test_sessions_domain_reaches_session_start_per_service_and_empty_keeps_the_host_only_default():
    out = run_script(utils_script(SESSION_STUBS + r"""
VARIABLES = {
    global = { MULTISITE = "yes", SESSIONS_CHECK_IP = "no", SESSIONS_CHECK_USER_AGENT = "no", SESSIONS_DOMAIN = "" },
    ["a.example"] = { SESSIONS_DOMAIN = ".a.example" },
    ["b.example"] = {},
}
for _ = 1, 2 do push(false) end
utils.get_session({ bw = { server_name = "a.example", remote_addr = "1.2.3.4" } })
utils.get_session({ bw = { server_name = "b.example", remote_addr = "1.2.3.4" } })
emit({ a = SESSION_STARTS[1] and SESSION_STARTS[1].cookie_domain or "none", b = SESSION_STARTS[2] and SESSION_STARTS[2].cookie_domain or "none" })
"""))
    assert out["a"] == ".a.example"
    assert out["b"] == "none"

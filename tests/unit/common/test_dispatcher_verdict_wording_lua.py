"""The access and log dispatchers state the decision that was applied, not the whitelist flag.

``access-lua.conf`` and ``log-lua.conf`` carry the verdict wording of every access-phase denial. The wording
used to follow ``is_whitelisted(ctx)``: a whitelisted client that a plugin ran before ``whitelist`` refused
(``mtls`` is ordered before it) got the 403 and a log that said ``allowed access from mtls`` in the access
phase and ``client was allowed with reason mtls`` in the log phase.

The real ``access_by_lua_block`` and ``log_by_lua_block`` run under plain ``lua`` with the BunkerWeb modules
stubbed; the stubs return what a plugin would, the dispatcher text is the file's own.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ACCESS_CONF = ROOT / "src" / "common" / "confs" / "server-http" / "access-lua.conf"
LOG_CONF = ROOT / "src" / "common" / "confs" / "server-http" / "log-lua.conf"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
local LEVELS = { [4] = "ERR", [5] = "WARN", [6] = "NOTICE", [7] = "INFO" }
local EXITS, REDIRECTS, EMITTED = {}, {}, {}
local function emit(kind, value) EMITTED[#EMITTED + 1] = kind .. "\t" .. tostring(value) end

ngx = {
    ERR = 4, WARN = 5, NOTICE = 6, INFO = 7, OK = 0,
    HTTP_MOVED_TEMPORARILY = 302, HTTP_BAD_REQUEST = 400, HTTP_TOO_MANY_REQUESTS = 429, HTTP_NOT_ALLOWED = 405,
    ctx = {}, var = { server_name = "svc.test" }, shared = { internalstore = {} },
    req = { is_internal = function() return false end },
    exit = function(status) EXITS[#EXITS + 1] = status; return status end,
    redirect = function(url, status) REDIRECTS[#REDIRECTS + 1] = url .. " " .. tostring(status) end,
}
package.loaded["ngx.errlog"] = { get_sys_filter_level = function() return 8 end }
package.loaded["cjson"] = { encode = function() return "{}" end }
package.loaded["bunkerweb.logger"] = {
    new = function(_, name)
        return { log = function(_, level, msg) emit("LOG", LEVELS[level] .. " [" .. name .. "] " .. msg) end }
    end,
}
package.loaded["bunkerweb.datastore"] = { new = function() return { get = function() return ORDER end } end }
package.loaded["bunkerweb.cachestore"] = { new = function() return { update = function() return true end } end }
package.loaded["bunkerweb.helpers"] = {
    fill_ctx = function()
        ngx.ctx.bw = ngx.ctx.bw or { remote_addr = "203.0.113.9", server_name = "svc.test" }
        return true, "ok", nil, ngx.ctx
    end,
    save_ctx = function() end,
    require_plugin = function(id) return PLUGINS[id] end,
    new_plugin = function(plugin) return true, plugin end,
    call_plugin = function(plugin) return true, plugin.result end,
}
package.loaded["bunkerweb.utils"] = {
    is_whitelisted = function(ctx) return ctx.bw.is_whitelisted == "yes" end,
    is_ip_whitelisted = function() return false, "no" end,
    is_banned = function() return false end,
    get_deny_status = function() return 403 end,
    get_security_mode = function() return MODE end,
    save_session = function() return true, "saved" end,
    set_reason = function(reason, data, ctx)
        ctx.bw.reason, ctx.bw.reason_data, ctx.bw.security_mode = reason or "unknown", data or {}, MODE
    end,
    -- the ban in the datastore is what get_reason finds for a request no plugin denied
    get_reason = function(ctx)
        if ctx.bw.reason then return ctx.bw.reason, ctx.bw.reason_data or {}, MODE end
        if STORED_BAN then return STORED_BAN, {}, MODE end
        return nil
    end,
}

local function access() %(access)s end
local function logphase() %(log)s end

ORDER = { access = { "p1" }, log = {} }
PLUGINS = { p1 = { access = true } }
MODE = "block"
%(scenario)s
ngx.ctx.bw = { remote_addr = "203.0.113.9", server_name = "svc.test", is_whitelisted = WHITELISTED and "yes" or "no" }
access()
logphase()
for _, line in ipairs(EMITTED) do print(line) end
for _, status in ipairs(EXITS) do print("EXIT\t" .. tostring(status)) end
for _, url in ipairs(REDIRECTS) do print("REDIRECT\t" .. url) end
"""


def lua_block(path, opener):
    match = re.search(rf"^{re.escape(opener)} \{{\n(.*)\n\}}\s*$", path.read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"{path.name}: {opener} not found"
    return match.group(1)


def run(tmp_path, *, mode="block", whitelisted=False, result=None, stored_ban=None, reason=None):
    """Run the access then the log dispatcher once; return ``(lines, exits, redirects)``."""
    scenario = [f'MODE = "{mode}"', f"WHITELISTED = {'true' if whitelisted else 'false'}"]
    if result is not None:
        scenario.append(f"PLUGINS.p1.result = {result}")
    if stored_ban:
        scenario.append(f'STORED_BAN = "{stored_ban}"')
    script = tmp_path / "dispatch.lua"
    body = HARNESS % {
        "access": lua_block(ACCESS_CONF, "access_by_lua_block"),
        "log": lua_block(LOG_CONF, "log_by_lua_block"),
        "scenario": "\n".join(scenario),
    }
    if reason:
        # a reason already recorded on the request (detect mode records none in the access dispatcher)
        body = body.replace("access()\nlogphase()", f'ngx.ctx.bw.reason, ngx.ctx.bw.reason_data = "{reason}", {{}}\naccess()\nlogphase()')
    script.write_text(body, encoding="utf-8")
    done = subprocess.run([str(LUA), str(script)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    lines, exits, redirects = [], [], []
    for row in done.stdout.splitlines():
        kind, _, value = row.partition("\t")
        {"LOG": lines, "EXIT": exits, "REDIRECT": redirects}[kind].append(value)
    return lines, exits, redirects


DENY = '{ ret = true, msg = "client certificate required", status = 403, data = { id = "mtls" } }'


def verdicts(lines):
    """Access and log phase lines that carry a verdict word."""
    return [line for line in lines if re.search(r"\b(allow|allowed|denied|deny)\b", line)]


@pytest.mark.parametrize("whitelisted", [False, True], ids=["not whitelisted", "whitelisted"])
def test_a_denied_request_is_logged_denied_in_both_phases(tmp_path, whitelisted):
    lines, exits, _ = run(tmp_path, whitelisted=whitelisted, result=DENY)
    assert exits == ["403"]
    assert verdicts(lines) == [
        "WARN [ACCESS] denied access from p1 : client certificate required",
        "INFO [LOG] client was denied with reason p1 and data = {}",
    ]


def test_a_whitelisted_request_that_a_plugin_lets_through_is_not_logged_as_a_denial(tmp_path):
    # whitelist answers OK (status 0): the access phase ends with a NOTICE and no reason is recorded
    lines, exits, _ = run(tmp_path, whitelisted=True, result='{ ret = true, msg = "IP is whitelisted", status = 0 }')
    assert exits == ["0"]
    assert "NOTICE [ACCESS] p1 returned status 0 : IP is whitelisted" in lines
    assert verdicts(lines) == []


def test_a_whitelisted_request_a_ban_record_would_have_denied_is_still_logged_allowed(tmp_path):
    # the whitelist rescued it: no plugin denied it, so the reason found at log time is not a decision applied
    lines, exits, _ = run(tmp_path, whitelisted=True, result='{ ret = true, msg = "ok" }', stored_ban="bad behavior")
    assert exits == []
    assert verdicts(lines) == ["INFO [LOG] client was allowed with reason bad behavior and data = {}"]


def test_a_request_denied_by_the_ban_record_is_still_logged_denied(tmp_path):
    lines, _, _ = run(tmp_path, whitelisted=False, result='{ ret = true, msg = "ok" }', stored_ban="bad behavior")
    assert verdicts(lines) == ["INFO [LOG] client was denied with reason bad behavior and data = {}"]


@pytest.mark.parametrize(
    ("whitelisted", "access_line", "log_line"),
    [
        (False, "WARN [ACCESS] detected deny access from p1 : client certificate required", "INFO [LOG] detected client deny with reason p1 and data = {}"),
        (True, "WARN [ACCESS] detected allow access from p1 : client certificate required", "INFO [LOG] detected client allow with reason p1 and data = {}"),
    ],
    ids=["not whitelisted", "whitelisted"],
)
def test_detect_mode_wording_is_unchanged(tmp_path, whitelisted, access_line, log_line):
    lines, exits, _ = run(tmp_path, mode="detect", whitelisted=whitelisted, result=DENY, reason="p1")
    assert exits == []
    assert verdicts(lines) == [access_line, log_line]


@pytest.mark.parametrize("whitelisted", [False, True], ids=["not whitelisted", "whitelisted"])
def test_a_redirect_is_logged_as_a_redirect(tmp_path, whitelisted):
    lines, exits, redirects = run(tmp_path, whitelisted=whitelisted, result='{ ret = true, msg = "challenge", redirect = "/c" }')
    assert "NOTICE [ACCESS] p1 redirect to /c : challenge" in lines
    assert redirects == ["/c 302"] and exits == []
    assert verdicts(lines) == []


def test_the_deny_branch_still_records_the_reason_the_log_phase_reports(tmp_path):
    lines, _, _ = run(tmp_path, result='{ ret = true, msg = "x", status = 429, data = { id = "limit" } }')
    assert "INFO [LOG] client was denied with reason p1 and data = {}" in lines

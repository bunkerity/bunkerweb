"""A reload NGINX refused must answer an error, not `reload successful`.

`POST /reload` used to send SIGHUP and return 200 as soon as the *signal* was delivered. NGINX
parses the new configuration in the master **after** the signal: when it refuses, it logs
`[emerg]`, keeps serving the previous cycle, and the signal still reports success. Nothing on
that path ever read the reload's real outcome -- the pre-`nginx -t` was the only thing that
could fail the call, so `DISABLE_CONFIGURATION_TESTING=yes` (which the whole integration suite
sets, `tests/utils/config.yml:15`) removed the last verdict and every refused reload answered
200. Proven in vivo on 2026-08-25, k8s `mtls_requires_client_certificate`:

    10:12:11 [notice] 65#65: signal 1 (SIGHUP) received from 82, reconfiguring
    10:12:11 [emerg]  65#65: duplicate location "/" in .../reverse-proxy.conf:38

with `POST /reload?test=no` answering `reload successful` **200** in that same second. The pod
never left the configuration it booted with and the spec's 200 came from the default server.

`confirm_reload()` is the fix, and this pins its three outcomes. Confirmation requires readiness from the new cycle. A configuration test cannot prove that
init_by_lua accepted it, and worker rotation alone cannot identify the requested reload.

Runs through the `lua` binary with OpenResty stubbed.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


def real_function(name: str) -> str:
    """Return the shipped `local function <name>` source, source-exact.

    Splicing the real body in is what keeps this file honest: delete or narrow the verdict in
    api.lua and the extraction fails here rather than the assertions passing on a copy.
    """
    body = re.search(rf"^local function {name}\(.*?^end$", API_LUA.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"{name}() is gone from {API_LUA}"
    return body.group(0)


HARNESS = """
-- Fake clock: ngx.sleep advances it instead of blocking, so the 2s wait costs nothing here.
local now = 1000
local exiting_after = %s   -- number of exiting() polls before the workers rotate, or -1 = never
local polls = 0
local popen_calls = 0
local popen_output = %s

ngx = {
    NOTICE = 1,
    ERR = 1,
    now = function() return now end,
    update_time = function() end,
    sleep = function(d) now = now + d end,
    worker = {
        exiting = function()
            polls = polls + 1
            return exiting_after >= 0 and polls > exiting_after
        end,
    },
}
local ready = false
shared = { internalstore = { get = function(_, key)
    if key == "misc_ready_current" and exiting_after >= 0 and now > 1000 + 0.05 * exiting_after then return "ok" end
end } }
read_reload_marker = function() return "current" end
logger = { log = function() end }
RELOAD_CONFIRM_TIMEOUT = 2
get_nginx_bin = function() return "nginx" end
get_nginx_conf = function() return "/etc/nginx/nginx.conf" end

local real_popen = io.popen
io.popen = function(command)
    assert(command:find(" -t ", 1, true), "the fallback must be a config test, got: " .. command)
    popen_calls = popen_calls + 1
    return { read = function() return popen_output end, close = function() end }
end
local _ = real_popen

%s

%s

local ok, detail = confirm_reload("current")
print(string.format("%%s|%%d|%%s", tostring(ok), popen_calls, detail))
"""


def run(exiting_after: int, popen_output: str):
    script = HARNESS % (exiting_after, "[==[" + popen_output + "]==]", real_function("test_nginx_conf"), real_function("confirm_reload"))
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    ok, popen_calls, detail = result.stdout.strip().split("|", 2)
    return ok == "true", int(popen_calls), detail


REFUSED = 'nginx: [emerg] duplicate location "/" in /etc/nginx/www.example.com/server-http/reverse-proxy.conf:38\nnginx: configuration file /etc/nginx/nginx.conf test failed\n'
CLEAN = "nginx: the configuration file /etc/nginx/nginx.conf syntax is ok\nnginx: configuration file /etc/nginx/nginx.conf test is successful\n"
NON_ROOT = 'nginx: the configuration file /etc/nginx/nginx.conf syntax is ok\nnginx: [emerg] open() "/var/run/nginx.pid" failed (13: Permission denied)\n'


def test_a_refused_reload_is_reported_as_a_failure():
    """The regression under test: NGINX kept the old cycle, so the call must not answer success."""
    ok, popen_calls, detail = run(-1, REFUSED)
    assert not ok, "a reload NGINX refused must not be reported as successful"
    assert popen_calls == 0, "nginx -t cannot confirm init_by_lua"
    assert "timed out" in detail, detail


def test_new_worker_readiness_confirms_without_a_configuration_test():
    """The common path: workers publish the requested token after initialization."""
    ok, popen_calls, detail = run(1, REFUSED)
    assert ok, f"a reload the master accepted must be reported as successful, got: {detail}"
    assert popen_calls == 0, "confirmation from the worker rotation must not run nginx -t at all"


def test_clean_syntax_without_readiness_times_out():
    ok, popen_calls, detail = run(-1, CLEAN)
    assert not ok, "clean syntax does not prove init_by_lua accepted the reload"
    assert popen_calls == 0
    assert "timed out" in detail


def test_non_root_permission_warnings_do_not_confirm_readiness():
    ok, _, _ = run(-1, NON_ROOT)
    assert not ok


def test_the_shipped_handler_actually_acts_on_the_verdict():
    """The functions above are only worth testing while POST /reload still fails on them."""
    src = API_LUA.read_text(encoding="utf-8")
    # DEV-2b5: the body moved into `reload_locked` when POST /reload was made to TAKE the swap
    # lock instead of polling it (Criticos REQUIRED 1); the handler is now the lock wrapper.
    handler = re.search(r"^local function reload_locked\(test_arg\).*?^end$", src, re.M | re.S)
    assert handler, "the POST /reload handler is gone from api.lua"
    body = handler.group(0)
    assert "confirm_reload(token)" in body, "POST /reload no longer confirms the reload it signalled"
    assert re.search(r"if not reloaded then.*?HTTP_INTERNAL_SERVER_ERROR", body, re.S), "an unconfirmed reload no longer answers an error"


def test_the_reloading_marker_is_created_before_the_signal():
    """The marker is removed by the NEW cycle's worker init (init-worker-lua.conf), and
    confirm_reload() only returns once those workers are up. Created after the wait, the marker
    outlives its remover and /health answers "reloading" forever -- the api;health red of run
    33106855238. Order in the handler source is the contract: marker, then HUP, then confirm."""
    src = API_LUA.read_text(encoding="utf-8")
    # DEV-2b5: the body moved into `reload_locked` when POST /reload was made to TAKE the swap
    # lock instead of polling it (Criticos REQUIRED 1); the handler is now the lock wrapper.
    handler = re.search(r"^local function reload_locked\(test_arg\).*?^end$", src, re.M | re.S)
    assert handler, "the POST /reload handler is gone from api.lua"
    body = handler.group(0)
    marker = body.find('open("/var/tmp/bunkerweb_reloading", "w")')
    hup = body.find('"HUP"')
    confirm = body.find("= confirm_reload(token)")
    assert marker != -1 and hup != -1 and confirm != -1, "marker write, HUP signal or confirm_reload missing from the handler"
    assert marker < hup < confirm, "the reloading marker must be written before the HUP signal (its remover is the new cycle's worker init)"

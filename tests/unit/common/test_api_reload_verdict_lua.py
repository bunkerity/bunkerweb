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

`confirm_reload()` is the fix, and this pins its three outcomes. Note what it must NOT do:
a refusal is immediate, a *success* can be slow (init_by_lua rebuilds the whole BunkerWeb
runtime in the master), so an unconfirmed wait may never be reported as a failure on its own --
`nginx -t` arbitrates. A false failure is not a cosmetic bug: push-configs answers one by
restoring a failover snapshot over a fleet that was fine.

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
    body = re.search(rf"^local function {name}\(\).*?^end$", API_LUA.read_text(encoding="utf-8"), re.M | re.S)
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
    sleep = function(d) now = now + d end,
    worker = {
        exiting = function()
            polls = polls + 1
            return exiting_after >= 0 and polls > exiting_after
        end,
    },
}
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

local ok, detail = confirm_reload()
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
    assert popen_calls == 1, "the unconfirmed wait must arbitrate with exactly one nginx -t"
    assert 'duplicate location "/"' in detail, f"the caller must be told what NGINX refused, got: {detail}"


def test_a_rotated_worker_set_confirms_the_reload_without_paying_for_a_test():
    """The common path: the master forked new workers and is shutting this one down."""
    ok, popen_calls, detail = run(1, REFUSED)
    assert ok, f"a reload the master accepted must be reported as successful, got: {detail}"
    assert popen_calls == 0, "confirmation from the worker rotation must not run nginx -t at all"


def test_a_slow_but_valid_reload_is_not_turned_into_a_false_failure():
    """init_by_lua can take longer than the wait on a large configuration. That is not a failure:
    answering one would make push-configs restore a failover snapshot over a healthy fleet."""
    ok, popen_calls, _ = run(-1, CLEAN)
    assert ok, "an unconfirmed wait is not a verdict; a clean nginx -t must keep the call successful"
    assert popen_calls == 1


def test_non_root_permission_warnings_are_still_not_a_failure():
    """`nginx -t` as a non-root user cannot write the pid file. Pre-existing behaviour, kept."""
    ok, _, _ = run(-1, NON_ROOT)
    assert ok, "a permission warning under a non-root test must not be read as a refused reload"


def test_the_shipped_handler_actually_acts_on_the_verdict():
    """The functions above are only worth testing while POST /reload still fails on them."""
    src = API_LUA.read_text(encoding="utf-8")
    handler = re.search(r'^api\.global\.POST\["\^/reload"\] = function\(self\).*?^end$', src, re.M | re.S)
    assert handler, "the POST /reload handler is gone from api.lua"
    body = handler.group(0)
    assert "confirm_reload()" in body, "POST /reload no longer confirms the reload it signalled"
    assert re.search(r"if not reloaded then.*?HTTP_INTERNAL_SERVER_ERROR", body, re.S), "an unconfirmed reload no longer answers an error"


def test_the_reloading_marker_is_created_before_the_signal():
    """The marker is removed by the NEW cycle's worker init (init-worker-lua.conf), and
    confirm_reload() only returns once those workers are up. Created after the wait, the marker
    outlives its remover and /health answers "reloading" forever -- the api;health red of run
    33106855238. Order in the handler source is the contract: marker, then HUP, then confirm."""
    src = API_LUA.read_text(encoding="utf-8")
    handler = re.search(r'^api\.global\.POST\["\^/reload"\] = function\(self\).*?^end$', src, re.M | re.S)
    assert handler, "the POST /reload handler is gone from api.lua"
    body = handler.group(0)
    marker = body.find('open("/var/tmp/bunkerweb_reloading", "w")')
    hup = body.find('"HUP"')
    confirm = body.find("= confirm_reload()")
    assert marker != -1 and hup != -1 and confirm != -1, "marker write, HUP signal or confirm_reload missing from the handler"
    assert marker < hup < confirm, "the reloading marker must be written before the HUP signal (its remover is the new cycle's worker init)"

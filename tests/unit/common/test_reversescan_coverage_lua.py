"""Reverse-scan access, socket outcomes, cache failures and thread errors."""

import pytest
from _lua_plugin_helpers import CORE, LUA, run_module, to_lua

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "reversescan" / "reversescan.lua"
PREAMBLE = r"""
CONNECT, DIALLED, CLOSED = {}, {}, 0
ngx.socket = { tcp = function()
    return {
        settimeout = function(_, timeout) TIMEOUT = timeout end,
        connect = function(_, host, port)
            DIALLED[#DIALLED + 1] = { host, port }
            local answer = CONNECT[port] or { false, "connection refused" }
            return answer[1], answer[2]
        end,
        close = function() CLOSED = CLOSED + 1 end,
    }
end }
package.loaded["bunkerweb.utils"].parse_duration = function(value, unit)
    assert(value == "250ms" and unit == "ms")
    return 250
end
"""


def run(body):
    return run_module(MODULE, body, preamble=PREAMBLE)


def access(*, ports="22 80", setup="", method="access", ip="192.0.2.1"):
    return run(f"""
VARIABLES = {{ USE_REVERSE_SCAN = "yes", REVERSE_SCAN_PORTS = {to_lua(ports)}, REVERSE_SCAN_TIMEOUT = "250ms" }}
{setup}
local p = new_plugin(PLUGIN, {{ remote_addr = {to_lua(ip)} }})
p.cachestore = p.cachestore_local
local r = p:{method}()
emit({{ result = summary(r), cache = CACHE, ttl = CACHE_TTL, metrics = METRICS,
        dialled = DIALLED, closed = CLOSED, timeout = TIMEOUT, logs = LOGS, killed = KILLED and #KILLED or 0 }})
""")


def test_disabled_scan_leaves_request_untouched():
    out = access(setup='VARIABLES.USE_REVERSE_SCAN = "no"')
    assert out["result"] == {"ret": True, "msg": "reverse scan not activated"}
    assert out["closed"] == 0
    assert out["cache"] == {}


def test_cached_open_denies_with_configured_status_and_metric():
    out = access(setup='DENY_STATUS = 444; CACHE["plugin_reverse_scan_192.0.2.1:22"] = "open"')
    assert out["result"] == {"ret": True, "msg": "port 22 is opened for IP 192.0.2.1", "status": 444}
    assert out["metrics"] == {"failed_22": 1}
    assert out["closed"] == 0


def test_cached_closed_skips_socket_and_passes():
    out = access(ports="22", setup='CACHE["plugin_reverse_scan_192.0.2.1:22"] = "close"')
    assert out["result"] == {"ret": True, "msg": "no port open for IP 192.0.2.1"}
    assert out["closed"] == 0


def test_uncached_closed_ports_are_cached_for_one_day():
    out = access()
    assert out["result"] == {"ret": True, "msg": "no port open for IP 192.0.2.1"}
    assert out["cache"] == {"plugin_reverse_scan_192.0.2.1:22": "close", "plugin_reverse_scan_192.0.2.1:80": "close"}
    assert out["ttl"] == 86400
    assert (out["timeout"], out["closed"]) == (250, 2)


def test_newly_open_port_denies_and_caches_open():
    out = access(ports="80", setup="CONNECT[80] = { true }", method="preread")
    assert out["result"] == {"ret": True, "msg": "port 80 is opened for IP 192.0.2.1", "status": 403}
    assert out["cache"] == {"plugin_reverse_scan_192.0.2.1:80": "open"}
    assert out["metrics"] == {"failed_80": 1}


@pytest.mark.parametrize(
    "setup,msg",
    [
        ('CACHE_ERROR = "unavailable"', "error getting info from cachestore : unavailable"),
        ('WAIT_ERROR = "thread failed"', "error while waiting thread : thread failed"),
        ('CACHE_SET_ERROR = "full"', "error while adding element to cache : full"),
    ],
)
def test_access_reports_cache_and_thread_failures(setup, msg):
    out = access(ports="22", setup=setup)
    assert out["result"] == {"ret": False, "msg": msg}
    assert out["cache"] == {}


@pytest.mark.parametrize("error", ["no route to host", "address family not supported", None])
def test_untried_port_is_logged_and_not_cached(error):
    out = access(ports="80", setup=f"CONNECT[80] = {{ false, {to_lua(error)} }}")
    assert out["result"] == {"ret": True, "msg": "no port open for IP 192.0.2.1"}
    assert out["cache"] == {}
    assert out["logs"] == [["WARN", f"could not scan port 80 : {error or 'unknown error'}"]]


@pytest.mark.parametrize("ip,host", [("192.0.2.1", "192.0.2.1"), ("2001:db8::1", "[2001:db8::1]")])
@pytest.mark.parametrize("ok,error", [(True, None), (False, "timeout"), (False, "connection refused")])
def test_scan_returns_port_outcome_and_closes_socket(ip, host, ok, error):
    out = run(f"""
CONNECT[80] = {{ {to_lua(ok)}, {to_lua(error)} }}
local open, port, err = PLUGIN.scan({to_lua(ip)}, 80, 250)
emit({{ open = open, port = port, err = err, dialled = DIALLED, closed = CLOSED, timeout = TIMEOUT }})
""")
    assert out == {"open": ok, "port": 80, "dialled": [[host, 80]], "closed": 1, "timeout": 250}


@pytest.mark.parametrize("stop", ["cached_open", "cached_error", "wait_error", "new_open"])
def test_early_exit_cancels_pending_scan_threads(stop):
    setup = {
        "cached_open": 'CACHE["plugin_reverse_scan_192.0.2.1:80"] = "open"',
        "cached_error": "",
        "wait_error": 'WAIT_ERROR = "thread failed"',
        "new_open": "CONNECT[22] = { true }",
    }[stop]
    if stop == "cached_error":
        # Fail only the second lookup, after the first port has spawned a scan.
        setup = """
local initialize = package.loaded["bunkerweb.plugin"].initialize
package.loaded["bunkerweb.plugin"].initialize = function(self, ...)
    initialize(self, ...)
    self.cachestore_local.get = function(_, key)
        if key:match(":80$") then return false, "unavailable" end
        return true, nil
    end
end
"""
    out = access(setup=setup)
    assert out["killed"] >= 1

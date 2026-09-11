"""The control plane must not be able to lock itself out of an instance.

`init_by_lua` loads `/etc/nginx/variables.env` into the per-worker LRU (`datastore.lua:39`), and
that LRU belongs to the Lua VM. A reload builds a NEW VM, so `init-lua.conf:116`'s "keeping
previous LRU data" branch keeps nothing at all: a reload that ran while the file was absent leaves
every worker of the new cycle with an empty internalstore.

`api:initialize` then reads no `API_WHITELIST_IP`, `is_allowed_ip()` fails closed, and every
control-plane request is answered 444 -- including `POST /confs`, the only thing that can put the
variables back. That is a deadlock the instance never leaves on its own: CI run 34576775876
(All-in-one `upgrade`) spent five minutes answering `ping` and refusing every push.

Two behaviours are pinned here, and they only make sense together:

* the IP whitelist falls back to the file on disk, so a push can land and repair the store;
* the API token falls back with it. Repairing only the whitelist would turn a *dead* control
  plane into an *unauthenticated* one -- `is_allowed_token()` fails OPEN when no token is
  configured (`api.lua:380`), so a whitelist-only fix would accept any bearer from a whitelisted
  IP. The two reads are one fix.

Runs the shipped `src/bw/lua/bunkerweb/api.lua` bodies through the `lua` binary with OpenResty
stubbed, splicing the real functions the way `test_instance_credential_lua.py` does -- so
narrowing the check in api.lua fails the extraction here rather than passing on a copy.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SOURCE = API_LUA.read_text(encoding="utf-8")


def _optional_local(name: str) -> str:
    """The disk fallback. Absent on the unfixed tree, which is what makes the red run behavioural."""
    body = re.search(rf"^local function {name}\(.*?^end$", SOURCE, re.M | re.S)
    return body.group(0) if body else ""


def _required(pattern: str, what: str) -> str:
    body = re.search(pattern, SOURCE, re.M | re.S)
    assert body, f"{what} is gone from {API_LUA}"
    return body.group(0)


SECURE_COMPARE = """
local function secure_compare(a, b)
    if #a ~= #b then return false end
    local diff = 0
    for i = 1, #a do if a:byte(i) ~= b:byte(i) then return false end end
    return diff == 0
end
"""

HARNESS = """
ngx = { NOTICE = 1, ERR = 2, WARN = 3 }
ERR = ngx.ERR
NOTICE = ngx.NOTICE
WARN = ngx.WARN
ENOENT = 2
logger = { log = function() end }
OPENS = 0
open = function(...) OPENS = OPENS + 1 return io.open(...) end
VARIABLES_PATH = %s

-- An empty internalstore: exactly what a worker forked from a VM whose init_by_lua could not
-- read variables.env answers, verbatim from the CI log.
local STORE = %s
get_variable = function(name)
    local value = STORE[name]
    if value == nil then
        return nil, "can't access variables from internalstore : not found"
    end
    return value
end

read_instance_credential = function() return nil, "absent" end
local HEADERS = %s
ngx_req = { get_headers = function() return HEADERS end }

-- Exact match, plus the two wildcards, because a "fallback" that quietly widened the whitelist to
-- everything would otherwise satisfy test_no_file_either_still_fails_CLOSED and ship.
is_ip_in_networks = function(ip, networks)
    for _, network in ipairs(networks) do
        if network == ip or network == "0.0.0.0/0" or network == "::/0" then return true end
    end
    return false
end

%s

%s

local api = {}

%s

%s

%s

%s
"""


def _lua_string(value):
    return "nil" if value is None else "[==[" + value + "]==]"


def _lua_table(mapping):
    return "{" + ", ".join(f'["{k}"] = [==[{v}]==]' for k, v in mapping.items()) + "}"


def run(body: str, *, variables_path: Path, store: dict, headers: dict | None = None, count_opens: bool = False):
    if count_opens:
        body = CHECK_IP_COUNTING_OPENS
    script = HARNESS % (
        _lua_string(str(variables_path)),
        _lua_table(store),
        _lua_table(headers or {}),
        SECURE_COMPARE,
        _optional_local("control_plane_variables_from_disk"),
        _required(r"^function api:initialize\(ctx\).*?^end$", "api:initialize()"),
        _required(r"^function api:is_allowed_ip\(\).*?^end$", "api:is_allowed_ip()"),
        _required(r"^function api:is_allowed_token\(\).*?^end$", "api:is_allowed_token()"),
        body,
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


CHECK_IP = """
local self = {}
api.initialize(self, { bw = { remote_addr = "127.0.0.1" } })
local ok, msg = api.is_allowed_ip(self)
print(tostring(ok) .. "|" .. msg)
"""

CHECK_IP_COUNTING_OPENS = """
local self = {}
api.initialize(self, { bw = { remote_addr = "127.0.0.1" } })
local ok, msg = api.is_allowed_ip(self)
print(tostring(ok) .. "|" .. msg .. "|opens=" .. tostring(OPENS))
"""

CHECK_TOKEN = """
local self = {}
api.initialize(self, { bw = { remote_addr = "127.0.0.1" } })
local ok, msg = api.is_allowed_token(self)
print(tostring(ok) .. "|" .. msg)
"""


def _variables(tmp_path, text):
    path = tmp_path / "variables.env"
    path.write_text(text, encoding="utf-8")
    return path


class TestEmptyInternalstore:
    def test_a_push_still_gets_through_when_the_store_lost_its_variables(self, tmp_path):
        """The regression this whole file exists for: 444 on /confs forever."""
        path = _variables(tmp_path, "SERVER_NAME=www.example.com\nAPI_WHITELIST_IP=127.0.0.1\n")
        assert run(CHECK_IP, variables_path=path, store={}) == "true|ok"

    def test_the_token_is_enforced_on_that_same_path(self, tmp_path):
        """Fixing only the whitelist would make an unauthenticated control plane REACHABLE."""
        path = _variables(tmp_path, "API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=the-instance-token\n")
        assert run(CHECK_TOKEN, variables_path=path, store={}) == "false|missing API token"
        out = run(CHECK_TOKEN, variables_path=path, store={}, headers={"authorization": "Bearer the-instance-token"})
        assert out == "true|ok"

    def test_no_file_either_still_fails_CLOSED(self, tmp_path):
        """The fallback is a last resort, never a licence to allow everything.

        The harness's `is_ip_in_networks` honours `0.0.0.0/0` and `::/0`, so the tempting wrong
        fix -- "no whitelist anywhere, let the push through" -- fails here instead of shipping.
        """
        out = run(CHECK_IP, variables_path=tmp_path / "absent.env", store={})
        assert out == "false|IP is not in API_WHITELIST_IP"

    def test_the_whole_file_is_read_once_even_though_two_settings_come_from_it(self, tmp_path):
        """api.conf builds this object twice per request; a read per setting is four scans.

        Counted through `open`, so the assertion is on the syscall the degraded path actually
        makes, not on the shape of the code.
        """
        path = _variables(tmp_path, "API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=t\n")
        out = run(CHECK_IP, variables_path=path, store={}, count_opens=True)
        assert out.endswith("|opens=1"), out

    def test_a_half_written_file_recovers_the_whitelist_without_a_token(self, tmp_path):
        """The one input where the fallback is LOOSER than refusing, pinned so it stays known.

        `Templator._write_config` (`src/common/gen/Templator.py:841`) writes `variables.env` with a
        non-atomic `write_text`, so a read can land after `API_WHITELIST_IP=` has flushed and before
        `API_TOKEN=` has. The whitelist is then recovered with no token, and `is_allowed_token()`
        treats "no token configured" as allow -- so this request is accepted with no bearer where
        the configured state wants one. It is accepted deliberately (the alternative is refusing
        every repair push whose file is mid-flush, i.e. no fix at all), it needs an already-empty
        store PLUS a concurrent render PLUS membership of `API_WHITELIST_IP`, and the real cure is
        an atomic write in `_write_config` -- outside this lane's globs, see report-W1.md §7.1.

        Not a red-first assertion: the unfixed code reaches `true|ok` here too, by never recovering
        anything. It is a design pin, and it is falsifiable -- an implementation that fabricated a
        token, or that refused a whitelist recovered without one, fails it.
        """
        path = _variables(tmp_path, "SERVER_NAME=www.example.com\nAPI_WHITELIST_IP=127.0.0.1\n")
        assert run(CHECK_TOKEN, variables_path=path, store={}) == "true|ok"

    def test_a_populated_store_is_never_overridden_by_the_file(self, tmp_path):
        """The store is the live view; the file is only consulted when the store has nothing."""
        path = _variables(tmp_path, "API_WHITELIST_IP=127.0.0.1\n")
        out = run(CHECK_IP, variables_path=path, store={"API_WHITELIST_IP": "10.0.0.1"})
        assert out == "false|IP is not in API_WHITELIST_IP"

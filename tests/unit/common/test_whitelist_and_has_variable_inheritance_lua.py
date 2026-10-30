"""``utils.has_variable`` and ``utils.is_ip_whitelisted`` resolve a service's EFFECTIVE value.

Ports of dev ``357dde078`` and ``b4cb64f4c``. Both functions read the per-service tables in
``internalstore["variables"]``, and both used to read them as if a service table always carried
every key:

* ``has_variable`` compared ``variables[server][key]`` directly, so a service whose table does not
  carry the key (only the ones it overrides are stored) answered ``nil ~= value`` and a setting
  enabled **globally** looked disabled fleet-wide. Every hook gated on it — the timers, the
  fleet-wide template switches — then did nothing.
* ``is_ip_whitelisted`` never consulted ``USE_WHITELIST`` at all. The whitelist lists are stored for
  every service whether or not the plugin is on for it, so a service with whitelisting **off** still
  lifted an active ban through its own configured entries, and so did the global list.

``get_variable``'s rule is the one both must follow: the service's own value when its table carries
one, the global value otherwise. Source-inspecting that is not enough — the two functions are
extracted here and run against a fake ``internalstore`` so the *answers* are asserted.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def _chunk(pattern: str, what: str) -> str:
    text = UTILS_LUA.read_text(encoding="utf-8")
    found = re.search(pattern, text, re.S | re.M)
    assert found, f"{what} not found in utils.lua -- renamed or restructured?"
    return found.group(0)


def has_variable_source() -> str:
    return _chunk(r"^utils\.has_variable = function.*?^end$", "has_variable")


def is_ip_whitelisted_source() -> str:
    return _chunk(r"^utils\.is_ip_whitelisted = function.*?^end$", "is_ip_whitelisted")


# `internalstore:get("variables", true)` is the only store either function reads, and
# `is_ip_whitelisted` also reaches for the cachestore and ipmatcher. All three are faked: the
# question here is which service table an answer comes from, not how a shared dict behaves.
PREAMBLE = r"""
local utils = {}
local var = { server_name = "" }

VARIABLES = {}
LISTS = {}

local internalstore = {
    get = function(_, key)
        if key == "variables" then return VARIABLES end
        local list = LISTS[key]
        if list == nil then return nil, "not found" end
        return list
    end,
}

-- No cache hit ever, so every call goes to the stored lists.
package.preload["bunkerweb.cachestore"] = function()
    return { new = function() return { get = function() return true, nil end } end }
end

-- Matches only the exact strings in the list; enough to tell "consulted" from "skipped".
local function ipmatcher_new(networks)
    local set = {}
    for _, n in ipairs(networks) do set[n] = true end
    return { match = function(_, ip) return set[ip] or false, nil end }, nil
end
"""


def run(body: str) -> str:
    script = "\n".join([PREAMBLE, has_variable_source(), is_ip_whitelisted_source(), body])
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


class TestHasVariableInheritsTheGlobalValue:
    def test_a_service_without_its_own_key_inherits_the_global_one(self):
        """The port. Before it, `variables["svc"]["USE_X"]` was nil and the answer was False."""
        out = run("""
            VARIABLES = {
                global = { MULTISITE = "yes", SERVER_NAME = "a.example.com", USE_X = "yes" },
                ["a.example.com"] = { SERVER_NAME = "a.example.com" },
            }
            local ok, err = utils.has_variable("USE_X", "yes")
            assert(err == "success", tostring(err))
            assert(ok == true, "a globally enabled setting must be visible through the service")
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_a_service_overriding_the_global_value_still_wins(self):
        """Anti-vacuity: inheritance must not become "the global value always answers"."""
        out = run("""
            VARIABLES = {
                global = { MULTISITE = "yes", SERVER_NAME = "a.example.com", USE_X = "yes" },
                ["a.example.com"] = { USE_X = "no" },
            }
            local ok = utils.has_variable("USE_X", "yes")
            assert(ok == false, "a service that switched the setting off must not report it on")
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_one_service_out_of_several_is_enough(self):
        out = run("""
            VARIABLES = {
                global = { MULTISITE = "yes", SERVER_NAME = "a.example.com b.example.com", USE_X = "no" },
                ["a.example.com"] = { USE_X = "no" },
                ["b.example.com"] = { USE_X = "yes" },
            }
            assert(utils.has_variable("USE_X", "yes") == true, "a single enabled service must answer true")
            print("ok")
            """)
        assert out.strip() == "ok"


class TestTheWhitelistIsOnlyConsultedWhereItIsEnabled:
    def test_a_service_with_the_whitelist_off_does_not_lift_a_ban(self):
        """The port. The lists exist for every service; only the switch says whether they apply."""
        out = run("""
            VARIABLES = {
                global = { MULTISITE = "yes", SERVER_NAME = "a.example.com", USE_WHITELIST = "no" },
                ["a.example.com"] = { USE_WHITELIST = "no" },
            }
            LISTS = { plugin_whitelist_lists_a_example_com = nil, ["plugin_whitelist_lists_a.example.com"] = { IP = { "1.2.3.4" } } }
            local ok, info = utils.is_ip_whitelisted("1.2.3.4", "a.example.com")
            assert(ok == false, "a disabled whitelist must not whitelist, got " .. tostring(ok) .. " / " .. tostring(info))
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_the_same_service_with_the_whitelist_on_does_whitelist(self):
        """Anti-vacuity for the test above: same list, same ip, switch flipped."""
        out = run("""
            VARIABLES = {
                global = { MULTISITE = "yes", SERVER_NAME = "a.example.com", USE_WHITELIST = "no" },
                ["a.example.com"] = { USE_WHITELIST = "yes" },
            }
            LISTS = { ["plugin_whitelist_lists_a.example.com"] = { IP = { "1.2.3.4" } } }
            local ok, info = utils.is_ip_whitelisted("1.2.3.4", "a.example.com")
            assert(ok == true, "an enabled whitelist must whitelist its own entry")
            assert(info == "ip", info)
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_a_service_inherits_the_global_switch(self):
        out = run("""
            VARIABLES = {
                global = { MULTISITE = "yes", SERVER_NAME = "a.example.com", USE_WHITELIST = "yes" },
                ["a.example.com"] = {},
            }
            LISTS = { ["plugin_whitelist_lists_a.example.com"] = { IP = { "1.2.3.4" } } }
            assert(utils.is_ip_whitelisted("1.2.3.4", "a.example.com") == true, "the global switch must reach the service")
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_the_global_list_is_gated_too(self):
        """The last-resort global list ran unconditionally, so it whitelisted with the plugin off."""
        out = run("""
            VARIABLES = { global = { MULTISITE = "no", SERVER_NAME = "", USE_WHITELIST = "no", WHITELIST_IP = "9.9.9.9" } }
            local ok = utils.is_ip_whitelisted("9.9.9.9", "")
            assert(ok == false, "the global list must not apply while whitelisting is off globally")
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_the_global_list_still_applies_when_it_is_enabled(self):
        out = run("""
            VARIABLES = { global = { MULTISITE = "no", SERVER_NAME = "", USE_WHITELIST = "yes", WHITELIST_IP = "9.9.9.9" } }
            assert(utils.is_ip_whitelisted("9.9.9.9", "") == true, "an enabled global list must still whitelist")
            print("ok")
            """)
        assert out.strip() == "ok"
